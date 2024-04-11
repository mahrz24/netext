use petgraph::algo::dijkstra;
use petgraph::graph::NodeIndex;
use petgraph::visit::EdgeRef;
use petgraph::Graph;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::collections::HashMap;
use std::collections::HashSet;
use std::collections::VecDeque;
use std::f64::MAX;

const SUBDIVISION_SIZE: i32 = 8;

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq)]
struct Point {
    x: i32,
    y: i32,
}

#[derive(Debug)]
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
enum SourceLocation {
    Concrete(DirectedPoint),
    Multiple(Vec<DirectedPoint>),
}

#[derive(Clone, Eq, PartialEq, Hash, Debug)]
enum TargetLocation {
    Concrete(DirectedPoint),
    Multiple(Vec<DirectedPoint>),
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
#[derive(Clone, Debug, Hash, Eq, PartialEq)]
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

    fn corner_points(&self) -> Vec<(i32, i32)> {
        let mut points = Vec::new();
        for x in [self.top_left.x, self.bottom_right.x].iter() {
            for y in [self.top_left.y, self.bottom_right.y].iter() {
                points.push((*x, *y));
            }
        }
        points
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

fn range_from_subdivision_index(
    subdivision_graph: &Graph<(i32, i32), f64>,
    subdivision_index: &NodeIndex,
    min: (i32, i32),
) -> Rectangle {
    let (subdivision_x, subdivision_y) = subdivision_graph[*subdivision_index];
    let (min_x, min_y) = min;

    let subdivision_min_x = min_x + subdivision_x * SUBDIVISION_SIZE;
    let subdivision_min_y = min_y + subdivision_y * SUBDIVISION_SIZE;
    let subdivision_max_x = min_x + (subdivision_x + 1) * SUBDIVISION_SIZE;
    let subdivision_max_y = min_y + (subdivision_y + 1) * SUBDIVISION_SIZE;

    Rectangle {
        top_left: Point::new(subdivision_min_x, subdivision_min_y),
        bottom_right: Point::new(subdivision_max_x, subdivision_max_y),
    }
}

#[pyfunction]
fn route_edge(
    py: Python,
    start: Point,
    end: Point,
    start_direction: Direction,
    end_direction: Direction,
    shapes: Vec<Shape>,
    lines: Vec<Vec<Point>>,
) -> PyResult<Vec<DirectedPoint>> {
    // Get the maximum and minimum coordinates
    let mut min_x = start.x.min(end.x);
    let mut min_y = start.y.min(end.y);
    let mut max_x = start.x.max(end.x);
    let mut max_y = start.y.max(end.y);

    // Update the maximum and minimum coordinates based on the nodes
    for node in &shapes {
        min_x = min_x.min(node.top_left.x);
        min_y = min_y.min(node.top_left.y);
        max_x = max_x.max(node.bottom_right.x);
        max_y = max_y.max(node.bottom_right.y);
    }


    let mut nodes_in_subdivision = HashMap::<(i32, i32), HashSet<Shape>>::new();

    println!("Shapes: {:?}", shapes);

    for node in &shapes {
        for (x, y) in node.corner_points() {
            let (subdivision_x, subdivision_y) = directed_point_to_subdivision(
                DirectedPoint::new(x, y, Direction::Center),
                Point::new(min_x, min_y),
            );

            let subdivision = nodes_in_subdivision
                .entry((subdivision_x, subdivision_y))
                .or_insert(HashSet::new());
            subdivision.insert(node.clone());
        }
    }

    println!("Nodes in subdivision: {:?}", nodes_in_subdivision);


    // Do a vertical and horizontal subdivision
    // Make sure that each subdivision is at most SUBDIVISION_SIZE units wide and high and at least 1 unit wide and high
    let n_subdivisions_x =
        (((max_x + 1) as f64 - min_x as f64) / SUBDIVISION_SIZE as f64).ceil() as i32;
    let n_subdivisions_y =
        (((max_y + 1) as f64 - min_y as f64) / SUBDIVISION_SIZE as f64).ceil() as i32;

    // Create a subdivision graph connecting neighboring subdivisions
    let mut subdivision_graph = Graph::<(i32, i32), f64>::new();
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

                    let node_weight = nodes_in_subdivision
                        .get(&(*target_x, *target_y))
                        .unwrap_or(&HashSet::new())
                        .len() as f64;
                    subdivision_graph.add_edge(source_index, target_index, 1.0 + node_weight);
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

    let mut subdivision_path = VecDeque::new();
    let mut current_subdivision_index = end_subdivision_index;

    while current_subdivision_index != start_subdivision_index {
        subdivision_path.push_front(current_subdivision_index);
        let edge = subdivision_graph
            .edges_directed(current_subdivision_index, petgraph::Direction::Incoming)
            .min_by(|edge1, edge2| {
                subdivision_path_weights
                    .get(&edge1.source())
                    .unwrap_or(&MAX)
                    .partial_cmp(
                        subdivision_path_weights
                            .get(&edge2.source())
                            .unwrap_or(&MAX),
                    )
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .unwrap();
        current_subdivision_index = edge.source();
    }

    subdivision_path.push_front(start_subdivision_index);

    // Add the last subdivision twice, as we need to route the endpoint within in the same subdivision
    // Or in the case of two subdivisions, we need to connect the routes coming from two sides

    // TODO: Check if we should always do this.
    if subdivision_path.len() <= 2 {
        subdivision_path.push_back(end_subdivision_index);
    }

    // For each subdivision part of the path, find the shortest path using a graph connecting each node
    // in the subdivision (with some margin to extend outside of the node).
    // Connect the boundaries in this graph to the goal (next subdivision or end)

    let mut directed_path_fwd = Vec::new();
    let mut directed_path_bwd = Vec::new();
    let start_point_fwd = DirectedPoint::new(start.x, start.y, start_direction);
    let start_point_bwd = DirectedPoint::new(end.x, end.y, end_direction);
    let mut current_start_point = start_point_fwd;
    let mut next_start_point = start_point_bwd;
    let mut is_fwd = true;
    let mut last_subdivision_index = start_subdivision_index;

    while subdivision_path.len() > 1 {
        let start_subdivision_index = if is_fwd {
            subdivision_path.pop_front().unwrap()
        } else {
            subdivision_path.pop_back().unwrap()
        };

        let end_subdivision_index = if is_fwd {
            subdivision_path.front().unwrap()
        } else {
            subdivision_path.back().unwrap()
        };

        let (start_subdivision_x, start_subdivision_y) = subdivision_graph[start_subdivision_index];

        let target_location = if *end_subdivision_index == start_subdivision_index {
            TargetLocation::Concrete(DirectedPoint::new(end.x, end.y, end_direction))
        } else {

            let (end_subdivision_x, end_subdivision_y) = subdivision_graph[*end_subdivision_index];

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

        let range = range_from_subdivision_index(
            &subdivision_graph,
            &start_subdivision_index,
            (min_x, min_y),
        );

        println!("Nodes in subdiv: {:?} {:?}", (start_subdivision_x, start_subdivision_y), nodes_in_subdivision.get(&(start_subdivision_x, start_subdivision_y)));

        let subdivision_path = route_edge_in_subdivision(
            range,
            SourceLocation::Concrete(current_start_point),
            target_location,
            nodes_in_subdivision
                .get(&(start_subdivision_x, start_subdivision_y))
                .unwrap_or(&HashSet::new()),
        );

        let mut last_point: DirectedPoint = current_start_point;

        for point in subdivision_path {
            if is_fwd {
                directed_path_fwd.push(point);
            } else {
                directed_path_bwd.push(point);
            }
            last_point = point
        }
        current_start_point = next_start_point;
        is_fwd = !is_fwd;
        next_start_point = last_point;
        last_subdivision_index = end_subdivision_index.clone();
    }

    // Connect the ends of the two paths
    let range =
        range_from_subdivision_index(&subdivision_graph, &last_subdivision_index, (min_x, min_y));

    println!(
        "Directed path fwd: {:?} => {:?}",
        directed_path_fwd.first().unwrap(),
        directed_path_fwd.last().unwrap()
    );

    if directed_path_bwd.is_empty() {
        return Ok(directed_path_fwd);
    }

    let mut connecting_path = route_edge_in_subdivision(
        range,
        SourceLocation::Multiple(directed_path_fwd.clone()),
        TargetLocation::Multiple(directed_path_bwd.clone()),
        nodes_in_subdivision
            .get(&subdivision_graph[start_subdivision_index])
            .unwrap_or(&HashSet::new()),
    );

    println!(
        "Directed path bwd: {:?} => {:?}",
        directed_path_bwd.first().unwrap(),
        directed_path_bwd.last().unwrap()
    );
    println!(
        "Connecting path: {:?} => {:?}",
        connecting_path.first().unwrap(),
        connecting_path.last().unwrap()
    );

    let fwd_index = directed_path_fwd
        .iter()
        .position(|&point| point == connecting_path[0])
        .unwrap();

    let bwd_index = directed_path_bwd
        .iter()
        .position(|&point| point == connecting_path.last().unwrap().clone())
        .unwrap();

    directed_path_fwd.truncate(fwd_index);
    directed_path_bwd.truncate(bwd_index);

    directed_path_bwd.reverse();

    directed_path_fwd.append(&mut connecting_path);
    directed_path_fwd.append(&mut directed_path_bwd);
    Ok(directed_path_fwd)
}

#[derive(Clone, Eq, PartialEq, Hash, Copy, Debug)]
enum PointOrPlaceholder {
    Point(DirectedPoint),
    SubdivisionPlaceholder,
    StartPlaceholder,
    EndPlaceholder,
}

fn route_edge_in_subdivision(
    range: Rectangle,
    start: SourceLocation,
    end: TargetLocation,
    shapes: &HashSet<Shape>,
) -> Vec<DirectedPoint> {
    let mut min_x = range.top_left.x;
    let mut min_y = range.top_left.y;
    let mut max_x = range.bottom_right.x;
    let mut max_y = range.bottom_right.y;

    min_x -= 2;
    min_y -= 2;
    max_x += 2;
    max_y += 2;

    // Create a graph
    let mut graph = Graph::<PointOrPlaceholder, f64>::new();

    // Create a map to store node indices
    let mut node_indices: HashMap<PointOrPlaceholder, NodeIndex> = HashMap::new();
    let mut shape_map: HashMap<(i32, i32), i32> = HashMap::new();
    println!("Shapes: {:?}", shapes);
    for x in min_x..=max_x {
        for y in min_y..=max_y {
            for shape in shapes {
                // Check if the point is inside the shape
                if x >= shape.top_left.x
                    && x <= shape.bottom_right.x
                    && y >= shape.top_left.y
                    && y <= shape.bottom_right.y
                {
                    // Increase counter for the position by one
                    shape_map
                        .entry((x, y))
                        .and_modify(|counter| *counter += 1)
                        .or_insert(1);
                }
            }

            for direction in Direction::all_directions() {
                let node_weight = PointOrPlaceholder::Point(DirectedPoint::new(x, y, direction));
                let node_index = graph.add_node(node_weight);
                node_indices.insert(node_weight, node_index);
            }
        }
    }

    println!("Shape map for subdivision ({:?}): {:?}", range, shape_map);

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

                let self_targets = other_directions.iter().map(|&d| {
                    (
                        DirectedPoint::new(x, y, d),
                        match d {
                            Direction::Up => 1.0,
                            Direction::Down => 1.0,
                            Direction::Left => 1.0,
                            Direction::Right => 1.0,
                            Direction::UpRight => 1.0,
                            Direction::UpLeft => 1.0,
                            Direction::DownRight => 1.0,
                            Direction::DownLeft => 1.0,
                            Direction::Center => 1.0,
                        },
                    )
                });

                // Add edges from down to up, right to left, etc.
                let targets =
                    match direction {
                        Direction::Up => self_targets
                            .chain([(DirectedPoint::new(x, y - 1, Direction::Down), 1.0)]),
                        Direction::Down => {
                            self_targets.chain([(DirectedPoint::new(x, y + 1, Direction::Up), 1.0)])
                        }
                        Direction::Left => self_targets
                            .chain([(DirectedPoint::new(x - 1, y, Direction::Right), 1.0)]),
                        Direction::Right => self_targets
                            .chain([(DirectedPoint::new(x + 1, y, Direction::Left), 1.0)]),
                        Direction::UpRight => self_targets
                            .chain([(DirectedPoint::new(x + 1, y - 1, Direction::DownLeft), 4.0)]),
                        Direction::UpLeft => self_targets
                            .chain([(DirectedPoint::new(x - 1, y - 1, Direction::DownRight), 4.0)]),
                        Direction::DownRight => self_targets
                            .chain([(DirectedPoint::new(x + 1, y + 1, Direction::UpLeft), 4.0)]),
                        Direction::DownLeft => self_targets
                            .chain([(DirectedPoint::new(x - 1, y + 1, Direction::UpRight), 4.0)]),
                        Direction::Center => self_targets
                            .chain([(DirectedPoint::new(x, y, Direction::UpRight), 1.0)]),
                    };

                for (target, weight) in targets {
                    let target_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                        target.x,
                        target.y,
                        target.direction,
                    ));
                    let target_index = match node_indices.get(&target_weight) {
                        Some(index) => *index,
                        None => continue,
                    };

                    if source_index != target_index
                        && graph.find_edge(source_index, target_index).is_none()
                    {
                        graph.add_edge(
                            source_index,
                            target_index,
                            weight + 100.0 * (*shape_map.get(&(x, y)).unwrap_or(&0) as f64),
                        );
                    }
                }
            }
        }
    }

    match start {
        SourceLocation::Multiple(ref start_points) => {
            let node_weight = PointOrPlaceholder::StartPlaceholder;
            let node_index = graph.add_node(node_weight);
            node_indices.insert(node_weight, node_index);
            for start_point in start_points {
                let source_weight = PointOrPlaceholder::StartPlaceholder;
                let source_index = *node_indices.get(&source_weight).unwrap();
                let target_weight = PointOrPlaceholder::Point(*start_point);
                if let Some(target_index) = node_indices.get(&target_weight) {
                    graph.add_edge(source_index, *target_index, 1.0);
                }
            }
        }
        SourceLocation::Concrete(_) => (),
    }

    match end {
        TargetLocation::Multiple(ref end_points) => {
            let node_weight = PointOrPlaceholder::EndPlaceholder;
            let node_index = graph.add_node(node_weight);
            node_indices.insert(node_weight, node_index);

            for end_point in end_points {
                let target_weight = PointOrPlaceholder::EndPlaceholder;
                let target_index = *node_indices.get(&target_weight).unwrap();
                let source_weight = PointOrPlaceholder::Point(*end_point);
                if let Some(source_index) = node_indices.get(&source_weight) {
                    graph.add_edge(*source_index, target_index, 1.0);
                }
            }
        }
        TargetLocation::Concrete(_) => (),
        TargetLocation::OtherSubdivision(direction) => {
            let node_weight = PointOrPlaceholder::SubdivisionPlaceholder;
            let node_index = graph.add_node(node_weight);
            node_indices.insert(node_weight, node_index);

            match direction {
                Direction::Center => {
                    panic!("Cannot route another subdivision in the direction center")
                }
                Direction::Up => {
                    for x in min_x..=max_x {
                        let source_weight =
                            PointOrPlaceholder::Point(DirectedPoint::new(x, min_y, Direction::Up));
                        let source_index = *node_indices.get(&source_weight).unwrap();
                        let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                        let target_index = *node_indices.get(&target_weight).unwrap();
                        graph.add_edge(source_index, target_index, 1.0);
                    }
                }
                Direction::Down => {
                    for x in min_x..=max_x {
                        let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                            x,
                            max_y,
                            Direction::Down,
                        ));
                        let source_index = *node_indices.get(&source_weight).unwrap();
                        let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                        let target_index = *node_indices.get(&target_weight).unwrap();
                        graph.add_edge(source_index, target_index, 1.0);
                    }
                }
                Direction::Left => {
                    for y in min_y..=max_y {
                        let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                            min_x,
                            y,
                            Direction::Left,
                        ));
                        let source_index = *node_indices.get(&source_weight).unwrap();
                        let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                        let target_index = *node_indices.get(&target_weight).unwrap();
                        graph.add_edge(source_index, target_index, 1.0);
                    }
                }
                Direction::Right => {
                    for y in min_y..=max_y {
                        let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                            max_x,
                            y,
                            Direction::Right,
                        ));
                        let source_index = *node_indices.get(&source_weight).unwrap();
                        let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                        let target_index = *node_indices.get(&target_weight).unwrap();
                        graph.add_edge(source_index, target_index, 1.0);
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
                    graph.add_edge(source_index, target_index, 1.0);
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
                    graph.add_edge(source_index, target_index, 1.0);
                }
                Direction::DownRight => {
                    let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                        max_x,
                        max_y,
                        Direction::UpLeft,
                    ));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1.0);
                }
                Direction::DownLeft => {
                    let source_weight = PointOrPlaceholder::Point(DirectedPoint::new(
                        min_x,
                        max_y,
                        Direction::UpRight,
                    ));
                    let source_index = *node_indices.get(&source_weight).unwrap();
                    let target_weight = PointOrPlaceholder::SubdivisionPlaceholder;
                    let target_index = *node_indices.get(&target_weight).unwrap();
                    graph.add_edge(source_index, target_index, 1.0);
                }
            }
        }
    }

    // Use Dijkstra's algorithm to find the shortest path
    let start_weight = match start {
        SourceLocation::Multiple(_) => PointOrPlaceholder::StartPlaceholder,
        SourceLocation::Concrete(start_point) => PointOrPlaceholder::Point(DirectedPoint::new(
            start_point.x,
            start_point.y,
            start_point.direction,
        )),
    };

    let end_weight: PointOrPlaceholder = match end {
        TargetLocation::Multiple(_) => PointOrPlaceholder::EndPlaceholder,
        TargetLocation::Concrete(end_point) => PointOrPlaceholder::Point(end_point),
        TargetLocation::OtherSubdivision(_) => PointOrPlaceholder::SubdivisionPlaceholder,
    };

    let start_index = *node_indices.get(&start_weight).unwrap();
    let end_index = *node_indices.get(&end_weight).unwrap();

    let path_weights = dijkstra(&graph, start_index, Some(end_index), |e| *e.weight());

    let mut path = Vec::new();
    let mut current_index = end_index;

    while current_index != start_index {
        path.push(current_index);
        let edge = graph
            .edges_directed(current_index, petgraph::Direction::Incoming)
            .min_by(|edge1, edge2| {
                path_weights
                    .get(&edge1.source())
                    .unwrap_or(&MAX)
                    .partial_cmp(path_weights.get(&edge2.source()).unwrap_or(&MAX))
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
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
            PointOrPlaceholder::StartPlaceholder => None,
            PointOrPlaceholder::EndPlaceholder => None,
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
