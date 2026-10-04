#!/usr/bin/env python3
"""Compare manually captured Project Understanding A/B metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


LOWER_IS_BETTER = (
    "search_calls",
    "search_queries",
    "read_calls",
    "read_items",
    "inspection_result_bytes",
    "meaningful_outer_calls",
    "wall_time_seconds",
)


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: run data must be an object")
    return data


def pct_delta(control: float, treatment: float) -> float | None:
    if control == 0:
        return None
    return (treatment - control) / control * 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("control", type=Path)
    parser.add_argument("treatment", type=Path)
    args = parser.parse_args()

    control = load(args.control)
    treatment = load(args.treatment)
    if control.get("task") != treatment.get("task"):
        raise ValueError("control/treatment task ids differ")

    rows = []
    for key in LOWER_IS_BETTER:
        c = control.get("metrics", {}).get(key)
        t = treatment.get("metrics", {}).get(key)
        if isinstance(c, (int, float)) and isinstance(t, (int, float)):
            rows.append(
                {
                    "metric": key,
                    "control": c,
                    "treatment": t,
                    "deltaPct": pct_delta(float(c), float(t)),
                }
            )

    result = {
        "task": control.get("task"),
        "quality": {
            "control": control.get("quality"),
            "treatment": treatment.get("quality"),
            "nonRegressing": (
                isinstance(control.get("quality"), int)
                and isinstance(treatment.get("quality"), int)
                and treatment["quality"] >= control["quality"]
            ),
        },
        "metrics": rows,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
