# Project Understanding Skill POC and A/B experiment

Design date: 2026-10-04. Source basis: `ba7945ceccb991b375562509534cc030701ff6b0`.

This document defines a **Skill-first experiment**, not a Runtime feature proposal.
The first question is whether a compact, reusable project-understanding snapshot
materially improves real coding-agent work when WebCodex already provides bounded
search, reads, Git inspection, semantic navigation, Workflow Sessions, and durable
execution. Runtime changes are out of scope until the experiment demonstrates a
repeatable benefit.

## Decision

Build the first Project Understanding prototype as an **operator-configured Runner
Skill outside the subject repository** and evaluate it against an otherwise identical
control.

Do not add a project-local Skill to the benchmark checkout. Project Skills live under
`.agents/skills`, so committing the treatment there would change the source tree and
invalidate the A/B comparison. A configured live Runner Skill root is a better
experimental carrier: it can expose `SKILL.md` and supported scripts without changing
the subject Project or widening ordinary Project filesystem authority.

The POC may write disposable dogfood artifacts under the already-ignored
`target/project-understanding-poc/` directory of the WebCodex checkout. That location
is an experiment convenience, **not** the proposed product persistence model.

The treatment must remain advisory:

- live Project tools are the source of truth;
- the snapshot cannot authorize a read, edit, process, Job, Project, or Session;
- stale or mismatched source identity causes the Skill to fall back to live inspection;
- deterministic facts, structural derivations, and LLM semantic summaries remain
  distinguishable in the snapshot;
- mutation and review conclusions must still be verified against current source.

## Problem statement

A fresh agent working in a mature repository repeatedly pays a discovery tax:

1. find the relevant subsystem;
2. search for entry points and contracts;
3. read several files to reconstruct relationships;
4. rediscover terminology and architectural boundaries;
5. only then start the task-specific inspection or edit.

WebCodex has optimized the mechanics of those steps. For example, `read_files`
coalesces bounded reads and `search_project_texts` provides bounded parallel search;
startup can also advertise semantic navigation through the Runner. These mechanisms
make live inspection efficient, but they deliberately do not retain a semantic model
of the Project between unrelated tasks.

The hypothesis is that a small reusable snapshot can reduce repeated discovery without
turning cached interpretation into execution truth.

## Goals

The POC should answer five questions.

1. Does a reusable project snapshot reduce repeated `search_project_texts` and
   `read_files` work on realistic tasks?
2. Does it reduce model-visible inspection bytes and meaningful outer calls without
   reducing correctness?
3. Does it improve time-to-first-correct-localization on architecture and impact
   questions?
4. How many warm tasks are required to amortize the one-time snapshot build cost?
5. Which snapshot facts are valuable enough to justify a later deterministic Runner
   implementation?

## Non-goals

The first experiment does **not**:

- add a graph database, vector database, embedding service, or GraphRAG stack;
- add new public Runtime tools;
- add Server-side repository scanning;
- persist Project understanding in Workflow Session, Goal, Agent, or ActionAudit state;
- infer authority or continuity from the snapshot;
- replace LSP, Git, search, file reads, validation, or review;
- attempt a complete symbol/call graph for every language;
- build a production dashboard;
- benchmark a deliberately inefficient control;
- claim token savings when exact model-token accounting is unavailable.

## Product boundary

The intended long-term layering is:

```text
Project Understanding Snapshot
            |
            v
      model localization
            |
            v
live search / LSP / reads / Git
            |
            v
 review / edit / validation / Job
```

The snapshot answers **where to look and what the project appears to contain**. The
Runtime answers **what is true now and what the caller may do**.

This boundary matters because WebCodex Projects are Runner-owned, authorization is
rechecked per canonical tool path, Workflow Session identity is explicit, and
ClientWindow/Goal/Job identities are not interchangeable. A semantic cache must not
become another implicit identity or authority channel.

## POC source identity

Keep the first experiment deliberately strict: build and reuse snapshots only for a
**clean Git checkout**.

A snapshot key contains:

```json
{
  "schemaVersion": 1,
  "project": "agent:<client_id>:<project_id>",
  "gitCommit": "<40-hex HEAD>",
  "clean": true,
  "generatorRevision": "<skill definition revision>"
}
```

Treatment startup verifies the current Project and HEAD before consuming the snapshot.
If the checkout is dirty, HEAD differs, the Project differs, or the generator revision
is incompatible, the Skill must report the mismatch and use live inspection instead
of pretending the cache is fresh.

This intentionally leaves performance on the table. A later Runtime design can use a
canonical clean/dirty source identity such as commit + frozen workspace fingerprint.
The POC should not invent a parallel workspace-identity algorithm inside a Skill.

## Compact snapshot shape

The POC should favor a small teaching/index artifact rather than a full repository
mirror.

```json
{
  "schemaVersion": 1,
  "source": {
    "project": "agent:special:webcodex",
    "gitCommit": "...",
    "clean": true,
    "generatedAt": "...",
    "generatorRevision": "..."
  },
  "overview": {
    "purpose": "...",
    "languages": ["rust", "typescript"],
    "entryPoints": ["..."],
    "majorDomains": ["..."]
  },
  "domains": [
    {
      "id": "tool-runtime",
      "summary": "...",
      "paths": ["src/tool_runtime"],
      "entryPoints": ["src/tool_runtime/mod.rs"],
      "relatedDomains": ["runner", "workflow-session"]
    }
  ],
  "landmarks": [
    {
      "path": "src/tool_runtime/search_project_texts.rs",
      "role": "...",
      "symbols": ["..."]
    }
  ],
  "relations": [
    {
      "from": "tool-runtime",
      "to": "runner",
      "kind": "dispatches_to",
      "evidence": "derived"
    }
  ],
  "readingTours": [
    {
      "id": "job-continuation",
      "paths": ["..."],
      "summary": "..."
    }
  ]
}
```

Bounds for the POC:

- at most 16 major domains;
- at most 96 landmarks;
- at most 160 relations;
- at most 12 reading tours;
- no source-file bodies;
- no raw command output;
- no credentials, environment dumps, absolute host paths, or protected configuration;
- target serialized snapshot: **<= 96 KiB**;
- normal startup projection derived from it: **<= 4 KiB**.

If a repository cannot fit those bounds, the Skill should summarize more aggressively
rather than silently increasing them.

## Evidence classes

Every retained fact must be one of three classes.

| Class | Meaning | Examples |
| --- | --- | --- |
| `observed` | Direct current-source or Runtime fact | file exists, Git HEAD, symbol returned by LSP, exact import found in source |
| `derived` | Deterministic or bounded structural inference from observed facts | directory cluster, import-neighbor relation, likely entry-point ranking |
| `semantic` | LLM interpretation | subsystem purpose, concise architecture summary, suggested reading order |

Do not turn a semantic summary into structural truth. For example, “this is the
authentication layer” can guide search, but an edit still requires current source
inspection.

The snapshot should retain small provenance hints such as source paths and evidence
class, not full source excerpts.

## Skill workflow

The prototype should use only existing WebCodex capabilities.

### Phase 0: bind the live Project

1. Start `work_on_project` for the exact registered Project.
2. Reuse its branch/HEAD/clean observation.
3. Load project instructions through the existing context projection.
4. Record whether semantic navigation is available.
5. Reject snapshot reuse when the strict POC source identity does not match.

### Phase 1: bounded project inventory

Use existing inspection primitives rather than shell-wide repository dumps:

- bounded project file listing for directory shape;
- targeted `read_files` for README, manifests, `AGENTS.md`, and known entry points;
- batched `search_project_texts` for subsystem names, tool definitions, protocol
  boundaries, and cross-cutting concepts;
- admitted read-only LSP navigation when the current Runner exposes it;
- Git only for source identity and task-relevant history.

The Skill should not read every file. The goal is a compact orientation index.

### Phase 2: structural organization

Build deterministic or bounded derived facts first:

- top-level directory/domain candidates;
- known entry points;
- manifest/workspace membership;
- strong import/reference relationships available from live evidence;
- likely tests adjacent to important modules;
- documentation landmarks.

Prefer LSP facts when available. Use search/source evidence as fallback. A future
implementation may add Tree-sitter for unsupported languages and non-code formats, but
the first POC should not add another parser stack merely to create a benchmark.

### Phase 3: semantic compression

Use the model only to produce bounded:

- project overview;
- major-domain summaries;
- landmark roles;
- a few cross-domain relationships;
- reading tours for recurring tasks.

Semantic output must reference observed paths. Unknown areas remain unknown rather
than being filled with plausible architecture.

### Phase 4: save and consume

For dogfood only, save the complete snapshot under:

```text
target/project-understanding-poc/<git-commit>/snapshot.json
```

A normal treatment task should receive only a compact startup brief, for example:

```text
Project: WebCodex
Source: ba7945ce (clean)

Major domains:
- Tool Runtime
- Runner / transport
- Workflow Session
- Projects / worktrees
- MCP adapters
- Desktop

Likely paths for this task:
- src/tool_runtime/...
- crates/webcodex-runner/...

Snapshot is advisory. Verify current source before conclusions or edits.
```

The Skill may query the full snapshot when localization requires it, but should not
inject the whole JSON into every prompt.

## A/B experiment

### Conditions

**A — control**

- no Project Understanding Skill available to the model;
- use the best current WebCodex workflow, including native batching and semantic
  navigation when available.

**B — treatment**

- same Runtime build and source snapshot;
- operator-configured Project Understanding Skill available;
- one prebuilt warm snapshot for the exact source identity;
- startup receives the bounded snapshot brief and may query the snapshot before live
  inspection.

The control must not be artificially degraded. It can use every ordinary WebCodex
capability that the treatment can use after localization.

### Isolation rules

For every compared run:

- same model family and thinking/effort setting;
- same WebCodex Server/Runner build;
- same source commit;
- same user prompt byte-for-byte;
- fresh model conversation/window;
- fresh Workflow Session;
- no copied findings from an earlier condition;
- no user hints after the run starts;
- same Direct/Host Code Mode surface within one comparison;
- mutation tasks, if added later, use independent managed worktrees from the exact
  same base commit.

Skill source must be outside the subject checkout so condition B does not change Git
state.

### Pilot task set

Start with six read-only tasks. They exercise repeated project understanding while
keeping correctness independently scorable.

#### T1 — Trace a public inspection tool

Prompt:

> Trace `search_project_texts` from its public/model-facing contract through
> canonical ToolRuntime execution to Runner/search execution and model result
> projection. Identify the important bounds/concurrency decisions and the files that
> own them. Do not modify code.

Expected loci include the tool contracts/registry, ToolRuntime
`search_project_texts`, canonical dispatch/search core, and result projection.

#### T2 — Explain continuity boundaries

Prompt:

> Explain the differences and allowed relationships between Workflow Session,
> ClientWindow, ActionAudit, Job, Goal, and durable Agent state. Identify the
> authoritative implementation/docs for each and call out at least three things that
> must never be inferred from another identity. Do not modify code.

This tests whether a snapshot helps with terminology and cross-domain navigation
without encouraging cached authority claims.

#### T3 — Trace managed-worktree authority

Prompt:

> Trace `work_on_project(project, mode=worktree)` from source Project selection to
> managed worktree registration. Identify the authority/freshness fences and explain
> why the model cannot simply choose an arbitrary destination path. Do not modify code.

#### T4 — Change-impact question

Prompt:

> Suppose we consider raising `MAX_SEARCH_PROJECT_TEXTS_CONCURRENCY` from 2 to 4.
> Identify the code, tests, documentation, resource-contention risks, and measurements
> that should be reviewed before making that change. Do not modify code.

This is intentionally not a text-search-only question; the answer should connect the
search implementation to Runner admission, result bounds, validation load, and
existing performance methodology.

#### T5 — New-maintainer reading tour

Prompt:

> Give a new maintainer a 10-minute reading order for understanding same-Job
> continuation: how a long-running validation/process becomes a durable Job, how it is
> observed without redispatch, how Workflow Session evidence records it, and how the
> model receives the next action. Use concrete files and explain why each is in the
> sequence.

#### T6 — Cross-layer review localization

Prompt:

> A proposed change claims that Project identity can be recovered from the current
> browser window whenever a model omits the Project field. Before reviewing a patch,
> identify the architecture/contracts that make this safe or unsafe and list the files
> you would inspect first. Do not modify code.

A correct answer should quickly reject the premise that a ClientWindow grants Project
authority and should locate the relevant identity/authorization/session boundaries.

### Quality rubric

Create the expected-fact checklist before any A/B run. Score the final answer without
looking at condition labels.

Per task:

- **2 — correct:** required architectural facts and primary source loci are present;
  no material authority or lifecycle error.
- **1 — partial:** core conclusion is correct but one important owner/relationship is
  missing or weakly sourced.
- **0 — incorrect:** material architectural error, invented authority, wrong primary
  owner, or task not completed.

Also record separately:

- fabricated file/symbol;
- stale-snapshot claim presented as live truth;
- missed primary subsystem;
- unnecessary broad scan;
- whether the first two inspection actions entered the correct subsystem.

Any treatment-only material authority error is a POC failure even if efficiency
improves.

### Execution order

Use two stages.

**Stage 1 — cheap pilot:** T1-T4, one A and one B run each, alternating condition order
by task. Stop if treatment quality is worse or snapshot consumption obviously adds
work.

**Stage 2 — repeatability:** all six tasks with ABBA-style order across fresh windows.
Do not pool runs that use different model/effort settings or different Runtime builds.

The goal is not statistical significance from a tiny benchmark. Repetition is to
detect large, useful effects and expose order/cache artifacts.

## Metrics

### Primary quality

- rubric score;
- material factual/authority errors;
- required source loci found;
- task completion.

Quality is a hard gate, not a trade for fewer calls.

### Primary efficiency

Collect from existing ActionAudit/Window evidence where available:

- meaningful WebCodex outer calls;
- `search_project_texts` calls and query count;
- `read_files` calls and item count;
- model-visible search/read result bytes;
- total model-visible WebCodex result bytes;
- time to first correct subsystem localization;
- task wall time excluding explicit human pauses;
- recovery/continuation calls caused by truncation or wrong localization.

Do not add overlapping nested durations to outer service time.

### Optional client metrics

If the selected client exposes exact per-run token usage, record:

- uncached input tokens;
- cached input tokens;
- output tokens.

If exact usage is unavailable, do **not** estimate private model tokens from tool bytes
or inter-call gaps. Tool-result bytes remain a separate observable.

### Snapshot build cost

Measure the cold build separately:

- outer calls;
- searches/reads;
- model-visible result bytes;
- wall time;
- exact token usage only when available;
- snapshot serialized bytes.

Do not hide the cold cost inside warm-task averages.

### Amortization

For any additive metric where lower is better:

```text
B = one-time snapshot build cost
C = mean/median control task cost
T = mean/median warm treatment task cost

break-even tasks = ceil(B / (C - T)), when C > T
```

Report break-even independently for at least:

- model-visible inspection bytes;
- search+read outer calls (descriptive because calls are not equal cost);
- exact input tokens when the client supplies them.

Do not combine unlike units into a synthetic score.

## POC success gate

Proceed to a Runtime-backed prototype only if all of the following hold in the
repeatability stage:

1. treatment quality is non-regressing: no new material authority/lifecycle errors and
   no lower aggregate rubric pass rate;
2. aggregate `search_project_texts + read_files` outer calls fall by at least **20%**;
3. model-visible inspection result bytes fall by at least **25%**;
4. at least **4 of 6** tasks show a clear localization/inspection reduction rather
   than the gain coming from one outlier;
5. cold snapshot build amortizes within **5 warm tasks** on either exact input tokens
   or, when tokens are unavailable, model-visible inspection bytes;
6. no task requires bypassing live verification to achieve the improvement.

Wall-time improvement is desirable but secondary because model scheduling, network,
and UI latency can dominate short repository inspections.

If the POC reduces calls but increases factual errors or causes the model to trust stale
facts, stop rather than compensating with more snapshot content.

## Failure modes to test explicitly

### Staleness

A snapshot at commit A must not silently answer as if it describes commit B. Include a
negative test that advances HEAD after snapshot creation and verifies fallback to live
inspection.

### Dirty worktree

The strict POC should refuse warm reuse in a dirty checkout. Later designs can support a
workspace fingerprint; do not weaken the first experiment to make reuse rates look
better.

### Semantic overclaim

Place at least one intentionally ambiguous subsystem in the evaluation rubric. The
snapshot should say “unknown/likely” rather than manufacture an ownership claim.

### Snapshot prompt bloat

Track startup projection bytes separately. If the treatment injects tens of KiB before
the task is known, it has reproduced the problem in another form. The normal brief is
capped at 4 KiB.

### Self-repository familiarity

WebCodex is a useful dogfood repository but the development model may already have
context from repeated work. A positive result here is necessary but not sufficient.
Before productization, repeat a smaller suite on one unfamiliar external repository.

### Worktree leakage

The snapshot is bound to exact POC source identity. Do not reuse a snapshot merely
because another worktree has the same repository basename or nearby path.

### Authority leakage

Snapshot storage and Skill execution do not widen `allowed_roots`, Project grants, or
ordinary read/shell authority. The Skill must continue to call canonical WebCodex
tools for live evidence.

## What to learn from Understand Anything without copying it

The useful product idea is the **reusable teaching/index artifact**, not a requirement
to duplicate its entire implementation.

Useful patterns to validate:

- persistent project orientation across tasks;
- separation of deterministic structure from LLM summaries;
- architecture/domain grouping;
- guided reading tours;
- incremental freshness checks;
- compact graph exploration rather than repeatedly reading the whole repository.

Deliberately deferred:

- repository-wide Tree-sitter extractor matrix;
- Louvain batching;
- embeddings/vector search;
- graph database;
- full React graph dashboard;
- LLM review of the complete snapshot.

WebCodex can add these only after measured demand. Existing LSP and live Runtime
evidence may make several unnecessary.

## Implementation-ready task breakdown

### P0 — Experiment carrier

Create an operator-configured Runner Skill package outside the WebCodex checkout:

```text
<configured-skill-root>/project-understanding/
  SKILL.md
  scripts/
    validate-snapshot.py
```

Requirements:

- discovery through the existing configured Runner Skill source;
- no subject-repository modifications;
- no new Runtime schema;
- no direct access outside canonical Skill/resource and Project tool boundaries.

### P1 — Snapshot builder

Implement the four phases above with hard bounds.

Acceptance:

- clean WebCodex checkout produces a <= 96 KiB snapshot;
- every landmark path exists;
- source identity matches the live Project/HEAD;
- semantic fields are labeled separately from observed/derived facts;
- generated file contains no absolute host path or credential material;
- dirty or mismatched source does not reuse the snapshot.

### P2 — Compact consumer

Add a treatment workflow that reads only the <= 4 KiB brief initially and selects
relevant domains/landmarks from the full snapshot only after seeing the task.

Acceptance:

- no whole-snapshot injection on normal startup;
- live verification remains mandatory for code/review conclusions;
- a stale snapshot produces an explicit fallback rather than an answer from cache.

### P3 — Benchmark fixtures

Freeze:

- the six prompts above;
- expected-fact/source-locus rubric;
- base WebCodex commit;
- model/effort setting;
- Runtime build identity;
- condition-order sheet.

Reuse existing ActionAudit/reporting where possible. Add only experiment-local
reporting if current views cannot calculate a named metric.

### P4 — Run Stage 1

Execute T1-T4 as fresh A/B pairs.

Stop conditions:

- any treatment-only material correctness/authority regression;
- no visible reduction in discovery work;
- snapshot startup overhead dominates ordinary inspection.

### P5 — Run Stage 2

Only after Stage 1 passes, execute the six-task repeated comparison and publish the raw
bounded evidence plus a summary table.

### P6 — Runtime decision

If the success gate passes, design the smallest deterministic Runtime layer that
replaces proven expensive Skill work.

Candidate order:

1. canonical Project/source snapshot identity;
2. deterministic file/symbol/import index on the Runner;
3. bounded `explore_project_area`-style projection;
4. incremental invalidation;
5. only then optional visualization or semantic enrichment.

Do not start by moving the complete Skill JSON into Server persistence.

## Runtime promotion criteria

A fact belongs in a future Runner index when it is:

- deterministically derivable from Project source;
- expensive enough to rediscover repeatedly;
- useful across multiple tasks;
- safe to bind to a concrete source identity;
- naturally bounded and invalidatable.

A fact should remain Skill/model-owned when it is:

- pedagogical wording;
- subjective architecture grouping;
- task-specific relevance;
- uncertain semantic interpretation;
- inexpensive to regenerate.

This keeps the Runtime authoritative about source facts while allowing Skills to evolve
quickly as model ergonomics change.

## Current experiment-harness boundary

P0-P3 are now allowed on this branch as experiment-only material:

- the Skill template lives outside `.agents/skills`, so checkout alone does not enable
  the treatment;
- benchmark prompts/rubrics and bounded validation/report helpers may live under
  `scripts/experiments/project_understanding/`;
- the configured live Skill copy used by treatment must still live outside the subject
  checkout;
- no Runtime source/schema/tool behavior changes are part of P0-P3;
- no benchmark result is presented as measured until a real fresh-window run occurs.

The next experimental action is **Stage 1 T1 control**, followed by the matching T1
treatment on the same frozen Project/HEAD. Do not implement a Runner knowledge graph
until real A/B evidence crosses the promotion gate.
