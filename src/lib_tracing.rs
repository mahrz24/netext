use pyo3::prelude::*;
use tracing::level_filters::LevelFilter;
use tracing_subscriber::{field::debug, filter::{self, Filtered}, fmt::{format::{DefaultFields, FmtSpan, Format, Pretty}, Layer}, layer::Layered, prelude::*, Registry, };
use std::{fs::File, sync::Arc};

#[pyclass]
pub struct LibTracer {

}

#[pymethods]
impl LibTracer {
    #[new]
    pub fn new() -> Self {
        tracing_subscriber::fmt().compact().with_span_events(FmtSpan::NEW | FmtSpan::CLOSE).init();
        Self {}
    }
}
