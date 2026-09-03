"""Small dice roller for Questforge.

Derived from adrianmelic/codex-questforge, MIT licensed.
Original copyright (c) 2026 Adrián Melic.
"""

from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass
from typing import Iterable

DICE_PATTERN = re.compile(r"^\s*(?P<count>\d*)d(?P<sides>\d+)\s*(?P<modifier>[+-]\s*\d+)?\s*$", re.IGNORECASE)

@dataclass(frozen=True)
class DiceRoll:
    notation: str
    total: int
    rolls: tuple[int, ...]
    modifier: int
    kept: tuple[int, ...]
    dropped: tuple[int, ...]
    mode: str

def parse_notation(notation: str) -> tuple[int, int, int]:
    match = DICE_PATTERN.match(notation)
    if not match:
        raise ValueError(f"Unsupported dice notation: {notation!r}")
    count = int(match.group("count")) if match.group("count") else 1
    sides = int(match.group("sides"))
    modifier_text = match.group("modifier")
    modifier = int(modifier_text.replace(" ", "")) if modifier_text else 0
    if count < 1: raise ValueError("Dice count must be at least 1.")
    if sides < 2: raise ValueError("Dice sides must be at least 2.")
    if count > 100: raise ValueError("Dice count must be 100 or lower.")
    return count, sides, modifier

def normalize_notation(count: int, sides: int, modifier: int) -> str:
    suffix = f"+{modifier}" if modifier > 0 else str(modifier) if modifier < 0 else ""
    return f"{count}d{sides}{suffix}"

def roll_dice(notation: str, mode: str = "normal", random_generator: random.Random | None = None) -> DiceRoll:
    count, sides, modifier = parse_notation(notation)
    mode = mode.lower()
    generator = random_generator or random.SystemRandom()
    if mode not in {"normal", "advantage", "disadvantage"}: raise ValueError("Mode must be normal, advantage, or disadvantage.")
    if mode in {"advantage", "disadvantage"} and (count, sides) != (1, 20): raise ValueError("Advantage and disadvantage apply only to 1d20 rolls.")
    if mode == "normal":
        rolls = tuple(generator.randint(1, sides) for _ in range(count)); kept = rolls; dropped = ()
    else:
        rolls = tuple(generator.randint(1, 20) for _ in range(2))
        kept_value = max(rolls) if mode == "advantage" else min(rolls)
        dropped_value = min(rolls) if mode == "advantage" else max(rolls)
        kept = (kept_value,); dropped = (dropped_value,)
    return DiceRoll(normalize_notation(count, sides, modifier), sum(kept) + modifier, rolls, modifier, kept, dropped, mode)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Roll dice for Questforge.")
    parser.add_argument("notation")
    parser.add_argument("--mode", choices=("normal", "advantage", "disadvantage"), default="normal")
    parser.add_argument("--seed", type=int)
    return parser

def main(arguments: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    generator = random.Random(args.seed) if args.seed is not None else None
    result = roll_dice(args.notation, mode=args.mode, random_generator=generator)
    print(result)
    return 0

if __name__ == "__main__": raise SystemExit(main())
