---
name: ticket-track
description: "CSV-based Ticket tracking system. Provides two core capabilities: (1) READ operations for querying ticket info without loading full files - use query/list/summary commands, (2) UPDATE operations for agents to track progress without reporting back - use claim/complete/release commands. Eliminates need for agents to report progress to main thread."
---

# Ticket Track

CSV-based Ticket status tracking - eliminates the need to read full files or ask agents for progress.

## Core Design

```text
Main Thread              CSV File                    Agent
    │                       │                          │
    │  READ (query/list)    │                          │
    ├──────────────────────►│                          │
    │◄──────────────────────┤                          │
    │  (direct read)        │                          │
    │                       │                          │
    │                       │  UPDATE (claim/complete) │
    │                       │◄─────────────────────────┤
    │                       │  (direct write)          │
```

**Key Benefits**:
- No need to read full ticket files for status
- No need to ask agents for progress
- Minimal context consumption

---

## READ Operations (Main Thread / Any Role)

Query ticket info without loading full files.

### Query Single Ticket

```bash
uv run scripts/ticket-tracker.py query 0.15.16-W1-001 --version v0.15.16
```

Output: Status, agent, action+target from CSV.

### List Tickets by Status

```bash
# All tickets
uv run scripts/ticket-tracker.py list

# Filter by status
uv run scripts/ticket-tracker.py list --in-progress
uv run scripts/ticket-tracker.py list --pending
uv run scripts/ticket-tracker.py list --completed
```

### Quick Summary

```bash
# Auto-detect version
uv run scripts/ticket-tracker.py summary

# Specify version
uv run scripts/ticket-tracker.py summary --version v0.15.16
```

**Output Example**:
```text
📊 Ticket Summary v0.15.16 (2/34 completed)
0.15.16-W1-001 | ✅ | parsley | Fix ISBNValidator.validate() 格式驗證
0.15.16-W1-002 | 🔄 | parsley | Implement ISBNScannerService.startScan()/stopScan() (1h30m)
0.15.16-W1-003 | ⏸️ | parsley | Implement ISBNScannerService 掃描結果處理
```

---

## UPDATE Operations (Agent Use)

Update status without reporting back to main thread.

### Claim Ticket (Before Starting)

```bash
uv run scripts/ticket-tracker.py claim 0.15.16-W1-001 --version v0.15.16
```

Records: `assigned=true`, `started_at=now`

### Complete Ticket (After Finishing)

```bash
uv run scripts/ticket-tracker.py complete 0.15.16-W1-001 --version v0.15.16
```

Records: `completed=true`

### Release Ticket (If Unable to Continue)

```bash
uv run scripts/ticket-tracker.py release 0.15.16-W1-001 --version v0.15.16
```

Records: `assigned=false`, clears `started_at`

---

## Admin Operations (Main Thread)

### Initialize Version

```bash
uv run scripts/ticket-tracker.py init v0.15.16
```

Creates version folder and empty `tickets.csv`.

### Add Ticket

```bash
uv run scripts/ticket-tracker.py add --id 0.15.16-W1-001 --version v0.15.16
```

Adds ticket to CSV tracking (typically use `/ticket-create` instead).

---

## CSV Format (Atomic Ticket v3.0)

```csv
ticket_id,action,target,agent,wave,dependencies,assigned,started_at,completed
0.15.16-W1-001,Fix,ISBNValidator.validate(),parsley,1,,false,,false
0.15.16-W2-001,Implement,Book AggregateRoot,parsley,2,W1-006;W1-007,false,,false
```

| Column | Description |
|--------|-------------|
| ticket_id | Format: `{Version}-W{Wave}-{Seq}` |
| action | Fix, Implement, Add, Refactor, Remove |
| target | Single responsibility target |
| agent | Executing agent name |
| wave | Dependency layer (1, 2, 3) |
| dependencies | Semicolon-separated dependency IDs |
| assigned | true/false |
| started_at | ISO timestamp |
| completed | true/false |

---

## Status Icons

| Icon | Status | Condition |
|------|--------|-----------|
| ⏸️ | Pending | `assigned=false` |
| 🔄 | In Progress | `assigned=true`, `completed=false` |
| ✅ | Completed | `completed=true` |

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

## Related Skills

- `/ticket-create` - Create Atomic Tickets interactively

## Resources

### scripts/
- `ticket-tracker.py` - Main tracking script

### references/
- `csv-ticket-tracking-methodology.md` - Full methodology
