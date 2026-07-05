"""一次性批次補標 130 檔 feedback memory backlog（1.5.0-W5-011.5）。

ANA W5-011 實測 130 檔 feedback memory 標註率 4%（積壓）。本腳本對
`unevaluated` 狀態的 feedback memory 逐檔分類，於 frontmatter 補上
`upgrade` 欄位：

- 內文含 canonical error-pattern 引用（`PATTERN_ID_RE` 命中）→
  `upgrade: done`（PC-162：僅在引用編號於 error-patterns/ 確實存在時才
  視為已升級，dangling pointer 不計入 done）
- 無 canonical 引用 → `upgrade: deferred` + `upgrade_reason`（顯式標註
  為專案特定 context，待後續跨專案價值評估，非靜默忽略）

依賴重用（禁複製，PC-135）：`memory_upgrade.py` 的 `_parse_frontmatter`
（YAML 解析）與 `find_dangling_pointers`（canonical 引用存在性驗證）。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from memory_upgrade import _parse_frontmatter, classify_memory, find_dangling_pointers  # noqa: E402

from lib.pattern_id import PATTERN_ID_RE  # noqa: E402

_UPGRADE_REASON = "project-specific context, pending cross-project value evaluation"


def _has_valid_canonical_reference(text: str, path: Path, error_patterns_dir) -> bool:
    """判斷檔案內文是否含至少一個「存在於 error-patterns/」的引用編號。

    以 `find_dangling_pointers` 反向推導：若命中編號但皆為 dangling，
    視為無有效引用（PC-162：dangling 引用不代表知識已在 canonical）。
    """
    all_ids = {m.group(0).upper() for m in PATTERN_ID_RE.finditer(text)}
    if not all_ids:
        return False
    dangling_ids = set(find_dangling_pointers(path, error_patterns_dir))
    return bool(all_ids - dangling_ids)


def _insert_upgrade_field(text: str, value: str, reason: str = None) -> str:
    """於 frontmatter 區塊末尾（`---` 結尾前）插入 `upgrade` 欄位。"""
    lines = text.splitlines(keepends=True)
    assert lines[0].strip() == "---", "frontmatter 必須以 --- 開頭"
    close_idx = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")

    new_lines = [f"upgrade: {value}\n"]
    if reason:
        new_lines.append(f'upgrade_reason: "{reason}"\n')

    return "".join(lines[:close_idx] + new_lines + lines[close_idx:])


def annotate_backlog(memory_dir, error_patterns_dir) -> dict:
    """對 memory_dir 下所有 `unevaluated` 狀態的 feedback memory 批次補標。"""
    memory_dir = Path(memory_dir)
    stats = {"done": 0, "deferred": 0, "skipped": 0}

    for path in sorted(memory_dir.glob("feedback_*.md")):
        state = classify_memory(path)
        if state != "unevaluated":
            stats["skipped"] += 1
            continue

        text = path.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter(text, source_name=path.name)
        if not frontmatter:
            # 無 frontmatter 或解析失敗，非本腳本處理範圍，跳過並可見
            sys.stderr.write(
                f"[batch_annotate_backlog] WARNING: '{path.name}' 無有效 "
                "frontmatter，跳過\n"
            )
            stats["skipped"] += 1
            continue

        if _has_valid_canonical_reference(text, path, error_patterns_dir):
            new_text = _insert_upgrade_field(text, "done")
            stats["done"] += 1
        else:
            new_text = _insert_upgrade_field(text, "deferred", _UPGRADE_REASON)
            stats["deferred"] += 1

        path.write_text(new_text, encoding="utf-8")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批次補標 feedback memory backlog 的 upgrade 狀態"
    )
    parser.add_argument("memory_dir")
    parser.add_argument("error_patterns_dir")
    args = parser.parse_args()

    stats = annotate_backlog(args.memory_dir, args.error_patterns_dir)
    print(f"done={stats['done']}, deferred={stats['deferred']}, skipped={stats['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
