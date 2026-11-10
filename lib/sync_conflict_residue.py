"""sync-pull 衝突標記殘留掃描（可重用模組）。

本模組提供「pull 同步範圍內的正式檔是否殘留三方合併衝突標記」的唯一判準，
供 sync-claude-pull.py 收尾掃描與 SessionStart hook 共用，避免兩處各寫一份判準。

範圍判準：只掃 pull 會寫入的檔案。走訪時套用與 pull 主同步迴圈相同的跳過規則
（REMOTE_ONLY 名稱、符號連結、should_exclude_on_pull），在下探前剪枝。
hook-logs、.sync-conflicts 等非同步範圍內容即使含標記字樣也不計入，
否則成功的 pull 會因與同步無關的日誌內容而 exit 1（tarrragon/claude#88）。

匯入方式（呼叫端需先把 .claude/ 加入 sys.path）：

    from lib.sync_conflict_residue import scan_conflict_marker_residue

本模組只讀檔案系統，不依賴 pull 的執行狀態（不需 clone、不讀 .sync-state.json）。
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from lib.sync_exclude_manifest import should_exclude_on_pull

# 三方合併衝突暫存目錄（local-only，不推送）。sync-claude-pull.py 由此匯入。
SYNC_CONFLICTS_DIR = ".sync-conflicts"

# 遠端 repo 專有：存在於遠端但 pull 不複製到本地 .claude/ 的名稱
# （project-templates 由特例函式複製到專案根目錄，不進 .claude/）。
# sync-claude-pull.py 由此匯入，維持單一定義。
REMOTE_ONLY = frozenset({".git", "project-templates"})

# 衝突標記行首樣式：git merge-file 產出的開頭與結尾標記（附標籤），不含 "======="
# ——後者單獨出現時可能與 markdown 分隔線等合法內容混淆。要求行首出現，避免命中
# 原始碼或文件中以字串字面描述標記格式的散文（非行首出現）。
# commands/sync-pull.md「衝突標記歸零驗證」手動 grep 步驟使用同一樣式。
CONFLICT_MARKER_LINE_RE = re.compile(r"^(?:<<<<<<< |>>>>>>> )", re.MULTILINE)


def is_outside_pull_scope(item: Path, rel: Path) -> bool:
    """判斷項目是否在 pull 同步範圍之外（pull 不會寫入它）。

    參數:
        item: 項目的絕對路徑（檢查符號連結用）
        rel: 項目相對 claude_dir 的路徑

    傳回:
        bool: True 表示 pull 不會寫入此項目，掃描應跳過
    """
    return (
        item.name in REMOTE_ONLY
        or item.is_symlink()
        or should_exclude_on_pull(rel)
    )


def _iter_pull_scope_files(claude_dir: Path):
    """走訪 claude_dir 下 pull 同步範圍內的一般檔案，排除目錄在下探前剪枝。"""
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        base = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not is_outside_pull_scope(base / name, (base / name).relative_to(claude_dir))
        ]
        for filename in filenames:
            path = base / filename
            rel = path.relative_to(claude_dir)
            if is_outside_pull_scope(path, rel) or not path.is_file():
                continue
            yield path, rel


def scan_conflict_marker_residue(claude_dir: Path) -> list[str]:
    """掃描 pull 同步範圍內的正式檔是否殘留三方合併衝突標記。

    Why：apply_upstream_delta 的 conflicts 清單只記錄本次已知的衝突，不涵蓋人工
    手動合併（commands/sync-pull.md 選項「手動合併」）誤把標記寫回正式檔的情境。
    本函式對檔案系統終態逐字掃描，作為簿記之外的獨立驗證。

    只掃描可解碼為 UTF-8 的文字檔；二進位或其他編碼視為不適用而略過
    （掃描對象為文字型框架檔）。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        list[str]: 命中檔案相對 claude_dir 的路徑（以 "/" 分隔），已排序；
            claude_dir 不存在時回空清單
    """
    hits: list[str] = []
    if not claude_dir.is_dir():
        return hits
    for path, rel in _iter_pull_scope_files(claude_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # 非 UTF-8 文字檔或讀取失敗：不屬掃描對象，略過
            continue
        if CONFLICT_MARKER_LINE_RE.search(text):
            hits.append(rel.as_posix())
    return sorted(hits)


def detect_conflict_residue(
    claude_dir: Path, before_time: float | None = None
) -> list[str]:
    """列出 .sync-conflicts/ 中 mtime 早於 before_time 的既有殘留檔。

    背景：前次 pull 的衝突副本若未處理即殘留，下次 pull 的新衝突會與舊殘留混雜，
    無人能分辨哪些已處理。pull 開始時以 mtime 早於本次執行時間為判準列出殘留，
    讓未處理衝突在新衝突寫入前可見；SessionStart hook 以預設值呼叫，列出全部。

    參數:
        claude_dir: .claude 目錄路徑
        before_time: 截止時間戳（epoch 秒），預設取呼叫當下時間。
                     mtime 早於此值者視為殘留。

    傳回:
        list[str]: 殘留檔相對 .sync-conflicts/ 的路徑清單（排除 .gitignore），已排序
    """
    conflicts_dir = claude_dir / SYNC_CONFLICTS_DIR
    if not conflicts_dir.is_dir():
        return []
    if before_time is None:
        before_time = time.time()
    residue: list[str] = []
    for item in sorted(conflicts_dir.rglob("*")):
        if not item.is_file() or item.is_symlink() or item.name == ".gitignore":
            continue
        try:
            mtime = item.stat().st_mtime
        except OSError:
            # 讀不到 mtime 視為殘留（寧可多警告，不靜默漏報）
            residue.append(str(item.relative_to(conflicts_dir)))
            continue
        if mtime < before_time:
            residue.append(str(item.relative_to(conflicts_dir)))
    return residue
