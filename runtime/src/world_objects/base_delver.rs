use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[pyclass]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseDelver {
    #[pyo3(get, set)]
    pub x: f32,
    #[pyo3(get, set)]
    pub y: f32,
    #[pyo3(get, set)]
    pub vx: f32,
    #[pyo3(get, set)]
    pub vy: f32,
    #[pyo3(get, set)]
    pub is_on_ground: bool,
    #[pyo3(get, set)]
    pub is_dead: bool,
    #[pyo3(get, set)]
    pub is_victory: bool,
}

#[pymethods]
impl BaseDelver {
    #[new]
    pub fn new(x: f32, y: f32) -> Self {
        BaseDelver {
            x,
            y,
            vx: 0.0,
            vy: 0.0,
            is_on_ground: false,
            is_dead: false,
            is_victory: false,
        }
    }
}
