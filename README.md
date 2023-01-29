# netext

Netext is a graph (network) rendering library for the terminal. It uses the awesome rich library to format output and can use different layout engines to place nodes and edges. The library has a very simple API that allows to render graphs created with networkx and integrates well with applications that use rich to output to the terminal. All styling and formatting is done via attributes the nodes and edges of the networkx graph data structures using special attributes keys.

The library is in early alpha stage and has currently no emphasis on performance, so please do not try to render large graphs with it and expect API changes in the future.
