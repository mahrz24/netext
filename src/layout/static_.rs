use pyo3::{exceptions, prelude::*, types::PyDict};

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

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        let mut node_positions = Vec::new();
        for node in graph.all_nodes() {
            let bound_node = node.clone_ref(py).into_bound(py);
            let node_data_result = graph.node_data(&bound_node);
            match node_data_result {
                Err(_) => continue,
                Ok(None) => continue,
                Ok(Some(node_data)) => {
                    let bound_data = node_data.bind(py);
                    if bound_data.is_instance_of::<PyDict>() {
                        let dict_result = bound_data.downcast::<PyDict>();
                        let dict = match dict_result {
                            Ok(value) => value,
                            Err(_) => return Err(PyErr::new::<exceptions::PyTypeError, _>("Data must be a dictionary"))
                        };
                        let x = dict.get_item("$x");
                        let y = dict.get_item("$y");

                        let x_val = match x {
                            Ok(Some(value)) => match value.extract::<i32>() {
                                Ok(value) => value,
                                Err(_) => 0,
                            }
                            _ => 0,
                        };

                        let y_val = match y {
                            Ok(Some(value)) => match value.extract::<i32>() {
                                Ok(value) => value,
                                Err(_) => 0,
                            }
                            _ => 0,
                        };

                        let point = Point::new(x_val, y_val);
                        node_positions.push((node.clone_ref(py), point));
                    }
                }
            }
        }
        Ok(node_positions)
    }
}
