# QuestForge GitHub Dice Gateway

An external, auditable dice-execution boundary for AI-run tabletop games.

An LLM can describe a dice roll without actually executing one. This gateway removes that ambiguity: the model declares the check and stakes first, submits a GitHub issue, GitHub Actions executes the authentic QuestForge roller outside the conversation, and a GitHub bot posts the result as a persistent receipt. The model should narrate only after retrieving that receipt.

## Trust model

`declare -> GitHub issue -> GitHub Actions -> verified roller -> bot receipt -> narration`

The request exists before the random result. The result is generated outside the chat. A missing receipt means **no roll exists**.

## What is included

- `questforge-runtime/scripts/roll_dice.py` — exact upstream QuestForge dice roller from `adrianmelic/codex-questforge`
- `questforge-runtime/scripts/roll_gate.py` — declaration-first execution gate and source-hash verification
- `questforge-runtime/scripts/github_issue_roll.py` — validates issue JSON and invokes the gate
- `.github/workflows/questforge-roll.yml` — GitHub Actions execution and bot receipt

The upstream roller is pinned by Git blob SHA:

`e330690b473a72f8bd7c0ca33fa509b1d25a9a37`

## Install

1. Fork or copy this repository into a GitHub repository with Actions enabled.
2. Ensure repository workflow permissions allow GitHub Actions to write issue comments (`Settings -> Actions -> General -> Workflow permissions`).
3. Give your AI/agent permission to create GitHub issues and read issue comments in that repository.
4. Instruct the agent to use the protocol below for every consequential roll.

No API keys or third-party Python packages are required by the gateway.

## Roll request

Create an issue whose title begins:

`[QF-ROLL]`

The issue body must be raw JSON. Example with a modifier:

```json
{
  "notation": "d20+5",
  "check": "Force the barred door",
  "dc": 14,
  "stakes": "Success opens the door; failure leaves it barred and alerts the guard.",
  "mode": "normal",
  "mode_reason": ""
}
```

Use exactly one of `dc` or `opposition`.

Advantage example:

```json
{
  "notation": "d20+3",
  "check": "Track the raiders through fresh snow",
  "dc": 13,
  "stakes": "Success keeps the trail; failure loses an hour.",
  "mode": "advantage",
  "mode_reason": "Fresh snow makes tracks unusually clear."
}
```

## Self-tests

Set `"self_test": true` to mark a roll non-canonical. A deterministic `seed` is accepted **only** on self-tests. Seeds are rejected for live rolls.

## Agent protocol

For consequential gameplay, the agent should:

1. Decide that uncertainty genuinely requires a roll.
2. Before rolling, state the check, dice notation/modifier, DC or opposition, stakes, and advantage/disadvantage state and reason.
3. Create the `[QF-ROLL]` issue containing exactly that declaration.
4. Wait/poll the same issue until `github-actions[bot]` posts `### QuestForge verified execution` or execution terminally fails.
5. Parse only the externally posted receipt.
6. Narrate the outcome caused by that result.

The agent must not invent a result, substitute another RNG, narrate before the receipt, or ask the player to check back merely because Actions is still running.

## Why GitHub?

GitHub provides three useful properties for this problem: an execution environment independent of the language model, an immutable-enough chronological request/result trail for ordinary game auditing, and a connector surface many AI agents can already write to and read from.

This is not cryptographic proof against a malicious repository owner. It is an auditable execution boundary intended to prevent the conversational model itself from silently choosing or fabricating the die result.

## Attribution

The dice roller originates from **QuestForge / `adrianmelic/codex-questforge`**, copyright © 2026 Adrián Melic, distributed under the MIT License. The gateway, hard execution protocol, GitHub Actions bridge, and generalized integration were developed by Trevor Pottie in 2026 while building a persistent AI-run tabletop campaign workflow.

See `LICENSE`.


## Durable execution repair

The repair workflow creates an issue-specific durable claim in Git before invoking the unchanged authentic roller, then creates and reads back an immutable-by-protocol result file before posting a comment. Concurrent creation uses GitHub Contents create semantics (no prior SHA); duplicate claims fail. Reruns reuse an existing result and never execute RNG again. A claim without result is an explicit recovery block, including validation failures after claiming. Do not delete a claim to get a more convenient result. Collaborator-originated requests only; workflow needs contents:write for these receipt files.

The owner can edit or rewrite repository history, so these are auditable records rather than proof against a malicious administrator. Test with `python -m unittest discover -s tests -v`. Transport and crash tests are mocked; no live roll was issued by this repair. Merge/deployment and one explicitly noncanonical integration self-test remain necessary before production certification. Existing request fields and upstream roller bytes are unchanged.
