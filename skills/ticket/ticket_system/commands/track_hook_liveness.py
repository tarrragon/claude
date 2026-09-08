"""
ticket track hook-liveness 命令

輸入 hook 檔路徑或名稱，查 `.claude/hook-logs/_liveness/*.jsonl` 回報該
hook 的觸發記錄（依 session 聚合筆數、最近一筆 ts、今日筆數），並明確印出
「以什麼名字查」——取代憑檔名慣例（去 `-hook` 後綴等）手組 grep。

動機（實測對照案例）：部分 hook（如某 file-ownership guard 類 hook）的
HOOK_NAME 常數帶 `-hook` 後綴，與其餘同類 hook 的命名慣例不一致；憑慣例
猜測名稱查 liveness 記錄得到「0 筆」，此結果與「hook 未觸發」這個合法
結論無法區分，會產生有據可查但錯誤的驗收記錄。

名稱解析邏輯（修訂版）：liveness 記錄的 "hook" 欄位值即
`run_hook_safely(main, "<literal>")` 呼叫的第二個位置參數字面值（見
`.claude/lib/hook_logging.py:run_hook_safely`），故原始碼掃描以此為第一
優先權威來源，取代舊版僅認 `HOOK_NAME = "..."` 常數的做法（實測：對
`.claude/hooks/*.py` 全量掃描，82 個檔案直接把字面字串傳給
run_hook_safely，另 30 個改用 `HOOK_NAME` 常數再傳入變數，兩種寫法互斥
不重疊）：
    1. 輸入為存在的檔案路徑 → 讀原始碼掃描 `run_hook_safely(..., "...")`
       呼叫的字面參數（來源 run_hook_safely_literal，最高信賴度）
    2. 無此呼叫 → 退回掃描 `HOOK_NAME = "..."` 常數（來源 hook_name_const）
    3. 輸入非存在的檔案路徑，且不含副檔名 → 嘗試在 search_root 底下的
       `.claude/hooks/<輸入>.py` 尋找對應檔案，找到則套用步驟 1-2
       （解決使用者直接輸入檔名 stem、不含 `.py`、且內部名稱與檔名不同
       的情形，如 bare-commit-guard-hook -> bare-commit-guard、
       task-dispatch-readiness-check -> agent-dispatch-check）
    4. 皆找不到對應原始碼 → 檔案存在但無法解析出宣告名稱時退回檔名去
       `.py`（來源 filename_stem，未經確認）；檔案完全不存在時視為字面
       名稱直接使用（來源 literal，未經確認）
    `resolution["source"]` 屬 `run_hook_safely_literal` / `hook_name_const`
    視為「已由原始碼確認」；屬 `filename_stem` / `literal` 視為「未確認的
    猜測」——0 筆訊息依此區分是否可將「hook 未觸發」列為候選解釋（見
    `_render_table` 與模組 docstring「紀律」段）。

liveness 記錄格式（.claude/lib/hook_logging.py 寫入）：每行一個 JSON
物件 `{"hook": ..., "session_id": ..., "pid": ..., "ts": ...}`，檔案位於
`.claude/hook-logs/_liveness/<session_id>.jsonl`（一 session 一檔）。

紀律：
- 掃描 `_liveness/` 用首層 os.scandir（紀律一，避免遞迴大目錄）
- 路徑基底用 git toplevel（紀律二之一，經 claude_lib_loader.current_project_root）
- 找不到任何記錄時，明確區分「名稱已由原始碼確認，此名稱無記錄」與「名稱
  未經確認（僅為猜測）」（紀律二之二，兩者原因不同：前者名稱正確、hook
  可能確實未觸發；後者名稱本身尚未確認，0 筆不能歸因為 hook 未觸發——
  訊息須列出已嘗試過的解析形式，不得把「未觸發」列為候選解釋，查詢工具
  的失敗形態不可與它要偵測的失敗形態同形）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.claude_lib_loader import current_project_root

FORMAT_TABLE = "table"
FORMAT_JSON = "json"

LIVENESS_SUBDIR = ("hook-logs", "_liveness")
HOOKS_SUBDIR = (".claude", "hooks")

# 已由原始碼確認的解析來源（可信任 0 筆代表 hook 確實未觸發）
CONFIRMED_SOURCES = frozenset({"run_hook_safely_literal", "hook_name_const"})

# `run_hook_safely(main, "actual-name")` 的字面第二參數 —— 這是
# .claude/lib/hook_logging.py 實際寫入 liveness "hook" 欄位的值，優先權威
# 來源見模組 docstring。
_RUN_HOOK_SAFELY_LITERAL_RE = re.compile(
    r'run_hook_safely\(\s*[^,]+,\s*["\']([^"\']+)["\']'
)


# ---------------------------------------------------------------------------
# 名稱解析（見模組 docstring）
# ---------------------------------------------------------------------------


def _resolve_hook_name_from_source(hook_path: Path) -> Optional[Dict[str, str]]:
    """從 hook 原始碼掃描實際傳給 run_hook_safely 的名稱。

    優先掃描 `run_hook_safely(..., "字面值")` 呼叫（最高信賴度，實測涵蓋
    82/122 個 .claude/hooks/*.py）；找不到才退回掃描 `HOOK_NAME = "..."`
    常數（涵蓋另外 30 個、與前者互斥不重疊的寫法）。

    Returns:
        {"name": str, "source": "run_hook_safely_literal"|"hook_name_const"}
        或 None（皆找不到）
    """
    try:
        source = hook_path.read_text(encoding="utf-8")
    except OSError:
        return None

    literal_match = _RUN_HOOK_SAFELY_LITERAL_RE.search(source)
    if literal_match:
        return {"name": literal_match.group(1), "source": "run_hook_safely_literal"}

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("HOOK_NAME"):
            continue
        if "=" not in stripped:
            continue
        _, _, value_part = stripped.partition("=")
        value = value_part.strip()
        if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
            return {"name": value[1:-1], "source": "hook_name_const"}

    return None


def resolve_hook_name(
    hook_input: str, *, search_root: Optional[Path] = None
) -> Dict[str, Any]:
    """解析使用者輸入（檔路徑或名稱）為查詢用的 hook 名稱。

    路徑查找順序：(1) 相對於目前執行時的 cwd（`Path.is_file()` 預設行為）
    (2) 相對於 `search_root`（通常為 git toplevel）(3) 輸入不含副檔名時，
    嘗試 `search_root/.claude/hooks/<輸入>.py`——使用者以檔名 stem 查詢
    （不含 `.py`）是最自然的輸入方式，補此層才能解析到對應原始碼。
    CLI 呼叫端經 `uv run --directory` 啟動時 cwd 會被改為 skill 目錄而非
    使用者實際所在目錄，(1) 常落空，故需 (2)(3) 兜底。

    Returns:
        {"name": str,
         "source": "run_hook_safely_literal"|"hook_name_const"
                    |"filename_stem"|"literal",
         "resolved_from_path": Optional[str],
         "attempted": List[str]}  # 已嘗試過的解析路徑/名稱，供查無記錄時展示
    """
    candidate_path = Path(hook_input)
    attempted: List[str] = [str(candidate_path)]

    if not candidate_path.is_file() and search_root is not None:
        rooted_candidate = search_root / hook_input
        attempted.append(str(rooted_candidate))
        if rooted_candidate.is_file():
            candidate_path = rooted_candidate

    if not candidate_path.is_file() and search_root is not None and not hook_input.endswith(".py"):
        hooks_dir_candidate = search_root
        for part in HOOKS_SUBDIR:
            hooks_dir_candidate = hooks_dir_candidate / part
        hooks_dir_candidate = hooks_dir_candidate / f"{hook_input}.py"
        attempted.append(str(hooks_dir_candidate))
        if hooks_dir_candidate.is_file():
            candidate_path = hooks_dir_candidate

    if candidate_path.is_file():
        source_result = _resolve_hook_name_from_source(candidate_path)
        if source_result:
            return {
                "name": source_result["name"],
                "source": source_result["source"],
                "resolved_from_path": str(candidate_path),
                "attempted": attempted,
            }
        return {
            "name": candidate_path.stem,
            "source": "filename_stem",
            "resolved_from_path": str(candidate_path),
            "attempted": attempted,
        }

    return {
        "name": hook_input,
        "source": "literal",
        "resolved_from_path": None,
        "attempted": attempted,
    }


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
        if resolution["source"] not in CONFIRMED_SOURCES:
            attempted = resolution.get("attempted") or [resolution["name"]]
            lines.append(
                "[無記錄，名稱未經確認] 已嘗試以下解析形式："
                + "；".join(attempted)
                + "，均未能從原始碼確認實際傳給 run_hook_safely 的名稱。"
            )
            if resolution["source"] == "filename_stem":
                lines.append(
                    "已找到檔案 '{}'，但無法解析出宣告名稱，暫以檔名 '{}' "
                    "查詢。".format(resolution["resolved_from_path"], resolution["name"])
                )
            else:
                lines.append(
                    "查無對應檔案，以字面輸入 '{}' 直接查詢。".format(resolution["name"])
                )
            lines.append(
                "0 筆不代表 hook 未觸發——名稱本身尚未確認正確，"
                "請提供 hook 檔案路徑或確認正確的 HOOK_NAME 後重試。"
            )
        else:
            lines.append(
                "[無記錄] 名稱已由原始碼確認為 '{}'（來源: {}），"
                "此名稱在 _liveness 無任何記錄，可能代表 hook 確實未觸發。".format(
                    resolution["name"], resolution["source"]
                )
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
