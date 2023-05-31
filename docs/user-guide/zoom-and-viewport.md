# Zoom and Viewport

When creating a [ConsoleGraph][netext.ConsoleGraph] it is possible to specify a zoom level and a viewport. The zoom level determines how close or far apart nodes are placed, but can also change the way and size of nodes. The viewport allows to select only a certain part of the graph to be rendered. By default the zoom level is one and the viewport is spanning all rendered parts of the graph.

# Viewport

The viewport, if explicitly specified, is passed as a region, e.g.:

```python
from netext.geometry import Region
...
ConsoleGraph(g, viewport=Region(-20, -25, 40, 15))
```

that determines the upper left point, i.e. `(-20, -25)` and the size of the region, i.e. `(40, 15)`.

!!! info

    Graphs are centered around the `(0,0)` coordinate, so negative coordinates are common for specifying viewports. You can use [ConsoleGraph.full_viewport][netext.ConsoleGraph.full_viewport] to find the maximum extent of your viewport.

# Zoom

You can specify the zoom of the rendered graph with respect to the default zoom level of 1 which is what is returned by the layout engine, where a larger value means zooming in and a smaller value means zooming out. It is possible to zoom x and y directions independently. Furthermore, to set the zoom to fit the available renderable area (with keeping the aspect ratio or not), by using [AutoZoom.FIT][netext.AutoZoom.FIT] or [AutoZoom.FIT_PROPORTIONAL][netext.AutoZoom.FIT_PROPORTIONAL] respectively.


## Level of Detail

The zoom level by default only changes how nodes are placed, but not the size or shape of nodes. This can be changes by introducing a mapping from zoom level to level of detail (lod). Such a map can be supplied to edges and nodes as an attribute. The default level of detail is one. For level of detail values other than one, the styling can be changed be adding `-{lod}` suffix to the attributes. For example, if you want to replace all nodes by small circles once you zoom our more than 50% you can do the following:

```python
# Add a mapping from zoom level ot level of detail.
nx.set_node_attributes(g, lambda zoom: 0 if zoom < 0.5 else 1, "$lod-map")
# For lod 0, remove the shape.
nx.set_node_attributes(g, JustContent(), "$shape-0")
# For lod 0, replace the content by a circle.
nx.set_node_attributes(g, lambda _, __, ___: "⏺", "$content-renderer-0")
```
