"""Internal utilities (text helpers, logging)."""

from ospf_engine.utils.text import (
    extract_device_from_filename,
    extract_device_from_prompt,
    iter_nonempty_lines,
    safe_int,
)

__all__ = [
    "extract_device_from_filename",
    "extract_device_from_prompt",
    "iter_nonempty_lines",
    "safe_int",
]
