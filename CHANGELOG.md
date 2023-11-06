
<a id='changelog-0.2.0'></a>
# 0.2.0 — 2023-11-06

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
