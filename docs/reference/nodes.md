# Node Attributes

## Visibility

The `show` attribute determines if nodes are rendered. Hidden nodes are not considered for edge routing but are passed and considered for the node layout.

Type: bool.

## Level of Detail

The `lod-map` attribute can be set to a function mapping zoom levels to discrete level of detail values. The function takes a single float parameter and returns an integer value. See [Zoom and Viewport](../user-guide/zoom-and-viewport.md) for details on how to use the level of detail to change the appearance of nodes on different zoom levels.

Type: Callable | None

## Shape

The `shape` attribute determines the surrounding decoration around the content of the node.

Type: str | None

Possible values are:

| Shape |  Value | Description |
|------|--------|-------------|
| Box | box | Renders a [Panel][rich.panel.Panel] around the content. (*Default*) |
| None | just-content | Only renders the content. |

### Examples

```{.rich title='Shapes' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0}, **{"$shape": "just-content"})
g.add_node("B", **{"$x": 20, "$y": 0})
g.add_edge("A", "B")


output = ConsoleGraph(g, layout_engine=StaticLayout())
```

### Box

The box shape renders the content within a [Panel][rich.panel.Panel]. For box shapes the folowing can attribute can be set:

#### Box Type

The box type is determined via `box-type`.

Type: [Box](https://rich.readthedocs.io/en/stable/appendix/box.html#appendix-box)

##### Example

```{.rich title='Box Types' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import box
from rich import print


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0}, **{"$box-type": box.DOUBLE})
g.add_node("B", **{"$x": 15, "$y": 0})
g.add_edge("A", "B")


output = ConsoleGraph(g, layout_engine=StaticLayout())
```

### Generic styling for all shapes

#### Style

The `style` attribute determines the [style][rich.style.Style] that is applied to the shape of the node (not the content).

Type: [Style][rich.style.Style] | None


##### Example

```{.rich title='Style' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0}, **{"$style": Style(color="red")})
g.add_node("B", **{"$x": 15, "$y": 0},  **{"$style": Style(bold=True, bgcolor="blue")})
g.add_edge("A", "B")

output = ConsoleGraph(g, layout_engine=StaticLayout())
```

#### Content Style

The `content-style` attribute is passed to the content renderer function.

Type: [Style][rich.style.Style] | None

##### Example

```{.rich title='Content Style' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style


import networkx as nx
g = nx.Graph()
g.add_node("A", **{"$x": 5, "$y": 0}, **{"$content-style": Style(color="red")})
g.add_node("B", **{"$x": 15, "$y": 0},  **{"$content-style": Style(bold=True, bgcolor="blue")})
g.add_edge("A", "B")

output = ConsoleGraph(g, layout_engine=StaticLayout())
```

#### Content Renderer

The `content-renderer` attribute is a function that takes three parameters, node label (`str`), node data (`Any`) and content [style][rich.style.Style] and returns a rich [renderable][rich.console.ConsoleRenderable].

Type: Callable | None

## Ports

The `ports` attribute determines the ports of the node. Ports are used to connect edges to nodes. Ports are defined as a dictionary mapping port names to port specifications. The port specifications are a dictionary with the following keys: `magnet`, `label`, `offset`, `symbol`, `symbol-connected`, `key`.

Ports are optional and a port only needs to be specified if it is used as a target or source of an edge. A port specification must at least contain a `label`. All other keys are optional.

| Key               | Type     | Description                                                                 |
|-------------------|----------|-----------------------------------------------------------------------------|
| `magnet`          | `str`    | The magnet position of the port.                                            |
| `label`           | `str`    | The label of the port.                                                      |
| `offset`          | `Tuple[int, int]` | The offset of the port from the node position.                        |
| `symbol`          | `str`    | The symbol to use for the port.                                              |
| `symbol-connected` | `str`    | The symbol to use for the port when it is connected to an edge.              |
| `key`             | `str`    | The key of the port used when sorting ports on a side of a node.                                         |


##### Example

```python
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style

import networkx as nx
g = nx.Graph()
g.add_node("X", **{
        "$x": 5,
        "$y": 0,
        "$ports": {"a": {"label": "a"}, "b": {"label": "b"}}
    }
)
g.add_node("Y", **{
    "$x": 25,
    "$y": 0,
    "$ports": {"a": {"label": "a"}, "b": {"label": "b"}}
    }
)
g.add_edge("X", "Y", **{"$start-port": "a", "$end-port": "a"})

print(ConsoleGraph(g, layout_engine=StaticLayout()))
```

```{.rich title='Ports' }
from netext import ConsoleGraph
from netext.layout_engines import StaticLayout
from rich import print
from rich.style import Style

import networkx as nx
g = nx.Graph()
g.add_node("X", **{"$x": 5, "$y": 0, "$ports": {"a": {"label": "a"}, "b": {"label": "b"}}})
g.add_node("Y", **{"$x": 25, "$y": 0, "$ports": {"a": {"label": "a"}, "b": {"label": "b"}}})
g.add_edge("X", "Y", **{"$start-port": "a", "$end-port": "a"})

output = ConsoleGraph(g, layout_engine=StaticLayout())
```
