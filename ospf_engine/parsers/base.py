"""Shared parser primitives. A parser callable takes (text, source, device)
and returns ``(list[Evidence], TopologyFacts)``.
"""

from __future__ import annotations

from typing import Callable

from ospf_engine.models import Evidence, TopologyFacts

ParserFn = Callable[[str, str, str], tuple[list[Evidence], TopologyFacts]]
"""Signature: parser(text, source_filename, device_id) -> (evidence, facts)."""


def empty_result() -> tuple[list[Evidence], TopologyFacts]:
    return [], TopologyFacts()
