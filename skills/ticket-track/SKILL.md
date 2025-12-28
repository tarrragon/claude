---
name: ticket-track
description: "Frontmatter-based Ticket tracking system. Provides two core capabilities: (1) READ operations for querying ticket info without loading full files - use query/list/summary commands, (2) UPDATE operations for agents to track progress without reporting back - use claim/complete/release commands. Eliminates need for agents to report progress to main thread."
---

# Ticket Track

Frontmatter-based Ticket status tracking - eliminates the need to read full files or ask agents for progress.

## Core Design

```text
Main Thread              Ticket Frontmatter           Agent
    |                           |                        |
    |  READ (query/list)        |                        |
    |-------------------------->|                        |
    |<--------------------------|                        |
    |  (direct read)            |                        |
    |                           |                        |
    |                           |  UPDATE (claim/complete)
    |                           |<-----------------------|
    |                           |  (direct write)        |
```

**Key Benefits**:
- No need to read full ticket files for status
- No need to ask agents for progress
- Minimal context consumption
- Single file architecture (status in frontmatter)

---

## Frontmatter Status Fields

Status is tracked directly in each Ticket's YAML frontmatter:

```yaml
---
# ... other fields ...

# === Status Tracking ===
status: "pending"        # pending | in_progress | completed
assigned: false          # true if someone claimed
started_at: null         # ISO 8601 timestamp
completed_at: null       # ISO 8601 timestamp
---
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "pending", "in_progress", "completed" |
| `assigned` | boolean | Whether someone has claimed the ticket |
| `started_at` | datetime | When work started (ISO 8601, e.g., 2025-12-27T10:30:00) |
| `completed_at` | datetime | When work completed (ISO 8601) |

---

## READ Operations (Main Thread / Any Role)

Query ticket info without loading full files.

### Query Single Ticket

```bash
uv run .claude/hooks/ticket-tracker.py query 0.16.0-W1-001 --version v0.16.0
```

Output: Status, agent, action+target, 5W1H from frontmatter.

### List Tickets by Status

```bash
# All tickets
uv run .claude/hooks/ticket-tracker.py list --version v0.16.0

# Filter by status
uv run .claude/hooks/ticket-tracker.py list --in-progress --version v0.16.0
uv run .claude/hooks/ticket-tracker.py list --pending --version v0.16.0
uv run .claude/hooks/ticket-tracker.py list --completed --version v0.16.0
```

### Quick Summary

```bash
# Auto-detect version
uv run .claude/hooks/ticket-tracker.py summary

# Specify version
uv run .claude/hooks/ticket-tracker.py summary --version v0.16.0
```

**Output Example**:
```text
📊 Ticket Summary v0.16.0 (2/34 completed) [markdown]
----------------------------------------------------------------------------------------------------
0.16.0-W1-001 | ✅ | parsley         | Fix ISBNValidator.validate() format validation
0.16.0-W1-002 | 🔄 | parsley         | Implement ISBNScannerService.startScan() (1h30m)
0.16.0-W1-003 | ⏸️ | parsley         | Implement ISBNScannerService result handling
```

---

## UPDATE Operations (Agent Use)

Update status without reporting back to main thread.

### Claim Ticket (Before Starting)

```bash
uv run .claude/hooks/ticket-tracker.py claim 0.16.0-W1-001 --version v0.16.0
```

Updates frontmatter:
- `assigned: true`
- `started_at: [current ISO timestamp]`
- `status: "in_progress"`

**Output**:
```text
✅ Claimed 0.16.0-W1-001
   Start Time: 2025-12-27T10:30:00
```

### Complete Ticket (After Finishing)

```bash
uv run .claude/hooks/ticket-tracker.py complete 0.16.0-W1-001 --version v0.16.0
```

Updates frontmatter:
- `status: "completed"`
- `completed_at: [current ISO timestamp]`

**Output**:
```text
✅ Completed 0.16.0-W1-001 (1h30m)
```

### Release Ticket (If Unable to Continue)

```bash
uv run .claude/hooks/ticket-tracker.py release 0.16.0-W1-001 --version v0.16.0
```

Updates frontmatter:
- `assigned: false`
- `started_at: null`
- `status: "pending"`

**Output**:
```text
✅ Released 0.16.0-W1-001
```

---

## Status Icons

| Icon | Status | Condition |
|------|--------|-----------|
| ⏸️ | Pending | `status: "pending"` |
| 🔄 | In Progress | `status: "in_progress"` |
| ✅ | Completed | `status: "completed"` |

---

## Backward Compatibility (v0.15.x CSV Format)

The tracker supports **read-only** access to old CSV-format tickets for historical reference.

### How It Works

When querying older versions (v0.15.x), the system:

1. **Auto-detects format**: Checks for `tickets/` directory (Markdown) or `tickets.csv` (CSV)
2. **Falls back to CSV**: If Markdown tickets not found, reads from CSV
3. **Display warning**: Shows read-only notice for CSV format

### Example

```bash
uv run .claude/hooks/ticket-tracker.py summary --version v0.15.16
```

**Output**:
```text
⚠️  v0.15.16 uses old CSV format (read-only mode)
   Status update commands (claim/complete/release) not supported in v0.15.x
   Please upgrade to v0.16.0+ for new Markdown Ticket system

📊 Ticket Summary v0.15.16 (15/34 completed) [csv]
----------------------------------------------------------------------------------------------------
...
```

### Limitations

| Operation | v0.16.0+ (Markdown) | v0.15.x (CSV) |
|-----------|---------------------|---------------|
| `summary` | ✅ Full support | ✅ Read-only |
| `list` | ✅ Full support | ✅ Read-only |
| `query` | ✅ Full support | ⚠️ Limited |
| `claim` | ✅ Full support | ❌ Not supported |
| `complete` | ✅ Full support | ❌ Not supported |
| `release` | ✅ Full support | ❌ Not supported |

---

## Best Practices

### Main Thread

- **DON'T** ask agents for progress → Use `summary` command
- **DON'T** read ticket files for status → Use `query` command
- **DO** run `summary` regularly for overview

### Agents

- **DON'T** report progress to main thread → Use `complete` command
- **DO** run `claim` before starting
- **DO** run `complete` after finishing

---

## File Structure

```text
docs/work-logs/
├── v0.16.0/                     # New version (Markdown format)
│   └── tickets/
│       ├── 0.16.0-W1-001.md     # Ticket with frontmatter
│       ├── 0.16.0-W1-002.md
│       └── ...
├── v0.15.16/                    # Old version (CSV format, read-only)
│   ├── tickets.csv              # Legacy CSV tracking
│   └── ...
```

---

## Related Skills

- `/ticket-create` - Create Atomic Tickets interactively

## Resources

### Scripts
- `.claude/hooks/ticket-tracker.py` - Main tracking script
- `.claude/hooks/frontmatter_parser.py` - Frontmatter parsing module

### References
- `.claude/methodologies/frontmatter-ticket-tracking-methodology.md` - Full methodology
- `.claude/methodologies/csv-ticket-tracking-methodology.md` - Legacy CSV methodology (deprecated)
