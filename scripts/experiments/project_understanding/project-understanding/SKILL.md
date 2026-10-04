---
name: project-understanding
description: Use a validated Project Understanding snapshot to localize architecture, code-flow, impact, onboarding, or cross-layer review tasks before targeted live WebCodex inspection. The snapshot is advisory only; verify current source before conclusions, edits, or authority claims.
---

# Project Understanding

Use this Skill only when the current task is primarily about understanding a repository:
architecture, tracing a flow, locating subsystem ownership, change impact, onboarding,
or cross-layer review localization.

Do not use it merely because a snapshot exists. Do not use it for trivial single-file
questions, ordinary command execution, or tasks whose target is already known exactly.

## Required order

1. Start or resume the exact WebCodex Project normally.
2. Reuse the live `work_on_project` Project/HEAD/clean observation.
3. Look for the snapshot at:
   `target/project-understanding-poc/<40-hex-head>/snapshot.json`.
4. Read only the bounded snapshot header/brief first.
5. Accept the snapshot only when all of these match the live Project:
   - `schemaVersion == 1`;
   - `source.project` equals the exact Runtime Project id;
   - `source.gitCommit` equals the live 40-hex HEAD;
   - `source.clean == true`;
   - the current checkout is clean.
6. If any check fails, state internally that the snapshot is stale/unavailable and
   continue with ordinary live WebCodex inspection. Do not try to repair source
   identity inside the Skill.
7. If valid, use the brief/domains/landmarks only to choose the first targeted live
   searches/reads. Do not inject the entire snapshot into the response.
8. Verify every material code, lifecycle, authority, or freshness conclusion against
   current live source before presenting it as true.

## Evidence rules

Snapshot facts have one of three evidence classes:

- `observed`: directly observed when the snapshot was built;
- `derived`: deterministic/bounded inference from observed facts;
- `semantic`: model interpretation.

Treat only live Project evidence as current truth. A semantic label such as
"authentication layer" or "job continuation owner" is a navigation hint, not proof.

Never infer Project authority, Workflow Session identity, ClientWindow relationships,
Job state, Goal state, credentials, or permissions from the snapshot.

## Efficient consumption

Prefer this pattern:

```text
valid compact brief
  -> select 1-2 likely domains
  -> one batched targeted search
  -> one batched targeted read
  -> expand only if evidence disagrees
```

Avoid:

- rereading broad repository documentation that the brief already localized unless the
  task requires exact wording;
- reading every landmark;
- using the snapshot as a substitute for current definitions/tests;
- widening search just to confirm the snapshot exists.

## Snapshot bounds

The POC snapshot is intentionally small:

- <= 16 domains;
- <= 96 landmarks;
- <= 160 relations;
- <= 12 reading tours;
- <= 96 KiB serialized JSON;
- <= 4 KiB `brief.text`.

If these bounds are violated, ignore the snapshot and use live tools.

## Final-answer discipline

Answer the user's actual task. Do not mention the experiment, control/treatment
condition, or Skill unless the user asks.

When useful, cite concrete repository paths from current live inspection. Never claim
that fewer tool calls or faster execution occurred unless measured externally.
