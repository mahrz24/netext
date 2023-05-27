# Zoom and Viewport

When creating a [TerminalGraph][netext.TerminalGraph] it is possible to specify a zoom level and a viewport. The zoom level determines how close or far apart nodes are placed, but can also change the way and size of nodes. The viewport allows to select only a certain part of the graph to be rendered. By default the zoom level is one and the viewport is spanning all rendered parts of the graph.

# Viewport

The viewport, if explicitly specified, is passed as a region, e.g.:

```python
from netext.geometry import Region
...
TerminalGraph(g, viewport=Region(-20, -25, 40, 15))
```

that determines the upper left point, i.e. `(-20, -25)` and the size of the region, i.e. `(40, 15)`.

!!! info

    Graphs are centered around the `(0,0)` coordinate, so negative coordinates are common for specifying viewports. You can use [TerminalGraph.full_viewport][netext.TerminalGraph.full_viewport] to find the maximum extent of your viewport.

# Zoom

You can specify the zoom of the rendered graph with respect to the default zoom level of 1 which is what is returned by the layout engine, where a larger value means zooming in and a smaller value means zooming out. It is possible to zoom x and y directions independently. Furthermore, to set the zoom to fit the available renderable area (with keeping the aspect ratio or not), by using [AutoZoom.FIT][netext.AutoZoom.FIT] or [AutoZoom.FIT_PROPORTIONAL][netext.AutoZoom.FIT_PROPORTIONAL] respectively.


## Level of Detail

The zoom level by default only changes how
