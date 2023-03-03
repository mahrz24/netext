# Edge Attributes

## Edge Routing Mode

The `edge-routing-mode` attribute determines how edges are routed from start to end point.

Each edge is represented as a concatenation of one or more edge segments (straight lines).

Possible values are:

| Edge Routing Mode |  Value | Description |
|------|--------|-------------|
| straight | [EdgeRoutingMode.straight][netext.edge_rasterizer.EdgeRoutingMode.straight] | Uses a single edge segment connecting start and endpoint. |
| orthogonal | [EdgeRoutingMode.orthogonal][netext.edge_rasterizer.EdgeRoutingMode.orthogonal] | Uses multiple vertical or horizontal edge segments. |


## Edge Segment Drawing Mode

The `edge-segment-drawing-mode` attribute determines how individual edge segments (straight lines) are drawn to the terminal.

Possible values are:

| Edge Segment Drawing Mode |  Value | Description |
|------|--------|-------------|
| box | EdgeSegmentDrawingMode.box | Uses box drawing characters to draw lines. Corners between edge segments are merged. |
| single character | EdgeSegmentDrawingMode.single_character | Uses a single character to draw the whole edge. |
| braille | EdgeSegmentDrawingMode.braille | Uses braille characters to draw the whole edge. |
