"""
Renders networkx graphs to the terminal.
"""

from netext.console_graph import ConsoleGraph, AutoZoom, ZoomSpec
from netext.properties.node import NodeProperties, Port
from netext.properties.shape import ShapeProperties, JustContent, Box
from netext.properties.edge import EdgeProperties

from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.geometry import Magnet, Region

__all__ = [
    "ConsoleGraph",
    "AutoZoom",
    "ZoomSpec",
    "NodeProperties",
    "Port",
    "ShapeProperties",
    "JustContent",
    "Box",
    "EdgeProperties",
    "EdgeSegmentDrawingMode",
    "EdgeRoutingMode",
    "ArrowTip",
    "Magnet",
    "Region",
]
