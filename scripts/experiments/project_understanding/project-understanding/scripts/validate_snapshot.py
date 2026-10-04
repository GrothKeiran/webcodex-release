#!/usr/bin/env python3
"""Validate a Project Understanding POC snapshot.

This is an experiment helper, not a Runtime authority check. It validates bounded
shape/privacy invariants so a treatment snapshot cannot silently grow into a source
mirror or contain obvious host-local paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_BYTES = 96 * 1024
MAX_BRIEF_BYTES = 4 * 1024
MAX_DOMAINS = 16
MAX_LANDMARKS = 96
MAX_RELATIONS = 160
MAX_TOURS = 12

HEX40 = re.compile(r"^[0-9a-f]{40}$")
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"^/"),
    re.compile(r"^[A-Za-z]:[\\/]"),
)


def fail(message: str) -> None:
    raise ValueError(message)


def require_list(obj: dict[str, Any], key: str, maximum: int) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        fail(f"{key} must be an array")
    if len(value) > maximum:
        fail(f"{key} has {len(value)} entries; maximum is {maximum}")
    return value


def check_project_relative_path(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty string")
    if any(pattern.search(value) for pattern in ABSOLUTE_PATH_PATTERNS):
        fail(f"{label} must be project-relative, got {value!r}")
    if ".." in Path(value).parts:
        fail(f"{label} must not traverse parents, got {value!r}")


def validate(data: dict[str, Any], raw_size: int) -> None:
    if raw_size > MAX_BYTES:
        fail(f"snapshot is {raw_size} bytes; maximum is {MAX_BYTES}")
    if data.get("schemaVersion") != 1:
        fail("schemaVersion must equal 1")

    source = data.get("source")
    if not isinstance(source, dict):
        fail("source must be an object")
    project = source.get("project")
    if not isinstance(project, str) or not project.startswith("agent:"):
        fail("source.project must be an exact Runtime Project id")
    commit = source.get("gitCommit")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        fail("source.gitCommit must be a lowercase 40-hex commit")
    if source.get("clean") is not True:
        fail("source.clean must be true for the strict POC")

    brief = data.get("brief")
    if not isinstance(brief, dict):
        fail("brief must be an object")
    brief_text = brief.get("text")
    if not isinstance(brief_text, str) or not brief_text.strip():
        fail("brief.text must be a non-empty string")
    if len(brief_text.encode("utf-8")) > MAX_BRIEF_BYTES:
        fail(f"brief.text exceeds {MAX_BRIEF_BYTES} bytes")

    domains = require_list(data, "domains", MAX_DOMAINS)
    landmarks = require_list(data, "landmarks", MAX_LANDMARKS)
    require_list(data, "relations", MAX_RELATIONS)
    tours = require_list(data, "readingTours", MAX_TOURS)

    allowed_evidence = {"observed", "derived", "semantic"}
    for index, domain in enumerate(domains):
        if not isinstance(domain, dict):
            fail(f"domains[{index}] must be an object")
        if domain.get("evidence") not in allowed_evidence:
            fail(f"domains[{index}].evidence must be observed/derived/semantic")
        for path in domain.get("paths", []):
            check_project_relative_path(path, f"domains[{index}].paths")

    for index, landmark in enumerate(landmarks):
        if not isinstance(landmark, dict):
            fail(f"landmarks[{index}] must be an object")
        check_project_relative_path(landmark.get("path"), f"landmarks[{index}].path")
        if landmark.get("evidence") not in allowed_evidence:
            fail(f"landmarks[{index}].evidence must be observed/derived/semantic")
        if any(key in landmark for key in ("content", "sourceText", "rawOutput")):
            fail(f"landmarks[{index}] must not embed source bodies/raw output")

    for index, tour in enumerate(tours):
        if not isinstance(tour, dict):
            fail(f"readingTours[{index}] must be an object")
        for path in tour.get("paths", []):
            check_project_relative_path(path, f"readingTours[{index}].paths")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--head")
    args = parser.parse_args()

    raw = args.snapshot.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        fail("top-level JSON value must be an object")
    validate(data, len(raw))

    if args.project is not None and data["source"]["project"] != args.project:
        fail(
            f"project mismatch: snapshot={data['source']['project']!r} "
            f"expected={args.project!r}"
        )
    if args.head is not None:
        expected = args.head.lower()
        if not HEX40.fullmatch(expected):
            fail("--head must be a 40-hex commit")
        if data["source"]["gitCommit"] != expected:
            fail(
                f"HEAD mismatch: snapshot={data['source']['gitCommit']} "
                f"expected={expected}"
            )

    print(
        json.dumps(
            {
                "ok": True,
                "bytes": len(raw),
                "project": data["source"]["project"],
                "gitCommit": data["source"]["gitCommit"],
                "briefBytes": len(data["brief"]["text"].encode("utf-8")),
                "domains": len(data["domains"]),
                "landmarks": len(data["landmarks"]),
                "relations": len(data["relations"]),
                "readingTours": len(data["readingTours"]),
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"snapshot validation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
