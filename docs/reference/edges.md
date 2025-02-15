# Edge Attributes

## Visibility

The `show` attribute determines if edges are rendered. Hidden edges are not considered for edge routing.

Type: bool.

## Level of Detail

The `lod-map` attribute can be set to a function mapping zoom levels to discrete level of detail values. The function takes a single float parameter and returns an integer value. See [Zoom and Viewport](../user-guide/zoom-and-viewport.md) for details on how to use the level of detail to change the appearance of edges on different zoom levels.

Type: Callable | None

## Arrow Tips

The `start-arrow-tip` and `end-arrow-tip` attribute determines if edges are rendered with arrow tips.

Type: [ArrowTip][netext.edge_rendering.arrow_tips.ArrowTip] | None.

Possible values are:

| Arrow   | Value                                                       | Description                                                                  |
| ------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------- |
| No tips | None                                                        | Uses a single edge segment connecting start and endpoint.                    |
| Arrow   | [ArrowTip.ARROW][netext.edge_rendering.arrow_tips.ArrowTip] | Show an arrow tip using characters matching the `edge-segment-drawing-mode`. |

### Examples

```{.rich title='ArrowTip.ARROW' }
from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.layout_engines import StaticLayout
from rich import print


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 5, "$y": 9})
g.add_edge("A", "B", **{"$end-arrow-tip": ArrowTip.ARROW})

g.add_node("C", **{"$x": 15, "$y": 0})
g.add_node("D", **{"$x": 15, "$y": 9})
g.add_edge("C", "D", **{"$end-arrow-tip": ArrowTip.ARROW,
                        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
                        "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL}
)

output = ConsoleGraph(g, layout_engine=StaticLayout())
```

## Label

The `label` attribute can be set to render a label on the edge.

Type: str | None.

### Example

```{.rich title='Label' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 5, "$y": 9})
g.add_edge("A", "B", **{"$label": "Label"})


output = ConsoleGraph(g, layout_engine=StaticLayout())
```

## Style

The `style` attribute determines the rich [style][rich.style.Style] used to render the edge characters.

Type: [Style][rich.style.Style] | None.

### Examples

```{.rich title='Style' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 5, "$y": 9})
g.add_edge("A", "B", **{"$style": Style(color="red")})

g.add_node("C", **{"$x": 15, "$y": 0})
g.add_node("D", **{"$x": 15, "$y": 9})
g.add_edge("C", "D", **{"$style": Style(color="blue", bold=True)})


g.add_node("E", **{"$x": 25, "$y": 0})
g.add_node("F", **{"$x": 25, "$y": 9})
g.add_edge("E", "F", **{"$style": Style(bgcolor="blue", bold=True)})


g.add_node("G", **{"$x": 35, "$y": 0})
g.add_node("H", **{"$x": 35, "$y": 9})
g.add_edge("G", "H"

)

output = ConsoleGraph(g, layout_engine=StaticLayout())
```

## Dash Pattern

The `dash-pattern` attribute determines a dash pattern. You can pass a list of integer values to it and the list will repeat an alternating on-off pattern for edges drawn.

### Examples

```{.rich title='Dashes' }

from netext import ConsoleGraph, EdgeSegmentDrawingMode, EdgeRoutingMode
from netext.layout_engines import StaticLayout
from rich import print

import networkx as nx
g = nx.Graph()
g.add_node("[1, 1]", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 5, "$y": 16})

g.add_edge("[1, 1]", "B", **{
    "$dash-pattern": [1, 1],
    "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
    "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL
})

g.add_node("[2, 1]", **{"$x": 17, "$y": 0})
g.add_node("D", **{"$x": 17, "$y": 16})

g.add_edge("[2, 1]", "D", **{
    "$dash-pattern": [2, 1],
    "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
    "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL
})

g.add_node("[3, 2, 1]", **{"$x": 30, "$y": 0})
g.add_node("F", **{"$x": 30, "$y": 16})

g.add_edge("[3, 2, 1]", "F", **{
    "$dash-pattern": [3, 2, 1],
    "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
    "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL
})


output = ConsoleGraph(g, layout_engine=StaticLayout())
```

## Magnets

The `start-magnet` and `end-magnet` attributes determine to which side of the node the edge is connected.

Type: [Magnet][netext.geometry.magnet.Magnet] | None

Possible values are:

| Magnet  | Value                                                   | Description                             |
| ------- | ------------------------------------------------------- | --------------------------------------- |
| Left    | [Magnet.LEFT][netext.geometry.magnet.Magnet.LEFT]       | Connect to the left side of the node    |
| Right   | [Magnet.RIGHT][netext.geometry.magnet.Magnet.RIGHT]     | Connect to the right side of the node   |
| Top     | [Magnet.TOP][netext.geometry.magnet.Magnet.TOP]         | Connect to the top side of the node     |
| Bottom  | [Magnet.BOTTOM][netext.geometry.magnet.Magnet.BOTTOM]   | Connect to the bottom side of the node  |
| Closest | [Magnet.CLOSEST][netext.geometry.magnet.Magnet.CLOSEST] | Connect to the closest magnet position. |

## Ports

The `start-port` and `end-port` attributes determine to which port of the corresponding node the edge is connected to. The port needs to be declared as a property of the node. If set, the `start-magnet` and `end-magnet` attributes are ignored respectively.

Type: str | None

## Edge Routing Mode

The `edge-routing-mode` attribute determines how edges are routed from start to end point.

Each edge is represented as a concatenation of one or more edge segments (straight lines).

Type: [EdgeRoutingMode][netext.edge_routing.modes.EdgeRoutingMode] | None

Possible values are:

| Edge Routing Mode | Value                                                                              | Description                                                           |
| ----------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Straight          | [EdgeRoutingMode.STRAIGHT][netext.edge_routing.modes.EdgeRoutingMode.STRAIGHT]     | Uses a single edge segment connecting start and endpoint. (_Default_) |
| Orthogonal        | [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL] | Uses multiple vertical or horizontal edge segments.                   |

### Example

```{.rich title='Edge Routing Mode' }
from netext import ConsoleGraph
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from netext.layout_engines import StaticLayout
from rich import print


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 13, "$y": 9})
g.add_edge("A", "B", **{"$edge-routing-mode": EdgeRoutingMode.STRAIGHT})

g.add_node("C", **{"$x": 21, "$y": 0})
g.add_node("D", **{"$x": 29, "$y": 9})
g.add_edge("C", "D", **{"$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL}
)

output = ConsoleGraph(g, layout_engine=StaticLayout())
```

## Edge Segment Drawing Mode

The `edge-segment-drawing-mode` attribute determines how individual edge segments (straight lines) are drawn to the terminal.

Possible values are:

| Edge Segment Drawing Mode | Value                                                                                                          | Description                                                                                                                                                                                                           |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Single character          | [EdgeSegmentDrawingMode.SINGLE_CHARACTER][netext.edge_rendering.modes.EdgeSegmentDrawingMode.SINGLE_CHARACTER] | Uses a single character to draw the whole edge. (_Default_)                                                                                                                                                           |
| Box                       | [EdgeSegmentDrawingMode.BOX][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX]                           | Uses box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL].                              |
| Rounded Box               | [EdgeSegmentDrawingMode.BOX_ROUNDED][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_ROUNDED]           | Uses box drawing characters to draw lines. Corners between edge segments are merged using rounded box characters. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL]. |
| Heavy Box                 | [EdgeSegmentDrawingMode.BOX_HEAVY][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_HEAVY]               | Uses thicker box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL].                      |
| Double Box                | [EdgeSegmentDrawingMode.BOX_DOUBLE][netext.edge_rendering.modes.EdgeSegmentDrawingMode.BOX_DOUBLE]             | Uses double line box drawing characters to draw lines. Corners between edge segments are merged. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL].                  |
| ASCII compatible          | [EdgeSegmentDrawingMode.ASCII][netext.edge_rendering.modes.EdgeSegmentDrawingMode.ASCII]                       | Uses ASCII characters to draw orthogonal lines. Corners between edge segments are merged with plus signs. Works only with [EdgeRoutingMode.ORTHOGONAL][netext.edge_routing.modes.EdgeRoutingMode.ORTHOGONAL].         |

### Examples

```{.rich title='Style' }
from netext import ConsoleGraph
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0})
g.add_node("B", **{"$x": 15, "$y": 9})
g.add_edge("A", "B", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.SINGLE_CHARACTER})

g.add_node("C", **{"$x": 25, "$y": 0})
g.add_node("D", **{"$x": 35, "$y": 9})
g.add_edge("C", "D", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX, "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL})



g.add_node("E", **{"$x": 45, "$y": 0})
g.add_node("F", **{"$x": 55, "$y": 9})
g.add_edge("E", "F", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX_ROUNDED,"$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL})


g.add_node("G", **{"$x": 65, "$y": 0})
g.add_node("H", **{"$x": 75, "$y": 9})
g.add_edge("G", "H", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX_HEAVY,"$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL})


g.add_node("I", **{"$x": 5, "$y": 13})
g.add_node("J", **{"$x": 15, "$y": 22})
g.add_edge("I", "J", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX_DOUBLE,"$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL})

g.add_node("K", **{"$x": 25, "$y": 13})
g.add_node("L", **{"$x": 35, "$y": 22})
g.add_edge("K", "L", **{"$edge-segment-drawing-mode": EdgeSegmentDrawingMode.ASCII,"$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL})

output = ConsoleGraph(g, layout_engine=StaticLayout())
```
