use pyo3::prelude::*;

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

#[pymethods]
impl Point {
    #[new]
    pub fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }

    #[getter]
    pub fn x(&self) -> i32 {
        self.x
    }

    #[getter]
    pub fn y(&self) -> i32 {
        self.y
    }
}
