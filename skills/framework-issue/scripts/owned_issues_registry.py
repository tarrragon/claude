"""owned-issues 本地登記檔：schema、路徑解析、讀寫，供 section_comment.py
（寫入端）與 session-start-issue-check-hook.py（讀取端）共用。

背景：session-start-issue-check-hook.py 原以「git 主 repo 目錄名稱
kebab-case 化」heuristic 推導 owner 前綴，再以 gh search issues 粗篩候選、
逐張讀 comments 驗證 owner——對「從未建立過 framework issue 區段」的
consumer，此為每次 SessionStart 皆付出固定 gh API 往返成本、且結果必然
為空（實測單次數秒等級，含 uv 啟動時間；SessionStart 現有數十支 hook 同
時觸發，此成本乘以 hook 數）。

本登記檔由 section_comment.py 的 init／update 子命令於成功寫入 GitHub 後
同步落地——此時 owner／issue number 已由呼叫端確定為真（init 呼叫者提供
owner 且已成功建立區段；update 呼叫者已讀回既有 comment 驗證首行標記），
故登記檔內容視為「本專案已知擁有」的正確清單，讀取端不需再驗證 owner
（省略舊路徑的候選發現＋本地驗證兩步驟，僅保留呼叫既有 check 子命令）。

落點：`.claude/state/framework-issue-owned.json`（per-worktree，已列入
.gitignore 的 `.claude/state/`，不入版控、不跨機器同步——與 gh 上的真實
狀態相比僅是本機快取，遺失/不同步時 fail-open 退回舊路徑，不影響正確性，
只影響是否能走快速路徑）。

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
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

SCHEMA_VERSION = 1
REGISTRY_RELATIVE_PARTS = (".claude", "state", "framework-issue-owned.json")

# 讀寫端解析 project root 的逾時（秒）：`git rev-parse` 正常網路下遠低於此值，
# 逾時值只是異常環境的安全上限（同 session-start-issue-check-hook.py 的
# GH_TIMEOUT_SECONDS 設計取向）。
_GIT_TOPLEVEL_TIMEOUT_SECONDS = 5


def _project_root() -> Path:
    """git worktree 根目錄解析（獨立於 .claude/lib，維持本模組零耦合——
    section_comment.py 家族現行不依賴 .claude/lib，見同目錄 gh_common.py
    的既有取向）。

    優先序精簡對齊 lib.git_utils.get_project_root()：CLAUDE_PROJECT_DIR
    環境變數 -> git rev-parse --show-toplevel -> Path.cwd()（永不失敗）。
    不含該函式的「向上搜尋 CLAUDE.md」第三層 fallback——該分支僅在前兩者
    皆失敗的極端情境才觸發，本模組的讀寫皆為 best-effort、無需完整覆蓋
    此邊界；呼叫端（hook）持有 .claude/lib 時應改傳入 project_root 參數
    覆寫本函式，維持與 hook 自身 get_project_root() 解析結果一致。
    """
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
