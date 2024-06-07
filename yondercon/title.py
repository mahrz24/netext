import time
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.padding import Padding
from rich.text import Text
from rich import box

c = Console()

c.clear()

layout = Layout()

layout.split_column(Layout(name="upper"), Layout(name="lower"))

layout["upper"].update(
    Padding(
        Panel(
            Text.from_markup(
                "[bold][green]Connect the dots[/green] - [blue]Terminal edition[/blue][/bold]", justify="center"
            ),
            padding=1,
            box=box.HEAVY,
        ),
        1,
    )
)
layout["lower"].update(
    Padding(Panel(Text("Yondercon 2024 - Malte Klemm", justify="center"), padding=1, box=box.SQUARE_DOUBLE_HEAD), 1)
)


with Live(layout, refresh_per_second=4):
    while True:
        time.sleep(1)
