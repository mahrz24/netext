# Node Attributes

## Visibility

The `show` attribute determines if nodes are rendered. Hidden nodes are not considered for edge routing but are passed and considered for the node layout.

Type: bool.

## Shape

The `shape` attribute determines the surrounding decoration around the content of the node.

Type: [Shape][netext.node_rasterizer.Shape] | None

Possible values are:

| Shape |  Value | Description |
|------|--------|-------------|
| Box | [Box][netext.node_rasterizer.Box] | Renders a [Panel][rich.panel.Panel] around the content. (*Default*) |
| None | [JustContent][netext.node_rasterizer.JustContent] | Only renders the content. |

### Box

The box shape renders the content within a [Panel][rich.panel.Panel]. For box shapes the folowing can attribute can be set:

#### Box Type

The box type is determined via `box-type`.

Type: [Box](https://rich.readthedocs.io/en/stable/appendix/box.html#appendix-box)

### Generic styling for all shapes

#### Style

The `style` attribute determines the [style][rich.style.Style] that is applied to the shape of the node (not the content).

Type: [Style][rich.style.Style] | None

#### Content Style

The `content-style` attribute is passed to the content renderer function.

Type: [Style][rich.style.Style] | None

#### Content Renderer

The `content-renderer` attribute is a function that takes three parameters, node label (`str`), node data (`Any`) and content [style][rich.style.Style] and returns a rich [renderable][rich.console.ConsoleRenderable].

Type: Callable | None
