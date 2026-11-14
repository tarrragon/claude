#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""規則 8 存量全樹掃描報告：列出 tracked `.claude/` 檔案中未豁免的專案 ticket ID 命中。

用途：rule8 守衛（reference-stability-rule8-guard-hook.py）與 commit 守衛只看新增行，
這是阻擋式判定的設計（全樹阻擋必然大量誤報）；代價是導入前就存在的命中永遠不可見。
本命令補上可見性：以守衛自身的判定函式對全樹掃描，依目錄分組輸出。只報告、不阻擋。

判定與守衛一致（直接重用守衛函式，不另寫一份）：
- 掃描範圍：is_scanned_path（.claude/ 下，排除 handoff/archive）
- 豁免：is_per_project_path（sync 排除區段）、is_exempt_path（第 4 類白名單、第 5 類測試路徑）
- 命中：find_ticket_id_hits（已排除 code fence、框架 ID、日期、CC 版本）
- marker：filter_marker_exempt（命中行本身或上一行的有效 rule8-exempt marker）
tracked 檔對 git check-ignore 恆為未忽略，故不套用 gitignore 本機檔豁免。

用法：
  uv run .claude/scripts/rule8-stock-report.py [--root <repo>] [--summary]

輸出寫 stdout；執行摘要另寫 .claude/hook-logs/rule8-stock-report/。結束碼：0 完成；
1 無法列出 tracked 檔或載入守衛（stderr 說明原因）。
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional

_CLAUDE_DIR = Path(__file__).resolve().parent.parent
_GUARD_PATH = _CLAUDE_DIR / "hooks" / "reference-stability-rule8-guard-hook.py"
_SCAN_ROOT = ".claude"
_UNGROUPED = "(根目錄)"

sys.path.insert(0, str(_CLAUDE_DIR))


class FileHits(NamedTuple):
    rel_path: str
    ids: List[str]
    marker_errors: int


class ScanResult(NamedTuple):
    scanned: int
    exempt: int
    unreadable: List[str]
    files: List[FileHits]


def load_guard():
    """載入 rule8 守衛模組（檔名含連字號，以檔案路徑載入）；失敗回傳 None。"""
    try:
        spec = importlib.util.spec_from_file_location("rule8_guard_for_report", _GUARD_PATH)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except (Exception, SystemExit) as exc:  # 守衛 import 失敗時會 sys.exit(0)
        sys.stderr.write(f"[rule8-stock-report] 無法載入守衛 {_GUARD_PATH}：{exc}\n")
        return None


def list_tracked(root: Path) -> Optional[List[str]]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", _SCAN_ROOT],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"[rule8-stock-report] git ls-files 失敗：{exc}\n")
        return None
    if proc.returncode != 0:
        sys.stderr.write(f"[rule8-stock-report] git ls-files 失敗：{proc.stderr.strip()}\n")
        return None
    return [p for p in proc.stdout.split("\0") if p]


def scan(
    root: Path, guard, rel_paths: List[str], read_path: Optional[Callable[[str], Path]] = None
) -> ScanResult:
    """以守衛判定掃描 rel_paths（皆為 `.claude/` 開頭的 repo 相對路徑）。

    read_path：由 rel_path 取得實際讀取位置；預設為 root / rel_path。sync-push 的
    待推送檔位於推送用暫存 repo（根即 .claude 內容），由呼叫端傳入對應函式。
    """
    read_path = read_path or (lambda rel: root / rel)
    scanned = exempt = 0
    unreadable: List[str] = []
    files: List[FileHits] = []
    for rel in rel_paths:
        if not guard.is_scanned_path(rel):
            continue
        if guard.is_per_project_path(rel) or guard.is_exempt_path(rel):
            exempt += 1
            continue
        try:
            text = read_path(rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable.append(rel)  # 二進位檔或讀取失敗：列入報告，不中止
            continue
        scanned += 1
        hits = guard.find_ticket_id_hits(text)
        if not hits:
            continue
        blocked, marker_errors = guard.filter_marker_exempt(rel, text, hits)
        if blocked or marker_errors:
            files.append(FileHits(rel, blocked, len(marker_errors)))
    return ScanResult(scanned, exempt, unreadable, files)


def group_key(rel_path: str) -> str:
    """依 .claude/ 下第一層目錄分組；直接位於 .claude/ 的檔案歸「根目錄」。"""
    parts = rel_path.split("/")
    return parts[1] if len(parts) > 2 else _UNGROUPED


def render(result: ScanResult, summary_only: bool) -> str:
    groups: Dict[str, List[FileHits]] = defaultdict(list)
    for fh in result.files:
        groups[group_key(fh.rel_path)].append(fh)
    total_ids = sum(len(fh.ids) for fh in result.files)
    lines = [
        "[rule8 存量報告] 只報告、不阻擋",
        f"受掃檔 {result.scanned}｜有未豁免命中的檔 {len(result.files)}｜ID 總數 {total_ids}"
        f"｜豁免路徑 {result.exempt}"
        f"｜無法讀取 {len(result.unreadable)}",
        "",
        "依目錄（檔數 / ID 數 / 副檔名分布）：",
    ]
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for name, fhs in ordered:
        exts = Counter(Path(fh.rel_path).suffix or "(無)" for fh in fhs)
        ext_text = "、".join(f"{ext} {n}" for ext, n in exts.most_common())
        lines.append(f"  {name}: {len(fhs)} 檔 / {sum(len(f.ids) for f in fhs)} 個 ID（{ext_text}）")
    if summary_only:
        return "\n".join(lines)
    for name, fhs in ordered:
        lines += ["", f"## {name}"]
        for fh in sorted(fhs, key=lambda f: f.rel_path):
            note = f"（marker 格式錯誤 {fh.marker_errors} 處）" if fh.marker_errors else ""
            lines.append(f"- {fh.rel_path}: {', '.join(fh.ids)}{note}")
    if result.unreadable:
        lines += ["", "## 無法讀取（未掃描）"] + [f"- {p}" for p in result.unreadable]
    return "\n".join(lines)


def _default_root() -> Path:
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else Path.cwd()


def _log_summary(result: ScanResult, root: Path) -> None:
    """執行摘要寫日誌（營運紀錄）；日誌失敗不影響報告輸出，但寫 stderr。"""
    try:
        from lib import setup_hook_logging  # noqa: PLC0415

        logger = setup_hook_logging("rule8-stock-report")
        logger.info(
            "存量報告：root=%s 受掃檔 %d、命中檔 %d、ID 總數 %d、豁免路徑 %d、無法讀取 %d",
            root, result.scanned, len(result.files),
            sum(len(fh.ids) for fh in result.files), result.exempt, len(result.unreadable),
        )
    except Exception as exc:  # noqa: BLE001 — 日誌失敗只影響營運紀錄
        sys.stderr.write(f"[rule8-stock-report] 寫日誌失敗：{exc}\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="規則 8 存量全樹掃描報告（只報告、不阻擋）")
    parser.add_argument("--root", help="要掃描的 repo 根目錄（預設為目前目錄的 git toplevel）")
    parser.add_argument("--summary", action="store_true", help="只輸出總數與目錄分組，不列逐檔明細")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else _default_root()
    guard = load_guard()
    if guard is None:
        return 1
    rel_paths = list_tracked(root)
    if rel_paths is None:
        return 1
    result = scan(root, guard, rel_paths)
    print(render(result, args.summary))
    _log_summary(result, root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
