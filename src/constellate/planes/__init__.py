"""Plane adapters. One directory per plane, one module per engine.

Adapters implement the protocols in constellate.core.protocol, pass the
conformance suite unchanged, and never import each other — wiring happens
only in constellate.factory.
"""
