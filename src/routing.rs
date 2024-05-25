use priority_queue::PriorityQueue;
use std::cmp::Reverse;
use std::collections::HashMap;

use pyo3::prelude::*;

use crate::{
    geometry::{DirectedPoint, Direction, Neighborhood, Point, Shape},
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    corner_cost: f64,
    diagonal_cost: f64,
    line_cost: f64,
    shape_cost: f64,
    shape_distance_cost: f64,
    line_distance_cost: f64,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(
        neighborhood: Neighborhood,
        corner_cost: f64,
        diagonal_cost: f64,
        line_cost: f64,
        shape_cost: f64,
        shape_distance_cost: f64,
        line_distance_cost: f64,
    ) -> Self {
        RoutingConfig {
            neighborhood,
            corner_cost,
            diagonal_cost,
            line_cost,
            shape_cost,
            shape_distance_cost,
            line_distance_cost,
        }
    }
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            neighborhood: Neighborhood::Orthogonal,
            corner_cost: 1.0,
            diagonal_cost: 1.0,
            line_cost: 1.0,
            shape_cost: 1.0,
            shape_distance_cost: 0.0,
            line_distance_cost: 0.0,
        }
    }
}

fn heuristic(a: &DirectedPoint, b: &DirectedPoint) -> i32 {
    (a.x - b.x).abs() + (a.y - b.y).abs()
}

fn get_neighbors(node: &DirectedPoint) -> Vec<DirectedPoint> {
    let mut neighbors = vec![];
    let x = node.x;
    let y = node.y;

    // Moving to another point in the current direction
    match node.direction {
        Direction::Up => neighbors.push(DirectedPoint::new(x, y - 1, Direction::Down)),
        Direction::UpRight => neighbors.push(DirectedPoint::new(x + 1, y - 1, Direction::DownLeft)),
        Direction::Right => neighbors.push(DirectedPoint::new(x + 1, y, Direction::Left)),
        Direction::DownRight => neighbors.push(DirectedPoint::new(x + 1, y + 1, Direction::UpLeft)),
        Direction::Down => neighbors.push(DirectedPoint::new(x, y + 1, Direction::Up)),
        Direction::DownLeft => neighbors.push(DirectedPoint::new(x - 1, y + 1, Direction::UpRight)),
        Direction::Left => neighbors.push(DirectedPoint::new(x - 1, y, Direction::Right)),
        Direction::UpLeft => neighbors.push(DirectedPoint::new(x - 1, y - 1, Direction::DownRight)),
        Direction::Center => neighbors.push(DirectedPoint::new(x, y, Direction::Center)),
    }

    // Changing direction
    for d in node.direction.other_directions(Neighborhood::Moore) {
        match d {
            Direction::Up => neighbors.push(DirectedPoint::new(x, y, Direction::Up)),
            Direction::UpRight => neighbors.push(DirectedPoint::new(x, y, Direction::UpRight)),
            Direction::Right => neighbors.push(DirectedPoint::new(x, y, Direction::Right)),
            Direction::DownRight => neighbors.push(DirectedPoint::new(x, y, Direction::DownRight)),
            Direction::Down => neighbors.push(DirectedPoint::new(x, y, Direction::Down)),
            Direction::DownLeft => neighbors.push(DirectedPoint::new(x, y, Direction::DownLeft)),
            Direction::Left => neighbors.push(DirectedPoint::new(x, y, Direction::Left)),
            Direction::UpLeft => neighbors.push(DirectedPoint::new(x, y, Direction::UpLeft)),
            Direction::Center => neighbors.push(DirectedPoint::new(x, y, Direction::Center)),
        }
    }
    neighbors
}

fn reconstruct_path(
    came_from: &HashMap<DirectedPoint, DirectedPoint>,
    current: DirectedPoint,
) -> Vec<DirectedPoint> {
    let mut total_path = vec![current];
    let mut current = current;
    while let Some(&parent) = came_from.get(&current) {
        current = parent;
        total_path.push(current);
    }
    total_path.reverse();
    total_path
}

#[pyclass]
pub struct EdgeRouter {
    pub shapes: HashMap<usize, Shape>,
    pub object_map: PyIndexSet,
    pub lines: HashMap<(usize, usize), Vec<Point>>,
}

#[pymethods]
impl EdgeRouter {
    #[new]
    pub fn new() -> Self {
        EdgeRouter {
            shapes: HashMap::default(),
            lines: HashMap::default(),
            object_map: PyIndexSet::default(),
        }
    }

    fn add_node(&mut self, node: &Bound<PyAny>, shape: Shape) -> PyResult<()> {
        let node_index = self.object_map.insert_full(node)?.0;
        self.shapes.insert(node_index, shape);
        Ok(())
    }

    fn add_edge(
        &mut self,
        start: &Bound<'_, PyAny>,
        end: &Bound<'_, PyAny>,
        line: Vec<Point>,
    ) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;
        self.lines.insert((start_index, end_index), line);
        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            self.shapes.remove(&index);
            // TODO: Needs some cleanup of the object map at some point.
        }
        Ok(())
    }

    fn remove_edge(
        &mut self,
        _py: Python<'_>,
        start: &Bound<'_, PyAny>,
        end: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let index_start = self.object_map.get_full(start)?;
        let index_end = self.object_map.get_full(end)?;
        if let (Some((index_start, _)), Some((index_end, _))) = (index_start, index_end) {
            self.lines.remove(&(index_start, index_end));
        }
        Ok(())
    }

    fn transition_cost(
        &self,
        src: &DirectedPoint,
        dst: &DirectedPoint,
        config: &RoutingConfig,
    ) -> i32 {
        // TODO Node to DirectedPoint,
        // Routing configuration passed in to route_edge
        // Use rtrees to find shapes
        let mut cost = 1.0;

        // Add corner cost if the direction turns (going from left to right is not a corner)
        if src.direction != dst.direction.opposite() {
            cost += config.corner_cost;
        }

        // Add diagonal cost if the direction is diagonal
        if src.direction.is_diagonal() {
            cost += config.diagonal_cost;
        }

        cost.round() as i32
    }

    fn route_edge(
        &self,
        start: Point,
        end: Point,
        start_direction: Direction,
        end_direction: Direction,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        let start = DirectedPoint::new(start.x, start.y, start_direction);
        let end = DirectedPoint::new(end.x, end.y, end_direction);

        let mut open_set = PriorityQueue::new();
        open_set.push(start, Reverse(0));

        let mut came_from = HashMap::new();
        let mut g_score = HashMap::new();
        g_score.insert(start, 0);

        let mut f_score = HashMap::new();
        f_score.insert(start, heuristic(&start, &end));

        while let Some((current, _)) = open_set.pop() {
            if current == end {
                return Ok(reconstruct_path(&came_from, current));
            }

            for neighbor in get_neighbors(&current) {
                let tentative_g_score = g_score.get(&current).unwrap_or(&(i32::MAX - 100))
                    + self.transition_cost(&current, &neighbor, &config);

                if tentative_g_score < *g_score.get(&neighbor).unwrap_or(&(i32::MAX - 100)) {
                    came_from.insert(neighbor, current);
                    g_score.insert(neighbor, tentative_g_score);
                    f_score.insert(neighbor, tentative_g_score + heuristic(&neighbor, &end));

                    open_set.push(neighbor, Reverse(*f_score.get(&neighbor).unwrap()));
                }
            }
        }

        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Goal not found.",
        ))
    }
}
