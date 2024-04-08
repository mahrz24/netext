use petgraph::algo::dijkstra;
use petgraph::graph::NodeIndex;
use petgraph::visit::EdgeRef;
use petgraph::Graph;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::collections::HashMap;
use std::i32::MAX;

const SUBDIVISION_SIZE: i32 = 10;

#[pyclass]
#[derive(Clone, Debug)]
struct Point {
    x: i32,
    y: i32,
}

struct Rectangle {
    top_left: Point,
    bottom_right: Point,
}

struct Size {
    width: i32,
    height: i32,
}

#[pymethods]
impl Point {
    #[new]
    fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }
}

#[pyclass]
#[derive(Clone, Copy, Eq, PartialEq, Hash, Debug)]
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

#[derive(Clone, Eq, PartialEq, Hash, Debug)]
enum TargetLocation {
    Concrete(DirectedPoint),
    OtherSubdivision(Direction),
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
#[derive(Clone, Eq, PartialEq, Hash, Copy, Debug)]
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

fn directed_point_to_subdivision(directed_point: DirectedPoint, min: Point) -> (i32, i32) {
    let x = (directed_point.x - min.x) / SUBDIVISION_SIZE;
    let y = (directed_point.y - min.y) / SUBDIVISION_SIZE;

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

    println!("Minimum coordinates: ({}, {})", min_x, min_y);
    println!("Maximum coordinates: ({}, {})", max_x, max_y);

    // Do a vertical and horizontal subdivision
    // Make sure that each subdivision is at most SUBDIVISION_SIZE units wide and high and at least 1 unit wide and high
    let n_subdivisions_x = ((max_x as f64 - min_x as f64) / SUBDIVISION_SIZE as f64).ceil() as i32;
    let n_subdivisions_y = ((max_y as f64 - min_y as f64) / SUBDIVISION_SIZE as f64).ceil() as i32;

    println!(
        "Number of subdivisions: ({}, {})",
        n_subdivisions_x, n_subdivisions_y
    );

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

            let targets = [(x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)];

            for (target_x, target_y) in targets.iter() {
                if *target_x >= 0
                    && *target_x < n_subdivisions_x
                    && *target_y >= 0
                    && *target_y < n_subdivisions_y
                {
                    let target_index = *subdivision_node_indices
                        .get(&(*target_x, *target_y))
                        .unwrap();
                    subdivision_graph.add_edge(source_index, target_index, 1);
                }
            }
        }
    }

    // Find a shortest path from start to end using the subdivision graph
    let (start_subdivision_x, start_subdivision_y) = directed_point_to_subdivision(
        DirectedPoint::new(start.x, start.y, start_direction),
        Point::new(min_x, min_y),
    );
    let (end_subdivision_x, end_subdivision_y) = directed_point_to_subdivision(
        DirectedPoint::new(end.x, end.y, end_direction),
        Point::new(min_x, min_y),
    );

    println!(
        "Finding path from ({}, {}) to ({}, {})",
        start.x, start.y, end.x, end.y
    );
    println!(
        "Finding path from subdivision ({}, {}) to ({}, {})",
        start_subdivision_x, start_subdivision_y, end_subdivision_x, end_subdivision_y
    );
    println!("Subdivision graph: {:?}", subdivision_graph);

    let start_subdivision_index = *subdivision_node_indices
        .get(&(start_subdivision_x, start_subdivision_y))
        .unwrap();

    let end_subdivision_index = *subdivision_node_indices
        .get(&(end_subdivision_x, end_subdivision_y))
        .unwrap();

    let subdivision_path_weights = dijkstra(
        &subdivision_graph,
        start_subdivision_index,
        Some(end_subdivision_index),
        |e| *e.weight(),
    );

    let mut subdivision_path = Vec::new();
    let mut current_subdivision_index = end_subdivision_index;

    while current_subdivision_index != start_subdivision_index {
        subdivision_path.push(current_subdivision_index);
        let edge = subdivision_graph
            .edges_directed(current_subdivision_index, petgraph::Direction::Incoming)
            .min_by_key(|edge| subdivision_path_weights.get(&edge.source()).unwrap_or(&MAX))
            .unwrap();
        current_subdivision_index = edge.source();
    }

    subdivision_path.push(start_subdivision_index);
    subdivision_path.reverse();

    // Add the last subdivision twice, as we need to route the endpoint within in the same subdivision
    subdivision_path.push(end_subdivision_index);

    println!("Subdivision path: {:?}", subdivision_path);

    // For each subdivision part of the path, find the shortest path using a graph connecting each node in the subdivision (with some margin to extend outside of the node)
    // Connect the boundaries in this graph to the goal (next subdivision or end)

    let mut directed_path = Vec::new();
    let start_point = DirectedPoint::new(start.x, start.y, start_direction);
    let mut current_start_point = &start_point;

    for i in 0..subdivision_path.len() - 1 {
        let start_subdivision_index = subdivision_path[i];

        let (start_subdivision_x, start_subdivision_y) = subdivision_graph[start_subdivision_index];

        let start_subdivision_min_x = min_x + start_subdivision_x * SUBDIVISION_SIZE;
        let start_subdivision_min_y = min_y + start_subdivision_y * SUBDIVISION_SIZE;
        let start_subdivision_max_x = min_x + (start_subdivision_x + 1) * SUBDIVISION_SIZE;
        let start_subdivision_max_y = min_y + (start_subdivision_y + 1) * SUBDIVISION_SIZE;

        let range = Rectangle {
            top_left: Point::new(start_subdivision_min_x, start_subdivision_min_y),
            bottom_right: Point::new(start_subdivision_max_x, start_subdivision_max_y),
        };

        let end_subdivision_index = subdivision_path[i + 1];
        let target_location = if end_subdivision_index == start_subdivision_index
            || i == subdivision_path.len() - 2
        {
            TargetLocation::Concrete(DirectedPoint::new(end.x, end.y, end_direction))
        } else {
            let (end_subdivision_x, end_subdivision_y) = subdivision_graph[end_subdivision_index];

            let subdivision_direction = if end_subdivision_x > start_subdivision_x {
                Direction::Right
            } else if end_subdivision_x < start_subdivision_x {
                Direction::Left
            } else if end_subdivision_y > start_subdivision_y {
                Direction::Down
            } else {
                Direction::Up
            };

            TargetLocation::OtherSubdivision(subdivision_direction)
        };

        println!("Routing from subdivision {:?} to subdivision {:?}", start_subdivision_index, end_subdivision_index);
        println!("From {:?} to {:?}", current_start_point, target_location);

        let subdivision_path =
            route_edge_in_subdivision(range, *current_start_point, target_location);

        println!("New start point: {:?}", current_start_point);
        println!("Directed path: {:?}", subdivision_path.clone());

        for point in subdivision_path {
            directed_path.push(point);
        }
        current_start_point = &directed_path.last().unwrap();
    }
    // Create nodes for all possible positions and directions

    Ok(directed_path)
}

#[derive(Clone, Eq, PartialEq, Hash, Copy, Debug)]
enum PointOrPlaceholder {
    Point(DirectedPoint),
    SubdivisionPlaceholder,
}

fn route_edge_in_subdivision(
    range: Rectangle,
    start: DirectedPoint,
    end: TargetLocation,
) -> Vec<DirectedPoint> {
    let mut min_x = range.top_left.x;
    let mut min_y = range.top_left.y;
    let mut max_x = range.bottom_right.x;
    let mut max_y = range.bottom_right.y;

    min_x -= 2;
    min_y -= 2;
    max_x += 2;
    max_y += 2;

    println!("Subdivision range: ({}, {}) to ({}, {})", min_x, min_y, max_x, max_y);

    // Create a graph
    let mut graph = Graph::<PointOrPlaceholder, i32>::new();

    // Create a map to store node indices
    let mut node_indices: HashMap<PointOrPlaceholder, NodeIndex> = HashMap::new();

    for x in min_x..=max_x {
        for y in min_y..=max_y {
            for direction in Direction::all_directions() {
                let node_weight = PointOrPlaceholder::Point(DirectedPoint::new(x, y, direction));
                let node_index = graph.add_node(node_weight);
                node_indices.insert(node_weight, node_index);
            }
        }
    }

    if let TargetLocation::OtherSubdivision(_) = end {
        let node_weight = PointOrPlaceholder::SubdivisionPlaceholder;
        let node_index = graph.add_node(node_weight);
        node_indices.insert(node_weight, node_index);
    }

    // Add edges
    for x in min_x..=max_x {
        for y in min_y..=max_y {
            for direction in Direction::all_directions() {
                let node_weight = PointOrPlaceholder::Point(DirectedPoint::new(x, y, direction));
                let source_index = match node_indices.get(&node_weight) {
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
                    let target_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                        target.x,
                        target.y,
                        target.direction,
                    ));
                    let target_index = match node_indices.get(&target_weight) {
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

    if let TargetLocation::OtherSubdivision(direction) = end {
        match direction {
            Direction::Center => panic!("Cannot route another subdivision in the direction center"),
            Direction::Up => {
                for x in min_x..=max_x {
                    let source_weight =
                        PointOrPlaceholder::Point(DirectedPoint::new(x, min_y, Direction::Up));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1);
                }
            }
            Direction::Down => {
                for x in min_x..=max_x {
                    let source_weight =
                        PointOrPlaceholder::Point(DirectedPoint::new(x, max_y, Direction::Down));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1);
                }
            }
            Direction::Left => {
                for y in min_y..=max_y {
                    let source_weight =
                        PointOrPlaceholder::Point(DirectedPoint::new(min_x, y, Direction::Left));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1);
                }
            }
            Direction::Right => {
                for y in min_y..=max_y {
                    let source_weight =
                        PointOrPlaceholder::Point(DirectedPoint::new(max_x, y, Direction::Right));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1);
                }
            }
            Direction::UpRight => {
                let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                    max_x,
                    min_y,
                    Direction::DownLeft,
                ));
                let source_index = *node_indices.get(&source_weight).unwrap();
                let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                let target_index = *node_indices.get(&target_weight).unwrap();
                graph.add_edge(source_index, target_index, 1);
            }
            Direction::UpLeft => {
                let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                    min_x,
                    min_y,
                    Direction::DownRight,
                ));
                let source_index = *node_indices.get(&source_weight).unwrap();
                let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                let target_index = *node_indices.get(&target_weight).unwrap();
                graph.add_edge(source_index, target_index, 1);
            }
            Direction::DownRight => {
                let source_weight =
                    PointOrPlaceholder::Point(DirectedPoint::new(max_x, max_y, Direction::UpLeft));
                let source_index = *node_indices.get(&source_weight).unwrap();
                let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                let target_index = *node_indices.get(&target_weight).unwrap();
                graph.add_edge(source_index, target_index, 1);
            }
            Direction::DownLeft => {
                let source_weight =
                    PointOrPlaceholder::Point(DirectedPoint::new(min_x, max_y, Direction::UpRight));
                let source_index = *node_indices.get(&source_weight).unwrap();
                let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                let target_index = *node_indices.get(&target_weight).unwrap();
                graph.add_edge(source_index, target_index, 1);
            }
        }
    }

    // Use Dijkstra's algorithm to find the shortest path
    let start_weight =
        PointOrPlaceholder::Point(DirectedPoint::new(start.x, start.y, start.direction));
    let end_weight: PointOrPlaceholder = match end {
        TargetLocation::Concrete(end_point) => PointOrPlaceholder::Point(end_point),
        TargetLocation::OtherSubdivision(_) => PointOrPlaceholder::SubdivisionPlaceholder,
    };

    println!("End weight: {:?}", end_weight);

    let start_index = *node_indices.get(&start_weight).unwrap();
    let end_index = *node_indices.get(&end_weight).unwrap();

    let path_weights = dijkstra(&graph, start_index, Some(end_index), |e| *e.weight());

    let mut path = Vec::new();
    let mut current_index = end_index;

    while current_index != start_index {
        path.push(current_index);
        let edge = graph
            .edges_directed(current_index, petgraph::Direction::Incoming)
            .min_by_key(|edge| path_weights.get(&edge.source()).unwrap_or(&MAX))
            .unwrap();
        current_index = edge.source();
    }

    path.push(start_index);
    path.reverse();

    // Convert NodeIndex to DirectedPoint
    let directed_path: Vec<DirectedPoint> = path
        .iter()
        .filter_map(|&node_index| match graph[node_index] {
            PointOrPlaceholder::Point(directed_point) => Some(directed_point),
            PointOrPlaceholder::SubdivisionPlaceholder => None,
        })
        .collect();

    return directed_path;
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
