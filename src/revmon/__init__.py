"""Revision-aware monitoring.

Measuring how much the maintenance recommendation for a deployed model changes
when the record it is monitored against is itself revised.

Two doors, and no others:

* `revmon.sources` is the only module that touches the network.
* `revmon.panel` is the only module that reads `data/`.

Reading `data/` from a script, or importing a network client anywhere else, is a
contract violation and a hook reports it. See `.claude/rules/datos.md`.
"""

__version__ = "0.1.0"
