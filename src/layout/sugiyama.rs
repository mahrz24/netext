use pyo3::prelude::*;

use crate::{geometry::Point, graph::CoreGraph};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct SugiyamaLayout {
}

#[pymethods]
impl SugiyamaLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (SugiyamaLayout {}, LayoutEngine {})
    }

    fn layout(&self, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        Ok(vec![])
    }
}
