use pyo3::prelude::*;

mod geometry;
mod graph;
mod layout;
mod pyindexset;
mod routing;

use geometry::{DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point, RectangularNode, Size};
use routing::{RoutingConfig, EdgeRouter};
use graph::CoreGraph;

// A module to wrap the Python functions and structs
#[pymodule]
fn _core(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<layout::sugiyama::SugiyamaLayout>()?;
    m.add_class::<layout::LayoutEngine>()?;
    m.add_class::<layout::static_::StaticLayout>()?;
    m.add_class::<layout::sugiyama::LayoutDirection>()?;
    m.add_class::<layout::force_directed::ForceDirectedLayout>()?;

    m.add_class::<CoreGraph>()?;
    m.add_class::<Point>()?;
    m.add_class::<Size>()?;
    m.add_class::<PlacedRectangularNode>()?;
    m.add_class::<RectangularNode>()?;
    m.add_class::<Direction>()?;
    m.add_class::<DirectedPoint>()?;
    m.add_class::<RoutingConfig>()?;
    m.add_class::<Neighborhood>()?;
    m.add_class::<EdgeRouter>()?;
    m.add_class::<LibTracer>()?;

    Ok(())
}
