use priority_queue::PriorityQueue;
use rstar::PointDistance;
use rstar::RTreeObject;
use std::cmp::min;
use std::cmp::Reverse;
use std::collections::HashMap;
use std::hash::Hash;
use std::sync::Arc;

use pyo3::prelude::*;

use crate::geometry::PointLike;
use crate::{
    geometry::{BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point},
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    corner_cost: i32,
    diagonal_cost: i32,
    line_cost: i32,
    shape_cost: i32,
    direction_change_margin_start: i32,
    direction_change_margin_end: i32,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(
        neighborhood: Neighborhood,
        corner_cost: i32,
        diagonal_cost: i32,
        line_cost: i32,
        shape_cost: i32,
        direction_change_margin_start: i32,
        direction_change_margin_end: i32,
    ) -> Self {
        RoutingConfig {
            neighborhood,
            corner_cost,
            diagonal_cost,
            line_cost,
            shape_cost,
            direction_change_margin_start,
            direction_change_margin_end,
        }
    }
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            neighborhood: Neighborhood::Orthogonal,
            corner_cost: 1,
            diagonal_cost: 1,
            line_cost: 1,
            shape_cost: 1,
            direction_change_margin_start: 1,
            direction_change_margin_end: 1,
        }
    }
}

fn heuristic(a: &DirectedPoint, b: &DirectedPoint, config: RoutingConfig) -> i32 {
    let lowest_distance = if config.neighborhood == Neighborhood::Orthogonal {
        (a.x - b.x).abs() + (a.y - b.y).abs()
    } else {
        (a.x - b.x).abs().max((a.y - b.y).abs())
    };

    let diagonal_cost = if config.diagonal_cost > 0 && b.direction.is_diagonal() {
        config.diagonal_cost
    } else {
        0
    };

    if a.direction == b.direction {
        (lowest_distance + diagonal_cost) * 12
    } else {
        (lowest_distance + diagonal_cost + config.corner_cost) * 12
    }
}

fn get_neighbors(
    node: &DirectedPoint,
    neighborhood: Neighborhood,
    allow_direction_change: bool,
) -> Vec<DirectedPoint> {
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

    let allowed_directions = if !allow_direction_change && node.direction != Direction::Center {
        match node.direction {
            Direction::Up => vec![Direction::Up, Direction::Down],
            Direction::UpRight => vec![Direction::UpRight, Direction::DownLeft],
            Direction::Right => vec![Direction::Right, Direction::Left],
            Direction::DownRight => vec![Direction::DownRight, Direction::UpLeft],
            Direction::Down => vec![Direction::Down, Direction::Up],
            Direction::DownLeft => vec![Direction::DownLeft, Direction::UpRight],
            Direction::Left => vec![Direction::Left, Direction::Right],
            Direction::UpLeft => vec![Direction::UpLeft, Direction::DownRight],
            Direction::Center => vec![Direction::Center],
        }
    } else {
        node.direction.other_directions(neighborhood)
    };

    let mut center_targets = vec![
                    DirectedPoint::new(x, y, Direction::Center),
                    DirectedPoint::new(x, y, Direction::Up),
                    DirectedPoint::new(x, y, Direction::Right),
                    DirectedPoint::new(x, y, Direction::Down),
                    DirectedPoint::new(x, y, Direction::Left),

                ];

    if neighborhood == Neighborhood::Moore {
        center_targets.push(DirectedPoint::new(x, y, Direction::UpRight));
        center_targets.push(DirectedPoint::new(x, y, Direction::DownRight));
        center_targets.push(DirectedPoint::new(x, y, Direction::DownLeft));
        center_targets.push(DirectedPoint::new(x, y, Direction::UpLeft));
    }

    // Changing direction
    for d in allowed_directions {
        match d {
            Direction::Up => neighbors.push(DirectedPoint::new(x, y, Direction::Up)),
            Direction::UpRight => neighbors.push(DirectedPoint::new(x, y, Direction::UpRight)),
            Direction::Right => neighbors.push(DirectedPoint::new(x, y, Direction::Right)),
            Direction::DownRight => neighbors.push(DirectedPoint::new(x, y, Direction::DownRight)),
            Direction::Down => neighbors.push(DirectedPoint::new(x, y, Direction::Down)),
            Direction::DownLeft => neighbors.push(DirectedPoint::new(x, y, Direction::DownLeft)),
            Direction::Left => neighbors.push(DirectedPoint::new(x, y, Direction::Left)),
            Direction::UpLeft => neighbors.push(DirectedPoint::new(x, y, Direction::UpLeft)),
            Direction::Center => neighbors.extend_from_slice(
                center_targets.as_slice()
            ),
        }
    }
    neighbors
}

fn reconstruct_path<T: Eq + Hash + Copy>(came_from: &HashMap<T, T>, current: T) -> Vec<T> {
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
    pub placed_nodes: HashMap<usize, PlacedRectangularNode>,
    pub placed_node_tree: rstar::RTree<PlacedRectangularNode>,
    pub placed_edge_tree: rstar::RTree<PlacedEdge>, // new field for edge spatial index
    pub object_map: PyIndexSet,
    pub shape_occlusion: HashMap<(i32, i32), i32>,
    pub line_occlusion: HashMap<(i32, i32), i32>,
    pub existing_edges: HashMap<(usize, usize), Vec<Point>>,
}

impl RTreeObject for PlacedRectangularNode {
    type Envelope = rstar::AABB<Point>;

    fn envelope(&self) -> Self::Envelope {
        let top_left = self.top_left();
        let bottom_right = self.bottom_right();
        rstar::AABB::from_corners(
            Point {
                x: top_left.x,
                y: top_left.y,
            },
            Point {
                x: bottom_right.x,
                y: bottom_right.y,
            },
        )
    }
}

// 1. Define a new struct for edges and implement RTreeObject.
#[derive(Clone)]
pub struct PlacedEdge {
    pub start: Point,
    pub end: Point,
}

impl rstar::RTreeObject for PlacedEdge {
    type Envelope = rstar::AABB<Point>;

    fn envelope(&self) -> Self::Envelope {
        let (min_x, max_x) = if self.start.x < self.end.x {
            (self.start.x, self.end.x)
        } else {
            (self.end.x, self.start.x)
        };
        let (min_y, max_y) = if self.start.y < self.end.y {
            (self.start.y, self.end.y)
        } else {
            (self.end.y, self.start.y)
        };
        rstar::AABB::from_corners(Point { x: min_x, y: min_y }, Point { x: max_x, y: max_y })
    }
}

impl PointDistance for PlacedEdge {
    fn distance_2(&self, point: &Point) -> i32 {
        point_segment_distance_sq(point, &self.start, &self.end).round() as i32
    }
}

impl EdgeRouter {
    fn transition_cost(
        &self,
        src: &DirectedPoint,
        dst: &DirectedPoint,
        config: &RoutingConfig,
        global_start: &DirectedPoint,
        global_end: &DirectedPoint,
    ) -> i32 {
        let mut cost: i32 = 0;

        if src.x != dst.x || src.y != dst.y {
            if src.direction.is_diagonal() {
                cost += 14 + config.diagonal_cost;
            } else {
                cost += 10;
            }
        }

        if src.direction != dst.direction.opposite() {
            cost += config.corner_cost;
        }

        // Continue with the old occlusion terms for shape and line.
        if config.shape_cost > 0 {
            if *self.shape_occlusion.get(&(dst.x, dst.y)).unwrap_or(&0) > 0 {
                cost += config.shape_cost;
            }
        }

        if config.line_cost > 0 {
            if *self.line_occlusion.get(&(dst.x, dst.y)).unwrap_or(&0) > 0 {
                cost += config.line_cost;
            }
        }

        cost
    }
}

#[pymethods]
impl EdgeRouter {
    #[new]
    pub fn new() -> Self {
        EdgeRouter {
            placed_nodes: HashMap::default(),
            placed_node_tree: rstar::RTree::new(),
            placed_edge_tree: rstar::RTree::new(), // initialize the new tree
            object_map: PyIndexSet::default(),
            shape_occlusion: HashMap::default(),
            line_occlusion: HashMap::default(),
            existing_edges: HashMap::default(),
        }
    }

    fn add_node(
        &mut self,
        node: &Bound<PyAny>,
        placed_node: PlacedRectangularNode,
    ) -> PyResult<()> {
        // TODO check for inserting twice
        let node_index = self.object_map.insert_full(node)?.0;
        self.placed_nodes.insert(node_index, placed_node);
        self.placed_node_tree.insert(placed_node);
        for x in placed_node.top_left().x..=placed_node.bottom_right().x {
            for y in placed_node.top_left().y..=placed_node.bottom_right().y {
                self.shape_occlusion
                    .entry((x, y))
                    .and_modify(|e| *e += 1)
                    .or_insert(1);
            }
        }

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

        for point in &line {
            self.line_occlusion
                .entry((point.x, point.y))
                .and_modify(|e| *e += 1)
                .or_insert(1);
        }

        self.existing_edges
            .insert((start_index, end_index), line.clone());

        // Insert each segment between consecutive points into the spatial index.
        let mut prev: Option<&Point> = None;
        for point in &line {
            if let Some(p) = prev {
                let edge = PlacedEdge {
                    start: *p,
                    end: *point,
                };
                self.placed_edge_tree.insert(edge);
            }
            prev = Some(point);
        }

        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            for x in
                self.placed_nodes[&index].top_left().x..=self.placed_nodes[&index].bottom_right().x
            {
                for y in self.placed_nodes[&index].top_left().y
                    ..=self.placed_nodes[&index].bottom_right().y
                {
                    self.shape_occlusion.entry((x, y)).and_modify(|e| *e -= 1);
                }
            }
            self.placed_nodes.remove(&index);
        }
        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn remove_edge(
        &mut self,
        _py: Python<'_>,
        start: &Bound<'_, PyAny>,
        end: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;

        if let Some(line) = self.existing_edges.get(&(start_index, end_index)) {
            for point in line {
                self.line_occlusion
                    .entry((point.x, point.y))
                    .and_modify(|e| *e -= 1);
            }
            self.existing_edges.remove(&(start_index, end_index));
        }

        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn route_edges(
        &mut self,
        edges: Vec<(
            Bound<'_, PyAny>,
            Bound<'_, PyAny>,
            DirectedPoint,
            DirectedPoint,
            RoutingConfig,
        )>,
    ) -> PyResult<Vec<Vec<DirectedPoint>>> {
        let mut result = Vec::new();

        for (u, v, start, end, config) in edges {
            let directed_points = self.route_edge(&u, &v, start, end, start, end, config)?;
            let path = directed_points
                .iter()
                .map(|p| Point::new(p.x, p.y))
                .collect();
            let _ = self.add_edge(&u, &v, path);
            result.push(directed_points);
        }
        Ok(result)
    }

    fn route_edge_astar(
        &self,
        start: DirectedPoint,
        end: DirectedPoint,
        global_start: DirectedPoint,
        global_end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        let mut open_set = PriorityQueue::new();
        open_set.push(start, Reverse(0));

        let mut came_from = HashMap::new();
        let mut g_score = HashMap::new();
        g_score.insert(start, 0);

        let mut f_score = HashMap::new();
        f_score.insert(start, heuristic(&start, &end, config));

        while let Some((current, _)) = open_set.pop() {
            if current == end
                || (end.direction == Direction::Center && current.x == end.x && current.y == end.y)
            {
                return Ok(reconstruct_path(&came_from, current));
            }

            let current_end_distance = (current.x - end.x).abs() + (current.y - end.y).abs();
            let current_start_distance = (current.x - start.x).abs() + (current.y - start.y).abs();

            for neighbor in get_neighbors(
                &current,
                config.clone().neighborhood,
                current_start_distance >= config.direction_change_margin_start && current_end_distance >= config.direction_change_margin_end,
            ) {
                let tentative_g_score = g_score.get(&current).unwrap_or(&(i32::MAX - 100))
                    + self.transition_cost(&current, &neighbor, &config, &global_start, &global_end);

                if tentative_g_score < *g_score.get(&neighbor).unwrap_or(&(i32::MAX - 100)) {
                    came_from.insert(neighbor, current);
                    g_score.insert(neighbor, tentative_g_score);
                    f_score.insert(
                        neighbor,
                        tentative_g_score + heuristic(&neighbor, &end, config),
                    );

                    open_set.push(neighbor, Reverse(*f_score.get(&neighbor).unwrap()));
                }
            }
        }

        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Goal not found.",
        ))
    }

    fn _route_edge(
        &self,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        start: DirectedPoint,
        end: DirectedPoint,
        global_start: DirectedPoint,
        global_end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        if (start.x - end.x).abs() + (start.y - end.y).abs() > 10
            && ((start.x - end.x).abs() > 3 && (start.y - end.y).abs() > 3)
        {
            // Create multiple intermediate point candidates
            let candidates = vec![
                // Midpoint
                (start.x + end.x) / 2, (start.y + end.y) / 2,
                // Corner points with proper offsets
                start.x + match start.direction {
                    Direction::Right | Direction::UpRight | Direction::DownRight => config.direction_change_margin_start,
                    Direction::Left | Direction::UpLeft | Direction::DownLeft => -config.direction_change_margin_start,
                    _ => 0,
                },
                end.y + match end.direction {
                    Direction::Up | Direction::UpRight | Direction::UpLeft => -config.direction_change_margin_end,
                    Direction::Down | Direction::DownRight | Direction::DownLeft => config.direction_change_margin_end,
                    _ => 0,
                },
                // Second corner point with offsets
                end.x + match end.direction {
                    Direction::Right | Direction::UpRight | Direction::DownRight => config.direction_change_margin_end,
                    Direction::Left | Direction::UpLeft | Direction::DownLeft => -config.direction_change_margin_end,
                    _ => 0,
                },
                start.y + match start.direction {
                    Direction::Up | Direction::UpRight | Direction::UpLeft => -config.direction_change_margin_start,
                    Direction::Down | Direction::DownRight | Direction::DownLeft => config.direction_change_margin_start,
                    _ => 0,
                },
            ];

            let intermediate_direction = Direction::Center;
            let mut best_path = None;
            let mut best_score = i32::MAX;

            // Try each pair of coordinates as an intermediate point
            for i in (0..candidates.len()).step_by(2) {
                if i + 1 >= candidates.len() {
                    break;
                }

                let intermediate_x = candidates[i];
                let intermediate_y = candidates[i + 1];

                let mut intermediate_point_start = DirectedPoint::new(
                    intermediate_x,
                    intermediate_y,
                    intermediate_direction,
                );

                let mut intermediate_point_end = DirectedPoint::new(
                    intermediate_x,
                    intermediate_y,
                    intermediate_direction.opposite(),
                );

                intermediate_point_start.debug = true;
                intermediate_point_end.debug = true;

                // Skip invalid intermediate points
                if !self.is_point_valid(&intermediate_point_start) {
                    continue;
                }

                let mut first_part_config = config.clone();
                let mut second_part_config = config.clone();
                second_part_config.direction_change_margin_start = 0;
                first_part_config.direction_change_margin_end = 0;

                if let (Ok(mut sub_path1), Ok(mut sub_path2)) = (
                    self._route_edge(u, v, start, intermediate_point_end, global_start, global_end, first_part_config),
                    self._route_edge(u, v, intermediate_point_start, end, global_start, global_end, second_part_config)
                ) {
                    // Measure the quality of this path
                    let mut full_path = sub_path1.clone();
                    full_path.append(&mut sub_path2.clone());

                    // Count direction changes (corners)
                    let mut corners = 0;
                    for i in 1..full_path.len() {
                        if i > 0 && full_path[i-1].direction != full_path[i].direction {
                            corners += 1;
                        }
                    }

                    // If we found a path with only one corner, use it immediately
                    if corners <= 1 {
                        let mut path = Vec::new();
                        path.append(&mut sub_path1);
                        path.append(&mut sub_path2);
                        return Ok(path);
                    }

                    // Score is combination of corners and path length
                    let score = corners * 10 + full_path.len() as i32;

                    if score < best_score {
                        let mut path = Vec::new();
                        path.append(&mut sub_path1);
                        path.append(&mut sub_path2);
                        best_path = Some(path);
                        best_score = score;
                    }
                }
            }

            // Return the best path found (if any)
            if let Some(path) = best_path {
                return Ok(path);
            }
        }
        self.route_edge_astar(start, end, global_start, global_end, config)
    }

    fn route_edge(
        &self,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        start: DirectedPoint,
        end: DirectedPoint,
        global_start: DirectedPoint,
        global_end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        self._route_edge(u, v, start, end, global_start, global_end, config)
    }

    fn is_point_valid(&self, point: &DirectedPoint) -> bool {
        // Check if the point is within any placed node
        for node in self.placed_nodes.values() {
            if node.contains_point(&point.as_point()) {
                return false;
            }
        }

        // Check if the point is on any existing edge
        if self.line_occlusion.get(&(point.x, point.y)).unwrap_or(&0) > &0 {
            return false;
        }

        true
    }
}

// 5. Create a helper to compute squared distance from a point to a segment.
fn point_segment_distance_sq(point: &Point, start: &Point, end: &Point) -> f32 {
    let px = point.x as f32;
    let py = point.y as f32;
    let x1 = start.x as f32;
    let y1 = start.y as f32;
    let x2 = end.x as f32;
    let y2 = end.y as f32;
    let dx = x2 - x1;
    let dy = y2 - y1;
    if dx == 0.0 && dy == 0.0 {
        // start and end are the same point
        let dx = px - x1;
        let dy = py - y1;
        return dx * dx + dy * dy;
    }
    // Calculate the projection factor t of point onto the edge vector
    let t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy);
    let t = t.clamp(0.0, 1.0);
    let proj_x = x1 + t * dx;
    let proj_y = y1 + t * dy;
    let diff_x = px - proj_x;
    let diff_y = py - proj_y;
    diff_x * diff_x + diff_y * diff_y
}
