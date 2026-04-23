"""Jinja2 templates for the v8.2.7 ``reporter`` module.

This sub-package is intentionally empty Python-wise — it only exists as a
package marker so :func:`importlib.resources` (and the Jinja2
``FileSystemLoader`` used by ``reporter.py``) can resolve the four
``*.md.j2`` templates that ship alongside it.
"""
