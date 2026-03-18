from textual.app import App, ComposeResult
from textual.widgets import Header
from netext.textual_widget.widget import GraphView


class GraphviewApp(App):
    """A Textual app that displays a graph."""

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield GraphView(
            nodes={"Hello": {}, "World": {}},
            edges=[("Hello", "World")],
        )


if __name__ == "__main__":
    app = GraphviewApp()
    app.run()
