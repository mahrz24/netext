# netext

[![pypi](https://img.shields.io/pypi/v/netext.svg)](https://pypi.python.org/pypi/netext)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Documentation](https://img.shields.io/badge/documentation-latest-green)](https://mahrz24.github.io/netext/)

![](logo.jpg)

Netext is a graph (network) rendering library for the terminal. It uses the awesome [rich](https://rich.readthedocs.io/en/stable/introduction.html) library to format output and can use different layout engines to place nodes and edges. The library has a very simple API that allows to render graphs created with networkx and integrates well with applications that use rich to output to the terminal. All styling and formatting is done via attributes the nodes and edges of the networkx graph data structures using special attributes keys.

![](example.svg)
