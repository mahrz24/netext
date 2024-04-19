use petgraph::graphmap::UnGraphMap;
use pyo3::prelude::*;
use pyo3::types::PyAny;
use std::collections::HashMap;

#[pyclass]
pub struct CoreGraph {
    graph: UnGraphMap<usize, ()>,
    object_map: HashMap<usize, PyObject>,
    data_map: HashMap<usize, PyObject>,
    edge_data_map: HashMap<(usize, usize), PyObject>,
}

#[pymethods]
impl CoreGraph {
    #[new]
    fn new() -> Self {
        CoreGraph {
            graph: UnGraphMap::new(),
            object_map: HashMap::new(),
            data_map: HashMap::new(),
            edge_data_map: HashMap::new(),
        }
    }

    #[staticmethod]
    fn from_edges(py: Python<'_>, edges: Vec<(&PyAny, &PyAny)>) -> PyResult<Self> {
        let mut graph = CoreGraph::new();
        for (a, b) in edges {
            graph.add_node(py, &a, None)?;
            graph.add_node(py, &b, None)?;
            graph.add_edge(py, &a, &b, None)?;
        }
        Ok(graph)
    }

    // Str representation of the graph
    fn __str__(&self) -> String {
        format!("{:?}", self.graph)
    }

    fn add_node(&mut self, py: Python<'_>, obj: &PyAny, data: Option<&PyAny>) -> PyResult<()> {
        let hash = obj.hash()? as usize;
        if !self.graph.contains_node(hash) {
            self.graph.add_node(hash);
            self.object_map.insert(hash, obj.into_py(py));
            if let Some(data) = data {
                self.data_map.insert(hash, data.into_py(py));
            }
        }
        Ok(())
    }

    fn add_edge(
        &mut self,
        _py: Python<'_>,
        obj_a: &PyAny,
        obj_b: &PyAny,
        data: Option<&PyAny>,
    ) -> PyResult<()> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;

        if self.graph.contains_node(hash_a) && self.graph.contains_node(hash_b) {
            self.graph.add_edge(hash_a, hash_b, ());
            if let Some(data) = data {
                self.edge_data_map.insert((hash_a, hash_b), data.into());
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    fn remove_node(&mut self, obj: &PyAny) -> PyResult<()> {
        let hash = obj.hash()? as usize;
        if self.graph.contains_node(hash) {
            self.graph.remove_node(hash);
            self.object_map.remove(&hash);
            self.data_map.remove(&hash);
            let edges_to_remove: Vec<(usize, usize)> = self
                .edge_data_map
                .keys()
                .filter(|(a, b)| *a == hash || *b == hash)
                .cloned()
                .collect();
            for edge in edges_to_remove {
                self.edge_data_map.remove(&edge);
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Node does not exist.",
            ));
        }
        Ok(())
    }

    fn remove_edge(&mut self, obj_a: &PyAny, obj_b: &PyAny) -> PyResult<()> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        if self.graph.contains_node(hash_a) && self.graph.contains_node(hash_b) {
            if self.graph.contains_edge(hash_a, hash_b) {
                self.graph.remove_edge(hash_a, hash_b);
                self.edge_data_map.remove(&(hash_a, hash_b));
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Edge does not exist.",
                ));
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    fn contains_node(&self, obj: &PyAny) -> PyResult<bool> {
        let hash = obj.hash()? as usize;
        Ok(self.graph.contains_node(hash))
    }

    fn contains_edge(&self, obj_a: &PyAny, obj_b: &PyAny) -> PyResult<bool> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        Ok(self.graph.contains_edge(hash_a, hash_b))
    }

    fn get_node_data(&self, obj: &PyAny) -> PyResult<Option<&PyObject>> {
        let hash = obj.hash()? as usize;
        match self.data_map.get(&hash) {
            Some(data) => Ok(Some(data)),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Node does not exist.",
            )),
        }
    }

    fn get_edge_data(&self, obj_a: &PyAny, obj_b: &PyAny) -> PyResult<Option<&PyObject>> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        match self.edge_data_map.get(&(hash_a, hash_b)) {
            Some(data) => Ok(Some(data)),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Edge does not exist.",
            )),
        }
    }

    fn update_node_data(&mut self, py: Python<'_>, obj: &PyAny, data: &PyAny) -> PyResult<()> {
        let hash = obj.hash()? as usize;
        if self.graph.contains_node(hash) {
            self.data_map.insert(hash, data.into_py(py));
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Node does not exist.",
            ));
        }
        Ok(())
    }

    fn update_edge_data(&mut self, py: Python<'_>, obj_a: &PyAny, obj_b: &PyAny, data: &PyAny) -> PyResult<()> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        if self.graph.contains_node(hash_a) && self.graph.contains_node(hash_b) {
            if self.graph.contains_edge(hash_a, hash_b) {
                self.edge_data_map.insert((hash_a, hash_b), data.into_py(py));
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Edge does not exist.",
                ));
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }
}
