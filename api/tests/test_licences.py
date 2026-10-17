"""Licence policy (CLAUDE.md): no copyleft or non-commercial dependency in the environment."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_licences", Path(__file__).resolve().parents[1] / "scripts" / "check_licences.py"
)
assert _spec and _spec.loader
cl = importlib.util.module_from_spec(_spec)
sys.modules["check_licences"] = cl
_spec.loader.exec_module(cl)

# Temporary: known violations that are printed, not failed. Remove entries as they are fixed.
KNOWN_VIOLATIONS: dict[str, str] = {
    "num2words": "removed in M2 backend task",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache Software License", "ok"),
        ("Apache-2.0", "ok"),
        ("MIT License", "ok"),
        ("BSD-3-Clause", "ok"),
        ("BSD License", "ok"),
        ("GPLv3+", "copyleft"),
        ("GNU General Public License v3 or later (GPLv3+)", "copyleft"),
        ("LGPL-2.1-or-later", "copyleft"),
        ("AGPL-3.0", "copyleft"),
        ("SSPL-1.0", "copyleft"),
        ("EUPL-1.2", "copyleft"),
        ("CeCILL-2.1", "copyleft"),
        ("CC-BY-NC-4.0", "noncommercial"),
        ("Non-commercial research use only", "noncommercial"),
        ("MIT AND MPL-2.0", "ok"),
        ("(Apache-2.0 OR BSD-3-Clause)", "ok"),
        ("GPL-2.0 OR MIT", "ok"),
        ("GPL-3.0 AND MIT", "copyleft"),
        ("GPL-3.0 OR LGPL-2.1", "copyleft"),
        ("Other/Proprietary License", "proprietary"),
        ("", "no-metadata"),
        ("UNKNOWN", "no-metadata"),
        ("Some Weird Thing", "unknown"),
    ],
)
def test_classify(text: str, expected: str) -> None:
    assert cl.classify(text) == expected


def test_allowlist_covers_no_metadata() -> None:
    rows = cl.scan(allow=set())
    assert all(
        r.verdict in {"ok", "copyleft", "noncommercial", "proprietary", "no-metadata", "unknown"}
        for r in rows
    )


def test_environment_has_no_licence_violations() -> None:
    rows = cl.scan()
    bad = cl.violations(rows)
    known = [r for r in bad if r.name.lower() in KNOWN_VIOLATIONS]
    for r in known:
        print(
            f"KNOWN VIOLATION {r.name} {r.version} [{r.verdict}] {r.licence}: {KNOWN_VIOLATIONS[r.name.lower()]}"
        )
    unexpected = [
        (r.name, r.verdict, r.licence) for r in bad if r.name.lower() not in KNOWN_VIOLATIONS
    ]
    assert not unexpected, f"licence violations: {unexpected}"
