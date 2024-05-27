use pyo3::prelude::*;

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

use crate::geometry::NodeShape;

// A module to wrap the Python functions and structs
#[pymodule]
fn _core(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<layout::sugiyama::SugiyamaLayout>()?;
    m.add_class::<layout::LayoutEngine>()?;
    m.add_class::<layout::static_::StaticLayout>()?;

    m.add_class::<CoreGraph>()?;
    m.add_class::<Point>()?;
    m.add_class::<NodeShape>()?;
    m.add_class::<Direction>()?;
    m.add_class::<DirectedPoint>()?;
    m.add_class::<RoutingConfig>()?;
    m.add_class::<Neighborhood>()?;
    m.add_class::<EdgeRouter>()?;
    m.add_class::<LibTracer>()?;

    Ok(())
}
