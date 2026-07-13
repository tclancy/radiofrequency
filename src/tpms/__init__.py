"""TPMS ingest slice-1 — parked-only tire-pressure capture for a home dashboard.

Scope: one vehicle (2013 Mazda CX-9), one frequency (315 MHz), rtl_433 decoder r156.
Reads JSON events from rtl_433 (stdin), writes to SQLite, exposes a small JSON API.

See docs/tpms-slice-1.md for the deployment plan on plexpi.
"""
