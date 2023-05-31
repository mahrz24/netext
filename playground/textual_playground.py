from netext.textual.widget import Graph
from netext import AutoZoom
from textual.app import App, ComposeResult

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")


class GraphApp(App):
    CSS_PATH = "textual_playground.css"

    def compose(self) -> ComposeResult:
        yield Graph(g, zoom=AutoZoom.FIT)


app = GraphApp()

app.run()
