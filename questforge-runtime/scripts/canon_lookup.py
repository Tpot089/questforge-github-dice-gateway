#!/usr/bin/env python3
"""QuestForge canonical-memory retriever.

Searches the live QuestForge GitHub tree first, then falls back to the
canonical ZIP archive. Outputs machine-readable JSON with provenance.
Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass

DEFAULT_REPO = "Tpot089/nextjs"
DEFAULT_REF = "main"
DEFAULT_ROOT = "questforge-canonical/live/ody-the-dunmarrow-ledger"
DEFAULT_ARCHIVE = "questforge-canonical/ody-dunmarrow-questforge-CANONICAL.zip"
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv", ".html"}
MAX_TEXT_BYTES = 2_000_000


@dataclass
class Match:
    source: str
    path: str
    score: int
    excerpt: str
    content_sha256: str
    html_url: str | None = None


def _tokens(query: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", query) if len(t) > 1]


def _score(text: str, query: str) -> int:
    hay = text.lower()
    phrase = " ".join(query.lower().split())
    tokens = _tokens(query)
    if not tokens:
        return 0
    score = 0
    if phrase and phrase in " ".join(hay.split()):
        score += 100
    present = 0
    for token in tokens:
        count = hay.count(token)
        if count:
            present += 1
            score += min(count, 20) * 5
    if present == len(tokens):
        score += 50
    elif present:
        score += present * 3
    return score


def _excerpt(text: str, query: str, radius: int = 700) -> str:
    low = text.lower()
    pos = low.find(query.lower())
    if pos < 0:
        for token in _tokens(query):
            pos = low.find(token)
            if pos >= 0:
                break
    if pos < 0:
        pos = 0
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    snippet = text[start:end].strip()
    if start:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def _decode(raw: bytes) -> str | None:
    if len(raw) > MAX_TEXT_BYTES:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None


def search_zip_bytes(data: bytes, query: str, limit: int = 8) -> tuple[str, list[Match]]:
    archive_sha = hashlib.sha256(data).hexdigest()
    matches: list[Match] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.file_size > MAX_TEXT_BYTES:
                continue
            lower = info.filename.lower()
            if not any(lower.endswith(ext) for ext in TEXT_EXTENSIONS):
                continue
            text = _decode(zf.read(info))
            if text is None:
                continue
            score = _score(text, query)
            if score <= 0:
                continue
            raw = text.encode("utf-8")
            matches.append(
                Match(
                    source="canonical_zip",
                    path=info.filename,
                    score=score,
                    excerpt=_excerpt(text, query),
                    content_sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
    matches.sort(key=lambda m: (-m.score, m.path))
    return archive_sha, matches[:limit]


def _request_json(url: str, token: str | None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "questforge-canon-retriever/1")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _request_bytes(url: str, token: str | None) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/octet-stream")
    req.add_header("User-Agent", "questforge-canon-retriever/1")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_repo_file(repo: str, path: str, ref: str, token: str | None) -> tuple[bytes, dict]:
    quoted = urllib.parse.quote(path, safe="/")
    meta_url = f"https://api.github.com/repos/{repo}/contents/{quoted}?ref={urllib.parse.quote(ref)}"
    meta = _request_json(meta_url, token)
    content = meta.get("content")
    if content and meta.get("encoding") == "base64":
        return base64.b64decode(content), meta
    download_url = meta.get("download_url")
    if not download_url:
        raise RuntimeError(f"GitHub did not expose bytes for {repo}:{path}@{ref}")
    return _request_bytes(download_url, token), meta


def search_github_live(
    repo: str,
    root: str,
    ref: str,
    query: str,
    token: str | None,
    limit: int = 8,
) -> list[Match]:
    if not token:
        return []
    q = f"{query} repo:{repo} path:{root}"
    url = "https://api.github.com/search/code?" + urllib.parse.urlencode(
        {"q": q, "per_page": min(limit * 3, 50)}
    )
    payload = _request_json(url, token)
    matches: list[Match] = []
    for item in payload.get("items", []):
        path = item.get("path", "")
        if not path.startswith(root + "/"):
            continue
        if not any(path.lower().endswith(ext) for ext in TEXT_EXTENSIONS):
            continue
        raw, meta = fetch_repo_file(repo, path, ref, token)
        text = _decode(raw)
        if text is None:
            continue
        score = _score(text, query)
        if score <= 0:
            continue
        matches.append(
            Match(
                source="questforge_live",
                path=path,
                score=score + 25,
                excerpt=_excerpt(text, query),
                content_sha256=hashlib.sha256(raw).hexdigest(),
                html_url=meta.get("html_url") or item.get("html_url"),
            )
        )
    matches.sort(key=lambda m: (-m.score, m.path))
    return matches[:limit]


def retrieve(
    query: str,
    *,
    repo: str = DEFAULT_REPO,
    ref: str = DEFAULT_REF,
    root: str = DEFAULT_ROOT,
    archive_path: str = DEFAULT_ARCHIVE,
    token: str | None = None,
    local_archive: str | None = None,
    limit: int = 8,
) -> dict:
    if not query.strip():
        raise ValueError("query must not be empty")

    errors: list[str] = []
    live_matches: list[Match] = []
    archive_matches: list[Match] = []
    archive_sha: str | None = None

    if token and not local_archive:
        try:
            live_matches = search_github_live(repo, root, ref, query, token, limit)
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError) as exc:
            errors.append(f"live_search: {type(exc).__name__}: {exc}")

    if not live_matches:
        try:
            if local_archive:
                with open(local_archive, "rb") as fh:
                    data = fh.read()
            else:
                if not token:
                    raise RuntimeError("GitHub token required for private canonical archive")
                data, _ = fetch_repo_file(repo, archive_path, ref, token)
            archive_sha, archive_matches = search_zip_bytes(data, query, limit)
        except (
            OSError,
            zipfile.BadZipFile,
            urllib.error.URLError,
            urllib.error.HTTPError,
            RuntimeError,
        ) as exc:
            errors.append(f"archive_search: {type(exc).__name__}: {exc}")

    matches = live_matches or archive_matches
    return {
        "schema": 1,
        "query": query,
        "status": "established_candidates" if matches else "not_established",
        "source_policy": "questforge_live_then_canonical_zip",
        "repo": repo,
        "ref": ref,
        "root": root,
        "archive_path": archive_path,
        "archive_sha256": archive_sha,
        "matches": [asdict(m) for m in matches],
        "errors": errors,
        "instruction": (
            "Treat matches as evidence candidates. Apply campaign canon hierarchy and supersession rules before use. "
            "If no authoritative match survives, do not invent the historical fact."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve established QuestForge campaign facts with provenance."
    )
    parser.add_argument(
        "query", help="Fact, agreement, event, NPC, property, or checkpoint detail to retrieve"
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--archive-path", default=DEFAULT_ARCHIVE)
    parser.add_argument("--archive", dest="local_archive", help="Local canonical ZIP; bypasses GitHub download")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument(
        "--token-env",
        default="QF_GITHUB_TOKEN",
        help="Environment variable containing a GitHub token able to read the private QuestForge repo",
    )
    args = parser.parse_args(argv)

    token = (
        os.environ.get(args.token_env)
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    )
    result = retrieve(
        args.query,
        repo=args.repo,
        ref=args.ref,
        root=args.root,
        archive_path=args.archive_path,
        token=token,
        local_archive=args.local_archive,
        limit=max(1, min(args.limit, 25)),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "established_candidates" else 3


if __name__ == "__main__":
    raise SystemExit(main())
