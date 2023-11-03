# Styling

## Nodes

::: netext.node_rasterizer.Shape
    handler: python
    options:
      show_source: false


::: netext.node_rasterizer.Box
    handler: python
    options:
      show_source: false


::: netext.node_rasterizer.JustContent
    handler: python
    options:
      show_source: false



## Edges

::: netext.geometry.magnet.Magnet
    handler: python
    options:
      show_source: false
      members: ["TOP", "LEFT", "RIGHT", "BOTTOM", "CENTER", "CLOSEST"]

::: netext.edge_rendering.arrow_tips.ArrowTip
    handler: python
    options:
      show_source: false
      members: ["ARROW"]


::: netext.edge_routing.modes.EdgeRoutingMode
    handler: python
    options:
      show_source: false
      members: ["STRAIGHT", "ORTHOGONAL"]

::: netext.edge_rendering.modes.EdgeSegmentDrawingMode
    handler: python
    options:
      show_source: false
      members: [
        "BOX",
        "BOX_ROUNDED",
        "BOX_HEAVY",
        "BOX_DOUBLE",
        "ASCII",
        "SINGLE_CHARACTER",
        "BRAILLE",
        "BLOCK",
      ]
