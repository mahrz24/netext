from textual.app import App, ComposeResult
from textual.widgets import Header
from netext.textual.widget import GraphView

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")


class GraphviewApp(App):
    """A Textual app that displays a graph."""

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield GraphView(g)


if __name__ == "__main__":
    app = GraphviewApp()
    app.run()
