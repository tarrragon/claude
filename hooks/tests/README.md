# Hook Tests Execution SOP

This directory contains Python tests for `.claude/hooks/`. Test files use two different dependency models, so do not assume a single global `pytest` environment.

## 1. Detect Inline Dependencies First

Before running a hook test file, check whether it declares PEP 723 inline script metadata:

```bash
rg -n "^# /// script|^# dependencies =" .claude/hooks/tests/<test-file>.py
```

Current files with inline dependencies:

```text
.claude/hooks/tests/test_agent_dispatch_check.py  -> pytest, pyyaml
.claude/hooks/tests/test_frontmatter_parser.py    -> pytest>=7.0, pyyaml>=6.0
.claude/hooks/tests/test_ticket_tracker.py        -> pytest
```

## 2. Single File Execution

For tests with PEP 723 metadata, run the file itself so `uv` reads the inline dependencies:

```bash
uv run .claude/hooks/tests/test_agent_dispatch_check.py
uv run .claude/hooks/tests/test_frontmatter_parser.py
uv run .claude/hooks/tests/test_ticket_tracker.py
```

For tests without inline dependencies, use an explicit pytest environment:

```bash
uv run --with pytest python -m pytest .claude/hooks/tests/<test-file>.py -v
```

Do not use bare `pytest` as the official verification command. A missing local pytest entrypoint only proves the current shell lacks pytest, not that the hook test is broken.

## 3. Targeted Test Selection

PEP 723 metadata is only consumed when `uv` runs the script file directly. If you need pytest node selection for a file with inline dependencies, mirror those dependencies as `--with` flags:

```bash
uv run --with pytest --with pyyaml python -m pytest \
  .claude/hooks/tests/test_agent_dispatch_check.py::test_agent_to_task_map_shortcircuit -v
```

For files without inline dependencies:

```bash
uv run --with pytest python -m pytest \
  .claude/hooks/tests/test_handoff_prompt_reminder_hook.py::test_reminder_message_points_to_runqueue_entry -v
```

## 4. Full Suite Strategy

There is no single command that automatically merges every test file's PEP 723 dependencies during pytest collection. Use one of these strategies:

- Run PEP 723 files directly with `uv run <file>`.
- Run ordinary pytest files with `uv run --with pytest python -m pytest <files...> -v`.
- For a mixed batch, pass the union of required dependencies explicitly, for example:

```bash
uv run --with pytest --with pyyaml python -m pytest .claude/hooks/tests/ -v
```

If a mixed batch fails with `ModuleNotFoundError` for a dependency declared in a test file header, rerun with that dependency added as `--with <package>` before treating the failure as a test regression.

## 5. Result Recording

Ticket Test Results should record the exact `uv` command used. For hook tests, prefer one of:

```bash
uv run .claude/hooks/tests/<pep723-test-file>.py
uv run --with pytest python -m pytest .claude/hooks/tests/<ordinary-test-file>.py -v
uv run --with pytest --with <dependency> python -m pytest .claude/hooks/tests/<test-file>.py -v
```
