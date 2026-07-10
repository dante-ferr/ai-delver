mod engine;
mod world_objects;

use pyo3::prelude::*;

#[pymodule]
fn runtime_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<world_objects::base_delver::BaseDelver>()?;
    m.add_class::<world_objects::base_goal::BaseGoal>()?;
    m.add_class::<engine::physics_engine::RustPhysicsEngine>()?;
    Ok(())
}
