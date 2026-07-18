use serde::{Deserialize, Serialize};

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Serialize, Deserialize)]
pub struct BaseGoal {
    pub x: f32,
    pub y: f32,
}

impl BaseGoal {
    pub fn new(x: f32, y: f32) -> Self {
        BaseGoal { x, y }
    }
}

#[cfg(feature = "python")]
#[pyo3::pymethods]
impl BaseGoal {
    #[new]
    fn py_new(x: f32, y: f32) -> Self {
        Self::new(x, y)
    }

    #[getter]
    fn x(&self) -> f32 {
        self.x
    }

    #[setter]
    fn set_x(&mut self, value: f32) {
        self.x = value;
    }

    #[getter]
    fn y(&self) -> f32 {
        self.y
    }

    #[setter]
    fn set_y(&mut self, value: f32) {
        self.y = value;
    }
}
