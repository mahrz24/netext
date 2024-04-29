pub mod sugiyama;
pub mod static_;
use pyo3::prelude::*;

use crate::{geometry::Point, graph::CoreGraph};

#[pyclass(subclass)]
pub struct LayoutEngine {
}

#[pymethods]
impl LayoutEngine {
    #[new]
    fn new() -> Self {
        LayoutEngine {}
    }

    fn layout(&self, _graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        Ok(vec![])
    }
}
