"""Modular parsers. Each module owns one show-command family.

Public entrypoint is `dispatcher.parse_files`, which routes by filename and
content and returns aggregated (evidence, facts).
"""

from ospf_engine.parsers.dispatcher import parse_file, parse_files, ParseResult

__all__ = ["ParseResult", "parse_file", "parse_files"]
