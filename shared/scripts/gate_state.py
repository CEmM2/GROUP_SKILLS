#!/usr/bin/env python3
"""gate_state.py — deterministic gate-file + task-JSON operations for AutViam.

Owns the mechanical, error-prone work the LLM should NOT do by hand:
  - gate-failure COUNTING and cap detection (the non-negotiable 3-failure cap)
  - per-task gate-file section init + Failure-counters line maintenance
  - task-JSON completion writeback / status set / rollback reset (fixed schema)
  - last-good Gate C commit SHA lookup (for rollback)
  - Session Reset Packet fact assembly

The LLM still authors the prose attempt blocks (domain language for BM25/semantic
search) and the Decision / Gate-Findings narrative; this script parses, counts, and
writes the machine state so it cannot drift across context compaction.

Gate-file format: templates/gate_entry.md. JSON attempt blocks are ```json fenced
inside each "## <task_id>: <title>" section. The cap block "## STATUS: …" belongs to
the task section above it (not a new task).
"""
import sys
import os
import json
import re
import argparse
import datetime
import glob

TASK_HDR = re.compile(r'^## (?!STATUS:)(.+?):\s*(.*)$')   # "## <id>: <title>", excludes "## STATUS:"
JSON_BLOCK = re.compile(r'```json\s*\n(.*?)\n```', re.DOTALL)
COUNTERS_LINE = re.compile(r'^\*\*Failure counters:\*\*.*$', re.MULTILINE)
GATES = ("A", "B", "C")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _dump_json(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4)
        f.write("\n")


def _sections(text):
    """Yield (task_id, start_offset, end_offset) for each task section."""
    lines = text.splitlines(keepends=True)
    offsets, o = [], 0
    for ln in lines:
        offsets.append(o)
        o += len(ln)
    heads = []
    for i, ln in enumerate(lines):
        m = TASK_HDR.match(ln.rstrip('\n'))
        if m:
            heads.append((m.group(1).strip(), offsets[i]))
    for j, (tid, start) in enumerate(heads):
        end = heads[j + 1][1] if j + 1 < len(heads) else len(text)
        yield tid, start, end


def _section(text, task_id):
    for tid, s, e in _sections(text):
        if tid == task_id:
            return text[s:e], s, e
    return None, None, None


def count_fails(text, task_id, gate):
    sec, _, _ = _section(text, task_id)
    if sec is None:
        return 0
    n = 0
    for blk in JSON_BLOCK.findall(sec):
        try:
            d = json.loads(blk)
        except Exception:
            continue
        if str(d.get("gate", "")).upper() == gate.upper() and d.get("result") == "fail":
            n += 1
    return n


def all_counts(text, task_id):
    return {g: count_fails(text, task_id, g) for g in GATES}


# ----------------------------- subcommands ---------------------------------- #

def cmd_count(a):
    print(count_fails(_read(a.gates), a.task_id, a.gate))


def cmd_counters(a):
    c = all_counts(_read(a.gates), a.task_id)
    print(f"A={c['A']} B={c['B']} C={c['C']}")


def cmd_sync_counters(a):
    text = _read(a.gates)
    sec, s, e = _section(text, a.task_id)
    if sec is None:
        sys.exit(f"no section for task {a.task_id}")
    c = all_counts(text, a.task_id)
    line = f"**Failure counters:** A={c['A']} B={c['B']} C={c['C']}"
    if COUNTERS_LINE.search(sec):
        new_sec = COUNTERS_LINE.sub(line, sec, count=1)
    else:  # insert after the **Started:** line if present, else after the header
        lines = sec.splitlines(keepends=True)
        out, inserted = [], False
        for ln in lines:
            out.append(ln)
            if not inserted and ln.startswith("**Started:**"):
                out.append(line + "\n")
                inserted = True
        if not inserted:
            out.insert(1, line + "\n")
        new_sec = "".join(out)
    _write(a.gates, text[:s] + new_sec + text[e:])
    print(line)


def cmd_cap_check(a):
    n = count_fails(_read(a.gates), a.task_id, a.gate)
    print(f"CAP-HIT {n}" if n >= 4 else f"OK {n}")


def cmd_init(a):
    if os.path.exists(a.gates) and _read(a.gates).strip():
        print(f"exists: {a.gates}")
        return
    os.makedirs(os.path.dirname(a.gates) or ".", exist_ok=True)
    _write(a.gates, f"# Phase {a.phase} Gate History\n\n"
                    f"Plan: `{a.plan}` · Branch: `{a.branch}`\n\n---\n")
    print(f"wrote {a.gates}")


def cmd_init_task(a):
    text = _read(a.gates) if os.path.exists(a.gates) else ""
    if _section(text, a.task_id)[0] is not None:
        print(f"task section exists: {a.task_id}")
        return
    started = a.started or datetime.date.today().isoformat()
    block = (f"\n## {a.task_id}: {a.title}\n\n"
             f"**Started:** {started} · **Completed:** in progress\n"
             f"**Failure counters:** A=0 B=0 C=0\n\n"
             f"### Gate A — Spec Compliance\n\n"
             f"### Gate B — Domain Quality\n\n"
             f"### Gate C — Verification\n")
    _write(a.gates, (text.rstrip("\n") + "\n" if text else "") + block)
    print(f"added section for {a.task_id}")


def cmd_last_good_sha(a):
    text = _read(a.gates)
    best = None
    for blk in JSON_BLOCK.findall(text):
        try:
            d = json.loads(blk)
        except Exception:
            continue
        if str(d.get("gate", "")).upper() == "C" and d.get("result") == "pass" and d.get("commit"):
            best = d["commit"]  # last one wins (most recent)
    if best:
        print(best)
    else:
        sys.exit("no passing Gate C commit found")


COMPLETION_FIELDS = ["completion_date", "test_completion", "review_score",
                     "review_breakdown", "review_status", "implementation_branch",
                     "completion_notes"]


def cmd_complete(a):
    t = _load_json(a.task_json)
    total = a.total
    rate = round(100 * a.passed / total) if total else 0
    t["status"] = "done"
    t["completion_date"] = a.date or datetime.date.today().isoformat()
    t["test_completion"] = {"passed": a.passed, "total": total,
                            "pass_rate": rate, "commands": a.commands or []}
    t["review_score"] = a.review_score
    t["review_breakdown"] = {"minor": a.minor, "medium": a.medium,
                             "high": a.high, "critical": a.critical}
    t["review_status"] = "approved"
    t["implementation_branch"] = a.branch
    if a.notes:
        t["completion_notes"] = a.notes
    _dump_json(a.task_json, t)
    print(f"completed {os.path.basename(a.task_json)} (pass_rate={rate})")


def cmd_set_status(a):
    t = _load_json(a.task_json)
    t["status"] = a.status          # leave other completion fields untouched (Step 7.2)
    _dump_json(a.task_json, t)
    print(f"status={a.status}")


def cmd_reset_task(a):
    t = _load_json(a.task_json)
    t["status"] = "pending"
    t["completion_date"] = ""
    t["test_completion"] = {"passed": 0, "total": 0, "pass_rate": 0, "commands": []}
    t["review_score"] = 0
    t["review_breakdown"] = {"minor": 0, "medium": 0, "high": 0, "critical": 0}
    t["review_status"] = ""
    t["implementation_branch"] = ""
    t["completion_notes"] = []
    _dump_json(a.task_json, t)
    print(f"reset {os.path.basename(a.task_json)} to pending")


def cmd_reset_packet(a):
    """Emit Session Reset Packet table rows with the deterministic cells filled.
    Gate A/B scores and Decision stay '?' for the LLM (scores aren't all stored; Decision is judgment)."""
    gates_text = _read(a.gates) if os.path.exists(a.gates) else ""
    rows = []
    for fp in sorted(glob.glob(os.path.join(a.json_dir, "*.json"))):
        try:
            t = _load_json(fp)
        except Exception:
            continue
        tid = t.get("task_id", os.path.splitext(os.path.basename(fp))[0])
        title = t.get("title", "")
        status = t.get("status", "")
        tc = t.get("test_completion") or {}
        gate_c = (f"{tc.get('passed', 0)}/{tc.get('total', 0)}"
                  if tc.get("total") else "not-run")
        rev = t.get("review_score")
        gate_b = f"{rev}/10" if (status == "done" and rev) else "?"
        rows.append(f"| {tid} | {title} | {status} | ? | {gate_b} | {gate_c} | ? |")
    print("| Task ID | Title | Status | Gate A Score | Gate B Score | Gate C | Decision |")
    print("|---------|-------|--------|--------------|--------------|--------|----------|")
    print("\n".join(rows))
    print("\n# '?' cells (Gate A score, Decision) need the LLM: read the gate file's review "
          "verdicts for Gate A scores and write the Decision per task.", file=sys.stderr)


def build_parser():
    p = argparse.ArgumentParser(description="AutViam gate-file / task-JSON helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("count", help="print fail count for a gate")
    s.add_argument("gates"); s.add_argument("task_id"); s.add_argument("gate")
    s.set_defaults(fn=cmd_count)

    s = sub.add_parser("counters", help="print 'A=n B=n C=n'")
    s.add_argument("gates"); s.add_argument("task_id")
    s.set_defaults(fn=cmd_counters)

    s = sub.add_parser("sync-counters", help="recompute and rewrite the Failure counters line")
    s.add_argument("gates"); s.add_argument("task_id")
    s.set_defaults(fn=cmd_sync_counters)

    s = sub.add_parser("cap-check", help="print 'CAP-HIT n' if >=4 fails else 'OK n'")
    s.add_argument("gates"); s.add_argument("task_id"); s.add_argument("gate")
    s.set_defaults(fn=cmd_cap_check)

    s = sub.add_parser("init", help="create the gate file header if absent")
    s.add_argument("gates"); s.add_argument("--phase", required=True)
    s.add_argument("--plan", required=True); s.add_argument("--branch", required=True)
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("init-task", help="add a per-task section skeleton if absent")
    s.add_argument("gates"); s.add_argument("task_id"); s.add_argument("title")
    s.add_argument("--started")
    s.set_defaults(fn=cmd_init_task)

    s = sub.add_parser("last-good-sha", help="print most recent passing Gate C commit")
    s.add_argument("gates")
    s.set_defaults(fn=cmd_last_good_sha)

    s = sub.add_parser("complete", help="write ExecPhase-owned completion fields to a task JSON")
    s.add_argument("task_json")
    s.add_argument("--branch", required=True)
    s.add_argument("--passed", type=int, required=True)
    s.add_argument("--total", type=int, required=True)
    s.add_argument("--review-score", dest="review_score", type=int, required=True)
    s.add_argument("--minor", type=int, default=0); s.add_argument("--medium", type=int, default=0)
    s.add_argument("--high", type=int, default=0); s.add_argument("--critical", type=int, default=0)
    s.add_argument("--commands", nargs="*", default=None)
    s.add_argument("--notes", nargs="*", default=None)
    s.add_argument("--date", default=None)
    s.set_defaults(fn=cmd_complete)

    s = sub.add_parser("set-status", help="set only the status field")
    s.add_argument("task_json"); s.add_argument("status")
    s.set_defaults(fn=cmd_set_status)

    s = sub.add_parser("reset-task", help="rollback: clear completion fields, status=pending")
    s.add_argument("task_json")
    s.set_defaults(fn=cmd_reset_task)

    s = sub.add_parser("reset-packet", help="emit Session Reset Packet table rows")
    s.add_argument("gates"); s.add_argument("json_dir")
    s.set_defaults(fn=cmd_reset_packet)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
