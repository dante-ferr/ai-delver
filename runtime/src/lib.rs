mod config;
mod engine;
mod world_objects;

pub use engine::physics_engine::{RuntimeError, RuntimeResult, RustPhysicsEngine};
pub use engine::world_config::WorldConfig;
pub use world_objects::delver::{BaseDelver, DelverConfig};
pub use world_objects::goal::BaseGoal;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pymodule]
fn runtime_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BaseDelver>()?;
    m.add_class::<BaseGoal>()?;
    m.add_class::<RustPhysicsEngine>()?;
    Ok(())
}
