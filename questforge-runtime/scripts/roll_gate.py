#!/usr/bin/env python3
"""Hard declaration-before-randomness gate for QuestForge rolls."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, random, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_GIT_BLOB = "e330690b473a72f8bd7c0ca33fa509b1d25a9a37"

def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes(); header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()

def load_roller(path: Path):
    actual = git_blob_sha1(path)
    if actual != EXPECTED_GIT_BLOB:
        raise RuntimeError(f"QuestForge roller hash mismatch: expected {EXPECTED_GIT_BLOB}, got {actual}")
    spec = importlib.util.spec_from_file_location("questforge_roll_dice", path)
    if spec is None or spec.loader is None: raise RuntimeError("Unable to load QuestForge roll_dice.py")
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module, actual

def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as h:
        h.write(json.dumps(payload, sort_keys=True) + "\n"); h.flush(); os.fsync(h.fileno())

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("notation"); p.add_argument("--check", required=True)
    t = p.add_mutually_exclusive_group(required=True); t.add_argument("--dc", type=int); t.add_argument("--opposition")
    p.add_argument("--stakes", required=True); p.add_argument("--mode", required=True, choices=("normal","advantage","disadvantage"))
    p.add_argument("--mode-reason", default=""); p.add_argument("--log", type=Path); p.add_argument("--self-test", action="store_true"); p.add_argument("--seed", type=int)
    a = p.parse_args()
    if a.mode != "normal" and not a.mode_reason.strip(): raise SystemExit("--mode-reason is required for advantage/disadvantage")
    if a.seed is not None and not a.self_test: raise SystemExit("--seed is forbidden for live rolls")
    module, source_blob = load_roller(Path(__file__).resolve().parent / "roll_dice.py")
    log_path = a.log or Path(os.environ.get("RUNNER_TEMP", "/tmp")) / ("qf-self-test.jsonl" if a.self_test else "qf-roll-log.jsonl")
    roll_id = str(uuid.uuid4())
    append_jsonl(log_path, {"event":"declaration","roll_id":roll_id,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"live":not a.self_test,"roller_git_blob":source_blob,"check":a.check,"notation":a.notation,"dc":a.dc,"opposition":a.opposition,"stakes":a.stakes,"mode":a.mode,"mode_reason":a.mode_reason})
    generator = random.Random(a.seed) if a.self_test and a.seed is not None else None
    result = module.roll_dice(a.notation, mode=a.mode, random_generator=generator)
    success = result.total >= a.dc if a.dc is not None else None
    append_jsonl(log_path, {"event":"result","roll_id":roll_id,"timestamp_utc":datetime.now(timezone.utc).isoformat(),"live":not a.self_test,"roller_git_blob":source_blob,"rolls":list(result.rolls),"kept":list(result.kept),"dropped":list(result.dropped),"modifier":result.modifier,"total":result.total,"dc":a.dc,"opposition":a.opposition,"success":success})
    target = f"DC {a.dc}" if a.dc is not None else f"opposition {a.opposition}"
    outcome = "success" if success is True else "failure" if success is False else "pending opposed resolution"
    test = " [SELF-TEST NON-CANON]" if a.self_test else ""
    print(f"@Questforge{test} roll receipt {roll_id}: {a.check}; {result.notation} {a.mode}; rolls={list(result.rolls)}; kept={list(result.kept)}; dropped={list(result.dropped) or '-'}; modifier={result.modifier}; total={result.total}; {target}; {outcome}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
