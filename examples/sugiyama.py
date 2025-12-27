from netext import ConsoleGraph, ArrowTip, EdgeSegmentDrawingMode, EdgeRoutingMode
from rich import print
from rich.style import Style

import networkx as nx
import colorsys

from netext.layout_engines import LayoutDirection, SugiyamaLayout

# Orient the binomial tree away from the root to have a clear flow direction
tree = nx.binomial_tree(5)
g = nx.bfs_tree(tree, 0)

nx.set_edge_attributes(g, ArrowTip.ARROW, "$end-arrow-tip")
nx.set_edge_attributes(g, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(g, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
nx.set_node_attributes(g, 1, "$slots")

# Assign varying saturation and brightness per node
depths = nx.single_source_shortest_path_length(g, 0)
max_depth = max(depths.values())
node_saturation = {}
node_brightness = {}
for node, depth in depths.items():
    # Saturation shifts with depth, brightness with the node id for variety
    node_saturation[node] = 0.5 + 0.4 * (depth / max_depth)
    node_brightness[node] = 0.6 + 0.35 * ((node % 7) / 6)

# Cycle hues per source node starting from a node-specific base hue
for source in g.nodes:
    outgoing = sorted(v for _, v in g.out_edges(source))
    if not outgoing:
        continue
    # Golden-ratio offset spreads starting hues across nodes
    base_hue = (source * 0.618033988749895) % 1.0
    for index, target in enumerate(outgoing):
        hue = (base_hue + index / len(outgoing)) % 1.0
        saturation = (node_saturation[source] + node_saturation[target]) / 2
        brightness = (node_brightness[source] + node_brightness[target]) / 2
        r, g_val, b = colorsys.hsv_to_rgb(hue, saturation, brightness)
        color = f"#{int(r * 255):02x}{int(g_val * 255):02x}{int(b * 255):02x}"
        g.edges[(source, target)]["$style"] = Style(color=color)

layout = SugiyamaLayout(direction=LayoutDirection.LEFT_RIGHT)

print(ConsoleGraph(g, layout_engine=layout))
