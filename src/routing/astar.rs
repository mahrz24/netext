use std::cmp::Reverse;
use std::collections::{BinaryHeap, HashMap};

use pyo3::prelude::*;
use rand::seq::SliceRandom;
use rand::Rng;

use crate::geometry::Orientation;

use super::grid::GridPoint;
use super::masked_grid::MaskedGrid;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
struct GridState {
    index: GridPoint,
    orientation: Orientation,
}

pub(crate) fn route_visibility_astar<CostFn, R>(
    masked_grid: &MaskedGrid,
    start_grid_point: GridPoint,
    end_grid_point: GridPoint,
    start_orientation: Orientation,
    end_orientation: Orientation,
    rng: &mut R,
    mut cost_fn: CostFn,
) -> PyResult<Vec<(GridPoint, Orientation)>>
where
    CostFn: FnMut(GridPoint, GridPoint, Orientation, Orientation) -> i32,
    R: Rng + ?Sized,
{
    if start_grid_point.0 as usize >= masked_grid.point_mask.len()
        || end_grid_point.0 as usize >= masked_grid.point_mask.len()
    {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid index out of bounds",
        ));
    }

    if !masked_grid.point_mask[start_grid_point] || !masked_grid.point_mask[end_grid_point] {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid point is blocked",
        ));
    }

    let start_state = GridState {
        index: start_grid_point,
        orientation: start_orientation,
    };
    let goal_state = GridState {
        index: end_grid_point,
        orientation: end_orientation,
    };

    if start_state == goal_state {
        return Ok(vec![(start_state.index, start_state.orientation)]);
    }

    let goal_coords = masked_grid.grid.grid_point_to_grid_coords(end_grid_point);

    if goal_coords.is_none() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "End grid point is out of bounds",
        ));
    }

    let goal_coords = goal_coords.unwrap();

    let heuristic = |state: GridState| -> i32 {
        let (sx, sy) = masked_grid.grid.grid_point_to_grid_coords(state.index).unwrap();
        (sx as i32 - goal_coords.0 as i32).abs() + (sy as i32 - goal_coords.1 as i32).abs()
    };

    let mut open_set: BinaryHeap<(Reverse<i32>, u64, GridState)> = BinaryHeap::new();
    let mut came_from: HashMap<GridState, GridState> = HashMap::new();
    let mut g_score: HashMap<GridState, i32> = HashMap::new();

    const MAX_SCORE: i32 = i32::MAX / 4;
    let mut insert_counter: u64 = 0;

    g_score.insert(start_state, 0);
    let start_f = heuristic(start_state);
    open_set.push((Reverse(start_f), insert_counter, start_state));
    insert_counter += 1;

    let mut neighbors_buf: Vec<(GridPoint, Orientation)> = Vec::with_capacity(3);

    while let Some((Reverse(_f_score), _order, current_state)) = open_set.pop() {
        if current_state == goal_state {
            let mut path = Vec::new();
            let mut cursor = current_state;
            path.push((cursor.index, cursor.orientation));
            while let Some(prev) = came_from.get(&cursor).copied() {
                cursor = prev;
                path.push((cursor.index, cursor.orientation));
            }
            path.reverse();
            return Ok(path);
        }

        let current_g = *g_score.get(&current_state).unwrap_or(&MAX_SCORE);

        masked_grid.fill_neighbors(
            current_state.index,
            current_state.orientation,
            &mut neighbors_buf,
        );
        neighbors_buf.shuffle(rng);
        for (neighbor_index, neighbor_orientation) in neighbors_buf.iter().copied() {
            // Do not allow in-place orientation flips at the start or end grid point.
            if neighbor_index == current_state.index
                && (current_state.index == start_grid_point || current_state.index == end_grid_point)
            {
                continue;
            }

            if !masked_grid.point_mask[neighbor_index] {
                continue;
            }

            let neighbor_state = GridState {
                index: neighbor_index,
                orientation: neighbor_orientation,
            };

            let step_cost = cost_fn(
                current_state.index,
                neighbor_state.index,
                current_state.orientation,
                neighbor_state.orientation,
            );

            if step_cost >= MAX_SCORE {
                continue;
            }

            let tentative_g = match current_g.checked_add(step_cost) {
                Some(sum) => sum,
                None => continue,
            };

            if tentative_g >= *g_score.get(&neighbor_state).unwrap_or(&MAX_SCORE) {
                continue;
            }

            came_from.insert(neighbor_state, current_state);
            g_score.insert(neighbor_state, tentative_g);
            let heuristic_cost = heuristic(neighbor_state);
            let f_score = match tentative_g.checked_add(heuristic_cost) {
                Some(value) => value,
                None => continue,
            };
            open_set.push((Reverse(f_score), insert_counter, neighbor_state));
            insert_counter += 1;
        }
    }

    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
        "Goal not found.",
    ))
}
