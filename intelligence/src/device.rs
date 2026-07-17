use anyhow::{bail, Context, Result};
use tch::Device;

pub fn resolve_device(value: &str) -> Result<Device> {
    match value.to_ascii_lowercase().as_str() {
        "auto" => {
            let device = Device::cuda_if_available();
            if matches!(device, Device::Cpu) {
                crate::cli::emit(
                    "info",
                    serde_json::json!({"message": "No CUDA device available; falling back to CPU"}),
                );
            }
            Ok(device)
        }
        "cpu" => Ok(Device::Cpu),
        "cuda" => {
            if !tch::Cuda::is_available() {
                bail!("device cuda requested but CUDA is not available in this libtorch build");
            }
            Ok(Device::Cuda(0))
        }
        "mps" => Ok(Device::Mps),
        value if value.starts_with("cuda:") => {
            if !tch::Cuda::is_available() {
                bail!("device {value} requested but CUDA is not available in this libtorch build");
            }
            Ok(Device::Cuda(
                value[5..]
                    .parse()
                    .context("invalid CUDA device index")?,
            ))
        }
        _ => bail!("device must be auto, cpu, cuda, cuda:N, or mps"),
    }
}

pub fn device_label(device: Device) -> String {
    match device {
        Device::Cpu => "cpu".into(),
        Device::Cuda(index) => format!("cuda:{index}"),
        Device::Mps => "mps".into(),
        Device::Vulkan => "vulkan".into(),
    }
}
