mod engine;
mod world_objects;

pub use engine::physics_engine::{RuntimeError, RuntimeResult, RustPhysicsEngine};
pub use world_objects::base_delver::BaseDelver;
pub use world_objects::base_goal::BaseGoal;

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
