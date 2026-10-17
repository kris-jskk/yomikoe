"""Classify every installed distribution by licence (policy: CLAUDE.md licensing bullet).

Usage: python scripts/check_licences.py [--json] [--allow NAME ...] [--npm WEBDIR]
Exit 0 when clean, 1 on violations.

Rules
- Permissive / OSI non-copyleft is OK: Apache, MIT, BSD, PSF, ISC, MPL-2.0 (file-level),
  BSL-1.0, Zlib, CC0, Unlicense, CNRI-Python, public domain.
- Copyleft (GPL, LGPL, AGPL, SSPL, EUPL, CeCILL) and non-commercial are violations.
- Compound expressions: "A OR B" is OK if ANY option is OK (the user may pick it);
  "A AND B" is OK only if ALL parts are OK. Only upper-case OR/AND are operators, so
  "GPL v2 or later" stays one option. AND binds tighter than OR; parentheses are ignored.
- Without an SPDX License-Expression, the License field and each License classifier are
  treated as alternative options (OR), which is how dual-licensed packages declare themselves.
- No licence metadata, or a string we cannot recognise ("Other/Proprietary"), is a
  violation unless the distribution name is on the allowlist.

npm mode (--npm WEBDIR): walks WEBDIR/node_modules/**/package.json with the same policy.
Production = `dependencies` of WEBDIR/package.json and their transitive closure
(`npm ls --omit=dev --all --json`, matched by package name); everything else is dev.
Supervisor ruling 2026-10-17 for npm: BlueOak-1.0.0 and 0BSD are allowed anywhere;
CC-BY-4.0 is allowed for DEV-ONLY data packages (currently caniuse-lite via eslint's
babel chain) and is a violation if it appears in a production dependency.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

OK, COPYLEFT, NONCOMMERCIAL, PROPRIETARY, NOMETA, UNKNOWN = (
    "ok",
    "copyleft",
    "noncommercial",
    "proprietary",
    "no-metadata",
    "unknown",
)

# Distributions with no licence metadata that were checked by hand. Keep small.
DEFAULT_ALLOW: dict[str, str] = {}

_NONCOMM = re.compile(r"non-?\s?commercial|\bcc[- ]by-nc|research (use )?only", re.IGNORECASE)
_COPYLEFT = re.compile(
    r"\b[la]?gpl|general public licen[sc]e|\bsspl\b|server side public|\beupl\b"
    r"|european union public|cecill",
    re.IGNORECASE,
)
_PERMISSIVE = re.compile(
    r"apache|\bmit\b|bsd|\bpsf|python software foundation|\bisc\b|\bmpl\b|mozilla public"
    r"|\bbsl\b|boost software|zlib|\bcc0|unlicense|public domain|\bhpnd\b|\bcnri\b",
    re.IGNORECASE,
)
_PROPRIETARY = re.compile(r"proprietary|all rights reserved", re.IGNORECASE)


def _classify_option(text: str) -> str:
    t = text.strip().strip("()").strip()
    if not t or t.upper() == "UNKNOWN":
        return NOMETA
    if _NONCOMM.search(t):
        return NONCOMMERCIAL
    if _COPYLEFT.search(t):
        return COPYLEFT
    if _PERMISSIVE.search(t):
        return OK
    if _PROPRIETARY.search(t):
        return PROPRIETARY
    return UNKNOWN


def classify(text: str) -> str:
    """Classify one licence string or SPDX-like expression."""
    ors = re.split(r"\s+OR\s+", text.replace("(", " ").replace(")", " ").strip())
    best = None
    for opt in ors:
        parts = [_classify_option(p) for p in re.split(r"\s+AND\s+", opt)]
        bad = next((p for p in parts if p != OK), None)
        verdict = bad or OK
        if verdict == OK:
            return OK
        best = best or verdict
    return best or NOMETA


def classify_options(options: list[str]) -> str:
    """Alternative licence declarations (OR): OK if any is OK, else the first problem."""
    verdicts = [classify(o) for o in options if o.strip()]
    if not verdicts:
        return NOMETA
    if OK in verdicts:
        return OK
    return next((v for v in verdicts if v not in (NOMETA, UNKNOWN)), verdicts[0])


@dataclass
class Row:
    name: str
    version: str
    verdict: str
    licence: str


def inspect(dist: md.Distribution) -> Row:
    m = dist.metadata
    expr = (m.get("License-Expression") or "").strip()
    raw = (m.get("License") or "").strip()
    raw_line = raw.splitlines()[0][:80] if raw else ""
    cls = [
        c.split("::")[-1].strip()
        for c in (m.get_all("Classifier") or [])
        if c.startswith("License ::") and c.count("::") >= 2
    ]
    if expr:
        verdict, shown = classify(expr), expr
    else:
        # Judge the first lines of the License field (full texts name the licence up top).
        head = " ".join(raw.splitlines()[:3])[:300]
        verdict = classify_options([head, *cls])
        shown = "; ".join(x for x in [raw_line, *cls] if x)
    return Row(m["Name"], m["Version"], verdict, shown or "-")


def scan(allow: set[str] | None = None) -> list[Row]:
    allowed = {a.lower().replace("_", "-") for a in (allow or set()) | set(DEFAULT_ALLOW)}
    rows = []
    for d in md.distributions():
        if not d.metadata["Name"]:
            continue
        r = inspect(d)
        if r.verdict in (NOMETA, UNKNOWN) and r.name.lower().replace("_", "-") in allowed:
            r.verdict = OK
            r.licence += " (allowlisted)"
        rows.append(r)
    return sorted(rows, key=lambda r: r.name.lower())


def violations(rows: list[Row]) -> list[Row]:
    return [r for r in rows if r.verdict != OK]


# ---- npm mode -------------------------------------------------------------------------

_BLUEOAK = re.compile(r"blue\s?oak", re.IGNORECASE)
_CCBY = re.compile(r"^\(?\s*cc-by-\d", re.IGNORECASE)


@dataclass
class NpmRow:
    name: str
    version: str
    verdict: str
    licence: str
    prod: bool


def _npm_licence(pkg: dict) -> str:
    lic = pkg.get("license")
    if isinstance(lic, dict):
        lic = lic.get("type")
    if not lic and isinstance(pkg.get("licenses"), list) and pkg["licenses"]:
        first = pkg["licenses"][0]
        lic = first.get("type") if isinstance(first, dict) else first
    return str(lic or "").strip()


def npm_verdict(lic: str, prod: bool) -> str:
    """Policy verdict for one npm licence string (see module docstring for the rulings)."""
    if _BLUEOAK.search(lic):
        return OK
    if _CCBY.match(lic):
        return PROPRIETARY if prod else OK  # dev-only data allowance
    return classify(lic)


def npm_prod_names(web: Path) -> set[str]:
    """Names in the production closure, from `npm ls --omit=dev --all --json`."""
    env = web / "scripts" / "env.sh"
    pre = f"source {shlex.quote(str(env))} && " if env.exists() else ""
    cmd = f"{pre}cd {shlex.quote(str(web))} && npm ls --omit=dev --all --json"
    out = subprocess.run(["bash", "-c", cmd], check=False, capture_output=True, text=True)
    tree = json.loads(out.stdout or "{}")
    names: set[str] = set()

    def walk(deps: dict) -> None:
        for n, d in (deps or {}).items():
            names.add(n)
            walk(d.get("dependencies", {}))

    walk(tree.get("dependencies", {}))
    return names


def scan_npm(web: Path) -> list[NpmRow]:
    prod_names = npm_prod_names(web)
    rows: dict[tuple[str, str], NpmRow] = {}
    for f in sorted((web / "node_modules").rglob("package.json")):
        try:
            pkg = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name, ver = pkg.get("name"), pkg.get("version")
        if not name or not ver:
            continue
        # only real package roots: <...>/node_modules/<name>/package.json
        rel = f.relative_to(web / "node_modules").parent.as_posix()
        if rel != name and not rel.endswith("/node_modules/" + name):
            continue
        key = (name, ver)
        if key in rows:
            continue
        lic = _npm_licence(pkg)
        prod = name in prod_names
        rows[key] = NpmRow(name, ver, npm_verdict(lic, prod), lic or "-", prod)
    return sorted(rows.values(), key=lambda r: r.name.lower())


def main_npm(web_dir: str, as_json: bool) -> int:
    web = Path(web_dir).resolve()
    if not (web / "node_modules").is_dir():
        print(f"no node_modules under {web}", file=sys.stderr)
        return 2
    rows = scan_npm(web)
    bad = [r for r in rows if r.verdict != OK]
    if as_json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
    else:
        tally: Counter[tuple[str, str]] = Counter(
            ("prod" if r.prod else "dev", r.licence) for r in rows
        )
        for scope in ("prod", "dev"):
            print(f"[{scope}]")
            for (sc, lic), n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0][1])):
                if sc == scope:
                    print(f"  {n:4} {lic}")
        print("production closure:", ", ".join(r.name for r in rows if r.prod))
        for r in bad:
            print(f"VIOLATION {r.name}@{r.version} [{r.verdict}] {r.licence} prod={r.prod}")
    nprod = sum(r.prod for r in rows)
    print(
        f"TOTAL {len(rows)} (prod {nprod}, dev {len(rows) - nprod})  "
        f"VIOLATIONS {len(bad)} {[r.name for r in bad]}",
        file=sys.stderr if as_json else sys.stdout,
    )
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow", action="append", default=[], metavar="NAME")
    ap.add_argument("--npm", metavar="WEBDIR", help="scan WEBDIR/node_modules instead")
    args = ap.parse_args(argv)
    if args.npm:
        return main_npm(args.npm, args.json)
    rows = scan(set(args.allow))
    bad = violations(rows)
    if args.json:
        print(json.dumps([asdict(r) for r in rows], indent=2))
    else:
        print(f"{'name':32} {'version':14} {'verdict':14} licence")
        for r in rows:
            print(f"{r.name:32} {r.version:14} {r.verdict:14} {r.licence}")
    summary = f"TOTAL {len(rows)}  VIOLATIONS {len(bad)} {[r.name for r in bad]}"
    print(summary, file=sys.stderr if args.json else sys.stdout)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
