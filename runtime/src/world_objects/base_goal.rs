use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[pyclass]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseGoal {
    #[pyo3(get, set)]
    pub x: f32,
    #[pyo3(get, set)]
    pub y: f32,
}

#[pymethods]
impl BaseGoal {
    #[new]
    pub fn new(x: f32, y: f32) -> Self {
        BaseGoal { x, y }
    }
}
