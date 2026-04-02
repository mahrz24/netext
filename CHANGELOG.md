<a id='changelog-0.4.1'></a>
# v0.4.1 — 02.04.2026

## Fixed

- Textual widget: setting graph attributes via `nx.set_node_attributes` / `nx.set_edge_attributes` on `GraphView.graph` no longer silently ignored. The `graph` setter now rebuilds the internal `ConsoleGraph` so changes are rendered.
- Textual widget: `_reset_console_graph` referenced undefined `self._zoom`; changed to `self.zoom` (the Textual reactive) so it works even when zoom has not been changed from the initial value.

## Added

- `GraphView.sync_graph()` method to rebuild the widget after in-place mutations to the underlying networkx graph.

<a id='changelog-0.4.0'></a>
# Routing & Architecture v0.4.0 — 27.03.2026

## Changed

- Completely rewritten edge routing engine in Rust using bucketed A* with node avoidance and edge decongestion.
    - Edge routing grid now inserts more intermediate lines between coordinates: the large-gap threshold is lowered from 6 to 5 units, midpoint is always included, and uniform fill (MIN_SPACING=4, up to 8 extra) kicks in for larger gaps. This provides more routing channels and reduces edge overlap.
    - Grid boundary padding increased from 3 to 7 units (3 routing channels), and boundaries are now included in the coordinate set before intermediate line generation. Edges routing around the outside of the graph now have proper routing channels in the padding area instead of just bare boundary lines.
    - Increased A* turn cost from 1 to 3× base cost, preventing tiny zigzag detours around minor congestion.
    - History costs for edge segments and corners now decay by 0.85× each rip-up iteration, preventing runaway accumulation from permanently biasing routes.
    - Current congestion cost is now computed directly from live `raw_usage` during A* traversal instead of from stale prefix sums. Each edge immediately sees congestion from prior edges in the same pass, preventing corridor pileups. History cost still uses prefix sums (unchanged within a pass).
- Decomposed `ConsoleGraph` into separate modules for graph transitions and mutations.
- Edge router is now seeded with existing edges for better incremental routing.
- Restructured Rust routing code into multiple modules.
- Consolidated project configuration: `pixi.toml` merged into `pyproject.toml` under `[tool.pixi.*]`.
- CI build tests now use `--no-index` to prevent accidental installation from PyPI.

## Fixed

- Division by zero error in Textual widget caused by `set_timer(0, ...)` during initialization.
- Multiple edge routing bugs around geometry computations and node intersection detection.
- Edge cases in `CoreGraph` node/edge removal and index set handling.
- Textual widget now calls `_resized()` synchronously in `on_mount` instead of deferring.

## Added

- CodSpeed benchmark integration for continuous performance tracking.
- Test and textual optional dependency groups in `pyproject.toml`.

<a id='changelog-0.3.1'></a>
# v0.3.1 — 2025-02-07

## Fixed

- Added missing `typing-extensions` runtime dependency.

<a id='changelog-0.3'></a>
# The Resurrection v0.3 — 2025-02-06

## Fixed

- A lot of bugs fixed around the layout engine and the rendering of nodes and edges.

## Added

- The whole layout and edge routing engine has been rewritten, now without 3rd party dependencies.
- Structured properties for nodes and edges.

<a id='changelog-0.2.1'></a>
# Port Repair v0.2.1 — 2023-11-13

## Fixed

- Multiple bugs around port rendering with update and removal of nodes.

<a id='changelog-0.2.0'></a>
# Textual Widget & Ports v0.2.0 — 2023-11-06

## Added

- Explicit selection of viewport to determine the renderable area.
- Zooming into graphs using a zoom level.
- Level of detail rendering of nodes and edges depending on the zoom level.
- ConsoleGraph is now mutable. Nodes and edges can be added, removed and updated.
- A textual widget with graph based events.
- Nodes can have ports.

## Changed

- Ortohogonal edge routing was improved with more candidates.
- Level of detail handling has been refactored.

## Fixed

- A bug in the edge routing code that missed edges and nodes in the intersection detection.
- Multiple smaller bugs with the orthogonal edge rendering, especially cutting edges with nodes.
- A few bugs with orthogonal edge rendering.

<a id='changelog-0.1.1'></a>
# 0.1.1 — 2023-05-13

## Added

- Three more examples to show how the library behaves with different graphs.

## Fixed

- A bug raising an error when rendering graphs with different box styles in the edges.

<a id='changelog-0.1.0'></a>
# 0.1.0 — 2023-05-05

## Added

- First release of the netext package.
