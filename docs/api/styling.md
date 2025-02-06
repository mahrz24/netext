# Styling & Properties

## Geometry

::: netext.Region
    handler: python
    options:
      show_source: false


## Nodes

::: netext.NodeProperties
    handler: python
    options:
      show_source: false


::: netext.Port
    handler: python
    options:
      show_source: false


::: netext.ShapeProperties
    handler: python
    options:
      show_source: false


::: netext.JustContent
    handler: python
    options:
      show_source: false

::: netext.Box
    handler: python
    options:
      show_source: false

## Edges

::: netext.EdgeProperties
    handler: python
    options:
      show_source: false

::: netext.Magnet
    handler: python
    options:
      show_source: false
      members: ["TOP", "LEFT", "RIGHT", "BOTTOM", "CENTER", "CLOSEST"]

::: netext.ArrowTip
    handler: python
    options:
      show_source: false
      members: ["ARROW"]

::: netext.EdgeRoutingMode
    handler: python
    options:
      show_source: false
      members: ["STRAIGHT", "ORTHOGONAL"]

::: netext.EdgeSegmentDrawingMode
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
        "BLOCK",
      ]
