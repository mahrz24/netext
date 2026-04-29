//! Sugiyama-style layered graph layout.
//!
//! Pipeline (driven by `SugiyamaLayout::layout`):
//!
//!   1. **Cycle removal** (`remove_cycles`): reverse a feedback arc set so the
//!      remaining graph is a DAG.
//!   2. **Layering** (`layer_disconnected_components` → `longest_path_layering`):
//!      assign each node an integer layer, processing each weakly-connected
//!      component independently.
//!   3. **Dummy node insertion** (`insert_dummy_nodes`): replace every edge
//!      that spans more than one layer with a chain through intermediate
//!      layers. After this step every edge is between adjacent layers.
//!   4. **Crossing minimization** (`barycenter_ordering`): order nodes within
//!      each layer to reduce the number of edge crossings, using alternating
//!      down/up barycenter sweeps.
//!   5. **Coordinate assignment** (`brandes_koepf_coordinates`): assign x-y
//!      positions using the Brandes–Köpf algorithm — see the function
//!      header for a detailed description.
//!
//! The final coordinates are returned across the PyO3 boundary as
//! `(PyObject, Point)` pairs. Dummy nodes are filtered out at this boundary
//! since they have no Python representation.
//!
//! Reference: Brandes & Köpf, *"Fast and Simple Horizontal Coordinate
//! Assignment"*, Graph Drawing 2001, LNCS 2265.

use std::collections::{HashMap, HashSet};

use petgraph::algo::greedy_feedback_arc_set;
use petgraph::graph::NodeIndex;
use petgraph::graphmap::DiGraphMap;
use petgraph::unionfind::UnionFind;
use petgraph::visit::IntoEdgeReferences;
use petgraph::visit::{NodeIndexable, Topo};
use pyo3::prelude::*;

use crate::geometry::Size;
use crate::{geometry::Point, graph::CoreGraph};

use super::{LayoutDirection, LayoutEngine};

/// Hard cap on barycenter sweep iterations. The algorithm stops earlier if
/// a full down+up pair leaves every layer's permutation unchanged.
const MAX_BARYCENTER_SWEEPS: usize = 24;

/// Dummy nodes have no real size — they're just bend points for long edges.
/// We give them a 1×1 box so the spacing math (which assumes positive width)
/// stays well-defined.
const DUMMY_WIDTH: i32 = 1;
const DUMMY_HEIGHT: i32 = 1;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct SugiyamaLayout {
    direction: LayoutDirection,
}

#[pymethods]
impl SugiyamaLayout {
    #[new]
    fn new(direction: LayoutDirection) -> (Self, LayoutEngine) {
        (SugiyamaLayout { direction }, LayoutEngine {})
    }

    #[getter]
    fn get_layout_direction(&self) -> Option<LayoutDirection> {
        Some(self.direction)
    }

    /// Top-level entry point: drive the full Sugiyama pipeline and return
    /// `(PyObject, Point)` for every original node.
    ///
    /// We work on a clone (`raw_graph`) so we can mutate it freely — reverse
    /// edges in cycle removal, append dummy nodes for long edges — without
    /// touching the caller's `CoreGraph`.
    ///
    /// The internal layout is always computed in "top-down" coordinates
    /// (layers stack along y, nodes in a layer spread along x). For
    /// `LeftRight` layouts we swap x↔y once at the very end.
    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        // Working copy: cycle removal reverses some edges, dummy insertion
        // adds new nodes/edges. Neither change is visible to the caller.
        let mut raw_graph = graph.graph.clone();
        self.remove_cycles(&mut raw_graph, &graph.graph);

        // After layering, `layer_map` maps each node id (== position in the
        // graph's IndexMap) to its integer layer. Disconnected components
        // are layered independently but share the same coordinate space.
        let mut layer_map = self.layer_disconnected_components(&raw_graph);

        // Replace edges spanning more than one layer with chains of dummy
        // nodes (one per intermediate layer). Dummies participate in ordering
        // and coordinate assignment so the long edge can be drawn through
        // intermediate "anchor" points; without them the crossing-min and
        // alignment passes are blind to long edges.
        let dummy_ids = insert_dummy_nodes(&mut raw_graph, &mut layer_map);

        // Group nodes into a `Vec<Vec<usize>>` (one inner vec per layer) so
        // we can talk about positions-within-layer cleanly.
        let layers = layers_from_layer_map(&layer_map);

        // Reduce edge crossings with alternating barycenter sweeps.
        let ordered_layers = self.barycenter_ordering(&raw_graph, layers);

        // Compute final x/y coordinates with Brandes–Köpf.
        let coordinates =
            self.brandes_koepf_coordinates(&ordered_layers, &raw_graph, graph, &dummy_ids);

        // For `LeftRight` layouts, reuse the top-down coordinate machinery
        // and swap the axes here. `width_in_direction` / `height_in_direction`
        // already account for the swap when measuring node sizes upstream.
        let final_coordinates: HashMap<usize, Point> =
            if self.direction == LayoutDirection::LeftRight {
                coordinates
                    .into_iter()
                    .map(|(node, point)| (node, Point::new(point.y, point.x)))
                    .collect()
            } else {
                coordinates
            };

        Ok(final_coordinates
            .into_iter()
            // Dummy nodes have indices past the original CoreGraph's node
            // range. They have no associated PyObject — drop them here so
            // they never leak across the FFI boundary.
            .filter(|(node, _)| !dummy_ids.contains(node))
            .filter_map(|(node, point)| {
                // Real nodes have ID == position in the original
                // object_map (CoreGraph inserts node objects in order),
                // so we can look up directly without going through
                // petgraph's NodeIndexable indirection.
                let object = graph.object_map.get_index(node);
                object.map(|object| (object.clone_ref(py), point))
            })
            .collect())
    }
}

// Internally we always work in "top-down" coordinates: x runs along a layer,
// y runs across layers. `width_in_direction` / `height_in_direction` adapt
// node sizes to that internal frame. For a `LeftRight` layout, the user's
// x-axis is our y-axis (and vice versa), so the user's "height" is what we
// treat as "width" while computing the layout.

fn width_in_direction(direction: LayoutDirection, size: &Size) -> i32 {
    match direction {
        LayoutDirection::TopDown => size.width(),
        LayoutDirection::LeftRight => size.height(),
    }
}

fn height_in_direction(direction: LayoutDirection, size: &Size) -> i32 {
    match direction {
        LayoutDirection::TopDown => size.height(),
        LayoutDirection::LeftRight => size.width(),
    }
}

/// Convert the `node → layer` mapping produced by layering into a
/// `Vec<Vec<usize>>` where outer index is layer index and inner contents
/// are the node ids in that layer.
///
/// The within-layer order returned here is just `node id` (sorted) — it's
/// arbitrary and serves only as a deterministic seed for the barycenter
/// sweep that runs next.
fn layers_from_layer_map(layer_map: &HashMap<usize, usize>) -> Vec<Vec<usize>> {
    let mut buckets: HashMap<usize, Vec<usize>> = HashMap::new();
    for (&node, &layer) in layer_map.iter() {
        buckets.entry(layer).or_default().push(node);
    }
    let mut indexed: Vec<(usize, Vec<usize>)> = buckets.into_iter().collect();
    indexed.sort_by_key(|(k, _)| *k);
    indexed
        .into_iter()
        .map(|(_, mut v)| {
            v.sort();
            v
        })
        .collect()
}

/// Replace every edge `(u, v)` with `layer(v) - layer(u) > 1` by a chain
/// of dummy nodes through every intermediate layer.
///
/// After this runs, every edge in the graph is between adjacent layers,
/// which is what the rest of the pipeline assumes.
///
/// Dummy id allocation: we pick `max(existing layer_map keys) + 1` as the
/// next available id. Since CoreGraph inserts nodes at sequential indices
/// 0..N-1 and layering produces layer_map keys in that same range, the
/// new id equals the next position in the petgraph IndexMap. This keeps
/// the invariant `NodeIndex value == position-in-IndexMap` intact, which
/// the barycenter / BK code relies on when calling `.index()`.
///
/// Returns the set of dummy node ids so downstream stages can recognize
/// them — most importantly, the conflict-marker (which treats dummy↔dummy
/// edges as "inner segments") and the final filter at the FFI boundary.
fn insert_dummy_nodes(
    raw_graph: &mut DiGraphMap<NodeIndex, ()>,
    layer_map: &mut HashMap<usize, usize>,
) -> HashSet<usize> {
    let mut is_dummy: HashSet<usize> = HashSet::new();
    let mut next_id: usize = layer_map
        .keys()
        .copied()
        .max()
        .map(|m| m + 1)
        .unwrap_or(0);

    // Snapshot the long-edge list first; we can't iterate `all_edges` while
    // mutating the graph below.
    let long_edges: Vec<(NodeIndex, NodeIndex)> = raw_graph
        .all_edges()
        .filter_map(|(u, v, _)| {
            let lu = *layer_map.get(&u.index())?;
            let lv = *layer_map.get(&v.index())?;
            if lv > lu + 1 {
                Some((u, v))
            } else {
                None
            }
        })
        .collect();

    for (u, v) in long_edges {
        let lu = layer_map[&u.index()];
        let lv = layer_map[&v.index()];
        // Drop the original long edge — we'll route it through dummies.
        raw_graph.remove_edge(u, v);

        // Walk through each intermediate layer, allocating one dummy per
        // layer and stitching it to the previous chain link.
        let mut prev = u;
        for layer_idx in (lu + 1)..lv {
            let dummy_id = next_id;
            next_id += 1;
            let dummy_ni = NodeIndex::new(dummy_id);
            raw_graph.add_node(dummy_ni);
            layer_map.insert(dummy_id, layer_idx);
            is_dummy.insert(dummy_id);
            raw_graph.add_edge(prev, dummy_ni, ());
            prev = dummy_ni;
        }
        // Close the chain: last dummy → original target.
        raw_graph.add_edge(prev, v, ());
    }

    is_dummy
}

// ---------------------------------------------------------------------------
// Crossing counting
//
// Counting edge crossings between two adjacent layers reduces to counting
// inversions in a list: enumerate edges in upper-endpoint order, list their
// lower-endpoint positions, and the number of inversions in that list equals
// the number of crossings. This is the standard merge-sort-based O(E log E)
// algorithm.
// ---------------------------------------------------------------------------

/// Count inversions in `arr` using merge sort. Mutates a scratch buffer
/// internally; `arr` itself is left unmodified.
fn inversions(arr: &[usize]) -> usize {
    if arr.len() < 2 {
        return 0;
    }
    let mut buf = arr.to_vec();
    let mut tmp = vec![0usize; buf.len()];
    let n = buf.len();
    merge_count(&mut buf, &mut tmp, 0, n)
}

/// Recursive merge step: sort `arr[lo..hi]` in place using `tmp` as scratch,
/// returning the number of inversions encountered.
fn merge_count(arr: &mut [usize], tmp: &mut [usize], lo: usize, hi: usize) -> usize {
    if hi - lo < 2 {
        return 0;
    }
    let mid = (lo + hi) / 2;
    let mut count = merge_count(arr, tmp, lo, mid) + merge_count(arr, tmp, mid, hi);
    let (mut i, mut j, mut k) = (lo, mid, lo);
    while i < mid && j < hi {
        if arr[i] <= arr[j] {
            tmp[k] = arr[i];
            i += 1;
        } else {
            tmp[k] = arr[j];
            j += 1;
            count += mid - i;
        }
        k += 1;
    }
    while i < mid {
        tmp[k] = arr[i];
        i += 1;
        k += 1;
    }
    while j < hi {
        tmp[k] = arr[j];
        j += 1;
        k += 1;
    }
    arr[lo..hi].copy_from_slice(&tmp[lo..hi]);
    count
}

/// Sum of crossings over all adjacent layer pairs. Used to track the best
/// permutation seen across barycenter sweeps — barycenter is a heuristic
/// and can occasionally regress, so we keep the best result rather than
/// returning whatever the last sweep produced.
fn total_crossings(layers: &[Vec<usize>], graph: &DiGraphMap<NodeIndex, ()>) -> usize {
    let mut total = 0usize;
    for i in 0..layers.len().saturating_sub(1) {
        let upper = &layers[i];
        let lower = &layers[i + 1];

        // Position lookup for the lower layer: node id → its index in `lower`.
        let mut pos_lower: HashMap<usize, usize> = HashMap::with_capacity(lower.len());
        for (p, &n) in lower.iter().enumerate() {
            pos_lower.insert(n, p);
        }

        // Walk upper nodes left-to-right; for each, record the lower-layer
        // positions of its outgoing neighbors. Sorting targets within a
        // single source ensures that two edges from the same upper node
        // don't get counted as crossing each other.
        let mut endpoints: Vec<usize> = Vec::new();
        for &u in upper {
            let mut targets: Vec<usize> = graph
                .neighbors_directed(NodeIndex::new(u), petgraph::Outgoing)
                .filter_map(|n| pos_lower.get(&n.index()).copied())
                .collect();
            targets.sort();
            endpoints.extend(targets);
        }

        // Inversions in `endpoints` == crossings between this layer pair.
        total += inversions(&endpoints);
    }
    total
}

// ---------------------------------------------------------------------------
// Barycenter ordering
// ---------------------------------------------------------------------------

/// Reorder one layer by the barycenter (= mean position) of each node's
/// neighbors in an adjacent layer.
///
/// `upward = false` is a "down sweep" step: order layer i by the average
/// position of its predecessors in layer i-1.
/// `upward = true` is an "up sweep" step: use successors in layer i+1.
///
/// Replaces the O(layer_size) `position(...)` lookup the older code did by
/// pre-building a `node → position` map for the neighbor layer; this turns
/// each lookup into O(1).
///
/// Stable sort with `orig_pos` as tiebreak: nodes with no neighbors (and
/// thus no defined barycenter) stay where they were, and ties in barycenter
/// preserve the prior order.
fn reorder_by_barycenter(
    layers: &mut [Vec<usize>],
    layer_idx: usize,
    upward: bool,
    graph: &DiGraphMap<NodeIndex, ()>,
) {
    let neighbor_layer_idx = if upward {
        layer_idx + 1
    } else {
        layer_idx - 1
    };
    let direction = if upward {
        petgraph::Outgoing
    } else {
        petgraph::Incoming
    };

    // O(1) position lookup for the neighbor layer.
    let mut pos: HashMap<usize, usize> = HashMap::with_capacity(layers[neighbor_layer_idx].len());
    for (p, &n) in layers[neighbor_layer_idx].iter().enumerate() {
        pos.insert(n, p);
    }

    let layer = &layers[layer_idx];
    let mut bc: Vec<(usize, usize, f32)> = layer
        .iter()
        .enumerate()
        .map(|(orig_pos, &node)| {
            let positions: Vec<usize> = graph
                .neighbors_directed(NodeIndex::new(node), direction)
                .filter_map(|n| pos.get(&n.index()).copied())
                .collect();
            // Nodes without any neighbor in the reference layer get +∞
            // so they sort to the end; the orig_pos tiebreak keeps their
            // relative order stable.
            let value = if positions.is_empty() {
                f32::INFINITY
            } else {
                positions.iter().sum::<usize>() as f32 / positions.len() as f32
            };
            (node, orig_pos, value)
        })
        .collect();

    // Sort by barycenter; ties (and NaN) fall back to the original
    // position so the sort is stable in spirit.
    bc.sort_by(|a, b| match a.2.partial_cmp(&b.2) {
        Some(std::cmp::Ordering::Equal) | None => a.1.cmp(&b.1),
        Some(o) => o,
    });

    layers[layer_idx] = bc.into_iter().map(|(node, _, _)| node).collect();
}

// ---------------------------------------------------------------------------
// Brandes–Köpf coordinate assignment
//
// The algorithm has four phases:
//
//   (a) Mark "Type 1 conflicts" — non-inner edges that cross inner edges
//       (an inner edge is one whose both endpoints are dummy nodes, i.e.
//       a link in a long-edge chain). These edges are forbidden from
//       carrying alignment in the next phase, which protects long edges
//       from being bent by short edges that try to align across them.
//
//   (b) Vertical alignment, run four times with different sweep
//       directions: each pass produces a partition of nodes into "blocks"
//       (chains where every member should share an x coordinate).
//
//   (c) Horizontal compaction, also run four times: produce one x value
//       per node by greedily packing blocks while respecting the minimum
//       node-to-node spacing within each layer.
//
//   (d) Balance: align the four resulting layouts to a common reference
//       and, per node, average the median two of the four x values.
//
// The four (alignment, compaction) directions are: down/up × left/right.
// Each one finds different "balanced" placements; averaging the median two
// rejects extreme placements caused by adversarial inputs and produces
// the smoothest result.
// ---------------------------------------------------------------------------

/// Phase (a): mark non-inner edges that cross inner edges.
///
/// Implements Algorithm 1 of Brandes & Köpf. For each adjacent layer pair
/// we scan the lower layer left-to-right, tracking the upper-layer
/// position window `(k0, k1]` between consecutive inner segments. Any
/// edge whose upper endpoint falls outside this window crosses (or is
/// otherwise positioned wrong relative to) the inner segment that closes
/// it, so it gets marked.
///
/// Inner edges themselves are never marked — their upper endpoints lie at
/// k1 by construction, which is on the boundary, not outside it.
fn mark_type1_conflicts(
    layers: &[Vec<usize>],
    graph: &DiGraphMap<NodeIndex, ()>,
    pos_in_layer: &HashMap<usize, usize>,
    dummy_ids: &HashSet<usize>,
) -> HashSet<(usize, usize)> {
    let mut marked: HashSet<(usize, usize)> = HashSet::new();
    if layers.len() < 2 {
        return marked;
    }

    // Helper: if `v` is a dummy node with an incoming edge from another
    // dummy in the upper layer (i.e. the lower end of an inner segment),
    // return the upper end's position.
    let incident_inner_upper = |v: usize| -> Option<usize> {
        if !dummy_ids.contains(&v) {
            return None;
        }
        graph
            .neighbors_directed(NodeIndex::new(v), petgraph::Incoming)
            .filter_map(|n| {
                let nu = n.index();
                if dummy_ids.contains(&nu) {
                    pos_in_layer.get(&nu).copied()
                } else {
                    None
                }
            })
            .next()
    };

    for i in 0..layers.len() - 1 {
        let upper = &layers[i];
        let lower = &layers[i + 1];

        // `k0` is the upper-position of the previous inner segment (or -1
        // if none yet). `l` is the index of the next lower-layer node we
        // need to scan. For each new inner segment (or end-of-layer), we
        // process all lower nodes between the previous inner segment and
        // this one, marking edges whose upper endpoints are outside
        // (k0, k1).
        let mut k0: i64 = -1;
        let mut l: usize = 0;
        for l1 in 0..lower.len() {
            let is_last = l1 + 1 == lower.len();
            let inner_pos = incident_inner_upper(lower[l1]);
            if is_last || inner_pos.is_some() {
                // End of current window: either the next inner segment,
                // or the end of the layer (where k1 = upper.len(), past
                // any real position).
                let k1: i64 = inner_pos
                    .map(|p| p as i64)
                    .unwrap_or(upper.len() as i64);
                while l <= l1 {
                    let v = lower[l];
                    for n in graph.neighbors_directed(NodeIndex::new(v), petgraph::Incoming) {
                        let u = n.index();
                        if let Some(&kp) = pos_in_layer.get(&u) {
                            let k = kp as i64;
                            if k <= k0 || k >= k1 {
                                // Inner-only edges (dummy↔dummy) are
                                // structurally protected and never marked.
                                if !(dummy_ids.contains(&u) && dummy_ids.contains(&v)) {
                                    marked.insert((u, v));
                                }
                            }
                        }
                    }
                    l += 1;
                }
                k0 = k1;
            }
        }
    }
    marked
}

/// Phase (b): partition nodes into vertical "blocks" — chains where every
/// member should share the same x coordinate.
///
/// `vertical_down`: if `true`, sweep layers top→bottom and align each node
/// with its **predecessor** (Incoming) median; if `false`, sweep
/// bottom→top and align with the **successor** (Outgoing) median.
///
/// `horizontal_right`: if `true`, walk each layer right→left and prefer
/// the right median when even-numbered. If `false`, walk left→right and
/// prefer the left median.
///
/// Each (vertical, horizontal) combination produces a different
/// partitioning. The caller runs all four; phase (d) averages them.
///
/// Output:
///   * `root[v]` — id of the topmost (or, for upward sweeps, bottommost)
///     node in v's block.
///   * `align[v]` — id of the next node in the cyclic chain along v's
///     block. For a singleton block, `align[v] == v`.
///
/// The `r` sentinel and the median preference together enforce the
/// invariant that within one pass, at most one node aligns with any given
/// upper-layer position. This prevents two nodes in the same layer from
/// claiming alignment to the same parent (which would make them overlap).
fn vertical_alignment(
    layers: &[Vec<usize>],
    graph: &DiGraphMap<NodeIndex, ()>,
    marked: &HashSet<(usize, usize)>,
    vertical_down: bool,
    horizontal_right: bool,
    pos_in_layer: &HashMap<usize, usize>,
) -> (HashMap<usize, usize>, HashMap<usize, usize>) {
    // Each node starts as its own singleton block.
    let mut root: HashMap<usize, usize> = HashMap::new();
    let mut align: HashMap<usize, usize> = HashMap::new();
    for layer in layers {
        for &v in layer {
            root.insert(v, v);
            align.insert(v, v);
        }
    }

    // Layer iteration order:
    //   down: layers 1..L (we look at the previous layer for predecessors)
    //   up:   layers (L-2)..0 (we look at the next layer for successors)
    let layer_indices: Vec<usize> = if vertical_down {
        (1..layers.len()).collect()
    } else {
        (0..layers.len().saturating_sub(1)).rev().collect()
    };

    for &i in &layer_indices {
        let layer = &layers[i];
        if layer.is_empty() {
            continue;
        }
        let neighbor_dir = if vertical_down {
            petgraph::Incoming
        } else {
            petgraph::Outgoing
        };

        // Within-layer iteration order — left-to-right or right-to-left.
        let inner_indices: Vec<usize> = if horizontal_right {
            (0..layer.len()).rev().collect()
        } else {
            (0..layer.len()).collect()
        };

        // `r` tracks the most recently consumed neighbor-layer position.
        // For a left-leaning sweep we accept any neighbor whose position
        // is strictly greater than `r` (so each new alignment moves
        // rightward); for a right-leaning sweep, strictly less.
        let mut r: i64 = if horizontal_right { i64::MAX } else { -1 };

        for k in inner_indices {
            let v = layer[k];

            // Sort the candidate neighbors by their position in the
            // adjacent layer; we'll align with one of the medians.
            let mut ups: Vec<usize> = graph
                .neighbors_directed(NodeIndex::new(v), neighbor_dir)
                .map(|n| n.index())
                .filter(|n| pos_in_layer.contains_key(n))
                .collect();
            ups.sort_by_key(|n| pos_in_layer[n]);

            if ups.is_empty() {
                continue;
            }
            let d = ups.len();
            // Even-degree nodes have two candidate medians; odd-degree
            // have one. The order in which we try them determines the
            // tie-break (left vs right preference).
            let mut medians: Vec<usize> = if d % 2 == 0 {
                vec![d / 2 - 1, d / 2]
            } else {
                vec![d / 2]
            };
            if horizontal_right {
                medians.reverse();
            }

            for m in medians {
                // Already aligned this node — done.
                if align[&v] != v {
                    break;
                }
                let u = ups[m];
                // Edge orientation in the marked set is always (upper,
                // lower) regardless of sweep direction.
                let edge = if vertical_down { (u, v) } else { (v, u) };
                if marked.contains(&edge) {
                    continue;
                }
                let u_pos = pos_in_layer[&u] as i64;
                let aligned_ok = if horizontal_right {
                    r > u_pos
                } else {
                    r < u_pos
                };
                if aligned_ok {
                    // Stitch v onto u's block. The block is a cyclic
                    // chain via `align`; `root` points to a canonical
                    // representative (used by horizontal compaction).
                    align.insert(u, v);
                    let r_u = root[&u];
                    root.insert(v, r_u);
                    align.insert(v, r_u);
                    r = u_pos;
                }
            }
        }
    }

    (root, align)
}

/// Working state for `place_block`. Implementing this as a struct (rather
/// than passing many `&mut` arguments) keeps the recursion in
/// `place_block` readable.
///
/// Maintained invariants:
/// * `sink[v]` is the canonical "sink" of the *class* containing v
///   (transitive closure of "shares-a-layer-edge with another block").
///   Initialized to v.
/// * `shift[s]` is the accumulated horizontal shift to apply to all
///   blocks whose sink is `s`. For a left-leaning compaction it's a
///   lower bound (`min`-folded) — typically negative — that ends up
///   pushing the class leftward. For a right-leaning compaction it's an
///   upper bound (`max`-folded), typically positive.
/// * `x[v]` is the tentative x of v's block-root, before applying class
///   shifts. `None` until the block has been placed.
struct CompactionState<'a> {
    layers: &'a [Vec<usize>],
    pos_in_layer: &'a HashMap<usize, usize>,
    layer_of: HashMap<usize, usize>,
    widths: &'a HashMap<usize, i32>,
    sink: HashMap<usize, usize>,
    shift: HashMap<usize, f32>,
    x: HashMap<usize, Option<f32>>,
    root: &'a HashMap<usize, usize>,
    align: &'a HashMap<usize, usize>,
    horizontal_right: bool,
}

impl<'a> CompactionState<'a> {
    /// "Predecessor in layer" for the current sweep direction:
    /// the node immediately to the left (left-leaning) or right
    /// (right-leaning) of `w` within the same layer.
    fn pred_in_layer(&self, w: usize) -> Option<usize> {
        let li = self.layer_of[&w];
        let pi = self.pos_in_layer[&w];
        if self.horizontal_right {
            if pi + 1 < self.layers[li].len() {
                Some(self.layers[li][pi + 1])
            } else {
                None
            }
        } else if pi > 0 {
            Some(self.layers[li][pi - 1])
        } else {
            None
        }
    }

    /// Minimum spacing between two nodes in the same layer, taken as
    /// half the sum of their widths plus a 1-cell gap.
    fn delta(&self, w: usize, p: usize) -> f32 {
        (self.widths[&w] as f32 + self.widths[&p] as f32) / 2.0 + 1.0
    }

    /// Place the block containing `v` (Algorithm 3 of Brandes & Köpf).
    ///
    /// Walks the cyclic `align` chain starting at v. For each member w,
    /// looks at w's same-layer "predecessor" p; if p is in a different
    /// already-placed block, either:
    ///   * (same class) push v's x out so v doesn't overlap u; or
    ///   * (different class) record a shift on the OTHER class so its
    ///     sink can be moved later to maintain min spacing.
    ///
    /// Recursive — the call graph is a DAG (each block is placed at most
    /// once thanks to the `is_some()` short-circuit) so stack depth is
    /// bounded by the number of blocks.
    fn place_block(&mut self, v: usize) {
        if self.x[&v].is_some() {
            return;
        }
        self.x.insert(v, Some(0.0));
        let mut w = v;
        loop {
            if let Some(p) = self.pred_in_layer(w) {
                // u is the block-root of p — i.e. the block to our left
                // (or right) in the layer.
                let u = self.root[&p];
                self.place_block(u);

                // First time we discover a left-neighbor block, we
                // adopt its sink as our class sink.
                if self.sink[&v] == v {
                    let su = self.sink[&u];
                    self.sink.insert(v, su);
                }
                let sv = self.sink[&v];
                let su = self.sink[&u];
                let xv = self.x[&v].unwrap();
                let xu = self.x[&u].unwrap();
                let d = self.delta(w, p);
                if sv != su {
                    // Different classes — record a shift on u's class
                    // so it can be moved later when its sink is placed.
                    // Direction-aware: left-lean records a lower bound,
                    // right-lean records an upper bound.
                    let cur = self.shift[&su];
                    let new = if self.horizontal_right {
                        cur.max(xv - xu + d)
                    } else {
                        cur.min(xv - xu - d)
                    };
                    self.shift.insert(su, new);
                } else {
                    // Same class — push v's x to maintain min spacing
                    // with u directly. Left-lean pushes right (max);
                    // right-lean pushes left (min).
                    let new_xv = if self.horizontal_right {
                        xv.min(xu - d)
                    } else {
                        xv.max(xu + d)
                    };
                    self.x.insert(v, Some(new_xv));
                }
            }
            w = self.align[&w];
            if w == v {
                break;
            }
        }
    }
}

/// Phase (c): assign one x value per node given a `(root, align)` block
/// partition.
///
/// Two passes:
///   1. Walk every block-root and call `place_block`, which fills in
///      tentative x values and accumulates per-class shifts.
///   2. Resolve final x: each node inherits x from its block-root,
///      plus the accumulated shift for its class sink.
///
/// `init_shift` is the identity element for the shift fold: ∞ for
/// left-lean (we'll `min`-fold towards a more negative value), -∞ for
/// right-lean (we'll `max`-fold towards a more positive value).
fn horizontal_compaction(
    layers: &[Vec<usize>],
    root: &HashMap<usize, usize>,
    align: &HashMap<usize, usize>,
    pos_in_layer: &HashMap<usize, usize>,
    widths: &HashMap<usize, i32>,
    horizontal_right: bool,
) -> HashMap<usize, f32> {
    let all_nodes: Vec<usize> = layers.iter().flatten().copied().collect();
    let layer_of: HashMap<usize, usize> = layers
        .iter()
        .enumerate()
        .flat_map(|(li, l)| l.iter().map(move |&n| (n, li)))
        .collect();

    let init_shift = if horizontal_right {
        f32::NEG_INFINITY
    } else {
        f32::INFINITY
    };
    let mut state = CompactionState {
        layers,
        pos_in_layer,
        layer_of,
        widths,
        // Each node initially in its own class; sinks settle as
        // `place_block` discovers neighboring blocks.
        sink: all_nodes.iter().map(|&v| (v, v)).collect(),
        shift: all_nodes.iter().map(|&v| (v, init_shift)).collect(),
        x: all_nodes.iter().map(|&v| (v, None)).collect(),
        root,
        align,
        horizontal_right,
    };

    // Pass 1: place each block (driven by its root).
    for &v in &all_nodes {
        if root[&v] == v {
            state.place_block(v);
        }
    }

    // Pass 2: realize final x — block-root x, plus class shift if any
    // was recorded. The "shifted" check rejects the identity sentinel
    // (no shift recorded for that class).
    let mut result: HashMap<usize, f32> = HashMap::with_capacity(all_nodes.len());
    for &v in &all_nodes {
        let r = root[&v];
        let xr = state.x[&r].unwrap_or(0.0);
        let s = state.shift[&state.sink[&r]];
        let mut x = xr;
        let shifted = if horizontal_right {
            s > f32::NEG_INFINITY
        } else {
            s < f32::INFINITY
        };
        if shifted {
            x += s;
        }
        result.insert(v, x);
    }
    result
}

/// Drive phases (a)–(d) of Brandes–Köpf with pre-computed widths/heights.
///
/// This is the dimension-agnostic core of `brandes_koepf_coordinates` —
/// taking widths and heights as plain maps lets the unit tests exercise
/// the algorithm without constructing a `CoreGraph` (which would require
/// a Python interpreter).
fn brandes_koepf_with_dimensions(
    layers: &Vec<Vec<usize>>,
    graph: &DiGraphMap<NodeIndex, ()>,
    widths: &HashMap<usize, i32>,
    heights: &HashMap<usize, i32>,
    dummy_ids: &HashSet<usize>,
) -> HashMap<usize, Point> {
    // Index lookup: node id → its position within its layer. Used by
    // every BK sub-routine.
    let mut pos_in_layer: HashMap<usize, usize> = HashMap::new();
    for layer in layers {
        for (pi, &node) in layer.iter().enumerate() {
            pos_in_layer.insert(node, pi);
        }
    }

    // Layers stack vertically with spacing = max height in the layer + 1
    // (one cell of breathing room between layers).
    let heights_per_layer: Vec<i32> = layers
        .iter()
        .map(|layer| {
            layer
                .iter()
                .map(|n| heights.get(n).copied().unwrap_or(1))
                .max()
                .unwrap_or(0)
        })
        .collect();

    // Phase (a).
    let marked = mark_type1_conflicts(layers, graph, &pos_in_layer, dummy_ids);

    // Phases (b)+(c) for each of the four sweep directions.
    // Index convention: 0=down-left, 1=down-right, 2=up-left, 3=up-right.
    // `balance` relies on this layout.
    let mut xs: [HashMap<usize, f32>; 4] = [
        HashMap::new(),
        HashMap::new(),
        HashMap::new(),
        HashMap::new(),
    ];
    let configs: [(bool, bool); 4] = [
        (true, false),  // down-left
        (true, true),   // down-right
        (false, false), // up-left
        (false, true),  // up-right
    ];
    for (idx, &(vd, hr)) in configs.iter().enumerate() {
        let (root, align) = vertical_alignment(layers, graph, &marked, vd, hr, &pos_in_layer);
        xs[idx] = horizontal_compaction(layers, &root, &align, &pos_in_layer, widths, hr);
    }

    // Phase (d): align the four layouts and average median-of-four.
    let final_x = balance(&xs);

    // Y-positions: cumulative layer heights with a 1-cell gap between layers.
    let mut layer_y: Vec<i32> = Vec::with_capacity(layers.len());
    let mut y_acc: i32 = 0;
    for h in &heights_per_layer {
        layer_y.push(y_acc);
        y_acc += h + 1;
    }

    // Translate x so the leftmost node sits at x=0, then round to integer
    // grid coordinates.
    let min_x = final_x.values().cloned().fold(f32::INFINITY, f32::min);
    let min_x = if min_x.is_finite() { min_x } else { 0.0 };
    let mut positions: HashMap<usize, Point> = HashMap::new();
    for (li, layer) in layers.iter().enumerate() {
        for &node in layer {
            let x_raw = final_x.get(&node).copied().unwrap_or(0.0);
            let x = (x_raw - min_x).round() as i32;
            let y = layer_y[li];
            positions.insert(node, Point::new(x, y));
        }
    }
    positions
}

/// Phase (d): translate the four layouts to a common reference, then for
/// each node take the average of the median two of the four x values.
///
/// The four layouts have different absolute coordinate systems:
///   * left-leaning (indices 0, 2) start at their *leftmost* node;
///   * right-leaning (1, 3) end at their *rightmost* node.
///
/// We pick a shared reference: the smallest leftmost (`common_min`) for
/// the left-leaning ones and the largest rightmost (`common_max`) for
/// the right-leaning ones. Each layout is shifted so its anchor sits on
/// the shared reference before we read off its node x's.
///
/// Median-of-four (vs. plain mean) is the paper's key trick for
/// robustness — extreme placements that only one of the four directions
/// produced get rejected.
fn balance(xs: &[HashMap<usize, f32>; 4]) -> HashMap<usize, f32> {
    // Sweep-direction → leaning:
    //   0: down-left,  1: down-right,  2: up-left,  3: up-right
    let left_indices = [0usize, 2];
    let right_indices = [1usize, 3];

    // Shared anchors across the two leanings.
    let common_min = left_indices
        .iter()
        .map(|&i| {
            xs[i]
                .values()
                .cloned()
                .fold(f32::INFINITY, f32::min)
        })
        .fold(f32::INFINITY, f32::min);
    let common_max = right_indices
        .iter()
        .map(|&i| {
            xs[i]
                .values()
                .cloned()
                .fold(f32::NEG_INFINITY, f32::max)
        })
        .fold(f32::NEG_INFINITY, f32::max);

    // Per-layout shift to align with the shared anchor.
    let mut shifts = [0.0f32; 4];
    for &i in &left_indices {
        let cur_min = xs[i].values().cloned().fold(f32::INFINITY, f32::min);
        shifts[i] = if cur_min.is_finite() {
            common_min - cur_min
        } else {
            0.0
        };
    }
    for &i in &right_indices {
        let cur_max = xs[i].values().cloned().fold(f32::NEG_INFINITY, f32::max);
        shifts[i] = if cur_max.is_finite() {
            common_max - cur_max
        } else {
            0.0
        };
    }

    // For each node: shift each layout's contribution, sort the four,
    // average the middle two.
    let nodes: Vec<usize> = xs[0].keys().copied().collect();
    let mut result: HashMap<usize, f32> = HashMap::with_capacity(nodes.len());
    for v in nodes {
        let mut vals = [
            xs[0][&v] + shifts[0],
            xs[1][&v] + shifts[1],
            xs[2][&v] + shifts[2],
            xs[3][&v] + shifts[3],
        ];
        vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let avg = (vals[1] + vals[2]) / 2.0;
        result.insert(v, avg);
    }
    result
}

impl SugiyamaLayout {
    /// Bridge from the Sugiyama pipeline (which knows about `CoreGraph`
    /// and `LayoutDirection`) into the dimension-agnostic
    /// `brandes_koepf_with_dimensions`.
    ///
    /// Translates each node's `Size` into a single "width along the
    /// layout direction" and "height along the layout direction" — the
    /// internal BK code is direction-blind. Dummy nodes get unit
    /// dimensions; we also clamp real widths/heights to ≥1 to keep
    /// minimum-spacing math from collapsing.
    fn brandes_koepf_coordinates(
        &self,
        layers: &Vec<Vec<usize>>,
        graph: &DiGraphMap<NodeIndex, ()>,
        core_graph: &CoreGraph,
        dummy_ids: &HashSet<usize>,
    ) -> HashMap<usize, Point> {
        let widths: HashMap<usize, i32> = layers
            .iter()
            .flatten()
            .map(|&n| {
                let w = if dummy_ids.contains(&n) {
                    DUMMY_WIDTH
                } else {
                    let size = core_graph
                        .size_by_index(NodeIndex::new(n))
                        .cloned()
                        .unwrap_or(Size::new(0, 0));
                    width_in_direction(self.direction, &size)
                };
                (n, w.max(1))
            })
            .collect();

        let heights: HashMap<usize, i32> = layers
            .iter()
            .flatten()
            .map(|&n| {
                let h = if dummy_ids.contains(&n) {
                    DUMMY_HEIGHT
                } else {
                    let size = core_graph
                        .size_by_index(NodeIndex::new(n))
                        .cloned()
                        .unwrap_or(Size::new(0, 0));
                    height_in_direction(self.direction, &size)
                };
                (n, h.max(1))
            })
            .collect();

        brandes_koepf_with_dimensions(layers, graph, &widths, &heights, dummy_ids)
    }

    /// Phase 4: alternating barycenter sweeps to reduce edge crossings.
    ///
    /// Even sweeps go top→bottom (each layer ordered by its predecessors);
    /// odd sweeps go bottom→top (each layer ordered by its successors).
    /// Two passes per "round" lets information propagate in both
    /// directions, which matters on graphs where the ideal ordering of
    /// layer i depends on layers both above *and* below it.
    ///
    /// We cap iterations at `MAX_BARYCENTER_SWEEPS` and stop early if a
    /// full round leaves the permutation unchanged. We also remember the
    /// best-by-crossing-count permutation seen, since barycenter is a
    /// heuristic and can occasionally regress on later sweeps.
    fn barycenter_ordering(
        &self,
        graph: &DiGraphMap<NodeIndex, ()>,
        layers: Vec<Vec<usize>>,
    ) -> Vec<Vec<usize>> {
        if layers.len() < 2 {
            return layers;
        }

        let mut current = layers;
        let mut best = current.clone();
        let mut best_crossings = total_crossings(&current, graph);

        for sweep in 0..MAX_BARYCENTER_SWEEPS {
            let before = current.clone();
            if sweep % 2 == 0 {
                // Down sweep: each layer ordered by predecessor barycenter.
                for i in 1..current.len() {
                    reorder_by_barycenter(&mut current, i, false, graph);
                }
            } else {
                // Up sweep: each layer ordered by successor barycenter.
                for i in (0..current.len() - 1).rev() {
                    reorder_by_barycenter(&mut current, i, true, graph);
                }
            }
            let cr = total_crossings(&current, graph);
            if cr < best_crossings {
                best_crossings = cr;
                best = current.clone();
            }
            // No change this sweep → no more progress to be made.
            if current == before {
                break;
            }
        }

        best
    }

    /// Phase 1: break cycles by reversing a feedback arc set.
    ///
    /// `greedy_feedback_arc_set` returns a small set of edges whose
    /// removal makes the graph acyclic. For each such edge we *reverse*
    /// it (rather than remove) so the rest of the topology is preserved
    /// — the layered layout still sees an edge between the two nodes,
    /// just pointing the other way. Self-loops are dropped without
    /// reversal.
    fn remove_cycles(
        &self,
        tgt_graph: &mut DiGraphMap<NodeIndex, ()>,
        src_graph: &DiGraphMap<NodeIndex, ()>,
    ) {
        let edges_to_remove = greedy_feedback_arc_set(src_graph);
        for edge in edges_to_remove {
            tgt_graph.remove_edge(edge.0, edge.1);
            if edge.0 != edge.1 {
                tgt_graph.add_edge(edge.1, edge.0, ());
            }
        }
    }

    /// Phase 2a: layer each weakly-connected component independently.
    ///
    /// We use union-find to label connected components, build a separate
    /// `DiGraphMap` for each, then layer them via longest-path. The
    /// per-component layer indices are merged back into a single global
    /// `layer_map` — components share the same coordinate space, so
    /// "layer 0" of one component lines up with "layer 0" of another.
    fn layer_disconnected_components(
        &self,
        graph: &DiGraphMap<NodeIndex, ()>,
    ) -> HashMap<usize, usize> {
        let mut layers = HashMap::new();
        let mut vertex_sets = UnionFind::new(graph.node_bound());

        // Union-find pass: every edge unions its two endpoints. The
        // resulting equivalence classes are the weakly-connected
        // components.
        for edge in graph.edge_references() {
            let (a, b) = (edge.0, edge.1);
            vertex_sets.union(graph.to_index(a), graph.to_index(b));
        }

        let labels = vertex_sets.into_labeling();

        // Build one DiGraphMap per component label. Node-only iteration
        // first so isolated nodes (no edges) still get registered.
        let mut subgraphs = HashMap::<usize, DiGraphMap<NodeIndex, ()>>::new();

        for node in graph.nodes() {
            subgraphs
                .entry(labels[graph.to_index(node)])
                .or_insert_with(DiGraphMap::new)
                .add_node(node);
        }

        for edge in graph.edge_references() {
            let (a, b) = (edge.0, edge.1);
            let a_label = labels[graph.to_index(a)];
            let b_label = labels[graph.to_index(b)];

            // Two endpoints in the same class always — but check anyway
            // for defensiveness.
            if a_label == b_label {
                subgraphs.get_mut(&a_label).unwrap().add_edge(a, b, ());
            }
        }

        // Layer each component, then merge the per-component layer maps.
        // The mapping `subgraph.from_index(node) → graph.to_index(...)`
        // translates the component-local index back to the global one.
        for (_, subgraph) in subgraphs {
            let component_layers = self.longest_path_layering(&subgraph);
            layers.extend(
                component_layers
                    .into_iter()
                    .map(|(node, layer)| (graph.to_index(subgraph.from_index(node)), layer)),
            );
        }

        layers
    }

    /// Phase 2b: assign each node the longest path from any source.
    ///
    /// This is the standard "longest path" layering: source nodes (no
    /// incoming edges) go in layer 0, every other node sits one layer
    /// below the maximum of its predecessors. Walking in topological
    /// order ensures every predecessor's layer is known by the time we
    /// reach the node itself.
    ///
    /// Compared to other layering choices (Coffman-Graham, network
    /// simplex, etc.), longest-path is O(V+E) and tends to produce a
    /// somewhat tall layout with empty positions at lower layers — but
    /// the dummy-node insertion that follows turns those empties into
    /// useful anchor points for long edges.
    fn longest_path_layering(&self, graph: &DiGraphMap<NodeIndex, ()>) -> HashMap<usize, usize> {
        let mut layers = HashMap::new();
        let mut topo = Topo::new(graph);

        if graph.node_count() == 0 {
            return layers;
        }

        if graph.node_count() == 1 {
            layers.insert(graph.to_index(graph.nodes().next().unwrap()), 0);
            return layers;
        }

        // Seed layer 0 with all source nodes.
        for node in graph.nodes().filter(|n| {
            graph
                .neighbors_directed(*n, petgraph::Incoming)
                .next()
                .is_none()
        }) {
            layers.insert(graph.to_index(node), 0);
        }

        // Topological walk: each node's layer = 1 + max(predecessor layer).
        while let Some(node_idx) = topo.next(graph) {
            let node_layer = graph
                .edges_directed(node_idx, petgraph::Incoming)
                .filter_map(|edge| layers.get(&graph.to_index(edge.0)).map(|l| l + 1))
                .max()
                .unwrap_or(0);

            layers.insert(graph.to_index(node_idx), node_layer);
        }

        layers
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn build_graph(edges: &[(usize, usize)], extra_nodes: &[usize]) -> DiGraphMap<NodeIndex, ()> {
        let mut g: DiGraphMap<NodeIndex, ()> = DiGraphMap::new();
        for &(a, b) in edges {
            g.add_edge(NodeIndex::new(a), NodeIndex::new(b), ());
        }
        for &n in extra_nodes {
            g.add_node(NodeIndex::new(n));
        }
        g
    }

    #[test]
    fn dummy_nodes_inserted_for_multi_layer_edges() {
        let mut g = build_graph(&[(0, 1), (1, 2), (0, 2)], &[]);
        let mut layer_map: HashMap<usize, usize> = HashMap::new();
        layer_map.insert(0, 0);
        layer_map.insert(1, 1);
        layer_map.insert(2, 2);
        let dummies = insert_dummy_nodes(&mut g, &mut layer_map);
        assert_eq!(dummies.len(), 1);
        let dummy_id = *dummies.iter().next().unwrap();
        assert_eq!(layer_map[&dummy_id], 1);
        assert!(!g.contains_edge(NodeIndex::new(0), NodeIndex::new(2)));
        assert!(g.contains_edge(NodeIndex::new(0), NodeIndex::new(dummy_id)));
        assert!(g.contains_edge(NodeIndex::new(dummy_id), NodeIndex::new(2)));
    }

    #[test]
    fn dummy_nodes_not_inserted_for_adjacent_edges() {
        let mut g = build_graph(&[(0, 1), (1, 2)], &[]);
        let mut layer_map: HashMap<usize, usize> = HashMap::new();
        layer_map.insert(0, 0);
        layer_map.insert(1, 1);
        layer_map.insert(2, 2);
        let dummies = insert_dummy_nodes(&mut g, &mut layer_map);
        assert!(dummies.is_empty());
    }

    #[test]
    fn barycenter_reduces_crossings() {
        // Two layers, four edges, initial ordering produces crossings.
        // Upper: 0, 1   Lower: 2, 3   Edges: 0->3, 1->2 (cross).
        let g = build_graph(&[(0, 3), (1, 2)], &[]);
        let layers = vec![vec![0usize, 1], vec![2usize, 3]];
        let cross_before = total_crossings(&layers, &g);
        assert!(cross_before > 0);

        let layout = SugiyamaLayout {
            direction: LayoutDirection::TopDown,
        };
        let result = layout.barycenter_ordering(&g, layers);
        let cross_after = total_crossings(&result, &g);
        assert!(cross_after < cross_before);
        assert_eq!(cross_after, 0);
    }

    #[test]
    fn barycenter_stable_on_optimal_input() {
        let g = build_graph(&[(0, 1), (1, 2)], &[]);
        let layers = vec![vec![0usize], vec![1usize], vec![2usize]];
        let layout = SugiyamaLayout {
            direction: LayoutDirection::TopDown,
        };
        let result = layout.barycenter_ordering(&g, layers.clone());
        assert_eq!(result, layers);
    }

    fn unit_dimensions(layers: &[Vec<usize>]) -> (HashMap<usize, i32>, HashMap<usize, i32>) {
        let mut widths = HashMap::new();
        let mut heights = HashMap::new();
        for &n in layers.iter().flatten() {
            widths.insert(n, 1);
            heights.insert(n, 1);
        }
        (widths, heights)
    }

    #[test]
    fn brandes_koepf_aligns_chain() {
        let g = build_graph(&[(0, 1), (1, 2), (2, 3)], &[]);
        let layers = vec![vec![0usize], vec![1usize], vec![2usize], vec![3usize]];
        let (widths, heights) = unit_dimensions(&layers);
        let dummies: HashSet<usize> = HashSet::new();
        let positions = brandes_koepf_with_dimensions(&layers, &g, &widths, &heights, &dummies);
        let xs: Vec<i32> = (0..4).map(|n| positions[&n].x).collect();
        assert!(
            xs.iter().all(|&x| x == xs[0]),
            "chain nodes should share x: {:?}",
            xs
        );
    }

    #[test]
    fn brandes_koepf_no_overlap_in_layer() {
        // Diamond: 0 -> 1, 0 -> 2, 1 -> 3, 2 -> 3
        let g = build_graph(&[(0, 1), (0, 2), (1, 3), (2, 3)], &[]);
        let layers = vec![vec![0usize], vec![1usize, 2], vec![3usize]];
        let mut widths = HashMap::new();
        let mut heights = HashMap::new();
        for &n in layers.iter().flatten() {
            widths.insert(n, 2);
            heights.insert(n, 1);
        }
        let dummies: HashSet<usize> = HashSet::new();
        let positions = brandes_koepf_with_dimensions(&layers, &g, &widths, &heights, &dummies);

        let mut by_y: HashMap<i32, Vec<(i32, usize)>> = HashMap::new();
        for (n, p) in &positions {
            by_y.entry(p.y).or_default().push((p.x, *n));
        }
        for entries in by_y.values_mut() {
            entries.sort();
            for w in entries.windows(2) {
                let gap = w[1].0 - w[0].0;
                let min_gap = (widths[&w[0].1] + widths[&w[1].1]) / 2 + 1;
                assert!(
                    gap >= min_gap,
                    "overlap in layer: nodes {:?} at xs {:?}, gap {} < min {}",
                    entries.iter().map(|(_, n)| n).collect::<Vec<_>>(),
                    entries.iter().map(|(x, _)| x).collect::<Vec<_>>(),
                    gap,
                    min_gap
                );
            }
        }
    }

    #[test]
    fn brandes_koepf_long_edge_with_dummies() {
        // 0 -> 3 spans 3 layers; after dummy insertion, the chain 0 -> d -> d -> 3
        // should produce equal x for all chain members.
        let mut g = build_graph(&[(0, 1), (1, 2), (2, 3), (0, 3)], &[]);
        let mut layer_map: HashMap<usize, usize> = HashMap::new();
        layer_map.insert(0, 0);
        layer_map.insert(1, 1);
        layer_map.insert(2, 2);
        layer_map.insert(3, 3);
        let dummies = insert_dummy_nodes(&mut g, &mut layer_map);
        assert_eq!(dummies.len(), 2, "expected 2 dummies for layer-3-spanning edge");

        let layers = layers_from_layer_map(&layer_map);
        let mut widths = HashMap::new();
        let mut heights = HashMap::new();
        for &n in layers.iter().flatten() {
            widths.insert(n, 1);
            heights.insert(n, 1);
        }

        let layout = SugiyamaLayout {
            direction: LayoutDirection::TopDown,
        };
        let ordered = layout.barycenter_ordering(&g, layers);
        let positions = brandes_koepf_with_dimensions(&ordered, &g, &widths, &heights, &dummies);
        // Real nodes 0,1,2,3 must all be present.
        for n in 0..=3 {
            assert!(positions.contains_key(&n), "missing real node {}", n);
        }
    }
}
