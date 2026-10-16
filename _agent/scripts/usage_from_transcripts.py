#!/usr/bin/env python3
"""Observed subagent usage from transcripts (never typed by hand).

Reads every tasks/*.output subagent transcript of this project's sessions and records, per
agent: the TASK line from the brief, the MODEL the brief requested, the model that actually
answered, and tokens by class summed over every API call. Keeps a cache at
_agent/registry/task-usage.json so rows survive transcript cleanup, and writes
_agent/token-ledger.md.

Columns (all from the API usage blocks):
  Started          = first timestamp in the transcript (UTC)
  Task             = the TASK line of the brief (or the first 60 characters of the prompt)
  Model (observed) = the model that answered most assistant turns
  Requested        = the MODEL line of the brief
  Turns / Tools    = assistant turns / tool_use blocks
  Final prompt     = input + cache_read + cache_create on the last call (what the harness
                     reports at completion; a context size, not consumption)
  New              = input + cache_create over all calls (tokens processed for the first time)
  Cache read       = cache_read over all calls (prefix re-read each call, billed ~10%)
  Output           = output over all calls
  Weighted input   = input + 1.25 x cache_create + 0.10 x cache_read (standard cache
                     multipliers; a cost proxy in input-token units; output listed apart)

Default transcript glob is derived from the current working directory:
  /private/tmp/claude-<uid>/<cwd with every "/" replaced by "-">/*/tasks/*.output
so run it from the project root (the SubagentStop hook does).

Run with:  python3 _agent/scripts/usage_from_transcripts.py [--verbose]
Test with: python3 _agent/scripts/usage_from_transcripts.py --transcripts 'GLOB' --out PATH
  (with --transcripts, the cache is neither read nor written unless --registry is given, so
  test rows never enter this project's ledger; --redact-tasks replaces task text with the
  agent id, for transcripts from other projects)
"""
import argparse, datetime, glob, json, os, re, sys

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_glob():
    return f'/private/tmp/claude-{os.getuid()}/{os.getcwd().replace("/", "-")}/*/tasks/*.output'


def summarize(path):
    models, turns, tools, ts, task, brief_model = {}, 0, 0, [], None, None
    tok = dict(input=0, output=0, cache_create=0, cache_read=0); last_prompt = 0
    for line in open(path, errors='ignore'):
        try: d = json.loads(line)
        except Exception: continue
        if not isinstance(d, dict): continue
        if d.get('timestamp'): ts.append(d['timestamp'])
        m = d.get('message') or {}
        if not isinstance(m, dict): continue
        c = m.get('content')
        if d.get('type') == 'user' and task is None:
            text = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in c if isinstance(x, dict)) if isinstance(c, list) else ''
            mt = re.search(r'TASK\s+(\S+)', text)
            task = mt.group(1) if mt else (re.sub(r'\s+', ' ', text.strip())[:60] or None)
            mm = re.search(r'MODEL\s+(\w+)', text); brief_model = mm.group(1) if mm else None
        if d.get('type') == 'assistant':
            turns += 1
            if m.get('model'): models[m['model']] = models.get(m['model'], 0) + 1
            u = m.get('usage') or {}
            i, o, cc, cr = (u.get('input_tokens') or 0), (u.get('output_tokens') or 0), (u.get('cache_creation_input_tokens') or 0), (u.get('cache_read_input_tokens') or 0)
            tok['input'] += i; tok['output'] += o; tok['cache_create'] += cc; tok['cache_read'] += cr
            last_prompt = i + cc + cr
            if isinstance(c, list): tools += sum(1 for x in c if isinstance(x, dict) and x.get('type') == 'tool_use')
    return dict(agent=os.path.basename(path).replace('.output', ''), task=task, brief_model=brief_model,
                models=models, model_observed=max(models, key=models.get) if models else None,
                tokens=tok, final_prompt=last_prompt, new_tokens=tok['input'] + tok['cache_create'],
                weighted_input=int(tok['input'] + 1.25 * tok['cache_create'] + 0.10 * tok['cache_read']),
                assistant_turns=turns, tool_calls=tools, started=min(ts) if ts else None, ended=max(ts) if ts else None,
                transcript=path, summarized_at=datetime.datetime.now().isoformat(timespec='seconds'))


def main():
    ap = argparse.ArgumentParser(description='Write the observed token ledger from subagent transcripts.')
    ap.add_argument('--transcripts', help='glob of transcript files (default: derived from cwd)')
    ap.add_argument('--out', default=os.path.join(AGENT_DIR, 'token-ledger.md'), help='markdown ledger to write')
    ap.add_argument('--registry', help='JSON cache (default: _agent/registry/task-usage.json, unless --transcripts is given)')
    ap.add_argument('--redact-tasks', action='store_true', help='write the agent id instead of the task text')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    pattern = a.transcripts or default_glob()
    reg_path = a.registry or (None if a.transcripts else os.path.join(AGENT_DIR, 'registry', 'task-usage.json'))
    if a.verbose:
        print(f'transcript glob: {pattern}')
        print(f'registry: {reg_path or "(none)"}; out: {a.out}')
    reg = {}
    if reg_path and os.path.exists(reg_path):
        try: reg = json.load(open(reg_path))
        except Exception: reg = {}
    files = glob.glob(pattern)
    for f in files:
        s = summarize(f)
        if s['assistant_turns']: reg[s['agent']] = s
    if reg_path:
        os.makedirs(os.path.dirname(reg_path), exist_ok=True)
        json.dump(reg, open(reg_path, 'w'), indent=1)

    rows = sorted(reg.values(), key=lambda r: r['started'] or '')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w') as out:
        out.write('# Token ledger, observed\n\nGenerated by `_agent/scripts/usage_from_transcripts.py` from the subagent transcripts; do not edit. '
                  '`Model (observed)` is the model that answered, not the one requested. Columns are defined in the script docstring: '
                  '**Final prompt** is the context size at the last call (what the harness reports at completion, not consumption); '
                  '**New** = input + cache-creation tokens; **Cache read** = prefix re-read on every call; '
                  '**Weighted input** = input + 1.25 x cache-create + 0.10 x cache-read, a cost proxy in input-token units, with output listed apart.\n\n')
        out.write('| Started | Task | Model (observed) | Requested | Turns | Tools | Final prompt | New | Cache read | Output | Weighted input |\n'
                  '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|\n')
        for r in rows:
            task = r['agent'] if a.redact_tasks else (r['task'] or '').replace('|', '/')
            out.write(f"| {(r['started'] or '')[:16]} | {task} | {r['model_observed']} | {r['brief_model'] or '-'} | {r['assistant_turns']} | {r['tool_calls']} | "
                      f"{r['final_prompt']:,} | {r['new_tokens']:,} | {r['tokens']['cache_read']:,} | {r['tokens']['output']:,} | {r['weighted_input']:,} |\n")
    print(f'{len(files)} transcripts read; {len(rows)} agents in ledger; {a.out} written')
    for r in rows:
        if r['brief_model'] and r['model_observed'] and r['brief_model'] not in r['model_observed']:
            print('MODEL MISMATCH:', r['agent'] if a.redact_tasks else r['task'], r['brief_model'], '->', r['model_observed'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
