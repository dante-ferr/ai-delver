use tch::{
    nn::{self, RNN},
    Device, Kind, Tensor,
};

pub struct NetworkOutput {
    pub run_logits: Tensor,
    pub jump_logits: Tensor,
    pub values: Tensor,
}

pub struct ActorCritic {
    local: nn::Linear,
    global_norm: nn::LayerNorm,
    global: nn::Linear,
    input: nn::Sequential,
    lstm: nn::LSTM,
    output: nn::Linear,
    run_head: nn::Linear,
    jump_head: nn::Linear,
    value_head: nn::Linear,
    device: Device,
}

impl ActorCritic {
    pub fn new(vs: &nn::Path, device: Device) -> Self {
        let local = nn::linear(vs / "local", 225, 128, Default::default());
        let global_norm = nn::layer_norm(vs / "global_norm", vec![7], Default::default());
        let global = nn::linear(vs / "global", 7, 64, Default::default());
        let input = nn::seq()
            .add(nn::linear(vs / "input_1", 192, 256, Default::default()))
            .add_fn(Tensor::relu)
            .add(nn::linear(vs / "input_2", 256, 128, Default::default()))
            .add_fn(Tensor::relu);
        let lstm = nn::lstm(vs / "lstm", 128, 128, Default::default());
        let output = nn::linear(vs / "output", 128, 64, Default::default());
        let run_head = nn::linear(vs / "run", 64, 3, Default::default());
        let jump_head = nn::linear(vs / "jump", 64, 2, Default::default());
        let value_head = nn::linear(vs / "value", 64, 1, Default::default());
        Self {
            local,
            global_norm,
            global,
            input,
            lstm,
            output,
            run_head,
            jump_head,
            value_head,
            device,
        }
    }

    pub fn forward_sequence(
        &self,
        local: &Tensor,
        global: &Tensor,
        episode_starts: &Tensor,
    ) -> NetworkOutput {
        let sizes = local.size();
        let (batch, steps) = (sizes[0], sizes[1]);
        let local_features = local
            .view([-1, 225])
            .apply(&self.local)
            .relu()
            .view([batch, steps, 128]);
        let global_features = global
            .view([-1, 7])
            .apply(&self.global_norm)
            .apply(&self.global)
            .relu()
            .view([batch, steps, 64]);
        let features = Tensor::cat(&[local_features, global_features], -1).apply(&self.input);
        let mut state = self.lstm.zero_state(batch);
        let mut outputs = Vec::with_capacity(steps as usize);
        for step in 0..steps {
            let keep = (Tensor::ones([batch], (Kind::Float, self.device))
                - episode_starts.select(1, step))
            .view([1, batch, 1]);
            state = nn::LSTMState((state.h() * &keep, state.c() * keep));
            let (output, next_state) = self
                .lstm
                .seq_init(&features.select(1, step).unsqueeze(1), &state);
            state = next_state;
            outputs.push(output.squeeze_dim(1));
        }
        let hidden = Tensor::stack(&outputs, 1)
            .view([-1, 128])
            .apply(&self.output)
            .relu();
        NetworkOutput {
            run_logits: hidden.apply(&self.run_head).view([batch, steps, 3]),
            jump_logits: hidden.apply(&self.jump_head).view([batch, steps, 2]),
            values: hidden.apply(&self.value_head).view([batch, steps]),
        }
    }

    pub fn initial_state(&self, batch: i64) -> nn::LSTMState {
        self.lstm.zero_state(batch)
    }

    pub fn action_and_value(
        &self,
        local: &Tensor,
        global: &Tensor,
        episode_starts: &Tensor,
        state: &mut nn::LSTMState,
    ) -> (Tensor, Tensor, Tensor, Tensor) {
        let batch = local.size()[0];
        let local_features = local.apply(&self.local).relu();
        let global_features = global.apply(&self.global_norm).apply(&self.global).relu();
        let features = Tensor::cat(&[local_features, global_features], -1).apply(&self.input);
        let keep = (Tensor::ones([batch], (Kind::Float, self.device)) - episode_starts)
            .view([1, batch, 1]);
        *state = nn::LSTMState((state.h() * &keep, state.c() * keep));
        let (hidden, next_state) = self.lstm.seq_init(&features.unsqueeze(1), state);
        *state = nn::LSTMState((next_state.h().detach(), next_state.c().detach()));
        let hidden = hidden.squeeze_dim(1).apply(&self.output).relu();
        let run_logits = hidden.apply(&self.run_head);
        let jump_logits = hidden.apply(&self.jump_head);
        let value = hidden.apply(&self.value_head).squeeze_dim(1);
        let run = run_logits.softmax(-1, Kind::Float).multinomial(1, true);
        let jump = jump_logits.softmax(-1, Kind::Float).multinomial(1, true);
        let log_prob = run_logits
            .log_softmax(-1, Kind::Float)
            .gather(1, &run, false)
            + jump_logits
                .log_softmax(-1, Kind::Float)
                .gather(1, &jump, false);
        (
            run.squeeze_dim(1),
            jump.squeeze_dim(1),
            log_prob.squeeze_dim(1),
            value,
        )
    }
}
