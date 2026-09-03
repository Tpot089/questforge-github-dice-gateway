#!/usr/bin/env python3
"""Translate a [QF-ROLL] GitHub issue into a verified QuestForge execution."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ALLOWED_KEYS = {"notation","check","dc","opposition","stakes","mode","mode_reason","self_test","seed"}
def fail(message): print(f"QuestForge gateway error: {message}", file=sys.stderr); raise SystemExit(2)

def main():
    if len(sys.argv) != 3: fail("usage: github_issue_roll.py <event.json> <receipt.md>")
    event = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")); issue = event.get("issue") or {}
    if not str(issue.get("title") or "").startswith("[QF-ROLL]"): fail("issue title must begin with [QF-ROLL]")
    try: request = json.loads(str(issue.get("body") or "").strip())
    except json.JSONDecodeError as exc: fail(f"issue body must be raw JSON: {exc}")
    if not isinstance(request, dict): fail("issue body JSON must be an object")
    unknown = set(request) - ALLOWED_KEYS
    if unknown: fail(f"unsupported fields: {sorted(unknown)}")
    for required in ("notation","check","stakes","mode"):
        if not str(request.get(required, "")).strip(): fail(f"missing required field: {required}")
    has_dc = request.get("dc") is not None; has_opp = bool(str(request.get("opposition") or "").strip())
    if has_dc == has_opp: fail("provide exactly one of dc or opposition")
    mode = str(request["mode"]).lower(); reason = str(request.get("mode_reason") or "")
    if mode not in {"normal","advantage","disadvantage"}: fail("invalid mode")
    if mode != "normal" and not reason.strip(): fail("mode_reason is required for advantage/disadvantage")
    gate = Path(__file__).resolve().parent / "roll_gate.py"
    command = [sys.executable,str(gate),str(request["notation"]),"--check",str(request["check"]),"--stakes",str(request["stakes"]),"--mode",mode]
    if has_dc: command += ["--dc",str(int(request["dc"]))]
    else: command += ["--opposition",str(request["opposition"])]
    if reason: command += ["--mode-reason",reason]
    if bool(request.get("self_test", False)):
        command.append("--self-test")
        if request.get("seed") is not None: command += ["--seed",str(int(request["seed"]))]
    elif request.get("seed") is not None: fail("seed is forbidden for live rolls")
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0: fail((completed.stderr or completed.stdout).strip() or "roll gate failed")
    receipt = completed.stdout.strip()
    md = "### QuestForge verified execution\n\n" + f"`{receipt}`\n\n" + f"- GitHub issue: #{issue.get('number')}\n- Execution: GitHub Actions hosted runner\n- Roller: `questforge-runtime/scripts/roll_dice.py`\n- Gate: `questforge-runtime/scripts/roll_gate.py`\n- Authentic upstream roller blob: `e330690b473a72f8bd7c0ca33fa509b1d25a9a37`\n"
    Path(sys.argv[2]).write_text(md, encoding="utf-8"); print(receipt); return 0

if __name__ == "__main__": raise SystemExit(main())
