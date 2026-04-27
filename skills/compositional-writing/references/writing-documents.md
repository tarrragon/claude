# Writing Documents — Situational Reference

> Situation: You are about to compose any markdown document — worklog, README, spec, methodology, error-pattern record, or ticket — where both human cognitive load and downstream AI token consumption matter.

## Before You Start: Identify Document Type

Different document types have different readers, lifespans, and structural demands. Pick the type first; the rest of this reference applies the five compositional principles to each.

| Document type                 | Primary reader                  | Lifespan               | Volatility                        | Core job                                                 |
| ----------------------------- | ------------------------------- | ---------------------- | --------------------------------- | -------------------------------------------------------- |
| Worklog                       | Future self / handoff receiver  | Per version (archived) | High (appended daily)             | Record decisions and milestones, not execution details   |
| README                        | Newcomer / marketplace visitor  | Permanent              | Low (stable)                      | Orient readers in one screen, route to deeper docs       |
| Spec (requirement / use case) | Implementers, reviewers, QA     | Permanent (versioned)  | Medium (evolves with scope)       | Define acceptable behaviour in testable terms            |
| Methodology                   | Framework users (cross-project) | Permanent              | Low (distilled)                   | Give experts a 30-second recall checklist                |
| Error-pattern                 | Debuggers, reviewers            | Permanent              | Low (append-only)                 | Capture root cause + prevention so it doesn't recur      |
| Ticket                        | Executor, dispatcher            | Per task (archived)    | Medium (mutated during execution) | Carry a single atomic intent from creation to completion |

Two rules follow from the table:

1. High-volatility documents (worklog, ticket) must stay append-only; rewriting history breaks the record.
2. Permanent documents (methodology, error-pattern, spec) must be distilled; every paragraph earns its keep.

---

## Principle 1 — Atomization × Documents: Section granularity and when to split

### Core question

How much content belongs in a single file, and when do you cut?

### Decision table

| Condition                                                                                         | Action                                      | Reason                                |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------- |
| One document covers one concept cleanly, body < ~500 lines                                        | Keep single file                            | Atomic at file level                  |
| Body crosses ~500 lines but concept is still one                                                  | Split into sub-sections, not separate files | File is still atomic                  |
| Body contains two independently retrievable concepts (reader consults only one at a time)         | Split into two files                        | Violates atomicity                    |
| Single file is consulted as five different situations (e.g. worklog + spec + methodology stacked) | Split by situation                          | Situation match beats line count      |
| Document is < 100 lines and only referenced from one place                                        | Consider merging upward                     | Under-atomic, creates navigation cost |

### Split heuristics by document type

- **Worklog**: Stays single per version. Append chronologically. Do not split by Wave unless the file exceeds ~2000 lines (rare).
- **README**: Always single file per directory. Route outward via links; do not fork README for sub-topics.
- **Spec**: Split by use case (one UC per file). Do not bundle multiple UCs for "efficiency".
- **Methodology**: One methodology per file. If a second concept appears, it is a second methodology.
- **Error-pattern**: One pattern per file. Multiple root causes → multiple files, cross-linked.
- **Ticket**: One ticket per file is the atomic contract. Splitting a ticket means creating child tickets, not subdividing the file.

### Anti-patterns

| Anti-pattern                                           | What happens                                                          |
| ------------------------------------------------------ | --------------------------------------------------------------------- |
| Stuffing three specs into one "spec-v2.md"             | Readers scan past unrelated sections; grep lands on wrong context     |
| Splitting a methodology into methodology-part-1/2/3    | Cross-references explode; readers lose the recall benefit             |
| Merging two error-patterns because "they feel similar" | Prevention measures dilute each other; future query returns ambiguity |

---

## Principle 2 — Indexing × Documents: MOC, directory structure, cross-document references

### Core question

Given many atomic documents, how does a reader find the right one?

### Three indexing mechanisms

1. **Directory layout** — the physical grouping implies a taxonomy. Keep depths shallow (≤ 3 levels); deeper trees hide documents.
2. **MOC (Map of Content)** — a landing document that lists siblings with one-line summaries. Every directory with more than 5 documents earns an MOC (README.md or index.md).
3. **Inline cross-reference** — when one document must point to another, use a stable relative path and describe *why* the reader should click, not just that they can.

### Cross-reference format

| Reference type                                            | Format                                 | Example                                                               |
| --------------------------------------------------------- | -------------------------------------- | --------------------------------------------------------------------- |
| Same-directory sibling                                    | Relative path + intent                 | `See [validation rules](./validation.md) for acceptable field values` |
| Cross-directory                                           | Full repo-relative path                | `Detailed flow: rules/decision-tree.md`                               |
| External (stable)                                         | URL with context                       | `Anthropic skill spec: https://...`                                   |
| External (volatile: ticket ID, commit hash, worklog path) | **Allowed only in volatile documents** | Never in spec / methodology / error-pattern content                   |

> A reference without intent ("see X.md") is a broken signpost. Always say what the reader gains by clicking.

### Indexing by document type

- **Worklog**: The worklog itself is an index of tickets. Each ticket row points into a detail file.
- **README**: Is the MOC for its directory. Must list every sibling one-line.
- **Spec**: Indexed by use case ID. Use cases form a flat catalogue; requirements nest under them.
- **Methodology**: Indexed by `methodologies/README.md`. Methodologies do not cross-reference methodologies-of-methodologies; keep one hop deep.
- **Error-pattern**: Indexed by a stable ID prefix scheme (e.g. category abbreviation + running number). The ID itself is the index key.
- **Ticket**: Indexed by worklog + `ticket track list`. CLI is the primary index, not a markdown TOC.

### Anti-patterns

| Anti-pattern                                              | What happens                                  |
| --------------------------------------------------------- | --------------------------------------------- |
| README that says "this folder contains various utilities" | Provides no routing; reader opens every file  |
| Spec referencing a ticket ID                              | Spec stability breaks when ticket is archived |
| Methodology A references methodology B which references A | Circular chase; no real content at the end    |

---

## Principle 3 — Explicit Intent & Business Logic × Documents: Inverted pyramid, spec vs process

### Core question

How do you make the point land in the first paragraph — and how do you separate "what the rules are" from "how we got here"?

### The inverted pyramid

Put the conclusion first. A reader who stops after the opening paragraph should still leave with the main takeaway.

| Pyramid level    | Content                           |
| ---------------- | --------------------------------- |
| Opening sentence | One-line answer or rule           |
| First paragraph  | The concrete action or constraint |
| Middle           | Context, reasoning, exceptions    |
| End              | Historical notes, references      |

### Spec vs process record — a mandatory split

| Aspect            | Spec (stable)                            | Process record (volatile)         |
| ----------------- | ---------------------------------------- | --------------------------------- |
| Voice             | Imperative / declarative                 | Narrative / chronological         |
| Tense             | Present ("the system must")              | Past ("we found that")            |
| Citations allowed | Other specs, external standards          | Tickets, commits, worklog entries |
| Ages well?        | Yes — designed to outlast implementation | No — tied to a moment             |
| Safe to rewrite?  | Yes (versioned)                          | No (append-only)                  |

**Rule**: Never mix the two in one document. A spec paragraph written in past tense is a process note; move it to worklog. A worklog entry that begins "the system must" is a spec fragment; promote it.

### Business logic, not syntax translation

Documents that touch business concepts must describe the *why*, not the *what of the syntax*.

| Description style                                                       | Fits                     | Fails                                                   |
| ----------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------- |
| "Readmoo extractor falls back to alternate selector when primary fails" | Business / design intent | —                                                       |
| "A try-catch wraps the primary selector call"                           | —                        | Syntax translation, reader could get this from the code |

Rule: if the sentence describes code mechanics a compiler already enforces, delete it and write the business reason instead.

### Anti-patterns

| Anti-pattern                                                             | Fix                                                                     |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Opening with "This document describes..." meta-talk                      | Delete, start with the actual rule                                      |
| Spec paragraph citing a ticket ID (e.g. `v{X}-W{Y}-{seq}`)               | Move citation to worklog; keep spec ID-free                             |
| Methodology paragraph preserving "we used to do X but found Y" narrative | Keep the distilled rule; move the narrative to error-pattern or worklog |

---

## Principle 4 — Searchability × Documents: Titles, frontmatter, grep-friendly structure

### Core question

When a human or AI greps for a concept, does the right document surface, and does the right section surface within it?

### Title conventions

| Document type | Title format                           | grep target                  |
| ------------- | -------------------------------------- | ---------------------------- |
| Worklog       | `v{version} {theme} 工作日誌`          | `v{X.Y.Z}`, `工作日誌`       |
| README        | `{directory name}` or `{concept name}` | Directory keyword            |
| Spec          | `{UC ID} {behaviour name}`             | UC ID is the key             |
| Methodology   | `{subject} 方法論`                     | `方法論` + subject           |
| Error-pattern | `{ID}: {one-line symptom}`             | Pattern ID + symptom keyword |
| Ticket        | `{ID} {verb + target}`                 | Ticket ID + verb             |

### Heading conventions

- Every H2 heading contains a concept keyword that a reader would actually search for ("Split heuristics", not "More details").
- Avoid generic headings: "Overview", "Introduction", "Details", "Notes". They produce grep hits on every document.
- Prefer question-form or imperative headings: "When to split", "How to cite a sibling doc".

### YAML frontmatter

Frontmatter is the most grep-friendly slice of a document. Use it for:

| Field       | Purpose               | Document types                                            |
| ----------- | --------------------- | --------------------------------------------------------- |
| `id`        | Stable anchor         | Ticket, error-pattern, spec                               |
| `status`    | Lifecycle state       | Ticket, worklog                                           |
| `type`      | Taxonomy              | Ticket (IMP / ANA / DOC), error-pattern (PC / IMP / ARCH) |
| `relatedTo` | Weak link to siblings | Ticket, spec                                              |
| `version`   | Scoping               | Worklog, ticket, spec                                     |
| `tags`      | Cross-cutting search  | Methodology, error-pattern                                |

Frontmatter must be machine-parseable. Never include narrative text in values; keep values atomic (ID strings, statuses, dates).

### Grep-friendly body conventions

- Put the keyword in the same line as the assertion: "Worklog must be append-only" (not "It must be append-only" on its own line).
- When listing rules, repeat the subject: every row of a rule table should contain the rule's noun, not rely on column headers alone.
- Use separators (`→`, `:`, `|`) consistently so regex-based tooling can parse structure.

### Anti-patterns

| Anti-pattern                                           | Fix                                |
| ------------------------------------------------------ | ---------------------------------- |
| Document with no `id` field searched by filename only  | Add frontmatter for stable ID      |
| H2 `## Details` appearing in 30 documents              | Rename to concept-specific heading |
| Rules written as "It does X; it does Y" (pronoun-only) | Repeat the subject in each row     |

---

## Principle 5 — Field Design × Documents: Structural templates by type

### Core question

What sections must a document of type X contain, and how do those sections differ in angle?

Each field in a template exists to answer a specific question. Two fields answering the same question are a bug.

### Worklog template

| Section      | Answers                              | Angle                |
| ------------ | ------------------------------------ | -------------------- |
| Metadata     | Which version, dates, status?        | Identification       |
| 版本目標     | What did this version set out to do? | Intent               |
| 進度追蹤     | What happened and when?              | Chronological record |
| Phase tables | Which tickets exist, what state?     | Snapshot             |
| 技術筆記     | What non-ticket decisions were made? | Lateral knowledge    |

Append-only sections: 進度追蹤, 技術筆記. Mutable: Phase tables (statuses flip).

### README template

| Section                     | Answers                           | Angle  |
| --------------------------- | --------------------------------- | ------ |
| Title + one-line purpose    | What is this directory / project? | Orient |
| Sibling index               | What's inside?                    | Route  |
| Quick start (if applicable) | How do I use this in 60 seconds?  | Action |
| Further reading             | Where do I go next?               | Defer  |

### Spec template

| Section                   | Answers                   | Angle          |
| ------------------------- | ------------------------- | -------------- |
| UC metadata               | Stable IDs, priority      | Identification |
| Actors                    | Who uses this?            | Scope          |
| Preconditions             | What must be true before? | Entry guard    |
| Main flow                 | What happens on success?  | Happy path     |
| Alternative / error flows | What else can happen?     | Edge cases     |
| Acceptance criteria       | When is this UC done?     | Test hook      |

Angles must not overlap: preconditions are entry guards, not flows; acceptance criteria are pass/fail, not behaviour descriptions.

### Methodology template (from methodology-writing core)

| Section   | Answers                                   | Angle          |
| --------- | ----------------------------------------- | -------------- |
| 核心概念  | What is this methodology in one sentence? | Recall trigger |
| 執行步驟  | What do I do, in order?                   | Action list    |
| 檢查清單  | How do I verify I did it right?           | Self-check     |
| Reference | Where is the full implementation guide?   | Defer to SKILL |

30-second rule: if a reader cannot read the whole methodology in 30 seconds, either split it or move detail into a SKILL.

### Error-pattern template

| Section    | Answers                   | Angle                  |
| ---------- | ------------------------- | ---------------------- |
| Symptom    | What did the reader see?  | Recognition            |
| Root cause | Why did it happen?        | Diagnosis              |
| Prevention | How to stop it next time? | Forward-looking action |
| Detection  | How do we catch it early? | Tooling / hook         |

Each section answers a different question. Symptom is not cause; cause is not prevention.

### Ticket template

Ticket fields are extensively defined elsewhere (designing-fields.md). Key angles here:

| Field cluster | Angle                                                                      |
| ------------- | -------------------------------------------------------------------------- |
| `what`        | Description of the action and target                                       |
| `why`         | Motivation (distinct from `what`)                                          |
| `acceptance`  | Pass/fail criteria (distinct from `what` and `why`)                        |
| `how`         | Strategy (distinct from `what` — `what` is the outcome, `how` is the path) |

Overlap between `what` and `why` is the most common ticket bug. Keep them at different angles.

### Anti-patterns

| Anti-pattern                                                      | Fix                                              |
| ----------------------------------------------------------------- | ------------------------------------------------ |
| README lists "features" and "what it does" as two sections        | Collapse — same angle                            |
| Spec has "preconditions" and "setup requirements" as two sections | Collapse — same angle                            |
| Ticket `what` describes motivation                                | Move motivation to `why`, keep `what` for action |

---

## Worklog-Specific Extensions (distilled from worklog-writing methodology)

### Tool compatibility

Markdown table cells in worklogs must not contain multi-byte status emoji (`⏳`, `[SYNC]`, `[FAIL]`, etc.). CLI parsers have hit Rust panics on char-boundary issues. Use plain text:

| Status      | Plain text |
| ----------- | ---------- |
| Waiting     | 待處理     |
| In progress | 進行中     |
| Done        | 已完成     |
| Cancelled   | 取消       |
| Skipped     | 跳過       |
| Blocked     | 阻塞       |
| Failed      | 失敗       |

Emoji is allowed outside table cells (in prose headings).

### Five events that must be logged

Worklog records *decisions and milestones*, not execution detail (detail lives in tickets).

| Event             | Trigger                          | Format                                       |
| ----------------- | -------------------------------- | -------------------------------------------- |
| Ticket completed  | `ticket track complete`          | `{date}: {id} 完成 — {summary}`              |
| Task split        | Child tickets created            | `{date}: {parent} 拆分 — {child1}, {child2}` |
| Unplanned finding | New ticket created mid-execution | `{date}: 新增 {id} — {reason}`               |
| UC progression    | Group of related tickets done    | `{date}: UC-XX 步驟 Y 完成 — {outcome}`      |
| Blocker / risk    | Block or design issue found      | `{date}: {id} 阻塞 — {cause}`                |

Prefer bullet list over table: easier to append, diff-friendly, still readable past 20 entries.

### Narrative summary as legal alternative

When a session closes many tickets in a sprint, per-ticket bullets become impractical. A narrative summary covering the ticket ID range + key outcomes is acceptable:

```markdown
### {date}: {theme} 衝刺
- {ticket-range} 可觀測性修復：全域錯誤處理、靜默失敗路徑消除
- {ticket-range} 審查結論全部修復：AppLogger 遷移、ErrorHandler 防護
```

Priority order: per-ticket bullets > narrative summary > no record. Sprint-style summary is the fallback, not the default.

---

## Methodology-Specific Extensions (distilled from methodology-writing)

### Reader is an expert

Readers already know the content; they just forgot a detail. Your job is to help them recall, not to teach.

Forbidden phrasings:

- "You should..." (condescending)
- "Remember that..." (teaching)
- "The lesson here is..." (sermonising)

Replace with description of what was done and what was observed.

### 30-second elevator test

A methodology must be readable in 30 seconds. Everything beyond that belongs in a SKILL or reference.

If rewriting an old verbose methodology, the test is:

| Check                                                            | If fail                  |
| ---------------------------------------------------------------- | ------------------------ |
| Does the file contain a complete operational workflow?           | Move it to a SKILL       |
| Does it contain runnable code examples or error-handling detail? | Move to a SKILL          |
| Does compression lose critical information?                      | Create a SKILL alongside |

Methodology remains as the 30-second recall card; SKILL holds the full walk-through.

### Experience-sharing variant (six guidelines)

When the document is an experience-sharing write-up (not a methodology), six additional rules apply:

1. Share experience, do not teach. No "you should" / "remember to".
2. State facts, do not dramatise. Avoid "totally blew up", "I was lazy", etc.
3. Use functional description, not function names, in prose.
4. Not every problem is your own fault — don't self-blame for library bugs.
5. Every case needs discovery → diagnosis → fix, not just "problem was X, fixed as Y".
6. Avoid specific product/SDK names in prose; describe the structural problem.

---

## Self-Validation Checklist (run before committing the document)

- [ ] Document type identified, and structure matches the type's template
- [ ] Opening paragraph states the conclusion / rule (inverted pyramid)
- [ ] Spec content contains no process narrative; process content is not dressed as spec
- [ ] No section duplicates another section's angle (no double-answered questions)
- [ ] Cross-references state *why* to click, not just *where* to click
- [ ] No reference to a ticket ID / commit hash / worklog path inside a stable document (spec / methodology / error-pattern)
- [ ] Table cells in worklogs contain plain-text status, not emoji
- [ ] File length is either atomic (< ~500 lines) or the body holds a single concept despite length
- [ ] Headings contain searchable concept keywords (no generic "Overview" / "Details")
- [ ] Frontmatter fields, if present, are atomic and machine-parseable

---

## Multi-pass Re-read（refinement protocol）

The checklist above is a single-frame final sweep — not multi-pass. Multi-pass requires each round to use a **different frame** to catch errors at different layers ([#82](principles/literal-interception-vs-behavioral-refinement.md) / [#83](principles/writing-multi-pass-review.md)).

For documents (worklog / spec / methodology / error-pattern):

| Round | Frame                                                             | Document-specific checklist                                                                 |
| ----- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 1     | Generation                                                        | Get content end-to-end; expect rough phrasing                                               |
| 2     | Intent ([#67](principles/ease-of-writing-vs-intent-alignment.md)) | Does the document type match the structure used? Spec / process / methodology not mixed?    |
| 3     | Opportunity-cost tone                                             | Grep "must / should / always / never" — translate absolutes to "A in scenario X / B in Y"   |
| 4     | Grep-ability / naming                                             | Headings contain concept keywords (not "Overview"); cross-references explain *why* to click |
| 5     | Counter-cases / boundaries                                        | "When not to apply" section present? Examples cover edge cases not just happy path?         |
| 6'    | Stability layer                                                   | If this is a stable document (spec/methodology), are ticket IDs / commit hashes scrubbed?   |
| 7'    | Atomic check                                                      | < 500 lines OR single concept despite length? Sections each answer one question?            |

Skip rules: quick worklog notes can skip rounds 4-7'; stable specs / methodology should run all rounds twice.

---

## Quick Routing by Scenario

| You are about to...             | Jump to                                                                |
| ------------------------------- | ---------------------------------------------------------------------- |
| Write or append a worklog entry | Principle 1 + Worklog extensions                                       |
| Start a README from scratch     | Principle 2 (indexing) + Principle 5 (README template)                 |
| Draft a use-case spec           | Principle 3 (spec vs process) + Principle 5 (spec template)            |
| Rewrite a bloated methodology   | Methodology extensions (30-second test) + Principle 1 (atomize)        |
| Record a new error-pattern      | Principle 5 (error-pattern template) + Principle 4 (ID as grep anchor) |
| Fill a ticket's fields          | Principle 5 (ticket template), then consult designing-fields.md        |
