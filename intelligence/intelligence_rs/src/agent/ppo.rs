use super::model::ActorCritic;
use crate::config::Config;
use tch::{
    nn::{self, OptimizerConfig},
    Device, Kind, Tensor,
};

pub struct Rollout {
    pub local: Tensor,
    pub global: Tensor,
    pub episode_starts: Tensor,
    pub runs: Tensor,
    pub jumps: Tensor,
    pub old_log_probs: Tensor,
    pub old_values: Tensor,
    pub rewards: Tensor,
    pub dones: Tensor,
    pub bootstrap_values: Tensor,
}

#[derive(Default)]
pub struct UpdateMetrics {
    pub loss: f64,
    pub policy_loss: f64,
    pub value_loss: f64,
    pub entropy: f64,
    pub updates: usize,
}

pub struct Ppo {
    pub vs: nn::VarStore,
    pub model: ActorCritic,
    optimizer: nn::Optimizer,
    config: Config,
    device: Device,
}

impl Ppo {
    pub fn new(config: Config, device: Device) -> tch::Result<Self> {
        let vs = nn::VarStore::new(device);
        let model = ActorCritic::new(&vs.root(), device);
        let optimizer = nn::Adam::default().build(&vs, config.learning_rate)?;
        Ok(Self {
            vs,
            model,
            optimizer,
            config,
            device,
        })
    }

    pub fn update(&mut self, rollout: Rollout) -> UpdateMetrics {
        let rewards = tensor_to_vec(&rollout.rewards);
        let dones = tensor_to_vec(&rollout.dones);
        let values = tensor_to_vec(&rollout.old_values);
        let bootstrap = tensor_to_vec(&rollout.bootstrap_values);
        let sizes = rollout.rewards.size();
        let (steps, envs) = (sizes[0] as usize, sizes[1] as usize);
        let (advantages, returns) = compute_gae(
            &rewards,
            &dones,
            &values,
            &bootstrap,
            steps,
            envs,
            self.config.gamma,
            self.config.gae_lambda,
        );
        let advantages = Tensor::from_slice(&advantages)
            .view([steps as i64, envs as i64])
            .transpose(0, 1)
            .to_device(self.device);
        let advantages =
            (&advantages - advantages.mean(Kind::Float)) / (advantages.std(true) + 1e-8);
        let returns = Tensor::from_slice(&returns)
            .view([steps as i64, envs as i64])
            .transpose(0, 1)
            .to_device(self.device);

        let local = rollout.local.transpose(0, 1);
        let global = rollout.global.transpose(0, 1);
        let starts = rollout.episode_starts.transpose(0, 1);
        let runs = rollout.runs.transpose(0, 1);
        let jumps = rollout.jumps.transpose(0, 1);
        let old_log_probs = rollout.old_log_probs.transpose(0, 1);
        let envs_per_batch = (self.config.minibatch_size / steps).max(1);
        let mut metrics = UpdateMetrics::default();

        for _ in 0..self.config.ppo_num_epochs {
            let permutation = Tensor::randperm(envs as i64, (Kind::Int64, self.device));
            for start in (0..envs).step_by(envs_per_batch) {
                let count = envs_per_batch.min(envs - start) as i64;
                let indices = permutation.narrow(0, start as i64, count);
                let output = self.model.forward_sequence(
                    &local.index_select(0, &indices),
                    &global.index_select(0, &indices),
                    &starts.index_select(0, &indices),
                );
                let run_logits = output.run_logits;
                let jump_logits = output.jump_logits;
                let new_log_probs = run_logits
                    .log_softmax(-1, Kind::Float)
                    .gather(-1, &runs.index_select(0, &indices).unsqueeze(-1), false)
                    .squeeze_dim(-1)
                    + jump_logits
                        .log_softmax(-1, Kind::Float)
                        .gather(-1, &jumps.index_select(0, &indices).unsqueeze(-1), false)
                        .squeeze_dim(-1);
                let selected_old = old_log_probs.index_select(0, &indices);
                let selected_advantages = advantages.index_select(0, &indices);
                let ratio = (new_log_probs - selected_old).exp();
                let clipped = ratio.clamp(
                    1.0 - self.config.clip_epsilon,
                    1.0 + self.config.clip_epsilon,
                );
                let policy_loss = -Tensor::minimum(
                    &(&ratio * &selected_advantages),
                    &(&clipped * &selected_advantages),
                )
                .mean(Kind::Float);
                let value_loss = (output.values - returns.index_select(0, &indices))
                    .pow_tensor_scalar(2)
                    .mean(Kind::Float);
                let entropy = categorical_entropy(&run_logits).mean(Kind::Float)
                    + categorical_entropy(&jump_logits).mean(Kind::Float);
                let loss = &policy_loss + self.config.value_coefficient * &value_loss
                    - self.config.entropy_regularization * &entropy;
                self.optimizer
                    .backward_step_clip(&loss, self.config.max_grad_norm);
                metrics.loss += loss.double_value(&[]);
                metrics.policy_loss += policy_loss.double_value(&[]);
                metrics.value_loss += value_loss.double_value(&[]);
                metrics.entropy += entropy.double_value(&[]);
                metrics.updates += 1;
            }
        }
        if metrics.updates > 0 {
            let count = metrics.updates as f64;
            metrics.loss /= count;
            metrics.policy_loss /= count;
            metrics.value_loss /= count;
            metrics.entropy /= count;
        }
        metrics
    }
}

fn categorical_entropy(logits: &Tensor) -> Tensor {
    let log_probs = logits.log_softmax(-1, Kind::Float);
    -(log_probs.exp() * log_probs).sum_dim_intlist([-1].as_slice(), false, Kind::Float)
}

fn tensor_to_vec(tensor: &Tensor) -> Vec<f32> {
    Vec::<f32>::try_from(&tensor.to_device(Device::Cpu).view([-1])).expect("float tensor")
}

pub fn compute_gae(
    rewards: &[f32],
    dones: &[f32],
    values: &[f32],
    bootstrap: &[f32],
    steps: usize,
    envs: usize,
    gamma: f32,
    lambda: f32,
) -> (Vec<f32>, Vec<f32>) {
    let mut advantages = vec![0.0; steps * envs];
    for env in 0..envs {
        let mut gae = 0.0;
        for step in (0..steps).rev() {
            let index = step * envs + env;
            let next_value = if step + 1 == steps {
                bootstrap[env]
            } else {
                values[(step + 1) * envs + env]
            };
            let continuing = 1.0 - dones[index];
            let delta = rewards[index] + gamma * next_value * continuing - values[index];
            gae = delta + gamma * lambda * continuing * gae;
            advantages[index] = gae;
        }
    }
    let returns = advantages
        .iter()
        .zip(values)
        .map(|(advantage, value)| advantage + value)
        .collect();
    (advantages, returns)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gae_stops_at_terminal() {
        let (advantages, _) = compute_gae(
            &[1.0, 10.0],
            &[1.0, 0.0],
            &[0.0, 0.0],
            &[0.0],
            2,
            1,
            1.0,
            1.0,
        );
        assert_eq!(advantages, vec![1.0, 10.0]);
    }
}
