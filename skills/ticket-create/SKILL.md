---
name: ticket-create
description: "Interactive Atomic Ticket design and creation tool following Single Responsibility Principle. Use when: (1) Creating new tickets for development tasks, (2) Breaking down complex requirements into atomic tickets, (3) Creating tickets from test failures, (4) Batch creating multiple tickets from requirements description. Each ticket must have exactly one Action + one Target."
---

# Ticket Create

Interactive Atomic Ticket design and creation tool - guides users to design tickets following Single Responsibility Principle.

## Core Principle

**Atomic Ticket = One Action + One Target (Single Responsibility)**

Every ticket must pass the four validation checks:

1. **Semantic Check**: Can express as "verb + single target"?
2. **Modification Reason Check**: Only one reason would cause modification?
3. **Acceptance Consistency**: All acceptance criteria point to same target?
4. **Dependency Independence**: No circular dependencies if split?

## Prohibited Evaluation Methods

**NEVER use these metrics to determine if splitting is needed**:
- Time estimates (30 minutes, 1 hour)
- Lines of code (50 lines, 100 lines)
- File count (2 files, 5 files)
- Test count (5 tests, 10 tests)

**ONLY use the four Single Responsibility checks above.**

## Interactive Flow

### Step 1: Requirement Collection

```text
Claude: Please describe the task you want to complete:
```

Wait for user input.

### Step 2: Responsibility Analysis

Analyze user requirement and identify independent responsibilities:

```text
Claude: I identified the following independent responsibilities:
1. [Responsibility 1]
2. [Responsibility 2]
...

Each responsibility will become an independent Atomic Ticket.
```

### Step 3: Single Responsibility Check

For each identified responsibility, perform four checks:

```text
Claude: Responsibility 1 "[description]" Single Responsibility Check:
✅ Semantic: Can express as "[verb] + [target]"
✅ Modification Reason: Only "[reason]" would cause modification
✅ Acceptance Consistency: All criteria point to [target]
✅ Dependency Independence: No circular dependencies
→ Meets Atomic Ticket standard
```

If not passing, suggest further splitting:

```text
Claude: ⚠️ Responsibility 2 "[description]" needs further splitting:
❌ Modification Reason: Has two modification reasons
   - Reason A: [description]
   - Reason B: [description]
→ Suggest splitting into:
   - Ticket A: [verb] [target A]
   - Ticket B: [verb] [target B]
```

### Step 4: Ticket Creation Confirmation

```text
Claude: Suggest creating the following Atomic Tickets:

| ID | Action | Target | Agent |
|----|--------|--------|-------|
| {VERSION}-W1-001 | Implement | startScan() method | parsley |
| {VERSION}-W1-002 | Implement | stopScan() method | parsley |

Confirm creation? (Y/n)
```

### Step 5: Create YAML

After confirmation, create YAML definition for each Ticket.

Run:
```bash
uv run scripts/ticket-creator.py create \
  --id "{VERSION}-W1-001" \
  --action "Implement" \
  --target "startScan() method" \
  --agent "parsley-flutter-developer"
```

### Step 6: CSV Tracking Integration (Default)

```text
Claude: Add to CSV tracking system? (Y/n/--no-track to skip)
```

Default linked, run:
```bash
uv run scripts/ticket-creator.py add-to-csv --id {TICKET_ID}
```

## Available Commands

### Interactive Mode (Default)

```bash
/ticket-create
```

Guided Q&A to create Tickets step by step.

### Batch Mode

```bash
/ticket-create batch --description "requirement description"
```

Auto-identify responsibilities from description and batch create Tickets.

### From Test Failures

```bash
/ticket-create from-tests
```

Auto-create fix Tickets from latest test results (one Ticket per failing test).

### Without CSV Linking

```bash
/ticket-create --no-track
```

Only create YAML, don't add to CSV tracking.

## Ticket ID Format

```text
{Version}-W{Wave}-{Seq}
```

**Examples**:
- `0.15.16-W1-001` - v0.15.16, Wave 1, Ticket 1
- `0.15.16-W2-003` - v0.15.16, Wave 2, Ticket 3

### Wave Definition (Dependency Layers)

| Wave | Meaning | Can Execute |
|------|---------|-------------|
| W1 | No dependencies | Immediately, in parallel |
| W2 | Depends on some W1 tickets | After W1 dependencies complete |
| W3 | Depends on some W2 tickets | After W2 dependencies complete |

**Wave Assignment Rule**: Tickets with no dependencies → W1, tickets depending on W1 → W2, etc.

---

## Naming Conventions

**Action (Verb)**:
- `Implement` - Create new feature
- `Fix` - Correct error
- `Add` - Add test or documentation
- `Refactor` - Improve structure
- `Remove` - Delete feature

**Target (Noun)**:
- Specific method: `startScan() method`
- Specific class: `ISBNValidator class`
- Specific test: `ISBNValidator.validate() test`

## Common Mistakes

| Wrong | Problem | Correct |
|-------|---------|---------|
| Implement scanning and offline support | Two targets | Split into two Tickets |
| Fix all ISBN tests | Multiple targets | One Ticket per test |
| Refactor and optimize SearchService | Two actions | Split into two Tickets |

## Related Skills

- `/ticket-track` - Track Ticket status

## Resources

### scripts/
- `ticket-creator.py` - Main creation script

### references/
- `atomic-ticket-methodology.md` - Full Single Responsibility methodology
