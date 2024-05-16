use pyo3::prelude::*;
use tracing::level_filters::LevelFilter;
use tracing_subscriber::{filter::{self, Filtered}, fmt::{format::{DefaultFields, Format, Pretty}, Layer}, layer::Layered, prelude::*, Registry};
use std::{fs::File, sync::Arc};

#[pyclass]
pub struct LibTracer {
    guard: Layered<Layered<Layer<Registry, DefaultFields, Format, Arc<File>>, Filtered<Layer<Registry, Pretty, Format<Pretty>>, LevelFilter, Registry>, Registry>, Registry>
}

#[pymethods]
impl LibTracer {
    #[new]
    pub fn new() -> Self {
        let stdout_log = tracing_subscriber::fmt::layer().pretty();

        // A layer that logs events to a file.
        let file = File::create("debug.log");
        let file = match file {
            Ok(file) => file,
            Err(error) => panic!("Error: {:?}", error),
        };
        let debug_log = tracing_subscriber::fmt::layer().with_writer(Arc::new(file));

        let guard = tracing_subscriber::registry().with(
            stdout_log
                // Add an `INFO` filter to the stdout logging layer
                .with_filter(filter::LevelFilter::INFO)
                // Combine the filtered `stdout_log` layer with the
                // `debug_log` layer, producing a new `Layered` layer.
                .and_then(debug_log)
        );
        Self {guard}
    }
}
