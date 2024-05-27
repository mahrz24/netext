use pyo3::prelude::*;
use tracing_flame::{FlameLayer, FlushGuard};
use std::{fs::File, io::BufWriter};
use tracing_subscriber::{
    fmt::{
        self, format::{FmtSpan}
    },
    prelude::*,
    Registry,
};

#[pyclass]
pub struct LibTracer {
    _guard: FlushGuard<BufWriter<File>>
}

#[pymethods]
impl LibTracer {
    #[new]
    pub fn new() -> Self {
        let fmt_layer = fmt::Layer::default()
            .compact()
            .with_span_events(FmtSpan::ENTER | FmtSpan::EXIT | FmtSpan::CLOSE);

        let (flame_layer, _guard) = FlameLayer::with_file("./tracing.folded").unwrap();

        let subscriber = Registry::default().with(fmt_layer).with(flame_layer);

        tracing::subscriber::set_global_default(subscriber).expect("Could not set global default");

        Self { _guard }
    }
}
