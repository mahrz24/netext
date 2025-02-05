"""
Renders networkx graphs to the terminal.
"""

from netext.console_graph import ConsoleGraph, AutoZoom, ZoomSpec
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.geometry import Magnet, Region

__all__ = [
    "ConsoleGraph",
    "AutoZoom",
    "ZoomSpec",
    "EdgeSegmentDrawingMode",
    "EdgeRoutingMode",
    "ArrowTip",
    "Magnet",
    "Region",
]
