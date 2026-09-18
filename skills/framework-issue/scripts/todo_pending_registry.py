"""todo delta 待處理清單本地登記檔：schema、路徑解析、讀寫，供
section_comment.py（寫入端 cmd_init／cmd_add／cmd_update）與
session-start-todo-delta-hook.py（讀取端）共用。

背景：「待辦與來源*」表格逐列無任何日期欄位，時間軸只能由本地快照製造；
而 SessionStart 路徑硬性禁止呼叫 `todo --json`（該呼叫預設範圍實測數秒
等級，SessionStart 已註冊數十支 hook，一支慢 hook 會改變整個啟動序列的
成本結構）。本登記檔把「有哪些列尚未被處理」這件事，改由**寫入端在每次
成功寫入後增量維護**，讀取端因此只需一次本地檔案讀取，不需任何 gh 呼叫。

同步模型（`sync_section_rows`）：呼叫端傳入一個「issue+owner 範圍內，此
次寫入後的完整列集合」，本模組對該範圍做全量同步——狀態為「待裁票」的列
upsert 進 pending；範圍內原本在 pending 但這次不再是「待裁票」（狀態改變
或整列消失）的項目視為**已處理**（ack）並移除。ack 訊號因此不是獨立的
「已讀」動作，而是隨 curator 正常的裁票／更新流程自然發生——這是
ack-based（而非 seen-based：本模組從不因為「被 SessionStart 印過」而
移除 pending 項目，只有底層資料真正變化才會移除）。

推送範圍的裁決：本登記檔只記錄**本 consumer 透過本機 section_comment.py
寫入**所產生的列——他方 consumer 或繞過本 CLI、直接以 `gh api` 寫入的列
不會出現在此登記檔，也就不會被推送。這是成本約束下的必然選擇：偵測他方
寫入需要重新拉取全量資料（即 `todo --json`），而 SessionStart 路徑禁止
此呼叫。此範圍限制記錄於此，供日後重評。

落點：`.claude/state/framework-issue-todo-pending.json`（per-worktree，
`.claude/state/` 已列入 .gitignore，不入版控、不跨機器同步、不寫入
canonical issue——與 `owned_issues_registry` 同一層級的本機快取，遺失
或損毀時的退化行為見 `load_pending` 與呼叫端 hook 的文件）。

Schema（v1）：
    {
      "schema_version": 1,
      "pending": [
        {
          "issue": 33,
          "owner": "graph-project-docs-manager-66",
          "source_ticket": "<ticket-id>",
          "type": "IMP",
          "task": "...",
          "acceptance_count": "5",
          "priority": "P1",
          "stage": "可立即執行",
          "updated_at": "<ISO8601>"
        }
      ]
    }

讀取失敗語意：缺檔／JSON 損毀／結構不符 schema 一律回傳 None（同
`owned_issues_registry` 慣例）。None 代表「無法判定目前有哪些未處理
項目」——呼叫端（`session-start-todo-delta-hook.py`）依此**選擇全列
沉默**而非全列重印：全列重印需要重建完整 baseline，即呼叫
`todo --json`，違反本機制的成本前提；沉默的代價是遺失期間新增的列
不會被通報，直到下一次寫入端呼叫重新建立範圍內的 pending 項目（見該
hook 檔頭的退化行為說明）。空清單（pending=[]）代表「已確認目前無未
處理項目」，兩者語意不同，呼叫端不可合併判斷。

誤報定義：本登記檔的內容可能落後於 canonical 真實狀態——若某列被
繞過本 CLI 的方式（直接 `gh api` 編輯 comment）標記為已處理，本登記檔
不會得知，會持續通報一個實際已處理的項目，直到下一次透過本 CLI 對同一
issue+owner 範圍執行寫入操作、觸發一次全量同步為止。這是本機快取類
機制共有的已知限制（同 `owned_issues_registry` 檔頭「遺失/不同步時...
只影響是否能走快速路徑」的定位），不是本模組的判定錯誤。
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCHEMA_VERSION = 1
REGISTRY_RELATIVE_PARTS = (".claude", "state", "framework-issue-todo-pending.json")

# 待通報狀態值：與 section_comment.py 的 TODO_STATUS_VALUES 語意一致，但
# 本模組刻意不 import section_comment（維持與 owned_issues_registry 同一
# 取向的零耦合），故獨立定義；兩者若未來分岔須同步維護，見上方 docstring。
PENDING_STATUS_VALUE = "待裁票"

_GIT_TOPLEVEL_TIMEOUT_SECONDS = 5


def _project_root() -> Path:
    """解析取向與 owned_issues_registry._project_root() 完全一致（同檔頭
    zero-coupling 理由），不重複展開說明。"""
    env_dir = os.getenv("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_GIT_TOPLEVEL_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return Path.cwd()


def registry_path(project_root: Optional[Path] = None) -> Path:
    """回傳登記檔絕對路徑；project_root 未提供時自動解析。"""
    root = project_root if project_root is not None else _project_root()
    for part in REGISTRY_RELATIVE_PARTS:
        root = root / part
    return root


def normalize_source_ticket(value: str) -> str:
    """正規化「來源票」欄位：去除前後空白與反引號包法差異（實測：同一份
    資料內兩種寫法並存，屬正規化不屬判定）。"""
    return (value or "").strip().strip("`").strip()


def _identity(issue: int, owner: str, source_ticket: str) -> str:
    return f"{issue}|{owner}|{normalize_source_ticket(source_ticket)}"


def load_pending(project_root: Optional[Path] = None) -> Optional[Dict]:
    """讀取登記檔。缺檔／JSON 損毀／schema 不符一律回傳 None（見檔頭
    讀取失敗語意）。"""
    path = registry_path(project_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != SCHEMA_VERSION:
        return None
    if not isinstance(data.get("pending"), list):
        return None
    return data


def pending_entries(project_root: Optional[Path] = None) -> Optional[List[Dict]]:
    """回傳登記檔內的 pending 項目清單；registry 缺失／損毀回傳 None。"""
    data = load_pending(project_root)
    if data is None:
        return None
    return [entry for entry in data["pending"] if isinstance(entry, dict)]


def _write_atomic(data: Dict, project_root: Optional[Path]) -> None:
    path = registry_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def sync_section_rows(
    issue_number: int,
    owner: str,
    rows: List[Dict[str, str]],
    updated_at: str,
    project_root: Optional[Path] = None,
) -> Tuple[int, int]:
    """對 `(issue_number, owner)` 範圍做一次全量同步，`rows` 為此次寫入後
    該範圍內的完整表格列集合（`來源票`／`做什麼`／`acceptance 條數`／
    `優先級`／`階段`／`狀態`，選填 `型別`）。

    狀態為 `PENDING_STATUS_VALUE`（待裁票）的列 upsert 進 pending；範圍內
    原本在 pending 但本次不再是「待裁票」（狀態改變或整列消失）的項目
    視為已處理並移除（見檔頭「同步模型」）。回傳 `(新增數, 移除數)` 供
    呼叫端即時回印（輔通道）。

    寫入失敗（權限、磁碟空間等）不重拋——同 `owned_issues_registry` 取向，
    本登記為 best-effort 局部加速快取，非核心功能；呼叫端已完成的
    GitHub 寫入不應因本機快取寫入失敗而回報錯誤。
    """
    try:
        data = load_pending(project_root) or {
            "schema_version": SCHEMA_VERSION,
            "pending": [],
        }
        existing = data["pending"]
        out_of_scope = [
            entry
            for entry in existing
            if not (entry.get("issue") == issue_number and entry.get("owner") == owner)
        ]
        in_scope = {
            _identity(entry.get("issue"), entry.get("owner"), entry.get("source_ticket", "")): entry
            for entry in existing
            if entry.get("issue") == issue_number and entry.get("owner") == owner
        }

        new_scoped = []
        current_ids = set()
        added = 0
        for row in rows:
            if row.get("狀態") != PENDING_STATUS_VALUE:
                continue
            source_ticket = normalize_source_ticket(row.get("來源票", ""))
            ident = _identity(issue_number, owner, source_ticket)
            current_ids.add(ident)
            if ident not in in_scope:
                added += 1
            new_scoped.append(
                {
                    "issue": issue_number,
                    "owner": owner,
                    "source_ticket": source_ticket,
                    "type": row.get("型別", ""),
                    "task": row.get("做什麼", ""),
                    "acceptance_count": row.get("acceptance 條數", ""),
                    "priority": row.get("優先級", ""),
                    "stage": row.get("階段", ""),
                    "updated_at": updated_at,
                }
            )

        removed = sum(1 for ident in in_scope if ident not in current_ids)
        data["pending"] = out_of_scope + new_scoped
        _write_atomic(data, project_root)
        return added, removed
    except OSError:
        # best-effort 快取，寫入失敗不影響呼叫端已完成的 GitHub 寫入結果
        # （同 owned_issues_registry.record_owned_issue 取向）。
        return 0, 0
