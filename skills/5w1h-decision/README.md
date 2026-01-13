# 5W1H Decision Framework - Quick Reference

## Purpose

Ensure systematic decision-making before creating todos by requiring:
- 5W1H complete analysis (Who, What, When, Where, Why, How)
- Executor/Dispatcher separation (Agile Refactor compliance)
- Task Type matching
- Avoidance language detection

## Enforcement Mechanisms

**Three-Layer Enforcement Architecture**:

| Layer | File | When Active |
|-------|------|-------------|
| **Output Style** | `.claude/output-styles/5w1h-format.md` | Always (system prompt) |
| **Hook** | UserPromptSubmit + PreToolUse | Each interaction |
| **SKILL** | This document | On-demand reference |

**Output Style** (v0.25.1+):
- System-level format enforcement
- Injected into Claude's system prompt automatically
- Ensures consistent 5W1H response structure

## Quick Start

### Required Format

```markdown
5W1H-{TOKEN}

Who: {agent} (executor) | rosemary-project-manager (dispatcher)
What: {Single responsibility function}
When: {Event trigger}
Where: {Architecture layer}
Why: {Requirement ID}
How: [Task Type: {TYPE}] {TDD strategy}
```

## Cheat Sheet

### Who - Executor/Dispatcher

| Scenario | Format |
|----------|--------|
| Code implementation | `parsley-flutter-developer (executor) \| rosemary (dispatcher)` |
| Task dispatch | `rosemary-project-manager (self-execute - dispatch/review)` |
| Documentation | `thyme-documentation-integrator (executor) \| rosemary (dispatcher)` |

### How - Task Types

| Type | Executor | Blocked |
|------|----------|---------|
| Implementation | parsley, sage, pepper | rosemary |
| Dispatch | rosemary | agents |
| Review | rosemary | agents |
| Documentation | thyme, rosemary | - |

### Avoidance Keywords (BLOCKED)

| Category | Keywords |
|----------|----------|
| Escape | "too complex", "workaround", "temporary" |
| Simplify | "simpler approach", "easier way" |
| Defer | "for now", "later", "skip" |
| Test | "simplify test", "basic test only" |

## Validation

### Quick Checklist

- [ ] Who has (executor) | (dispatcher)
- [ ] What is single responsibility
- [ ] When has trigger event
- [ ] Where has architecture layer
- [ ] Why has requirement reference
- [ ] How has [Task Type: XXX]

### Run Validation

```bash
# Generate session token
uv run .claude/skills/5w1h-decision/scripts/generate_token.py

# Validate content
uv run .claude/skills/5w1h-decision/scripts/validate_5w1h.py "content"
```

## Common Mistakes

### Missing Task Type

```markdown
// WRONG
How: TDD strategy

// CORRECT
How: [Task Type: Implementation] TDD strategy
```

### Main Thread Implementation

```markdown
// WRONG
Who: rosemary-project-manager
How: [Task Type: Implementation] Build classes

// CORRECT
Who: parsley-flutter-developer (executor) | rosemary (dispatcher)
How: [Task Type: Implementation] Build classes
```

## Full Documentation

See [SKILL.md](./SKILL.md) for complete reference.

### Related Files

| File | Purpose |
|------|---------|
| [Output Style](../../../.claude/output-styles/5w1h-format.md) | System-level format enforcement |
| [SKILL.md](./SKILL.md) | Complete 5W1H reference |
| [5W1H Methodology](../../../.claude/methodologies/5w1h-self-awareness-methodology.md) | Full methodology |
