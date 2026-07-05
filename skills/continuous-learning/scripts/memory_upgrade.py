"""memory promote/scan 升級工具核心（1.5.0-W5-011.3）。

規則層（quality-baseline 規則 7 / PC-061）已定義「捕獲時分流」與「升級後處理
三步」，但三步（建 error-pattern 檔 + 原 memory 頂部標註 + MEMORY.md 索引修剪）
仍是純人工多步操作，130 檔 feedback memory 實測標註率僅 4%。本模組將三步
機械化為單一 `promote` 命令，並提供 `scan` 使積壓（未評估 / deferred /
dangling pointer）可見化，使正確路徑成為最低摩擦路徑
（opinionated-default-design 主張 2/3）。

依賴重用（禁複製，PC-135）：
- allocator：`.claude/skills/error-pattern/lib/allocator.py` 的
  `allocate_pattern_id` / `identify_project_code`
- ID regex：`.claude/lib/pattern_id.py` 的 `PATTERN_ID_RE`（SSOT）

頂部標註格式精確對齊
`.claude/skills/continuous-learning/references/upgrade-decision-tree.md:186-192`。
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_claude_dir = Path(__file__).resolve().parents[3]  # .claude
if str(_claude_dir) not in sys.path:
    sys.path.insert(0, str(_claude_dir))

_allocator_lib = _claude_dir / "skills" / "error-pattern" / "lib"
if str(_allocator_lib) not in sys.path:
    sys.path.insert(0, str(_allocator_lib))

from lib.pattern_id import PATTERN_ID_RE  # noqa: E402
from allocator import (  # noqa: E402
    _CATEGORY_DIRS,
    allocate_pattern_id,
    identify_project_code,
)

_STATUS_ANNOTATION_MARKER = "> **Status**: Upgraded"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)


def _parse_frontmatter(text: str, source_name: str = "<unknown>") -> dict:
    """解析檔案開頭的 YAML frontmatter；無 frontmatter 或解析失敗回傳空 dict。

    真實資料常見 frontmatter 值含未引號冒號（如
    `description: ... originSessionId: xxx`）導致 `yaml.safe_load` 拋
    `ScannerError`；此為單一壞檔的 malformed 資料，不應中斷整批掃描
    （PC-165：測試綠燈遮蔽 runtime，須以真實資料驗證邊界）。捕獲後回傳
    空 dict（該檔歸類為 unevaluated）並寫 stderr 警告含檔名，符合
    observability 規則 1（異常不可靜默吞掉）。
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        sys.stderr.write(
            f"[memory_upgrade] WARNING: malformed frontmatter in "
            f"'{source_name}'，視為 unevaluated（{exc}）\n"
        )
        return {}


def classify_memory(memory_file) -> str:
    """依 frontmatter `upgrade` 鍵與頂部標註分類三態。

    無 `upgrade` 鍵 → "unevaluated"；`upgrade: deferred` → "deferred"；
    frontmatter `upgrade: done` 或頂部已有 Status 標註 → "upgraded"。
    """
    text = Path(memory_file).read_text(encoding="utf-8")
    if _STATUS_ANNOTATION_MARKER in text:
        return "upgraded"

    frontmatter = _parse_frontmatter(text, source_name=Path(memory_file).name)
    upgrade = frontmatter.get("upgrade")
    if upgrade == "deferred":
        return "deferred"
    if upgrade == "done":
        return "upgraded"
    return "unevaluated"


def find_dangling_pointers(memory_file, error_patterns_dir) -> list:
    """抓內文所有前綴號 `<CAT>-<PROJ>-NNN`，回傳 error_patterns_dir 下找不到對應檔者。

    flat base（`PC-099`）只有 CAT-NNN 兩段，不屬前綴號掃描範圍，不誤報。
    """
    text = Path(memory_file).read_text(encoding="utf-8")
    dangling = set()
    for match in PATTERN_ID_RE.finditer(text):
        pattern_id = match.group(0).upper()
        parts = pattern_id.split("-")
        if len(parts) != 3:
            # flat base（CAT-NNN）非前綴號，跳過。
            continue
        cat, proj = parts[0], parts[1]
        cat_dir = Path(error_patterns_dir) / _CATEGORY_DIRS.get(cat, cat.lower())
        prefix = f"{cat}-{proj}-"
        found = cat_dir.is_dir() and any(
            p.name.upper().startswith(prefix) for p in cat_dir.glob(f"{prefix}*.md")
        )
        if not found:
            dangling.add(pattern_id)
    return sorted(dangling)


def scan_memory_dir(memory_dir, error_patterns_dir) -> dict:
    """掃 `feedback_*.md`，回傳未評估 / deferred / dangling 三類清單（值為檔名）。"""
    result = {"unevaluated": [], "deferred": [], "dangling": []}
    memory_dir = Path(memory_dir)
    if not memory_dir.is_dir():
        return result

    for path in sorted(memory_dir.glob("feedback_*.md")):
        state = classify_memory(path)
        if state == "unevaluated":
            result["unevaluated"].append(path.name)
        elif state == "deferred":
            result["deferred"].append(path.name)

        ids = find_dangling_pointers(path, error_patterns_dir)
        if ids:
            result["dangling"].append({"file": path.name, "ids": ids})

    return result


def annotate_upgraded(memory_file, dest_path: str, date: str) -> None:
    """於原 memory 檔案 frontmatter 之後插入三行升級標註（冪等）。

    格式精確對齊 upgrade-decision-tree.md:186-192。已標註則不重複插入。
    """
    memory_file = Path(memory_file)
    text = memory_file.read_text(encoding="utf-8")
    if _STATUS_ANNOTATION_MARKER in text:
        return

    annotation = (
        f"{_STATUS_ANNOTATION_MARKER} — 已升級至框架共用層\n"
        f"> **Upgraded To**: `{dest_path}`\n"
        f"> **Upgraded Date**: {date}\n"
    )

    match = _FRONTMATTER_RE.match(text)
    if match:
        insert_at = match.end()
        new_text = text[:insert_at] + "\n" + annotation + text[insert_at:]
    else:
        new_text = annotation + "\n" + text

    memory_file.write_text(new_text, encoding="utf-8")


def prune_memory_index(index_file, memory_filename: str) -> bool:
    """移除 MEMORY.md 中指向 `memory_filename` 的索引行；找不到回 False（graceful）。"""
    index_file = Path(index_file)
    if not index_file.is_file():
        return False

    marker = f"]({memory_filename})"
    lines = index_file.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if marker not in line]
    if len(kept) == len(lines):
        return False

    index_file.write_text("".join(kept), encoding="utf-8")
    return True


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "untitled"


def promote_memory(
    memory_file,
    category: str,
    claude_dir,
    project_code: str,
    dest_title: str,
    date: str,
    memory_dir,
) -> dict:
    """一步完成：分配編號 → 建 error-pattern 檔 → 標註原檔 → 修剪索引。"""
    memory_file = Path(memory_file)
    claude_dir = Path(claude_dir)
    memory_dir = Path(memory_dir)

    pattern_id = allocate_pattern_id(category, claude_dir, project_code)
    cat_dir_name = _CATEGORY_DIRS[category.upper()]
    dest_dir = claude_dir / "error-patterns" / cat_dir_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{pattern_id}-{_slugify(dest_title)}.md"

    source_content = memory_file.read_text(encoding="utf-8")
    dest_content = (
        f"# {pattern_id}: {dest_title}\n\n"
        f"> 由 memory 升級工具自動產生骨架，來源：`{memory_file.name}`，"
        "內容待人工/agent 精修。\n\n"
        "## 原始 memory 內容\n\n"
        f"{source_content}\n"
    )
    dest_path.write_text(dest_content, encoding="utf-8")

    relative_dest = str(dest_path)
    annotate_upgraded(memory_file, relative_dest, date)

    index_file = memory_dir / "MEMORY.md"
    index_pruned = prune_memory_index(index_file, memory_file.name)

    return {
        "pattern_id": pattern_id,
        "dest_path": relative_dest,
        "index_pruned": index_pruned,
    }


# --- CLI ---


def _cmd_scan(args) -> int:
    memory_dir = Path(args.memory_dir)
    error_patterns_dir = memory_dir.parent.parent / "error-patterns"
    if args.error_patterns_dir:
        error_patterns_dir = Path(args.error_patterns_dir)

    result = scan_memory_dir(memory_dir, error_patterns_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"未評估（{len(result['unevaluated'])}）:")
    for name in result["unevaluated"]:
        print(f"  - {name}")
    print(f"deferred（{len(result['deferred'])}）:")
    for name in result["deferred"]:
        print(f"  - {name}")
    print(f"dangling pointer（{len(result['dangling'])}）:")
    for item in result["dangling"]:
        print(f"  - {item['file']}: {', '.join(item['ids'])}")
    return 0


def _cmd_promote(args) -> int:
    memory_file = Path(args.memory_file)
    claude_dir = Path(args.claude_dir) if args.claude_dir else _claude_dir
    repo_toplevel = claude_dir.parent
    registry_path = claude_dir / "error-patterns" / "_project-registry.yaml"
    project_code = args.project_code or identify_project_code(
        registry_path, repo_toplevel
    )
    memory_dir = Path(args.memory_dir) if args.memory_dir else memory_file.parent

    result = promote_memory(
        memory_file=memory_file,
        category=args.category,
        claude_dir=claude_dir,
        project_code=project_code,
        dest_title=args.title,
        date=args.date,
        memory_dir=memory_dir,
    )
    print(f"pattern_id: {result['pattern_id']}")
    print(f"dest_path: {result['dest_path']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="memory 升級工具（promote / scan）")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="掃描 memory 積壓三類清單")
    scan_parser.add_argument("--memory-dir", required=True)
    scan_parser.add_argument("--error-patterns-dir", default=None)
    scan_parser.add_argument("--json", action="store_true")
    scan_parser.set_defaults(func=_cmd_scan)

    promote_parser = sub.add_parser("promote", help="升級單一 memory 檔案")
    promote_parser.add_argument("memory_file")
    promote_parser.add_argument("--category", required=True)
    promote_parser.add_argument("--title", required=True)
    promote_parser.add_argument("--date", required=True)
    promote_parser.add_argument("--claude-dir", default=None)
    promote_parser.add_argument("--project-code", default=None)
    promote_parser.add_argument("--memory-dir", default=None)
    promote_parser.set_defaults(func=_cmd_promote)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
