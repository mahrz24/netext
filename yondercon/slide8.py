from rich.markdown import Markdown
from rich import print

print(
    Markdown("""
# Lessons learned and thoughts on the process

- Having your own project, free from any constraints, is a great way to learn new things.
- Development on the library happens in bursts, with long periods of inactivity.
- Python packaging is a mess, I went from poetry to hatch and now settled on rye.
- Graph layout is not easy and python is not the best language for it.
    - I *had* to learn rust to make this part fast and usable in the terminal.
    - Some throwback moments to graph theory classes.
- Rich is a great library for terminal output and the textual ecosystem is developing quickly.

""")
)
