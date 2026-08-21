"""NovaMart synthetic e-commerce data generator.

Produces a coherent operational (OLTP) history — customers, sellers, products,
orders, order items and payments — at configurable scale (5M+ order items at
``--scale 1.0``). The record-building logic in :mod:`novamart_gen.schema` is
pure and unit-tested; :mod:`novamart_gen.generate` wires it to sinks (CSV or
Postgres) and to a continuous mutator that produces CDC change events.
"""

__version__ = "0.1.0"
