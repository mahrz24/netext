from textual.app import App, ComposeResult
from netext.geometry.point import FloatPoint
from netext.textual_widget.widget import GraphView
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.properties.arrow_tips import ArrowTip
from netext.properties.edge import EdgeProperties
from rich.style import Style

import networkx as nx
import pytest


class DummyApp(App):
    def __init__(self, *args, **kwargs):
        self._graph = kwargs.pop("graph")
        self._scroll_via_viewport = kwargs.pop("scroll_via_viewport", False)
        self.clicked = 0
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield GraphView(
            self._graph,
            zoom=1,
            scroll_via_viewport=self._scroll_via_viewport,
            id="graph",
        )

    def on_graph_view_element_click(self, event: GraphView.ElementClick) -> None:
        self.clicked += 1


def _make_styled_graph():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)
    return graph


@pytest.mark.asyncio
async def test_minimal_app():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)):
        assert True


@pytest.mark.asyncio
async def test_add_remove_app():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)) as _:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3

        app.query_one(GraphView).remove_node(1)
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 2


@pytest.mark.asyncio
async def test_click_event():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3
        offset = app.query_one(GraphView).graph_to_widget_coordinates(FloatPoint(10, 1))

        await pilot.click(GraphView, offset=offset)
        assert app.clicked == 1


@pytest.mark.asyncio
async def test_sync_graph_picks_up_node_styles():
    graph = _make_styled_graph()
    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)):
        gv = app.query_one(GraphView)

        # Before styling: default node style
        assert gv.node_properties(1).style == Style()
        assert gv.node_properties(1).content_style == Style()

        # Mutate the networkx graph in-place (like the bug reporter's code)
        nx.set_node_attributes(gv.graph, Style(color="green"), "$style")
        nx.set_node_attributes(gv.graph, Style(color="white"), "$content-style")

        # Without sync, styles are still default
        assert gv.node_properties(1).style == Style()

        # After sync, styles are picked up
        gv.sync_graph()
        assert gv.node_properties(1).style == Style(color="green")
        assert gv.node_properties(1).content_style == Style(color="white")
        assert gv.node_properties(2).style == Style(color="green")
        assert gv.node_properties(2).content_style == Style(color="white")


@pytest.mark.asyncio
async def test_sync_graph_picks_up_edge_attributes():
    graph = _make_styled_graph()
    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)):
        gv = app.query_one(GraphView)

        nx.set_edge_attributes(gv.graph, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
        nx.set_edge_attributes(gv.graph, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
        nx.set_edge_attributes(gv.graph, ArrowTip.NONE, "$start-arrow-tip")
        nx.set_edge_attributes(gv.graph, ArrowTip.ARROW, "$end-arrow-tip")
        nx.set_edge_attributes(gv.graph, Style(color="blue"), "$style")

        gv.sync_graph()

        # Verify edge properties were applied by checking the core graph edge data
        edge_data = gv._console_graph._core_graph.edge_data(1, 2)
        props = EdgeProperties.from_data_dict(edge_data)
        assert props.style == Style(color="blue")
        assert props.routing_mode == EdgeRoutingMode.ORTHOGONAL
        assert props.segment_drawing_mode == EdgeSegmentDrawingMode.BOX
        assert props.start_arrow_tip == ArrowTip.NONE
        assert props.end_arrow_tip == ArrowTip.ARROW


@pytest.mark.asyncio
async def test_graph_setter_rebuilds_console_graph():
    graph = _make_styled_graph()
    app = DummyApp(graph=graph)
    async with app.run_test(size=(80, 24)):
        gv = app.query_one(GraphView)

        # Create a new graph with styles baked in
        new_graph = _make_styled_graph()
        nx.set_node_attributes(new_graph, Style(color="red"), "$style")

        # Assigning via setter should rebuild the console graph
        gv.graph = new_graph
        assert gv.node_properties(1).style == Style(color="red")
        assert gv.node_properties(2).style == Style(color="red")
