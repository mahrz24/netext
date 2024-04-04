use petgraph::algo::dijkstra;
use petgraph::graph::NodeIndex;
use petgraph::visit::EdgeRef;
use petgraph::Graph;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::collections::HashMap;

#[pyclass]
#[derive(Clone)]
struct Point {
    x: i32,
    y: i32,
}

#[pymethods]
impl Point {
    #[new]
    fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }
}

#[pyclass]
#[derive(Clone, Copy, Eq, PartialEq, Hash)]
enum Direction {
    #[pyo3(name = "CENTER")]
    Center = -1,
    #[pyo3(name = "UP")]
    Up = 0,
    #[pyo3(name = "DOWN")]
    Down = 1,
    #[pyo3(name = "LEFT")]
    Left = 2,
    #[pyo3(name = "RIGHT")]
    Right = 3,
    #[pyo3(name = "UP_RIGHT")]
    UpRight = 4,
    #[pyo3(name = "UP_LEFT")]
    UpLeft = 5,
    #[pyo3(name = "DOWN_RIGHT")]
    DownRight = 6,
    #[pyo3(name = "DOWN_LEFT")]
    DownLeft = 7,
}

impl Direction {
    fn all_directions() -> Vec<Direction> {
        vec![
            Direction::Center,
            Direction::Up,
            Direction::Down,
            Direction::Left,
            Direction::Right,
            Direction::UpRight,
            Direction::UpLeft,
            Direction::DownRight,
            Direction::DownLeft,
        ]
    }

    fn other_directions(&self) -> Vec<Direction> {
        Direction::all_directions()
            .iter()
            .filter(|&d| *d != *self)
            .cloned()
            .collect()
    }
}

#[pyclass]
#[derive(Clone)]
struct Shape {
    top_left: Point,
    bottom_right: Point,
}

#[pymethods]
impl Shape {
    #[new]
    fn new(top_left: Point, bottom_right: Point) -> Self {
        Shape {
            top_left,
            bottom_right,
        }
    }
}

#[pyclass]
#[derive(Clone)]
struct DirectedPoint {
    x: i32,
    y: i32,
    direction: Direction,
}

#[pymethods]
impl DirectedPoint {
    #[new]
    fn new(x: i32, y: i32, direction: Direction) -> Self {
        DirectedPoint { x, y, direction }
    }

    #[getter]
    fn get_x(&self) -> PyResult<i32> {
        Ok(self.x)
    }

    #[getter]
    fn get_y(&self) -> PyResult<i32> {
        Ok(self.y)
    }

    #[getter]
    fn get_direction(&self) -> PyResult<Direction> {
        Ok(self.direction.clone())
    }

    fn __len__(&self) -> PyResult<usize> {
        Ok(3) // The number of elements in the class
    }

    fn __getitem__(&self, idx: usize, py: Python<'_>) -> PyResult<PyObject> {
        let direction = match Py::new(py, self.direction) {
            Ok(direction) => direction,
            Err(e) => return Err(e),
        };

        match idx {
            0 => Ok(self.x.to_object(py)),
            1 => Ok(self.y.to_object(py)),
            2 => Ok(direction.to_object(py)),
            _ => Err(PyIndexError::new_err("index out of range")),
        }
    }
}

fn directed_point_to_subdivision(
    directed_point: DirectedPoint,
    min: Point,
    n_subdivisions_x: i32,
    n_subdivisions_y: i32,
) -> (i32, i32) {
    let x = (directed_point.x - min.x) / n_subdivisions_x;
    let y = (directed_point.y - min.y) / n_subdivisions_y;

    (x, y)
}

#[pyfunction]
fn route_edge(
    py: Python,
    start: Point,
    end: Point,
    start_direction: Direction,
    end_direction: Direction,
    nodes: Vec<Shape>,
    routed_edges: Vec<Vec<Point>>,
) -> PyResult<Vec<DirectedPoint>> {
    // Create a graph
    let mut graph = Graph::<(i32, i32, Direction), i32>::new();

    // Create a map to store node indices
    let mut node_indices: HashMap<(i32, i32, Direction), NodeIndex> = HashMap::new();

    // Get the maximum and minimum coordinates
    let mut min_x = start.x.min(end.x);
    let mut min_y = start.y.min(end.y);
    let mut max_x = start.x.max(end.x);
    let mut max_y = start.y.max(end.y);

    // Update the maximum and minimum coordinates based on the nodes
    for node in &nodes {
        min_x = min_x.min(node.top_left.x);
        min_y = min_y.min(node.top_left.y);
        max_x = max_x.max(node.bottom_right.x);
        max_y = max_y.max(node.bottom_right.y);
    }

    // Do a vertical and horizontal subdivision
    // Make sure that each subdivision is at most 15 units wide and high and at least 1 unit wide and high
    let n_subdivisions_x = ((max_x - min_x) / 15).max(1);
    let n_subdivisions_y = ((max_y - min_y) / 15).max(1);

    // Create a subdivision graph connecting neighboring subdivisions
    let mut subdivision_graph = Graph::<(i32, i32), i32>::new();
    let mut subdivision_node_indices: HashMap<(i32, i32), NodeIndex> = HashMap::new();
    for x in 0..n_subdivisions_x {
        for y in 0..n_subdivisions_y {
            let node_index = subdivision_graph.add_node((x, y));
            subdivision_node_indices.insert((x, y), node_index);
        }
    }

    for x in 0..n_subdivisions_x {
        for y in 0..n_subdivisions_y {
            let source_index = *subdivision_node_indices.get(&(x, y)).unwrap();

            let targets = [
                (x + 1, y),
                (x, y + 1),
                (x - 1, y),
                (x, y - 1),
            ];

            for (target_x, target_y) in targets.iter() {
                if *target_x >= 0 && *target_x < n_subdivisions_x && *target_y >= 0 && *target_y < n_subdivisions_y {
                    let target_index = *subdivision_node_indices.get(&(*target_x, *target_y)).unwrap();
                    subdivision_graph.add_edge(source_index, target_index, 1);
                }
            }
        }
    }

    // Find a shortest path from start to end using the subdivision graph
    let (start_subdivision_x, start_subdivision_y) = directed_point_to_subdivision(
        DirectedPoint::new(start.x, start.y, start_direction),
        Point::new(min_x, min_y),
        n_subdivisions_x,
        n_subdivisions_y,
    );
    let (end_subdivision_x, end_subdivision_y) = directed_point_to_subdivision(
        DirectedPoint::new(end.x, end.y, end_direction),
        Point::new(min_x, min_y),
        n_subdivisions_x,
        n_subdivisions_y,
    );
    let start_subdivision_index = *subdivision_node_indices.get(&(start_subdivision_x, start_subdivision_y)).unwrap();
    let end_subdivision_index = *subdivision_node_indices.get(&(end_subdivision_x, end_subdivision_y)).unwrap();

    let subdivision_path_weights = dijkstra(&subdivision_graph, start_subdivision_index, Some(end_subdivision_index), |e| *e.weight());

    let mut subdivision_path = Vec::new();
    let mut current_subdivision_index = end_subdivision_index;

    while current_subdivision_index != start_subdivision_index {
        subdivision_path.push(current_subdivision_index);
        let edge = subdivision_graph.edges_directed(current_subdivision_index, petgraph::Direction::Incoming).min_by_key(|edge| subdivision_path_weights.get(&edge.source()).unwrap()).unwrap();
        current_subdivision_index = edge.source();
    }

    subdivision_path.push(start_subdivision_index);
    subdivision_path.reverse();


    // For each subdivision part of the path, find the shortest path using a graph connecting each node in the subdivision (with some margin to extend outside of the node)
    // Connect the boundaries in this graph to the goal (next subdivision or end)

    // Create nodes for all possible positions and directions
    for x in min_x..=max_x {
        for y in min_y..=max_y {
            for direction in Direction::all_directions() {
                let node_index = graph.add_node((x, y, direction));
                node_indices.insert((x, y, direction), node_index);
            }
        }
    }

    // Add edges
    for x in min_x..=max_x {
        for y in min_y..=max_y {
            for direction in Direction::all_directions() {
                let source_index = match node_indices.get(&(x, y, direction)) {
                    Some(index) => *index,
                    None => continue,
                };

                let other_directions = direction.other_directions();

                let self_targets = other_directions
                    .iter()
                    .map(|&d| DirectedPoint::new(x, y, d));

                // Add edges from down to up, right to left, etc.
                let targets = match direction {
                    Direction::Up => {
                        self_targets.chain([DirectedPoint::new(x, y - 1, Direction::Down)])
                    }
                    Direction::Down => {
                        self_targets.chain([DirectedPoint::new(x, y + 1, Direction::Up)])
                    }
                    Direction::Left => {
                        self_targets.chain([DirectedPoint::new(x - 1, y, Direction::Right)])
                    }
                    Direction::Right => {
                        self_targets.chain([DirectedPoint::new(x + 1, y, Direction::Left)])
                    }
                    Direction::UpRight => {
                        self_targets.chain([DirectedPoint::new(x + 1, y - 1, Direction::DownLeft)])
                    }
                    Direction::UpLeft => {
                        self_targets.chain([DirectedPoint::new(x - 1, y - 1, Direction::DownRight)])
                    }
                    Direction::DownRight => {
                        self_targets.chain([DirectedPoint::new(x + 1, y + 1, Direction::UpLeft)])
                    }
                    Direction::DownLeft => {
                        self_targets.chain([DirectedPoint::new(x - 1, y + 1, Direction::UpRight)])
                    }
                    Direction::Center => {
                        self_targets.chain([DirectedPoint::new(x - 1, y + 1, Direction::UpRight)])
                    }
                };

                for target in targets {
                    let target_index =
                        match node_indices.get(&(target.x, target.y, target.direction)) {
                            Some(index) => *index,
                            None => continue,
                        };

                    if source_index != target_index {
                        graph.add_edge(source_index, target_index, 1);
                    }
                }
            }
        }
    }

    // Use Dijkstra's algorithm to find the shortest path

    let start_index = *node_indices
        .get(&(start.x, start.y, start_direction))
        .unwrap();
    let end_index = *node_indices.get(&(end.x, end.y, end_direction)).unwrap();

    let path_weights = dijkstra(&graph, start_index, Some(end_index), |e| *e.weight());

    let mut path = Vec::new();
    let mut current_index = end_index;

    while current_index != start_index {
        path.push(current_index);
        let edge = graph
            .edges_directed(current_index, petgraph::Direction::Incoming)
            .min_by_key(|edge| path_weights.get(&edge.source()).unwrap())
            .unwrap();
        current_index = edge.source();
    }

    path.push(start_index);
    path.reverse();

    // Convert NodeIndex to DirectedPoint
    let directed_path: Vec<DirectedPoint> = path
        .iter()
        .map(|&node_index| {
            let (x, y, direction) = graph[node_index];
            DirectedPoint::new(x, y, direction)
        })
        .collect();

    Ok(directed_path)
}

// A module to wrap the Python functions and structs
#[pymodule]
fn _core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Point>()?;
    m.add_class::<Shape>()?;
    m.add_class::<Direction>()?;
    m.add_class::<DirectedPoint>()?;
    m.add_function(wrap_pyfunction!(route_edge, m)?)?;
    Ok(())
}
