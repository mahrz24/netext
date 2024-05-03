use pyo3::{prelude::*, types::PyDict};

use crate::{geometry::Point, graph::CoreGraph};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct StaticLayout {}

#[pymethods]
impl StaticLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (StaticLayout {}, LayoutEngine {})
    }

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(&PyObject, Point)>> {
        let mut node_positions = Vec::new();
        for node in graph.all_nodes() {
            let node_ref = node.clone();
            let node_data = graph
                .node_data(&node_ref.into_bound(py))?
                .unwrap()
                .into_bound(py);
            if node_data.is_instance_of::<PyDict>() {
                let dict = node_data.downcast::<PyDict>()?;
                let x = dict.get_item("$x")?.unwrap();
                let y = dict.get_item("$y")?.unwrap();

                let x_val = match x.extract::<i32>() {
                    Ok(value) => value,
                    Err(_) => 0,
                };

                let y_val = match y.extract::<i32>() {
                    Ok(value) => value,
                    Err(_) => 0,
                };

                let point = Point::new(x_val, y_val);
                node_positions.push((node, point));
            }
        }
        Ok(node_positions)
    }
}
