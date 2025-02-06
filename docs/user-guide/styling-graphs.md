# Styling Graphs

## Node Styling

!!! info "Node Styling Attributes"

    See the [Node Attribute Reference](../reference/nodes.md) for a list
    of all node styling attributes.


Nodes can be styled by adding attributes to the networkx graph nodes. All netext attributes are starting with a `$` sign to avoid clashes with other attributes.

If you want to style the whole graph in the same way you can call:

```python
import networkx as nx
...
nx.set_node_attributes(g, "none", "$shape")
```

To set the shape of all nodes in the graph `g` to none. Alternatively you can set individual attributes:

```python
g.nodes["somenode"]["$shape"] = "none"
```

## Edge Styling

!!! info "Edge Styling Attributes"

    See the [Edge Attribute Reference](../reference/edges.md) for a list
    of all edge styling attributes.

Edges can be styled in a similar way as nodes.


If you want to style the whole graph in the same way you can call:

```python
import networkx as nx
...
nx.set_edge_attributes(g, EdgeRoutingMode.straight, "$edge-routing-mode")
```

To set the shape of all nodes in the graph `g` to none. Alternatively you can set individual attributes:

```python
g.edges["a"]["b"]["$edge-routing-mode"] = EdgeRoutingMode.straight
```

## Styling via Properties

You can also style the graph via properties. This way you can use code completion to see all available properties and their values
and also benefit from type checking. The attribute based styling, however is easier to encode when storing the graph in a file.

```python
import networkx as nx
from netext import EdgeProperties, NodeProperties, EdgeRoutingMode
...
nx.set_edge_attributes(g, EdgeProperties(routing_mode=EdgeRoutingMode.ORTHOGONAL), "$properties")
```

See the [API Documentation](../api/styling.md) for a full documentation of all possible properties.
