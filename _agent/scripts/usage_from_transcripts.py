#!/usr/bin/env python3
"""Observed usage and cost from transcripts (never typed by hand).

Reads every tasks/*.output subagent transcript of this project's sessions, plus the main
session transcripts (the supervisor), and records per agent: the TASK line from the brief,
the MODEL the brief requested, the model that actually answered, tokens by class and dollars
summed over every API call. Keeps a cache at _agent/registry/task-usage.json so rows survive
transcript cleanup, and writes _agent/token-ledger.md.

A transcript writes one line per content block, and every line of one API response repeats
that response's usage block. Calls are therefore counted once per message id, with the usage
of the last line seen for that id (output_tokens grows while the response streams).

Columns (all from the API usage blocks):
  Started          = first timestamp in the transcript (UTC)
  Task             = the TASK line of the brief (or the first 60 characters of the prompt);
                     "supervisor (session <id>)" for a main session
  Model (observed) = the model that answered most calls
  Requested        = the MODEL line of the brief
  Turns / Tools    = API calls (unique message ids) / tool_use blocks (unique ids)
  Final prompt     = input + cache_read + cache_create on the last call (what the harness
                     reports at completion; a context size, not consumption)
  New              = input + cache_create over all calls (tokens processed for the first time)
  Cache read       = cache_read over all calls (prefix re-read each call)
  Output           = output over all calls
  Weighted input   = input + 1.25 x cache_create + 0.10 x cache_read (legacy proxy in
                     input-token units, kept for continuity; Cost $ supersedes it)
  Cost $           = per call: input x in + cache_write_5m x w5m + cache_write_1h x w1h
                     + cache_read x read + output x out, rates per million from RATES
  Model rate       = blank when the call's model is in RATES; otherwise the fallback used

Default globs are derived from the current working directory (run it from the project root;
the SubagentStop hook does):
  subagents:  /private/tmp/claude-<uid>/<cwd with every "/" replaced by "-">/*/tasks/*.output
  sessions:   ~/.claude/projects/<cwd with every "/" replaced by "-">/*.jsonl

Run with:  python3 _agent/scripts/usage_from_transcripts.py [--verbose]
Test with: python3 _agent/scripts/usage_from_transcripts.py --transcripts 'GLOB' --out PATH
  (with --transcripts, the cache is neither read nor written unless --registry is given, and
  no session transcripts are read unless --sessions is given, so test rows never enter this
  project's ledger; --redact-tasks replaces task text with the agent id)
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = 2

# USD per million tokens. Source and date of the last check:
RATES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing.md"
RATES_CHECKED = "2026-10-17"
RATES: dict[str, dict] = {
    "claude-fable-5-1": {
        "input": 10.0,
        "write_5m": 12.5,
        "write_1h": 20.0,
        "read": 0.25,
        "output": 50.0,
    },
    "claude-opus-5-5": {
        "input": 4.0,
        "write_5m": 5.0,
        "write_1h": 8.0,
        "read": 0.20,
        "output": 20.0,
    },
    "claude-sonnet-5-5": {
        "input": 2.0,
        "write_5m": 2.5,
        "write_1h": 4.0,
        "read": 0.10,
        "output": 10.0,
    },
    # Haiku 5.5 is tiered on the prompt size of the call.
    "claude-haiku-5-5": {
        "input": 0.10,
        "write_5m": 0.125,
        "write_1h": 0.20,
        "read": 0.01,
        "output": 0.50,
        "over_100k": {
            "input": 0.50,
            "write_5m": 0.625,
            "write_1h": 1.0,
            "read": 0.05,
            "output": 2.50,
        },
    },
}
FALLBACK_MODEL = "claude-opus-5-5"
CLASSES = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
RATE_KEY = {
    "input": "input",
    "cache_write_5m": "write_5m",
    "cache_write_1h": "write_1h",
    "cache_read": "read",
    "output": "output",
}


def rate_for(model: str | None, prompt_tokens: int = 0) -> tuple[dict, str]:
    """Rates for a model id (prefix match, so dated or suffixed ids resolve) and a flag."""
    for key in sorted(RATES, key=len, reverse=True):
        if model and model.startswith(key):
            r = RATES[key]
            if "over_100k" in r and prompt_tokens > 100_000:
                return r["over_100k"], ""
            return r, ""
    return RATES[FALLBACK_MODEL], f"fallback {FALLBACK_MODEL} for {model}"


def usage_classes(u: dict) -> dict[str, int]:
    """Split one usage block into billing classes."""
    cc_total = u.get("cache_creation_input_tokens") or 0
    br = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
    w1h = br.get("ephemeral_1h_input_tokens") or 0
    w5m = br.get("ephemeral_5m_input_tokens") or 0
    w5m += max(cc_total - w1h - w5m, 0)  # no breakdown: treat as 5-minute writes
    return {
        "input": u.get("input_tokens") or 0,
        "cache_write_5m": w5m,
        "cache_write_1h": w1h,
        "cache_read": u.get("cache_read_input_tokens") or 0,
        "output": u.get("output_tokens") or 0,
    }


def call_cost(model: str | None, u: dict) -> tuple[dict[str, float], str]:
    """Dollar cost of one API call by class, and the rate flag."""
    t = usage_classes(u)
    prompt = t["input"] + t["cache_write_5m"] + t["cache_write_1h"] + t["cache_read"]
    r, flag = rate_for(model, prompt)
    return {k: t[k] * r[RATE_KEY[k]] / 1e6 for k in CLASSES}, flag


def _text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def summarize(path: str, kind: str = "task") -> dict:
    """One ledger row from a transcript. kind is "task" (tasks/*.output) or "supervisor"."""
    calls: dict[str, tuple[str | None, dict]] = {}
    tool_ids: set = set()
    ts: list[str] = []
    task = brief_model = None
    brief_chars = 0
    nonstandard_speed = 0
    with open(path, errors="ignore") as fh:
        lines = fh.readlines()
    for n, line in enumerate(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or (kind == "supervisor" and d.get("isSidechain")):
            continue
        if d.get("timestamp"):
            ts.append(d["timestamp"])
        m = d.get("message") or {}
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if d.get("type") == "user" and task is None and kind == "task":
            text = _text(c)
            brief_chars = len(text)
            mt = re.search(r"TASK\s+(\S+)", text)
            task = (
                mt.group(1) if mt else (re.sub(r"\s+", " ", text.strip())[:60] or None)
            )
            mm = re.search(r"MODEL\s+(\w+)", text)
            brief_model = mm.group(1) if mm else None
        if d.get("type") == "assistant":
            calls[m.get("id") or f"line{n}"] = (m.get("model"), m.get("usage") or {})
            if isinstance(c, list):
                for x in c:
                    if isinstance(x, dict) and x.get("type") == "tool_use":
                        tool_ids.add(x.get("id") or f"{n}:{len(tool_ids)}")
    models: dict[str, int] = {}
    tok = {k: 0 for k in CLASSES}
    cost = {k: 0.0 for k in CLASSES}
    flags: set = set()
    last_prompt = 0
    for model, u in calls.values():
        if model:
            models[model] = models.get(model, 0) + 1
        t = usage_classes(u)
        for k in CLASSES:
            tok[k] += t[k]
        cc, flag = call_cost(model, u)
        for k in CLASSES:
            cost[k] += cc[k]
        if flag:
            flags.add(flag)
        if u.get("speed") not in (None, "standard"):
            nonstandard_speed += 1
        last_prompt = (
            t["input"] + t["cache_write_5m"] + t["cache_write_1h"] + t["cache_read"]
        )
    if nonstandard_speed:
        flags.add(f"{nonstandard_speed} calls at non-standard speed, priced standard")
    stem = os.path.basename(path).rsplit(".", 1)[0]
    if kind == "supervisor":
        session, agent, task = (
            stem,
            f"supervisor:{stem}",
            f"supervisor (session {stem[:8]})",
        )
    else:
        session, agent = os.path.basename(os.path.dirname(os.path.dirname(path))), stem
    cache_create = tok["cache_write_5m"] + tok["cache_write_1h"]
    return {
        "schema": SCHEMA,
        "kind": kind,
        "agent": agent,
        "session": session,
        "task": task,
        "brief_model": brief_model,
        "brief_chars": brief_chars,
        "models": models,
        "model_observed": max(models, key=models.get) if models else None,
        "tokens": dict(tok, cache_create=cache_create),
        "cost": round(sum(cost.values()), 6),
        "cost_by_class": {k: round(v, 6) for k, v in cost.items()},
        "rate_flag": "; ".join(sorted(flags)),
        "final_prompt": last_prompt,
        "new_tokens": tok["input"] + cache_create,
        "weighted_input": int(
            tok["input"] + 1.25 * cache_create + 0.10 * tok["cache_read"]
        ),
        "assistant_turns": len(calls),
        "tool_calls": len(tool_ids),
        "started": min(ts) if ts else None,
        "ended": max(ts) if ts else None,
        "transcript": path,
        "summarized_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }


def upgrade_legacy(r: dict) -> dict:
    """A cached row whose transcript is gone: price its summed tokens at the observed model."""
    if r.get("schema") == SCHEMA:
        return r
    t = r["tokens"]
    u = {
        "input_tokens": t.get("input", 0),
        "output_tokens": t.get("output", 0),
        "cache_creation_input_tokens": t.get("cache_create", 0),
        "cache_read_input_tokens": t.get("cache_read", 0),
    }
    cc, flag = call_cost(r.get("model_observed"), u)
    tok = usage_classes(u)
    r = dict(r, kind="task", brief_chars=r.get("brief_chars", 0))
    r["session"] = r.get("session") or os.path.basename(
        os.path.dirname(os.path.dirname(r.get("transcript", "")))
    )
    r["tokens"] = dict(tok, cache_create=t.get("cache_create", 0))
    r["cost_by_class"] = cc
    r["cost"] = round(sum(cc.values()), 6)
    r["rate_flag"] = "; ".join(
        x for x in (flag, "legacy row: transcript gone, tokens not de-duplicated") if x
    )
    return r


def milestone(r: dict) -> str:
    if r["kind"] == "supervisor":
        return "supervisor"
    m = re.match(r"(m\d+)-", r.get("task") or "")
    return m.group(1) if m else "other"


def totals(rows: list[dict]) -> dict:
    t = {k: 0 for k in CLASSES}
    for r in rows:
        for k in CLASSES:
            t[k] += r["tokens"].get(k, 0)
    t["rows"] = len(rows)
    t["cost"] = sum(r["cost"] for r in rows)
    return t


def driver(r: dict) -> str:
    """One line naming the cost class that dominated a row, from its numbers."""
    cb, cost = r["cost_by_class"], r["cost"] or 1e-9
    top = max(cb, key=cb.get)
    share = cb[top] / cost
    t = r["tokens"]
    if top == "cache_read":
        return (
            f"prefix re-read over {r['assistant_turns']} turns: {t['cache_read'] / 1e6:.1f}M cache-read tokens "
            f"({share:.0%} of cost)"
        )
    if top.startswith("cache_write"):
        return (
            f"new context written to cache: {(t['cache_write_5m'] + t['cache_write_1h']) / 1e3:.0f}k tokens "
            f"({share:.0%} of cost)"
        )
    if top == "output":
        return f"long outputs: {t['output']:,} output tokens ({share:.0%} of cost)"
    return f"uncached input: {t['input']:,} tokens ({share:.0%} of cost)"


def levers(rows: list[dict]) -> list[str]:
    tasks = [r for r in rows if r["kind"] == "task"]
    total = sum(r["cost"] for r in rows) or 1e-9
    out = []
    small_opus = [
        r
        for r in tasks
        if "opus" in (r.get("model_observed") or "") and r["tool_calls"] < 15
    ]
    s_cost = sum(r["cost"] for r in small_opus)
    s_sonnet = 0.0
    for r in small_opus:
        t = r["tokens"]
        u = {
            "input_tokens": t["input"],
            "output_tokens": t["output"],
            "cache_creation_input_tokens": t["cache_write_5m"] + t["cache_write_1h"],
            "cache_creation": {
                "ephemeral_5m_input_tokens": t["cache_write_5m"],
                "ephemeral_1h_input_tokens": t["cache_write_1h"],
            },
            "cache_read_input_tokens": t["cache_read"],
        }
        s_sonnet += sum(call_cost("claude-sonnet-5-5", u)[0].values())
    out.append(
        f"**Opus tasks under 15 tool calls** (Sonnet candidates): {len(small_opus)} tasks, ${s_cost:,.2f}; "
        f"the same tokens at Sonnet 5.5 rates would be ${s_sonnet:,.2f} (saving ${s_cost - s_sonnet:,.2f}, "
        "assuming Sonnet used the same tokens, which is unverified)."
    )
    saved = 0.0
    for r in tasks:
        if not r.get("brief_chars"):
            continue
        rate, _ = rate_for(r.get("model_observed"))
        brief_tok = r["brief_chars"] / 4
        saved += 0.30 * brief_tok * r["assistant_turns"] * rate["read"] / 1e6
    out.append(
        f"**Briefs 30 % shorter**: about ${saved:,.2f} of cache-read cost saved. Proportional estimate: "
        "brief tokens taken as characters / 4, re-read once per turn at the model's cache-read rate; "
        "turns held constant."
    )
    # whole words of the task slug, so "m1-fixtures" is not a fix
    rerun = [
        r
        for r in tasks
        if re.search(r"(^|-)(fix|red|tighten)(-|$)", r.get("task") or "")
    ]
    out.append(
        f"**Evidence re-runs** (task-name words fix / red / tighten): {len(rerun)} tasks, "
        f"${sum(r['cost'] for r in rerun):,.2f}"
        + (f" ({', '.join(sorted(r['task'] for r in rerun))})." if rerun else ".")
    )
    sup = sum(r["cost"] for r in rows if r["kind"] == "supervisor")
    out.append(
        f"**Supervisor vs workers**: supervisor sessions ${sup:,.2f} ({sup / total:.0%}), "
        f"workers ${total - sup:,.2f} ({(total - sup) / total:.0%})."
    )
    return out


def _tot_row(label: str, t: dict) -> str:
    return (
        f"| {label} | {t['rows']} | {t['input']:,} | {t['cache_write_5m']:,} | {t['cache_write_1h']:,} | "
        f"{t['cache_read']:,} | {t['output']:,} | {t['cost']:,.2f} |\n"
    )


def write_ledger(rows: list[dict], path: str, redact: bool = False) -> None:
    def name(r):
        return (
            r["agent"]
            if redact and r["kind"] == "task"
            else (r["task"] or "").replace("|", "/")
        )

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as out:
        out.write(
            "# Token ledger, observed\n\nGenerated by `_agent/scripts/usage_from_transcripts.py` from the subagent and "
            "main-session transcripts; do not edit. `Model (observed)` is the model that answered, not the one "
            "requested. Columns are defined in the script docstring: **Final prompt** is the context size at the last "
            "call (what the harness reports at completion, not consumption); **New** = input + cache-creation tokens; "
            "**Cache read** = prefix re-read on every call; **Weighted input** is the legacy proxy (1.25 x cache-create "
            "+ 0.10 x cache-read); **Cost $** is priced per call from the rates below.\n\n"
        )
        out.write(
            f"## Rates (USD per million tokens)\n\nSource: {RATES_SOURCE}, checked {RATES_CHECKED}.\n\n"
        )
        out.write(
            "| Model | Input | Cache write 5m | Cache write 1h | Cache read | Output |\n|---|---:|---:|---:|---:|---:|\n"
        )
        for k, r in RATES.items():
            out.write(
                f"| {k} | {r['input']} | {r['write_5m']} | {r['write_1h']} | {r['read']} | {r['output']} |\n"
            )
            if "over_100k" in r:
                o = r["over_100k"]
                out.write(
                    f"| {k} (prompt > 100k) | {o['input']} | {o['write_5m']} | {o['write_1h']} | {o['read']} | {o['output']} |\n"
                )
        out.write(
            f"\nModels not in the table are priced at {FALLBACK_MODEL} and flagged in `Model rate`.\n\n"
        )

        out.write(
            "## Tasks\n\n| Started | Task | Model (observed) | Requested | Turns | Tools | Final prompt | New | Cache read "
            "| Output | Weighted input | Cost $ | Model rate |\n|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
        )
        for r in rows:
            out.write(
                f"| {(r['started'] or '')[:16]} | {name(r)} | {r['model_observed']} | {r.get('brief_model') or '-'} | "
                f"{r['assistant_turns']} | {r['tool_calls']} | {r['final_prompt']:,} | {r['new_tokens']:,} | "
                f"{r['tokens']['cache_read']:,} | {r['tokens']['output']:,} | {r['weighted_input']:,} | "
                f"{r['cost']:,.2f} | {r.get('rate_flag') or ''} |\n"
            )

        head = "| Group | Rows | Input | Cache write 5m | Cache write 1h | Cache read | Output | Cost $ |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
        out.write("\n## Totals\n\n### By session\n\n" + head)
        out.writelines(
            _tot_row(f"session {s[:8]}", totals([r for r in rows if r["session"] == s]))
            for s in sorted({r["session"] for r in rows})
        )
        out.write("\n### By milestone (task-name prefix)\n\n" + head)
        for g in ("m1", "m2", "m3", "m4", "other", "supervisor"):
            grp = [r for r in rows if milestone(r) == g]
            if grp:
                out.write(_tot_row(g, totals(grp)))
        out.write("\n### Project\n\n" + head + _tot_row("project total", totals(rows)))

        out.write(f"\n## Cost review ({datetime.date.today().isoformat()})\n\n")
        out.write(
            "Ten most expensive rows. Cache-read share = cache-read dollars / row dollars.\n\n"
            "| # | Task | Model | Cost $ | Turns | Final prompt | Cache-read share | Driver |\n"
            "|---:|---|---|---:|---:|---:|---:|---|\n"
        )
        for i, r in enumerate(sorted(rows, key=lambda r: -r["cost"])[:10], 1):
            share = r["cost_by_class"]["cache_read"] / (r["cost"] or 1e-9)
            out.write(
                f"| {i} | {name(r)} | {r['model_observed']} | {r['cost']:,.2f} | {r['assistant_turns']} | "
                f"{r['final_prompt']:,} | {share:.0%} | {driver(r)} |\n"
            )
        out.write("\n### Levers\n\n" + "".join(f"- {x}\n" for x in levers(rows)))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write the observed token ledger from transcripts."
    )
    ap.add_argument(
        "--transcripts",
        help="glob of subagent transcript files (default: derived from cwd)",
    )
    ap.add_argument(
        "--sessions",
        help="glob of main-session jsonl files (default: derived from cwd, unless --transcripts)",
    )
    ap.add_argument(
        "--out",
        default=os.path.join(AGENT_DIR, "token-ledger.md"),
        help="markdown ledger to write",
    )
    ap.add_argument(
        "--registry",
        help="JSON cache (default: _agent/registry/task-usage.json, unless --transcripts is given)",
    )
    ap.add_argument(
        "--redact-tasks",
        action="store_true",
        help="write the agent id instead of the task text",
    )
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    slug = os.getcwd().replace("/", "-")
    pattern = (
        a.transcripts or f"/private/tmp/claude-{os.getuid()}/{slug}/*/tasks/*.output"
    )
    sessions = a.sessions or (
        None
        if a.transcripts
        else os.path.expanduser(f"~/.claude/projects/{slug}/*.jsonl")
    )
    reg_path = a.registry or (
        None
        if a.transcripts
        else os.path.join(AGENT_DIR, "registry", "task-usage.json")
    )
    if a.verbose:
        print(f"transcript glob: {pattern}\nsession glob: {sessions or '(none)'}")
        print(f"registry: {reg_path or '(none)'}; out: {a.out}")
    reg: dict = {}
    if reg_path and os.path.exists(reg_path):
        try:
            with open(reg_path) as fh:
                reg = json.load(fh)
        except ValueError:
            reg = {}
    files = glob.glob(pattern)
    sfiles = glob.glob(sessions) if sessions else []
    for f, kind in [(f, "task") for f in files] + [(f, "supervisor") for f in sfiles]:
        s = summarize(f, kind)
        if s["assistant_turns"]:
            reg[s["agent"]] = s
    reg = {k: upgrade_legacy(v) for k, v in reg.items()}
    if reg_path:
        os.makedirs(os.path.dirname(reg_path), exist_ok=True)
        with open(reg_path, "w") as fh:
            json.dump(reg, fh, indent=1)

    rows = sorted(reg.values(), key=lambda r: r["started"] or "")
    write_ledger(rows, a.out, a.redact_tasks)
    print(
        f"{len(files)} transcripts and {len(sfiles)} sessions read; {len(rows)} rows in ledger; "
        f"total ${sum(r['cost'] for r in rows):,.2f}; {a.out} written"
    )
    for r in rows:
        if (
            r.get("brief_model")
            and r["model_observed"]
            and r["brief_model"] not in r["model_observed"]
        ):
            print(
                "MODEL MISMATCH:",
                r["agent"] if a.redact_tasks else r["task"],
                r["brief_model"],
                "->",
                r["model_observed"],
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
