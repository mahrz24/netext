use petgraph::graphmap::DiGraphMap;
use pyo3::prelude::*;
use pyo3::types::PyAny;
use std::collections::HashMap;

#[pyclass]
pub struct CoreGraph {
    pub graph: DiGraphMap<usize, ()>,
    pub object_map: HashMap<usize, PyObject>,
    data_map: HashMap<usize, PyObject>,
    edge_data_map: HashMap<(usize, usize), PyObject>,
}

#[pymethods]
impl CoreGraph {
    #[new]
    fn new() -> Self {
        CoreGraph {
            graph: DiGraphMap::new(),
            object_map: HashMap::new(),
            data_map: HashMap::new(),
            edge_data_map: HashMap::new(),
        }
    }

    #[staticmethod]
    fn from_edges(py: Python<'_>, edges: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>) -> PyResult<Self> {
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

    fn add_node(&mut self, py: Python<'_>, obj: &Bound<'_, PyAny>, data: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
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
        obj_a: &Bound<'_, PyAny>,
        obj_b: &Bound<'_, PyAny>,
        data: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;

        if self.graph.contains_node(hash_a) && self.graph.contains_node(hash_b) {
            self.graph.add_edge(hash_a, hash_b, ());
            if let Some(data) = data {
                self.edge_data_map.insert((hash_a, hash_b), data.as_unbound().clone());
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    fn remove_node(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
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

    fn remove_edge(&mut self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<()> {
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

    fn contains_node(&self, obj: &Bound<'_, PyAny>) -> PyResult<bool> {
        let hash = obj.hash()? as usize;
        Ok(self.graph.contains_node(hash))
    }

    fn contains_edge(&self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<bool> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        Ok(self.graph.contains_edge(hash_a, hash_b))
    }

    fn node_data_or_default(&self, obj: &Bound<'_, PyAny>, default: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let hash = obj.hash().unwrap() as usize;
        match self.data_map.get(&hash) {
            Some(data) => Ok(data.clone()),
            None => Ok(default.clone().unbind())
        }
    }

    pub fn node_data(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<&PyObject>> {
        let hash = obj.hash()? as usize;
        match self.data_map.get(&hash) {
            Some(data) => Ok(Some(data)),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                format!("Node does {:?} not exist.", obj),
            )),
        }
    }

    fn edge_data(&self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<Option<&PyObject>> {
        let hash_a = obj_a.hash()? as usize;
        let hash_b = obj_b.hash()? as usize;
        match self.edge_data_map.get(&(hash_a, hash_b)) {
            Some(data) => Ok(Some(data)),
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Edge does not exist.",
            )),
        }
    }

    fn edge_data_or_default(&self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>, default: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let hash_a = obj_a.hash().unwrap() as usize;
        let hash_b = obj_b.hash().unwrap() as usize;
        match self.edge_data_map.get(&(hash_a, hash_b)) {
            Some(data) => Ok(data.clone()),
            None => Ok(default.clone().unbind())
        }
    }

    fn update_node_data(&mut self, py: Python<'_>, obj: &Bound<'_, PyAny>, data: &Bound<'_, PyAny>) -> PyResult<()> {
        let hash = obj.hash()? as usize;
        if self.graph.contains_node(hash) {
            self.data_map.insert(hash, data.into_py(py));
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Node does {:?} not exist.", obj),
            ));
        }
        Ok(())
    }

    fn update_edge_data(&mut self, py: Python<'_>, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>, data: &Bound<'_, PyAny>) -> PyResult<()> {
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

    pub fn all_nodes(&self) -> Vec<&PyObject> {
        self.object_map.values().collect()
    }

    fn all_edges(&self) -> Vec<(&PyObject, &PyObject)> {
        let edges: Vec<(&PyObject, &PyObject)> = self
            .graph
            .all_edges()
            .map(|(a, b, _)| {
                let obj_a = self.object_map.get(&a).unwrap();
                let obj_b = self.object_map.get(&b).unwrap();
                (obj_a, obj_b)
            })
            .collect();
        edges
    }

    fn neighbors(&self, obj: &Bound<'_, PyAny>) -> PyResult<Vec<&PyObject>> {
        let hash = obj.hash()? as usize;
        if self.graph.contains_node(hash) {
            let neighbours: Vec<&PyObject> = self
                .graph
                .neighbors(hash)
                .filter_map(|neighbour| self.object_map.get(&neighbour))
                .collect();
            Ok(neighbours)
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Node does {:?} not exist.", obj),
            ))
        }
    }
}
