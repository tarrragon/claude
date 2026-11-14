"""owned-issues 本地登記檔：schema、路徑解析、讀寫，供 section_comment.py
（寫入端）與 session-start-issue-check-hook.py（讀取端）共用。

背景：session-start-issue-check-hook.py 原以專案目錄名推導 owner 前綴、
以 gh search issues 粗篩候選再驗證 owner。這條路徑每次 SessionStart 都
付出 gh 往返成本，而且把專案名送到 GitHub。現在 hook 只讀本登記檔，缺檔
時不發 gh 命令；前綴搜尋移到使用者明示執行的 `rebuild-owned`
（rebuild_owned.py），以 write_registry 整份覆寫本登記檔。

本登記檔由 section_comment.py 的 init／update 子命令於成功寫入 GitHub 後
同步落地——此時 owner／issue number 已由呼叫端確定為真（init 呼叫者提供
owner 且已成功建立區段；update 呼叫者已讀回既有 comment 驗證首行標記），
故登記檔內容視為「本專案已知擁有」的正確清單，讀取端不需再驗證 owner
（省略舊路徑的候選發現＋本地驗證兩步驟，僅保留呼叫既有 check 子命令）。

落點：共用狀態根下的 `.claude/state/framework-issue-owned.json`。根目錄一律
經 `lib.hook_base.get_shared_state_root` 解析：在 linked worktree 內寫入或
讀取時都落在主倉庫，同一專案的所有 worktree 共用一份；本模組不另寫根目錄
解析。`.claude/state/` 已列入 .gitignore，不入版控、不跨機器同步——與 gh 上的
真實狀態相比僅是本機快取，遺失/不同步時 fail-open 退回舊路徑，不影響正確性，
只影響是否能走快速路徑。

Schema（v1）：
    {
      "schema_version": 1,
      "issues": [
        {"number": 81, "owner": "flutter-balance-99", "updated_at": "<ISO8601>"}
      ]
    }

讀取失敗語意：缺檔／JSON 損毀／結構不符 schema 一律回傳 None（不是空
清單）——None 代表「無法判定」，呼叫端（hook）依此 fail-open 退回舊路徑；
空清單（issues=[]）代表「已確認本專案無擁有任何 issue 區段」，呼叫端可
安全跳過整個 gh 呼叫鏈（acceptance 條款：無擁有區段時不發 gh API 呼叫）。
兩者語意不同，呼叫端不可合併判斷。

已知未覆蓋路徑（見對應 ticket how.strategy 的產生路徑盤點表）：本功能
上線前已建立、上線後從未再經 update 呼叫的既有 owned issue 不會自動出現
於本登記檔——登記檔無回填/遷移機制，需靠一次 update 呼叫補登；繞過
section_comment.py、直接以 gh api 建立/更新區段 comment 者同樣不會被記錄。
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 掛載 `.claude` 根目錄以 import lib（scripts -> framework-issue -> skills -> .claude）。
_CLAUDE_ROOT = Path(__file__).resolve().parents[3]
if str(_CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_ROOT))

from lib.hook_base import get_shared_state_root  # noqa: E402

SCHEMA_VERSION = 1
REGISTRY_RELATIVE_PARTS = (".claude", "state", "framework-issue-owned.json")


def registry_path(project_root: Optional[Path] = None) -> Path:
    """回傳登記檔絕對路徑，根目錄經 get_shared_state_root 解析。

    project_root 是呼叫端已解析的專案根，只在不處於 linked worktree 時採用
    （語意同 get_shared_state_root 的 default_root）；linked worktree 內一律
    解析到主倉庫，讓讀寫兩端落在同一份登記檔。
    """
    root = get_shared_state_root(project_root)
    for part in REGISTRY_RELATIVE_PARTS:
        root = root / part
    return root


def load_registry(project_root: Optional[Path] = None) -> Optional[Dict]:
    """讀取登記檔。缺檔／JSON 損毀／schema 不符一律回傳 None（見檔頭語意說明）。"""
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
    if not isinstance(data.get("issues"), list):
        return None
    return data


def owned_issue_numbers(project_root: Optional[Path] = None) -> Optional[List[int]]:
    """回傳登記檔內的 issue number 清單；registry 缺失／損毀回傳 None。"""
    data = load_registry(project_root)
    if data is None:
        return None
    numbers = []
    for entry in data["issues"]:
        if isinstance(entry, dict) and isinstance(entry.get("number"), int):
            numbers.append(entry["number"])
    return numbers


def write_registry(entries: List[Dict], project_root: Optional[Path] = None) -> Path:
    """以 entries 整份覆寫登記檔（供 rebuild-owned 使用），回傳寫入路徑。

    entries 為 {"number", "owner", "updated_at"} 清單；空清單代表「已確認本專案
    沒有擁有任何 issue」，讀取端據此不發任何 gh 命令。與 record_owned_issue 不同，
    寫入失敗會拋出 OSError：重建是使用者明示執行的命令，失敗須讓使用者看見。
    """
    path = registry_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"schema_version": SCHEMA_VERSION, "issues": list(entries)},
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)
    return path


def record_owned_issue(
    number: int,
    owner: str,
    updated_at: str,
    project_root: Optional[Path] = None,
) -> None:
    """新增或更新一筆登記（依 number 覆蓋既有項），供 section_comment.py
    cmd_init／cmd_update 於成功寫入 GitHub 後呼叫。

    原子寫入（暫存檔 + os.replace），避免半寫檔案被讀端撞見（同
    lib.pm_registry 手法，本模組獨立實作不 import 該模組——無需其跨行程
    鎖，本登記檔寫入頻率低（僅 init/update 觸發，非高頻並行路徑），偶發
    race 的最壞結果是遺失一次登記，下次 init/update 會覆蓋補正，不影響
    正確性只影響是否能走快速路徑（同檔頭 fail-open 語意）。

    寫入失敗（權限、磁碟空間等）不重拋——本登記為 best-effort 局部加速
    快取，非核心功能；呼叫端（cmd_init/cmd_update）已完成的 GitHub 寫入
    不應因本機快取寫入失敗而回報錯誤。
    """
    path = registry_path(project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = load_registry(project_root) or {
            "schema_version": SCHEMA_VERSION,
            "issues": [],
        }
        issues = [
            entry
            for entry in data["issues"]
            if not (isinstance(entry, dict) and entry.get("number") == number)
        ]
        issues.append({"number": number, "owner": owner, "updated_at": updated_at})
        data["issues"] = issues

        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError:
        # best-effort 快取，寫入失敗不影響呼叫端已完成的 GitHub 寫入結果
        # （見本函式 docstring）；無 logger 可用（section_comment.py 非
        # hook，不掛 hook_utils），靜默略過為刻意設計，非遺漏。
        pass
