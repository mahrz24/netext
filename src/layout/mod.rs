pub mod sugiyama;
pub mod static_;
pub mod force_directed;
use pyo3::prelude::*;

use crate::{geometry::Point, graph::CoreGraph};

#[pyclass]
#[derive(Clone, Copy, Eq, PartialEq, Hash, Debug)]
pub enum LayoutDirection {
    #[pyo3(name = "TOP_DOWN")]
    TopDown = 0,
    #[pyo3(name = "LEFT_RIGHT")]
    LeftRight = 1,
}


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

    #[getter]
    fn get_layout_direction(&self) -> Option<LayoutDirection> {
        None
    }
}
