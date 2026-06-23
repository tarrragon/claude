---
name: skill-sync
description: 'Sync Claude Code skills between local .claude/skills/ and a remote skills repository. Use for: pulling skills from remote, pushing local skills to remote, listing available remote skills.'
---

# skill-sync

Sync Claude Code skills between local `.claude/skills/` and a remote skills repository.

## Installation

```bash
uv tool install --from .claude/skills/skill-sync skill-sync
```

## Commands

| Command | Description |
|---------|-------------|
| `skill-sync pull <name>` | Pull a skill from the remote repo to `.claude/skills/<name>/` |
| `skill-sync push <name>` | Push a local skill to the remote repo |
| `skill-sync list` | List all available skills in the remote repo |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SKILL_SYNC_REPO` | `https://github.com/tarrragon/claude-skills.git` | Remote skills repository URL |

## Notes

- `project-integration/` subdirectories are excluded from both pull and push operations
- This tool has zero framework dependencies and works in any project

---

**Version**: 1.0.0
