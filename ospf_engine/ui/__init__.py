"""Streamlit UI. Imports streamlit lazily so the engine remains importable
without streamlit installed (e.g. for unit tests or the CLI benchmark)."""

from ospf_engine.ui.app import render

__all__ = ["render"]
