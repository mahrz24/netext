# Node Attributes

## Shape

The `shape` attribute determines the surrounding decoration around the content of the node.

Default: `box`.

### Box

The box shape renders the content within a `rich` panel with

#### Box Type

## Style

The `style` attribute determines the style (`Style`) that is applied to the shape of the node (not the content).

## Content Style

The `content-style` attribute is passed to the content renderer function.

## Content Renderer

The `content-renderer` attribute is a function that takes three parameters, node label (`str`), node data (`Any`) and content style (`Style`) and returns a rich renderable (`RenderableType`).
