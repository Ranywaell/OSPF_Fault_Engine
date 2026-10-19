"""Optional SQLite mirror of the fault knowledge base.

The runtime catalogue is the typed Python dict in
:mod:`ospf_engine.reasoning.knowledge_base`. This module exists to satisfy the
brief's "Suggested tools: ... SQLite ..." requirement and to give the operator
a portable, queryable copy of the catalogue.

Usage from the command line::

    python -m ospf_engine.reasoning.kb_sqlite snapshot
        # writes data/faults.db with one row per fault

    python -m ospf_engine.reasoning.kb_sqlite list
        # prints every fault stored in data/faults.db

    python -m ospf_engine.reasoning.kb_sqlite show "OSPF Area Mismatch"
        # prints the cause / verify / fix for one fault

Usage from Python::

    from ospf_engine.reasoning.kb_sqlite import snapshot_to_db, load_from_db
    snapshot_to_db()
    faults = load_from_db()

The default DB path is ``<project_root>/data/faults.db``.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from ospf_engine.models import Fault, FaultCategory
from ospf_engine.reasoning.knowledge_base import FAULT_CATALOG


_DEFAULT_DB = Path(
    os.environ.get(
        "OSPF_ENGINE_KB_DB",
        Path(__file__).resolve().parents[2] / "data" / "faults.db",
    )
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS faults (
    name              TEXT PRIMARY KEY,
    category          TEXT NOT NULL,
    cause             TEXT NOT NULL,
    verify            TEXT NOT NULL,
    fix               TEXT NOT NULL,
    fix_dependencies  TEXT NOT NULL DEFAULT ''
);
"""

_SEP = "\n||\n"  # multi-line-safe separator for list fields


def _serialise(items: tuple[str, ...]) -> str:
    return _SEP.join(items)


def _deserialise(blob: str) -> tuple[str, ...]:
    if not blob:
        return ()
    return tuple(blob.split(_SEP))


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)
    return conn


def snapshot_to_db(db_path: Path = _DEFAULT_DB) -> Path:
    """Write the in-memory FAULT_CATALOG to a SQLite file. Idempotent."""
    conn = _connect(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM faults")
            conn.executemany(
                "INSERT INTO faults VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        f.name,
                        f.category.value,
                        f.cause,
                        _serialise(f.verify),
                        f.fix,
                        _serialise(f.fix_dependencies),
                    )
                    for f in FAULT_CATALOG.values()
                ],
            )
    finally:
        conn.close()
    return db_path


def load_from_db(db_path: Path = _DEFAULT_DB) -> dict[str, Fault]:
    """Read the catalogue back out of SQLite into typed `Fault` objects."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"No knowledge-base SQLite file at {db_path}. Run "
            "'python -m ospf_engine.reasoning.kb_sqlite snapshot' first."
        )

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name, category, cause, verify, fix, fix_dependencies FROM faults"
        ).fetchall()
    finally:
        conn.close()

    out: dict[str, Fault] = {}
    for name, cat, cause, verify, fix, deps in rows:
        out[name] = Fault(
            name=name,
            category=FaultCategory(cat),
            cause=cause,
            verify=_deserialise(verify),
            fix=fix,
            fix_dependencies=_deserialise(deps),
        )
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_snapshot(args: argparse.Namespace) -> int:
    path = snapshot_to_db(Path(args.db))
    print(f"Snapshot written: {path} ({len(FAULT_CATALOG)} faults).")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    catalog = load_from_db(Path(args.db))
    width = max(len(name) for name in catalog)
    for name, fault in sorted(catalog.items()):
        print(f"  {name.ljust(width)}  [{fault.category.value}]")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    catalog = load_from_db(Path(args.db))
    fault = catalog.get(args.name)
    if fault is None:
        print(f"Unknown fault: {args.name!r}", file=sys.stderr)
        return 2
    print("=" * 70)
    print(f"  {fault.name}  [{fault.category.value}]")
    print("=" * 70)
    print()
    print("Cause:")
    print(f"  {fault.cause}")
    print()
    print("Verify:")
    for cmd in fault.verify:
        print(f"  > {cmd}")
    print()
    print("Safe fix:")
    for line in fault.fix.splitlines():
        print(f"  {line}")
    if fault.fix_dependencies:
        print()
        print("Fix dependencies (apply these BEFORE this fault):")
        for dep in fault.fix_dependencies:
            print(f"  - {dep}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help=f"Path to the SQLite knowledge-base file (default: {_DEFAULT_DB}).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="Write FAULT_CATALOG to SQLite.")
    p_snap.set_defaults(func=_cmd_snapshot)

    p_list = sub.add_parser("list", help="List all faults stored in the DB.")
    p_list.set_defaults(func=_cmd_list)

    p_show = sub.add_parser("show", help="Print one fault from the DB.")
    p_show.add_argument("name")
    p_show.set_defaults(func=_cmd_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
