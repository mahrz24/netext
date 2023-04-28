# Edge Attributes

## Visibility

The `show` attribute determines if edges are rendered. Hidden edges are not considered for edge routing.

Type: bool.

## Arrow Tips

The `start-arrow-tip` and `end-arrow-tip` attribute determines if edges are rendered with arrow tips.

Type: [ArrowTip][netext.edge_rendering.arrow_tips.ArrowTip] | None.

Possible values are:

| Arrow |  Value | Description |
|------|--------|-------------|
| No tips | None | Uses a single edge segment connecting start and endpoint. |
| Arrow | [ArrowTip.ARROW][netext.edge_rendering.arrow_tips.ArrowTip] | Show an arrow tip using characters matching the `edge-segment-drawing-mode`. |

## Label

The `label` attribute can be set to render a label on the edge.

Type: str | None.

## Style

The `style` attribute determines the rich [style][rich.style.Style] used to render the edge characters.

Type: [Style][rich.style.Style] | None.

## Edge Routing Mode

The `edge-routing-mode` attribute determines how edges are routed from start to end point.

Each edge is represented as a concatenation of one or more edge segments (straight lines).

Type: [EdgeRoutingMode][netext.edge_routing.modes.EdgeRoutingMode] | None

Possible values are:

| Edge Routing Mode |  Value | Description |
|------|--------|-------------|
| Straight | [EdgeRoutingMode.STRAIGHT][netext.edge_routing.modes.EdgeRoutingMode.STRAIGHT] | Uses a single edge segment connecting start and endpoint. (*Default*) |
| Orthogonal | [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL] | Uses multiple vertical or horizontal edge segments. |


## Edge Segment Drawing Mode

The `edge-segment-drawing-mode` attribute determines how individual edge segments (straight lines) are drawn to the terminal.

Possible values are:

| Edge Segment Drawing Mode |  Value | Description |
|------|--------|-------------|
| Single character | [EdgeSegmentDrawingMode.SINGLE_CHARACTER][netext.edge_rendering.modes.EdgeSegmentDrawingMode.SINGLE_CHARACTER] | Uses a single character to draw the whole edge. (*Default*) |
| Box | [EdgeSegmentDrawingMode.BOX][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX] | Uses box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL].  |
| Rounded Box | [EdgeSegmentDrawingMode.BOX_ROUNDED][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_ROUNDED] | Uses box drawing characters to draw lines. Corners between edge segments are merged using rounded box characters. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL]. |
| Heavy Box | [EdgeSegmentDrawingMode.BOX_HEAVY][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_HEAVY] | Uses thicker box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL]. |
| Double Box | [EdgeSegmentDrawingMode.BOX_DOUBLE][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_DOUBLE] | Uses double line box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL]. |
| ASCII compatible | [EdgeSegmentDrawingMode.ASCII][netext.edge_rendering.modes.EdgeSegmentDrawingMode.ASCII] | Uses ASCII characters to draw orthogonal lines. Corners between edge segments are merged with plus signs. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL]. |
| Braille | [EdgeSegmentDrawingMode.BRAILLE][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BRAILLE] | Uses braille characters to draw the whole edge. |
| Block | [EdgeSegmentDrawingMode.BLOCK][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BLOCK] | Uses 2x3 block characters to draw the whole edge. |
