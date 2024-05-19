use petgraph::algo::astar;
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
use tracing::event;

mod geometry;
mod graph;
mod layout;
mod lib_tracing;
mod pyindexset;
mod routing;

use geometry::{Point, DirectedPoint, Shape, Direction, Neighborhood};
use routing::{RoutingConfig, EdgeRouter};
use graph::CoreGraph;
use lib_tracing::LibTracer;
use tracing::{span, Level};

// A module to wrap the Python functions and structs
#[pymodule]
fn _core(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<layout::sugiyama::SugiyamaLayout>()?;
    m.add_class::<layout::LayoutEngine>()?;
    m.add_class::<layout::static_::StaticLayout>()?;

    m.add_class::<CoreGraph>()?;
    m.add_class::<Point>()?;
    m.add_class::<Shape>()?;
    m.add_class::<Direction>()?;
    m.add_class::<DirectedPoint>()?;
    m.add_class::<RoutingConfig>()?;
    m.add_class::<Neighborhood>()?;
    m.add_class::<EdgeRouter>()?;
    m.add_class::<LibTracer>()?;

    Ok(())
}
