# Library Setup

* ~~Precommit with black, flake8, isort~~
* ~~Github actions~~
* ~~Coverage~~
* ~~Setup ASV benchmarking~~
* Write a README (add badges)
* Setup code owners
* Enable dependabot & codeql
* Add documentation
* Switch to mypy

# Refactoring

* ~~Extract buffer renderer to own module to make it better testable~~
* ~~Clean up bresenham line drawing algorithm~~

# Tests & Benchmarks

* ~~Tests for buffer renderer~~
* Tests for edge rasterizer
* Tests for node rasterizer
* ~~Simple tests for terminal graph~~
* Benchmarks for buffer renderer
* ~~Bring code coverage to a healthy level~~

# Features

* Different edge routing algorithms
    * ~~ Direct connection ~~
    * ~~ Straight lines ~~
* Better line rendering
    * Use magnets on the node border for edge positions
    * Edge routing gives multiple segments of an edge, each segment can be drawn using different algorithms
        * Box characters (straight lines only) with corner connection (only for straight lines)
            * For this mode straight lines or direct connection should not matter
        * General, lines draw into a bitmap buffer, that is turned into segments (makes braille box drawing easier to use)
            * Simple mode (dots along the lines)
            * Braille (not for straight lines)
* ~~Attributes for nodes~~
* Attributes for edges
* ~~Custom node rendering~~
* Edge labels
* Node labels (not part of the placement algorithm)
* Specify attribute on the graph level and propagate to nodes / edges
* Directed edges (arrow heads)
