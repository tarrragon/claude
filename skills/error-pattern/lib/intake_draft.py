#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""依收錄請求格式從本地 pattern 檔組出 issue 草稿，印到 stdout。

格式唯一定義處：.claude/skills/framework-issue/references/content-intake-request.md
本工具不寫入 .claude/。缺項（README 無該列、carrier 未填、ID 無專案代號）
在 stderr 報出並以 exit 1 結束，不產生半成品。
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

_ID_RE = re.compile(r"^([A-Z]+)-([A-Z0-9]+)-(\d+)")
_MIN_FENCE = 4
_SUBSTITUTION_PLACEHOLDER = "<替換專案名稱與檔案路徑後仍有意義的理由，一句>"

_STATEMENT = """主控方依下列條件收錄；任一條不接受，於 issue 留言說明，不自行改寫後收錄。

- 檔名前綴與出處（`source_project`）保留。
- 區塊 1 至 3 的字面不改寫；格式或用語需調整時，退回 consumer 修改。
- 區塊 3 的列收錄後，下次 `sync-pull` 帶回的列須與 consumer 本地列字面相同。"""


class DraftError(Exception):
    """草稿缺項，無法產生。"""


def _frontmatter(text):
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _fence(content, language):
    longest = max((len(m) for m in re.findall(r"`+", content)), default=0)
    ticks = "`" * max(_MIN_FENCE, longest + 1)
    return f"{ticks}{language}\n{content.rstrip(chr(10))}\n{ticks}"


def _readme_row(readme_path, pattern_id):
    prefix = f"| {pattern_id} |"
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line
    raise DraftError(f"README 索引缺 {pattern_id} 的列：{readme_path}")


def _registry_block(registry_path, code, project_dir):
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    registered = {p.get("code"): p for p in data.get("projects") or []}
    if code in registered:
        return "已登錄", registered[code].get("dir", project_dir)
    entry = f"  - code: {code}\n    dir: {project_dir}\n    note: ''"
    return entry, project_dir


def build_draft(pattern_path, claude_dir):
    pattern_path, claude_dir = Path(pattern_path), Path(claude_dir)
    text = pattern_path.read_text(encoding="utf-8")
    match = _ID_RE.match(pattern_path.name)
    if not match:
        raise DraftError(f"檔名無來源前綴 ID（<類別>-<專案代號>-NNN）：{pattern_path.name}")
    pattern_id = match.group(0)
    carrier = _frontmatter(text).get("carrier")
    if not carrier:
        raise DraftError(f"{pattern_id} frontmatter 未填 carrier")

    patterns_dir = claude_dir / "error-patterns"
    row = _readme_row(patterns_dir / "README.md", pattern_id)
    project_dir = claude_dir.resolve().parent.name
    registry, source_project = _registry_block(
        patterns_dir / "_project-registry.yaml", match.group(2), project_dir
    )
    version = (claude_dir / "VERSION").read_text(encoding="utf-8").strip()
    target = pattern_path.resolve().relative_to(patterns_dir.resolve()).as_posix()
    registry_body = registry if registry == "已登錄" else _fence(registry, "yaml")
    return "\n".join(
        [
            "<!-- content-intake-request -->",
            "",
            "### 0. 請求資訊",
            "",
            "| 欄位 | 值 |",
            "|------|-----|",
            f"| pattern_id | {pattern_id} |",
            f"| target_path | {target} |",
            f"| source_project | {source_project} |",
            f"| framework_version | {version} |",
            "| status | 待收錄 |",
            "",
            "### 1. pattern 全文",
            "",
            _fence(text, "markdown"),
            "",
            "### 2. 索引列",
            "",
            _fence(row, "markdown"),
            "",
            "### 3. registry 列",
            "",
            registry_body,
            "",
            "### 4. 可攜性判定",
            "",
            "| 欄位 | 值 |",
            "|------|-----|",
            "| 判定 | 可攜 |",
            f"| 替換測試 | {_SUBSTITUTION_PLACEHOLDER} |",
            f"| carrier | {carrier} |",
            "",
            "### 5. 原樣收錄聲明",
            "",
            _STATEMENT,
            "",
        ]
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern", help="pattern 檔路徑")
    parser.add_argument("--claude-dir", default=".claude", help=".claude 目錄")
    args = parser.parse_args(argv)
    try:
        draft = build_draft(args.pattern, args.claude_dir)
    except (DraftError, OSError, ValueError) as exc:
        sys.stderr.write(f"intake_draft: {exc}\n")
        return 1
    sys.stdout.write(draft)
    return 0


if __name__ == "__main__":
    sys.exit(main())
