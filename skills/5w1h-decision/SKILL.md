---
name: 5w1h-decision
description: "5W1H Decision Framework Tool. Use for: (1) Systematic decision-making before creating todos, (2) Preventing duplicate implementation, (3) Detecting avoidance behavior, (4) Ensuring agile refactor compliance with executor/dispatcher separation"
---

# 5W1H Decision Framework - Systematic Decision Making

## Core Principles

| Principle | Description | Validation |
|-----------|-------------|------------|
| Systematic Thinking | Every decision requires 5W1H analysis | All 6 questions answered |
| No Duplication | Check existing implementation first | Who analysis complete |
| No Avoidance | Reject escape language | Why validation passed |
| Agile Compliance | Executor/Dispatcher separation | How task type matched |
| TDD Integration | Test-first strategy required | How includes TDD steps |

---

## 5W1H Framework Quick Reference

### Who (Responsibility Attribution)

```markdown
Who: {Executor Agent} (executor) | rosemary-project-manager (dispatcher)
- Domain: {Responsible class/module}
- Existing: {Search result for duplicates}
```

**Valid Patterns**: `parsley-flutter-developer (executor) | rosemary-project-manager (dispatcher)`

---

### What (Function Definition)

```markdown
What: {Function Name}
- Description: {One sentence description}
- Input: {Explicit input types}
- Output: {Explicit output types}
- Exception: {Error handling}
```

---

### When (Trigger Timing)

```markdown
When: {Event Name}
- Trigger: {User action / System event}
- Side Effects: {List all side effects}
- Integration: {Event system integration point}
```

---

### Where (Execution Location)

```markdown
Where: {Layer} / {Component}
- Architecture: {Domain/Application/Infrastructure/Presentation}
- Component: {Specific class or module}
- UseCase: {UseCase call chain}
```

---

### Why (Motivation Validation)

```markdown
Why: {Requirement Reference}
- Requirement ID: {UC-XXX}
- Business Value: {User benefit}
- User Scenario: {Specific use case}
```

**Avoidance Language Detection** (BLOCKED):
- Quality compromise: "too complex", "workaround", "temporary fix", "quick fix"
- Simplification: "simpler approach", "easier way", "simplify"
- Problem ignoring: "ignore for now", "skip for now", "deal with later"
- Test compromise: "simplify test", "lower test standard", "basic test only"
- Code escape: "comment out", "disable", "temporarily disable"

---

### How (Implementation Strategy)

```markdown
How: [Task Type: {TYPE}] {Strategy Description}
```

**Task Type vs Executor Mapping**:

| Task Type | Valid Executor | Invalid Executor |
|-----------|----------------|------------------|
| Implementation | parsley, sage, pepper | rosemary (BLOCKED) |
| Dispatch | rosemary | Any agent (BLOCKED) |
| Review | rosemary | Any agent (BLOCKED) |
| Documentation | thyme, rosemary | - |
| Analysis | lavender, rosemary | - |
| Planning | rosemary, lavender | - |

---

## Checklist Before Todo Creation

### Completeness Check

- [ ] **Who**: Executor/Dispatcher clearly identified, no duplicate implementation
- [ ] **What**: Single responsibility, clear I/O definition
- [ ] **When**: Trigger timing explicit, side effects identified
- [ ] **Where**: Correct architecture layer, UseCase path clear
- [ ] **Why**: Requirement reference, no avoidance language
- [ ] **How**: Task Type present, TDD strategy, matches executor

### Agile Refactor Compliance Check

- [ ] Who has `(executor) | (dispatcher)` format
- [ ] How has `[Task Type: XXX]` prefix
- [ ] Implementation tasks assigned to agents (not main thread)
- [ ] Dispatch/Review tasks assigned to main thread

### Quality Gate

**ALL items must be checked before creating todo.**

Missing any item = BLOCKED

---

## Key References

| Reference | Purpose |
|-----------|---------|
| [Complete Template](./references/5w1h-template.md) | Full template format and token generation |
| [Common Violations](./references/common-violations.md) | Violation patterns and fixes |
| [Integration Details](./references/integration-details.md) | Hook/Output Style/Token validation engine |
| [5W1H Methodology](.claude/methodologies/5w1h-self-awareness-methodology.md) | Complete methodology |
| [Agile Refactor Methodology](.claude/methodologies/agile-refactor-methodology.md) | Executor/Dispatcher separation rules |

---

## Quick Reference Card

### Required Format

```text
5W1H-{TOKEN}

Who: {agent} (executor) | rosemary-project-manager (dispatcher)
What: {Single responsibility function}
When: {Event trigger with side effects}
Where: {Architecture layer / Component}
Why: {Requirement ID + Business value}
How: [Task Type: {TYPE}] {TDD strategy steps}
```

### System-Level Enforcement

5W1H format is automatically enforced via:
- **Output Style** (system prompt injection) - Always active
- **PreToolUse Hook** - Validates todo creation
- **UserPromptSubmit Hook** - Generates session token
