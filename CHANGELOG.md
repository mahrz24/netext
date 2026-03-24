<a id='changelog-0.4.0'></a>
# Routing & Architecture v0.4.0 — 2026-03-24

## Changed

- Completely rewritten edge routing engine in Rust using bucketed A* with node avoidance and edge decongestion.
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
