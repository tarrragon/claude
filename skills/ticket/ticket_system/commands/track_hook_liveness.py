"""
ticket track hook-liveness 命令

輸入 hook 檔路徑或名稱，查 `.claude/hook-logs/_liveness/*.jsonl` 回報該
hook 的觸發記錄（依 session 聚合筆數、最近一筆 ts、今日筆數），並明確印出
「以什麼名字查」——取代憑檔名慣例（去 `-hook` 後綴等）手組 grep。

動機（實測對照案例）：部分 hook（如某 file-ownership guard 類 hook）的
HOOK_NAME 常數帶 `-hook` 後綴，與其餘同類 hook 的命名慣例不一致；憑慣例
猜測名稱查 liveness 記錄得到「0 筆」，此結果與「hook 未觸發」這個合法
結論無法區分，會產生有據可查但錯誤的驗收記錄。

名稱解析邏輯（三層，與 hook-health-monitor.py:_resolve_hook_name_from_source
同源，本檔複製最小必要邏輯——兩檔案不共用 import 路徑，抽公用 lib 需將
`.claude/hooks/hook-health-monitor.py` 一併納入修改範圍，超出本檔職責，
故僅複製並註明來源）：
    1. 輸入為存在的檔案路徑 → 讀原始碼掃描 `HOOK_NAME = "..."` 常數
    2. 無 HOOK_NAME 常數 → 退回檔名去 `.py`（即 Path(x).stem）
    3. 輸入非存在的檔案路徑 → 視為字面名稱直接使用（不做 `-hook` 猜測，
       避免重蹈「猜錯得 0 筆且無法區分」的問題——找不到記錄時明確告知
       「以哪個名字查」，讓使用者自行判斷是否猜錯）

liveness 記錄格式（.claude/lib/hook_logging.py 寫入）：每行一個 JSON
物件 `{"hook": ..., "session_id": ..., "pid": ..., "ts": ...}`，檔案位於
`.claude/hook-logs/_liveness/<session_id>.jsonl`（一 session 一檔）。

紀律：
- 掃描 `_liveness/` 用首層 os.scandir（紀律一，避免遞迴大目錄）
- 路徑基底用 git toplevel（紀律二之一，經 claude_lib_loader.current_project_root）
- 找不到任何記錄時，明確區分「名稱已解析為 X，X 無記錄」與「無法解析名稱」
  （紀律二之二，兩者原因不同：前者可能是名稱對但 hook 真的沒觸發，後者是
  輸入路徑不存在也不是任何已知名稱）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.claude_lib_loader import current_project_root

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

LIVENESS_SUBDIR = ("hook-logs", "_liveness")


# ---------------------------------------------------------------------------
# 名稱解析（三層，見模組 docstring）
# ---------------------------------------------------------------------------


def _resolve_hook_name_from_source(hook_path: Path) -> Optional[str]:
    """從 hook 原始碼掃描 `HOOK_NAME = "..."` 常數。

    複製自 .claude/hooks/hook-health-monitor.py:_resolve_hook_name_from_source
    （同源，見模組 docstring「不共用 import 路徑」說明）。
    """
    try:
        source = hook_path.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("HOOK_NAME"):
            continue
        if "=" not in stripped:
            continue
        _, _, value_part = stripped.partition("=")
        value = value_part.strip()
        if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
            return value[1:-1]

    return None


def resolve_hook_name(
    hook_input: str, *, search_root: Optional[Path] = None
) -> Dict[str, Any]:
    """解析使用者輸入（檔路徑或名稱）為查詢用的 hook 名稱。

    路徑查找順序：(1) 相對於目前執行時的 cwd（`Path.is_file()` 預設行為）
    (2) 相對於 `search_root`（通常為 git toplevel）。CLI 呼叫端經
    `uv run --directory` 啟動時 cwd 會被改為 skill 目錄而非使用者實際
    所在目錄，(1) 常落空，故需 (2) 兜底，讓使用者傳入「相對於專案根目錄」
    的慣用路徑（如 `.claude/hooks/foo-hook.py`）也能解析。

    Returns:
        {"name": str, "source": "hook_name_const"|"filename_stem"|"literal",
         "resolved_from_path": Optional[str]}
    """
    candidate_path = Path(hook_input)
    if not candidate_path.is_file() and search_root is not None:
        rooted_candidate = search_root / hook_input
        if rooted_candidate.is_file():
            candidate_path = rooted_candidate

    if candidate_path.is_file():
        hook_name_const = _resolve_hook_name_from_source(candidate_path)
        if hook_name_const:
            return {
                "name": hook_name_const,
                "source": "hook_name_const",
                "resolved_from_path": str(candidate_path),
            }
        return {
            "name": candidate_path.stem,
            "source": "filename_stem",
            "resolved_from_path": str(candidate_path),
        }

    return {"name": hook_input, "source": "literal", "resolved_from_path": None}


# ---------------------------------------------------------------------------
# Liveness 掃描（首層 scandir，紀律一）
# ---------------------------------------------------------------------------


def _liveness_dir(project_root: Path) -> Path:
    d = project_root / ".claude"
    for part in LIVENESS_SUBDIR:
        d = d / part
    return d


def _iter_liveness_files(liveness_dir: Path) -> List[Path]:
    """首層 scandir 取得 *.jsonl 檔案清單（不遞迴，紀律一）。"""
    files: List[Path] = []
    try:
        with os.scandir(liveness_dir) as it:
            for entry in it:
                try:
                    if entry.is_file() and entry.name.endswith(".jsonl"):
                        files.append(Path(entry.path))
                except OSError:
                    continue
    except OSError:
        pass
    return files


def scan_liveness(
    hook_name: str,
    liveness_dir: Path,
    *,
    since: Optional[datetime] = None,
    session_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """掃描 liveness 目錄，回傳對指定 hook_name 的聚合結果。

    Returns:
        {
            "total": int,
            "by_session": {session_id: count, ...},
            "latest_ts": Optional[str],
            "today_count": int,
        }
    """
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0
    by_session: Dict[str, int] = {}
    latest_ts: Optional[str] = None
    today_count = 0

    for path in _iter_liveness_files(liveness_dir):
        if session_filter and path.stem != session_filter:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("hook") != hook_name:
                continue
            ts = record.get("ts")
            if since is not None and ts:
                try:
                    if datetime.fromisoformat(ts) < since:
                        continue
                except ValueError:
                    pass

            total += 1
            session_id = record.get("session_id", path.stem)
            by_session[session_id] = by_session.get(session_id, 0) + 1
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts
            if isinstance(ts, str) and ts.startswith(today):
                today_count += 1

    return {
        "total": total,
        "by_session": by_session,
        "latest_ts": latest_ts,
        "today_count": today_count,
    }


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------


def _render_table(resolution: Dict[str, Any], result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(
        "解析名稱: {} (來源: {})".format(resolution["name"], resolution["source"])
    )
    if resolution.get("resolved_from_path"):
        lines.append("解析自檔案: {}".format(resolution["resolved_from_path"]))

    if result["total"] == 0:
        if resolution["source"] == "literal":
            lines.append(
                "[無記錄] 名稱 '{}' 為字面輸入（非解析自既有檔案），"
                "0 筆可能代表名稱輸入錯誤或 hook 確實未觸發，"
                "請確認輸入是否為正確的 HOOK_NAME。".format(resolution["name"])
            )
        else:
            lines.append(
                "[無記錄] 名稱已解析為 '{}'，此名稱在 _liveness 無任何記錄"
                "（hook 可能確實未觸發）。".format(resolution["name"])
            )
        return "\n".join(lines)

    lines.append("總筆數: {}".format(result["total"]))
    lines.append("今日筆數: {}".format(result["today_count"]))
    lines.append("最近一筆 ts: {}".format(result["latest_ts"]))
    lines.append("依 session 聚合:")
    for session_id, count in sorted(
        result["by_session"].items(), key=lambda kv: kv[1], reverse=True
    ):
        lines.append("  {}: {}".format(session_id, count))
    return "\n".join(lines)


def _render_json(resolution: Dict[str, Any], result: Dict[str, Any]) -> str:
    payload = {"resolution": resolution, **result}
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def execute_hook_liveness(args: argparse.Namespace) -> int:
    """執行 track hook-liveness 命令（version-agnostic）。

    Returns:
        0: 正常輸出（含 0 筆情形，0 筆不是錯誤，是合法結論之一）
        2: 無法定位專案根目錄，或輸入為空
    """
    hook_input = getattr(args, "hook", None)
    if not hook_input:
        sys.stderr.write("hook-liveness 需要指定 hook 檔路徑或名稱\n")
        return 2

    project_root_str = current_project_root()
    if not project_root_str:
        sys.stderr.write("無法定位 git toplevel（專案根目錄）\n")
        return 2
    project_root = Path(project_root_str)

    resolution = resolve_hook_name(hook_input, search_root=project_root)
    liveness_dir = _liveness_dir(project_root)

    since_dt: Optional[datetime] = None
    since_arg = getattr(args, "since", None)
    if since_arg:
        try:
            since_dt = datetime.fromisoformat(since_arg)
        except ValueError:
            sys.stderr.write(
                "--since 格式錯誤，需為 ISO 格式（如 2026-08-21 或 2026-08-21T00:00:00）\n"
            )
            return 2

    result = scan_liveness(
        resolution["name"],
        liveness_dir,
        since=since_dt,
        session_filter=getattr(args, "session", None),
    )

    fmt = getattr(args, "format", FORMAT_TABLE) or FORMAT_TABLE
    if fmt == FORMAT_JSON:
        print(_render_json(resolution, result))
    else:
        print(_render_table(resolution, result))
    return 0


# execute alias 對齊 track.py 命名慣例
execute = execute_hook_liveness


def register_hook_liveness(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 hook-liveness 子命令 parser。"""
    p = subparsers.add_parser(
        "hook-liveness",
        help=(
            "從 hook 檔路徑或名稱解析 HOOK_NAME 後查 _liveness 觸發記錄，"
            "取代憑檔名慣例手組 grep"
        ),
    )
    p.add_argument(
        "hook",
        help="hook 檔路徑（如 .claude/hooks/foo-hook.py）或已知的 HOOK_NAME 字面名稱",
    )
    p.add_argument(
        "--since",
        default=None,
        help="只計入此 ISO 時間之後的記錄（如 2026-08-21 或 2026-08-21T00:00:00）",
    )
    p.add_argument(
        "--session",
        default=None,
        help="只掃描指定 session_id 的 liveness 檔案",
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
