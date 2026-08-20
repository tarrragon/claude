"""
ticket track activity 命令（multi-PM 協調層 Phase 2，issue tarrragon/claude#77）

L1 activity：票面進度是事件驅動更新（claim/append-log/complete），事件間
有 27-35 分鐘常態靜默窗口，靜默本身無法判斷「在做/卡住/session 已死」。
本命令從既有副作用機械推導每張 in_progress 票的最後活動時間，把靜默從
歧義降為可判定狀態，不倚賴「要求勤更新」的紀律解法（紀律解法必退化）。

三源（取最新者，附來源標記）：
  1. ticket md 檔案 mtime
  2. `git log --grep=<id>` 最後一筆 commit 時間
  3. working tree 髒檔命中該票 where.files 的歸屬（取命中檔案的磁碟 mtime）

三源皆缺 → no-signal（非報錯，票剛 claim 尚無任何副作用時的正常狀態）。
固定值輸出（CLI-first、AI-last，AI 只讀結論不做判定）。

git 呼叫一律經 `.claude/lib/git_utils.run_git_command`（已內建
`--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`，
Phase 1 審查教訓），lazy import 經 `ticket_system.lib.claude_lib_loader`
共用實作，不重寫第三份 subprocess 呼叫路徑。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from ticket_system.lib.claude_lib_loader import load_claude_lib
from ticket_system.lib.command_tracking_messages import TrackMessages
from ticket_system.lib.file_conflict import where_files as _lib_where_files
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.version import get_active_versions

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

SOURCE_MD_MTIME = "md_mtime"
SOURCE_GIT_COMMIT = "git_commit"
SOURCE_DIRTY_FILE = "dirty_file"
NO_SIGNAL = "no-signal"


# ---------------------------------------------------------------------------
# Lib 載入：lazy import `.claude/lib/git_utils`（收斂自五處近乎相同複本，
# 共用實作見 ticket_system.lib.claude_lib_loader）
# ---------------------------------------------------------------------------


def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Thin wrapper：對外暴露以便測試 patch；git_utils 不可用時降級回傳失敗。"""
    git_utils = load_claude_lib("git_utils")
    if git_utils is None:
        return False, "git_utils unavailable"
    return git_utils.run_git_command(args, cwd=cwd)


# ---------------------------------------------------------------------------
# 三源推導
# ---------------------------------------------------------------------------

def _where_files(ticket: Dict[str, Any]) -> List[str]:
    """委派 `lib.file_conflict.where_files`：涵蓋本函式原本的舊逗號分隔
    字串格式容錯，並一併剝離逐檔讀寫意圖標記（`::read` / `::write`）。"""
    return _lib_where_files(ticket)


def _md_mtime_source(ticket_path: Optional[str]) -> Optional[Tuple[datetime, str]]:
    if not ticket_path:
        return None
    p = Path(ticket_path)
    if not p.exists():
        return None
    try:
        ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return (ts, SOURCE_MD_MTIME)


_GIT_LOG_GREP_CANDIDATES = 30

# 子票 ID 尾綴樣式：父票 ID 之後緊接「. + 數字」（如父票 ID 後接 ".3"）。
# 用於判斷 commit subject 中的 ticket_id 命中是否其實是子票 ID 的字首子字串。
_CHILD_TICKET_SUFFIX_RE = re.compile(r"^\.\d")


def _commit_references_ticket(subject: str, ticket_id: str) -> bool:
    """判斷 commit subject 是否含 ticket_id 的獨立引用（非子票 ID 的字首子字串）。

    父票 ID 恰為子票 ID 的字首子字串（例如父票 ID 是子票 ID 去掉
    ".N" 尾綴後的前段），單純字串比對會讓子票 commit 誤算作父票的活動
    訊號。逐一掃描 subject 中所有出現位置，命中後緊接「. + 數字」視為
    子票引用而跳過，直到找到獨立引用或掃完為止。
    """
    start = 0
    while True:
        pos = subject.find(ticket_id, start)
        if pos == -1:
            return False
        end = pos + len(ticket_id)
        tail = subject[end:end + 2]
        if not _CHILD_TICKET_SUFFIX_RE.match(tail):
            return True
        start = end


def _git_commit_source(ticket_id: str, cwd: Optional[str] = None) -> Optional[Tuple[datetime, str]]:
    """`git log --grep=<id>` 最新一筆「獨立引用」commit 的 committer 時間（ISO 8601）。

    `--fixed-strings`：ticket_id 含點號，未加此旗標會被 git 的預設 BRE
    正規表示式引擎當萬用字元解讀，造成誤命中。

    父子票邊界：git 層級的 --grep 命中無法區分父票 ID 恰為子票 ID 字首子
    字串的情況（審查實測：有子票的父票顯示的活動時間其實是子票的
    commit）。取最近 N 筆候選（committer 時間 + subject），Python 端依
    `_commit_references_ticket` 逐一驗證是否為獨立引用，跳過僅命中子票的
    候選；全數候選皆非獨立引用時回傳 None（該源為缺，非報錯）。

    僅檢查 commit subject（`%s`），不含 body：本專案 commit message 慣例為
    `type(ticket_id): description`，ticket_id 一律出現在 subject，body 掃描
    非必要且會引入多行解析複雜度。
    """
    if not ticket_id:
        return None
    ok, out = run_git_command(
        [
            "log", "--grep", ticket_id, "--fixed-strings",
            "--format=%cI%x00%s", "-n", str(_GIT_LOG_GREP_CANDIDATES),
        ],
        cwd=cwd,
    )
    if not ok or not out:
        return None
    for line in out.splitlines():
        parts = line.split("\x00", 1)
        if len(parts) != 2:
            continue
        ts_str, subject = parts
        if not _commit_references_ticket(subject, ticket_id):
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (ts, SOURCE_GIT_COMMIT)
    return None


def list_dirty_files(cwd: Optional[str] = None) -> List[str]:
    """回傳 working tree 髒檔路徑清單（porcelain 格式，含 staged/unstaged/untracked）。"""
    ok, out = run_git_command(["status", "--porcelain"], cwd=cwd)
    if not ok or not out:
        return []
    paths: List[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain 格式 "XY <path>"；rename 情況為 "XY old -> new"，取新路徑
        path_part = line[3:]
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1]
        path_part = path_part.strip()
        if path_part:
            paths.append(path_part)
    return paths


def _path_matches(dirty_path: str, declared: str) -> bool:
    """判斷髒檔路徑是否命中宣告路徑：精確相符，或宣告為其上層目錄前綴
    （PurePosixPath 前綴比對，非 string startswith——避免 "lib/foo" 誤命中
    "lib/foobar.dart" 這類同前綴不同路徑段的假陽性）。
    """
    try:
        dp = PurePosixPath(dirty_path)
        decl = PurePosixPath(declared.rstrip("/"))
    except ValueError:
        return dirty_path == declared
    return dp == decl or decl in dp.parents


def _dirty_file_source(
    where_files: List[str], dirty_paths: List[str], project_root: Path
) -> Optional[Tuple[datetime, str]]:
    matched_paths: List[Path] = []
    for dirty in dirty_paths:
        for declared in where_files:
            if _path_matches(dirty, declared):
                matched_paths.append(project_root / dirty)
                break
    if not matched_paths:
        return None
    latest: Optional[datetime] = None
    for p in matched_paths:
        try:
            ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if latest is None or ts > latest:
            latest = ts
    if latest is None:
        return None
    return (latest, SOURCE_DIRTY_FILE)


def compute_activity(
    ticket: Dict[str, Any],
    *,
    dirty_paths: List[str],
    project_root: Path,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """對單一 ticket 彙整三源，回傳最新活動時間與來源標記；三源皆缺回傳 no-signal。"""
    ticket_id = ticket.get("id") or ""
    md_source = _md_mtime_source(ticket.get("_path"))
    commit_source = _git_commit_source(ticket_id, cwd=cwd)
    dirty_source = _dirty_file_source(_where_files(ticket), dirty_paths, project_root)

    candidates = [s for s in (md_source, commit_source, dirty_source) if s is not None]
    who = ticket.get("who") or {}
    agent = who.get("current") if isinstance(who, dict) else None

    if not candidates:
        return {"id": ticket_id, "last_activity": None, "source": NO_SIGNAL, "agent": agent}

    latest_ts, latest_source = max(candidates, key=lambda pair: pair[0])
    return {
        "id": ticket_id,
        "last_activity": latest_ts.isoformat(),
        "source": latest_source,
        "agent": agent,
    }


def attribute_dirty_files(
    tickets: List[Dict[str, Any]], dirty_paths: List[str], project_root: Path
) -> List[Dict[str, Any]]:
    """髒檔歸屬（第三源獨立輸出，供 `onboard` 命令複用，不重算最新活動時間）。

    對每張 ticket 找出命中其 where.files 的髒檔清單；僅回傳有命中的 ticket。
    """
    result: List[Dict[str, Any]] = []
    for t in tickets:
        where_files = _where_files(t)
        if not where_files:
            continue
        matched = sorted({d for d in dirty_paths for f in where_files if _path_matches(d, f)})
        if matched:
            result.append({"id": t.get("id"), "files": matched})
    return result


# ---------------------------------------------------------------------------
# 資料蒐集
# ---------------------------------------------------------------------------

def _gather_in_progress_tickets(
    explicit_version: Optional[str],
) -> List[Dict[str, Any]]:
    if explicit_version:
        versions = [explicit_version]
    else:
        versions = get_active_versions() or []
    aggregated: List[Dict[str, Any]] = []
    for version in versions:
        for t in list_tickets(version) or []:
            if t.get("status") == "in_progress":
                aggregated.append(t)
    return aggregated


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _render_table(rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = ["=== Ticket Activity (L1) ==="]
    if not rows:
        lines.append("（無 in_progress ticket）")
        return "\n".join(lines)

    col_id = max(len("id"), max(len(str(r["id"])) for r in rows))
    col_source = max(len("source"), max(len(r["source"]) for r in rows))
    header = f"  {'id':<{col_id}}  {'last_activity':<25}  {'source':<{col_source}}  agent"
    lines.append(header)
    lines.append("  " + "-" * (col_id + col_source + 45))
    for r in rows:
        last = r["last_activity"] or "-"
        agent = r.get("agent") or "-"
        lines.append(f"  {r['id']:<{col_id}}  {last:<25}  {r['source']:<{col_source}}  {agent}")
    return "\n".join(lines)


def _render_json(rows: List[Dict[str, Any]]) -> str:
    return json.dumps({"activity": rows}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def execute_activity(args: argparse.Namespace) -> int:
    """執行 track activity 命令（version-agnostic，read-only）。"""
    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    explicit_version = getattr(args, "version", None)

    tickets = _gather_in_progress_tickets(explicit_version)
    project_root = get_project_root()
    dirty_paths = list_dirty_files(cwd=str(project_root))

    rows = [
        compute_activity(
            t, dirty_paths=dirty_paths, project_root=project_root, cwd=str(project_root)
        )
        for t in tickets
    ]
    rows.sort(key=lambda r: str(r.get("id") or ""))

    if fmt == FORMAT_JSON:
        print(_render_json(rows))
    else:
        print(_render_table(rows))
    return 0


def register_activity(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 activity 子命令 parser。"""
    p = subparsers.add_parser(
        "activity",
        help=(
            "L1 activity：md mtime + git log --grep + 髒檔歸屬三源機械推導"
            "每張 in_progress 票的最後活動時間（multi-PM 協調層 Phase 2）"
        ),
    )
    p.add_argument(
        "--version",
        default=None,
        help="指定版本（覆蓋自動偵測 active 版本）",
    )
    p.add_argument(
        "--all",
        action="store_true",
        default=False,
        help=TrackMessages.ARG_ALL_COMPAT,
    )
    p.add_argument(
        "--format",
        choices=[FORMAT_TABLE, FORMAT_JSON],
        default=FORMAT_TABLE,
        help=f"輸出格式（預設 {FORMAT_TABLE}）",
    )
    return p


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
