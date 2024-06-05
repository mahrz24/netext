# A few examples of the rich library for terminal output
from rich import print
from rich.markdown import Markdown

print("[bold red]Hello World[/bold red]")
print("[bold blue]Hello World[/bold blue]")

print(
    Markdown("""

# Hello World

This is a markdown string

- This is a list
- This is *another list item*

And a table:

| Name | Age |
| ---- | --- |
| Alice | 20 |
| Bob | 21 |

""")
)
