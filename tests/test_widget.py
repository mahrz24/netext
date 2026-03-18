from typing import Any, Hashable
from textual.app import App, ComposeResult
from netext.geometry.point import FloatPoint
from netext.textual_widget.widget import GraphView
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.properties.arrow_tips import ArrowTip
from netext.properties.edge import EdgeProperties
from rich.style import Style

import pytest


class DummyApp(App):
    def __init__(self, *args, **kwargs):
        self._graph_nodes: dict[Hashable, dict[str, Any]] = kwargs.pop("nodes")
        self._graph_edges = kwargs.pop("edges")
        self._scroll_via_viewport = kwargs.pop("scroll_via_viewport", False)
        self.clicked = 0
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield GraphView(
            nodes=self._graph_nodes,
            edges=self._graph_edges,
            zoom=1,
            scroll_via_viewport=self._scroll_via_viewport,
            id="graph",
        )

    def on_graph_view_element_click(self, event: GraphView.ElementClick) -> None:
        self.clicked += 1


def _make_graph_data():
    nodes = {
        1: {"$x": 1, "$y": 1},
        2: {"$x": 10, "$y": 1},
    }
    edges = [(1, 2)]
    return nodes, edges


@pytest.mark.asyncio
async def test_minimal_app():
    nodes, edges = _make_graph_data()

    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test():
        assert True


@pytest.mark.asyncio
async def test_add_remove_app():
    nodes, edges = _make_graph_data()

    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test() as _:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3

        app.query_one(GraphView).remove_node(1)
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 2


@pytest.mark.asyncio
async def test_click_event():
    nodes, edges = _make_graph_data()

    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test() as pilot:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3
        offset = app.query_one(GraphView).graph_to_widget_coordinates(FloatPoint(10, 1))

        await pilot.click(GraphView, offset=offset)
        assert app.clicked == 1


@pytest.mark.asyncio
async def test_set_graph_picks_up_node_styles():
    nodes, edges = _make_graph_data()
    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test():
        gv = app.query_one(GraphView)

        # Before styling: default node style
        assert gv.node_properties(1).style == Style()
        assert gv.node_properties(1).content_style == Style()

        # Update graph with styled nodes via set_graph
        styled_nodes = {
            1: {"$x": 1, "$y": 1, "$style": Style(color="green"), "$content-style": Style(color="white")},
            2: {"$x": 10, "$y": 1, "$style": Style(color="green"), "$content-style": Style(color="white")},
        }
        gv.set_graph(nodes=styled_nodes, edges=edges)

        assert gv.node_properties(1).style == Style(color="green")
        assert gv.node_properties(1).content_style == Style(color="white")
        assert gv.node_properties(2).style == Style(color="green")
        assert gv.node_properties(2).content_style == Style(color="white")


@pytest.mark.asyncio
async def test_set_graph_picks_up_edge_attributes():
    nodes, edges = _make_graph_data()
    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test():
        gv = app.query_one(GraphView)

        styled_edges = [(1, 2, {
            "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
            "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
            "$start-arrow-tip": ArrowTip.NONE,
            "$end-arrow-tip": ArrowTip.ARROW,
            "$style": Style(color="blue"),
        })]
        gv.set_graph(nodes=nodes, edges=styled_edges)

        # Verify edge properties were applied by checking the core graph edge data
        edge_data = gv._console_graph._core_graph.edge_data(1, 2)
        props = EdgeProperties.from_data_dict(edge_data)
        assert props.style == Style(color="blue")
        assert props.routing_mode == EdgeRoutingMode.ORTHOGONAL
        assert props.segment_drawing_mode == EdgeSegmentDrawingMode.BOX
        assert props.start_arrow_tip == ArrowTip.NONE
        assert props.end_arrow_tip == ArrowTip.ARROW


@pytest.mark.asyncio
async def test_set_graph_replaces_graph():
    nodes, edges = _make_graph_data()
    app = DummyApp(nodes=nodes, edges=edges)
    async with app.run_test():
        gv = app.query_one(GraphView)

        # Replace with styled graph
        new_nodes = {
            1: {"$x": 1, "$y": 1, "$style": Style(color="red")},
            2: {"$x": 10, "$y": 1, "$style": Style(color="red")},
        }
        gv.set_graph(nodes=new_nodes, edges=edges)
        assert gv.node_properties(1).style == Style(color="red")
        assert gv.node_properties(2).style == Style(color="red")
