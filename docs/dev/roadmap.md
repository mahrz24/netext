# Roadmap

## To Do List

### Library Setup

* [ ] Write a README (add badges)
* [ ] Setup code owners
* [ ] Enable dependabot & codeql
* Add documentation
    * [x] Automatic rendering of examples as svgs
    * [x] Document all style attributes
    * [x] First tutorial
    * [x] How to style nodes
    * [x] How to style edges
    * [ ] Clean up all crosslinks
    * [ ] Add now missing attributes
* [x] Switch to mypy

### Refactoring

* [x] Remove offset and use spacers instead
* [x] Rename line into strip to algin with textual
* [x] Use enums for all styles

### Tests & Benchmarks

* [ ] More tests for edge rasterizer
* [ ] Benchmarks for buffer renderer
* [ ] Benchmarks for different graph sizes
* [ ] Add snapshot tests

### Layout Engines

* [ ] Support for graphviz layout
* [ ] Edge routing layout engine(s)

### Features

* Better line rendering
    * [x] Use magnets on the node border for edge positions
    * Multiple line segment rendering mechanisms
        * [x] Box characters (straight lines only) with corner connection (only for straight lines)
        * [x] Single character mode
        * [ ] ASCII lines
        * [x] Braille (not for straight lines)
* Attributes for edges
    * [ ] Arrow tips
    * [ ] Dash patterns
    * [ ] Thickness (only certain modes)
* [x] Edge labels
* [ ] Node labels (as labels separate to the node itself)
* [ ] Specify attribute on the graph level and propagate to nodes / edges
* [ ] Partial rendering, clipping and adaptive sizing
* [ ] Textual widget with CSS styling support
