# Project Understanding Skill experiment harness

This directory implements the experiment described in
`docs/experiments/project-understanding-skill-poc.md` without changing WebCodex
Runtime behavior.

## Contents

- `project-understanding/SKILL.md` — treatment Skill package template.
- `project-understanding/scripts/validate_snapshot.py` — bounded snapshot validator.
- `tasks.json` — byte-frozen prompts and quality concepts for T1-T6.
- `report.py` — small comparator for manually captured A/B metrics.

The package intentionally lives outside `.agents/skills`, so merely checking out this
branch does not make the treatment visible as a Project Skill.

## Materialize the treatment package

For an actual treatment run, copy the package to an operator-configured Skill root
outside the subject checkout, for example:

```text
/root/git/.webcodex-experiments/skills/
  project-understanding/
    SKILL.md
    scripts/validate_snapshot.py
```

Then add only the parent root to the special Runner's configured `[skills].roots` and
hot-reload the Runner configuration. Remove that root again for a control run.

Do **not** configure the root before collecting the control result.

## Snapshot location

For dogfood, the treatment snapshot belongs under the benchmark Project itself:

```text
target/project-understanding-poc/<40-hex-head>/snapshot.json
```

`target/` is ignored in WebCodex. The snapshot must pass:

```bash
python3 scripts/experiments/project_understanding/project-understanding/scripts/validate_snapshot.py \
  target/project-understanding-poc/<head>/snapshot.json \
  --project <exact-runtime-project-id> \
  --head <40-hex-head>
```

A control run should happen before this file is generated in the benchmark Project.

## Run capture

Each task uses a fresh chat window and fresh Workflow Session. Keep the exact final
Workflow Session id; it allows later server-side inspection without asking the model
to estimate its own tool metrics.

A minimal run record, created after inspection, is:

```json
{
  "task": "T1",
  "condition": "control",
  "sessionId": "wc_sess_...",
  "quality": 2,
  "metrics": {
    "search_calls": 0,
    "search_queries": 0,
    "read_calls": 0,
    "read_items": 0,
    "inspection_result_bytes": 0,
    "meaningful_outer_calls": 0,
    "wall_time_seconds": 0
  }
}
```

Do not ask the model to invent these counts. Recover them from WebCodex evidence after
the run.
