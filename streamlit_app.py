"""Thin Streamlit entrypoint.

Run with::

    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import sys


def _ensure_package_on_path() -> None:
    """When Streamlit launches this file by path, the project root may not be
    on sys.path. Add it explicitly so ``import ospf_engine`` works."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


_ensure_package_on_path()


from ospf_engine.ui import render  # noqa: E402

render()
