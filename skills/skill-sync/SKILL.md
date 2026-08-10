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
| `skill-sync pull` | Report only. Compares every installed skill against the remote manifest by content hash and prints what diverges, along with the `pull` / `push` command for each. Writes nothing — `--force` has no effect on this path |
| `skill-sync pull <name>` | Copy the remote copy of one skill over `.claude/skills/<name>/`. Files that exist only locally are kept. Prompts before applying unless `--force` |
| `skill-sync push <name>` | Copy one local skill to the remote repo. Files that exist only on the remote are kept. Prompts before applying unless `--force`; `-m` sets the commit message |
| `skill-sync push <name> --prune` | Push, and delete files that exist only on the remote. Use after deleting or renaming files locally, otherwise the removal never reaches other consumers |
| `skill-sync list` | List the remote repo's top-level entries with the first line of each `SKILL.md`. Non-skill entries at the root (`README.md`, `versions.json`) appear too, with an empty description |

Direction is never inferred. A content hash proves two copies differ, not which one is newer, so `skill-sync pull` (no name) stops at reporting and leaves the choice of `pull <name>` or `push <name>` to you. Version strings are shown for reading, never compared: two copies that evolved separately can carry the same version number and different content.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SKILL_SYNC_REPO` | `https://github.com/tarrragon/claude-skills.git` | Remote skills repository URL |

## Notes

- `project-integration/`, `hook-logs/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `build/` and `*.egg-info` are excluded from every comparison, and `--prune` cannot reach them — neither their files nor a directory of theirs left empty
- Deletion is opt-in on purpose: keeping remote-only files by default protects upstream content from being wiped by a stale local copy, at the cost of local deletions not propagating until `--prune` is passed
- A `.skill-sync-override` file inside a skill directory declares its local content as deliberate customization. `skill-sync pull` (no name) then skips that skill when reporting divergence, and the marker itself is left out of the content hash
- Consumers outside this CLI should call `sync_status_report(skills_dir)` rather than assembling the pipeline from its parts; re-deriving the fetch also re-derives which repo it points at
- This tool has zero framework dependencies and works in any project

---

**Version**: 1.6.0 — `update_sync_manifest` 與 `_extract_local_manifest` 掃描時，對「目錄內無精確大寫 `SKILL.md` 但存在其他大小寫變體」輸出 stderr 告警，不再靜默略過。此前這類目錄不進入 manifest，手動補寫的記錄會被下一次重算抹除，形成補齊後回退的循環。判準讀 `os.scandir` 的真實 dirent 名稱——`Path.exists()` 在 case-insensitive 檔案系統上對小寫檔回 True，`Path.glob()` 的大小寫敏感性則同時受 Python 版本（3.13 起改為探測檔案系統）與檔案系統影響，兩者當判準都會失效。同檔 docstring 原稱 glob 在 posix 平台恆為 case-sensitive，一併更正為版本相依的準確敘述。
**Version**: 1.5.0 — Documentation correction. The `skill-sync pull` (no name) row claimed it pulls outdated skills automatically and reports conflicts where the local copy is newer; it does neither. That path writes nothing, and a content hash cannot tell which copy is newer — the wording described behaviour removed when hash comparison replaced version-string comparison. Every other row was re-checked against the code in the same pass: `--force` and `-m` were undocumented, `list` also prints non-skill root entries, and the `.skill-sync-override` marker was absent from the notes entirely. `compute_content_hash` now states why it must not be confused with the identically named function in `.claude/lib/sync_exclude_manifest.py`.
**Version**: 1.4.0 — `--prune` now honours `EXCLUDE_DIRS` when removing directories the deletion emptied, so an already-empty `project-integration/` survives; previously the sweep was unconditional and the "cannot reach them" guarantee above held for files only. `unlink` tolerates a missing target and `rmdir` tolerates `OSError`, so a symlinked or unwritable directory no longer aborts a push midway through an already-modified clone. `cmd_push` folds the diff and the prune decision into one plan via `build_push_plan`, and `print_diff_preview` no longer takes a `prune` argument — callers no longer keep two views of the same policy in sync by hand.
**Version**: 1.3.0 — Adds a public `sync_status_report(skills_dir)` that owns repo resolution, manifest fetch and classification in one call, so a consumer needs one entry point instead of assembling the middle of the pipeline itself. A consumer that re-derived the fetch also re-derived the repo it pointed at, and ended up comparing local content against a different remote than this CLI used (see `ARCH-BAL-016`). Diverged entries now carry their own `pull_command` / `push_command`, so consumers print what this module says to run rather than keeping a hand-written copy that drifts from the actual subcommands. Remote fetch timeout drops from 10s to 5s.
**Version**: 1.2.0 — Adds `--prune` to `push`: deletes remote-only files when asked, keeps them by default. Without it a file deleted or renamed locally never reaches the remote, and other consumers keep pulling it down (observed: four hooks removed or renamed locally still sitting in the canonical repo). Also extracts `build_parser()`, so a downstream project that prints a `skill-sync` command can assert in a test that the subcommand exists.
**Version**: 1.1.0
