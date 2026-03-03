# 5W1H Integration Details

## Hook Integration

### PreToolUse Hook Integration

The 5W1H validation system is integrated into the Hook ecosystem:

- **Hook Name**: `5w1h-checker` (in `PreToolUse` hooks)
- **Trigger**: Before TodoWrite operations
- **Validation Scope**:
  - Checks all 6 W/H sections are present
  - Validates executor/dispatcher format
  - Detects avoidance language
  - Validates Task Type format
  - Ensures Agile Refactor compliance

### Session Token Generation

The UserPromptSubmit Hook automatically:
1. Generates a new session token: `5W1H-{YYYYMMDD}-{HHMMSS}-{random}`
2. Injects it into the user's context
3. Reminds about 5W1H format requirements

---

## Output Style Integration (System-Level Enforcement)

### Overview

Since v0.25.1, **5W1H format is enforced at the system level** via Output Style, not through manual activation or Hook execution.

**File Location**: `.claude/output-styles/5w1h-format.md`

### Enforcement Mechanism

- Output Style is injected into Claude's **system prompt**
- Every response **MUST follow the 5W1H format structure**
- **No manual activation required** — always active for all decisions

### Why System-Level Enforcement Matters

This dual-layer approach provides **robustness**:

| Layer | Mechanism | Purpose | Robustness |
|-------|-----------|---------|-----------|
| **System Prompt (Output Style)** | Injected at system level | Response format structure | Consistent even if Hooks fail |
| **PreToolUse Hook** | Validation before tool execution | Todo validation | Active verification |
| **UserPromptSubmit Hook** | Token generation + reminder | User reminder | Contextual assistance |

### Key Advantage

- Output Style provides **consistent format enforcement** without relying on Hook execution
- Even if Hooks fail or are temporarily disabled, Claude still follows the 5W1H format due to system-level injection
- Dual-layer approach ensures format compliance from multiple angles

---

## Token Generation Details

### Token Format

```text
5W1H-{YYYYMMDD}-{HHMMSS}-{random}
```

**Components**:
- `5W1H`: Fixed prefix identifying framework
- `YYYYMMDD`: Date in ISO 8601 format (e.g., 20250925)
- `HHMMSS`: Time in 24-hour format (e.g., 191735 for 19:17:35)
- `random`: 6-character alphanumeric suffix for uniqueness (e.g., a7b3c2)

**Example**: `5W1H-20250925-191735-a7b3c2`

### Automatic Token Injection

- **When**: Each time user submits a decision-making prompt
- **Where**: Injected into session context
- **Format**: Displayed at the start of decision analysis
- **Purpose**: Tracking related decisions across session

### Manual Token Generation

If needed, generate a token manually:

```bash
uv run .claude/skills/5w1h-decision/scripts/generate_token.py
```

### Token Validation

To validate 5W1H content against the token:

```bash
uv run .claude/skills/5w1h-decision/scripts/validate_5w1h.py "your 5w1h content here"
```

---

## Validation Engine Details

### Validation Scope

The 5W1H validation system checks:

1. **Completeness**: All 6 W/H sections present
2. **Format**: Proper executor/dispatcher and Task Type format
3. **Language**: No avoidance language detected
4. **Consistency**: Who-How executor/dispatcher alignment
5. **Traceability**: Requirement references present (for Why section)

### Avoidance Language Detection

**Blocked Keywords**:
- Quality compromise: "too complex", "workaround", "temporary fix", "quick fix"
- Simplification: "simpler approach", "easier way", "simplify"
- Problem ignoring: "ignore for now", "skip for now", "deal with later"
- Test compromise: "simplify test", "lower test standard", "basic test only"
- Code escape: "comment out", "disable", "temporarily disable"

### Task Type Validation

**Valid Task Type vs Executor Mapping**:

| Task Type | Valid Executors | Block Pattern |
|-----------|-----------------|---------------|
| Implementation | parsley, sage, pepper, thyme | rosemary executing Implementation |
| Dispatch | rosemary | Any agent executing Dispatch |
| Review | rosemary | Any agent executing Review |
| Documentation | thyme, rosemary | - |
| Analysis | lavender, rosemary | - |
| Planning | rosemary, lavender | - |

---

## Related Files

- **Framework Definition**: `.claude/methodologies/5w1h-self-awareness-methodology.md`
- **Agile Refactor Rules**: `.claude/methodologies/agile-refactor-methodology.md`
- **Avoidance Detection**: `.claude/methodologies/claude-self-check-methodology.md`
- **Output Style Enforcement**: `.claude/output-styles/5w1h-format.md`
- **Project Guidelines**: `CLAUDE.md` → Skill References section
