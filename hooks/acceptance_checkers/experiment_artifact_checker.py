"""
Experiment Artifact Checker - complete 前實驗器材殘留掃描

`ticket track complete <id>` 前掃描工作區，找出屬於本票、依規範命名
（`experiment-<ticket-id>-<用途>.<副檔名>`）但尚未妥善處置的實驗器材，
不依賴票面登記本身是否完整。

背景：實驗器材存活期治理規範原僅要求「執行 complete 的一方於 complete
前人工掃描工作區」，多視角審查指出人工自檢的執行完全依賴收尾方記得執行，
而該規範的制訂本身正是源於一次收尾判斷失準的實測案例。本 checker 把該
人工步驟自動化，人工自檢降為 fallback（parallel-dispatch.md「存活期治理」
節同步更新引用）。

三情境判定：
    - 已登記已處置（status=kept 且指名接手者）：不阻擋，器材合法留存。
    - 已登記未處置（status=active，或值非預期）：阻擋，fail-closed。
    - 未登記殘留（git status 有檔案但 list-artifacts 查無登記）：阻擋，
      這正是「不依賴票面登記完整性」條款要防的情況——沒登記的器材最可能
      被漏處置。
    另有第四種登記與實況不一致的情況（status=removed 但檔案仍在工作區）
    一併歸類為阻擋，理由見 `_classify_status` docstring。

設計決策（完整理由見本票 Solution 章節）：
    1. 阻擋（非警告）：三情境的補救動作都是單一 CLI 呼叫
       （`ticket track resolve-artifact`），且掃描範圍已用本票 ID 前綴
       嚴格限定（見下方「掃描範圍」），假陽性風險低，符合規範原文
       「必須對每個在場器材擇一處置」的語氣強度。
    2. git 工作區掃描職責在本 checker（非要求 CLI 承載）：實驗器材
       登記 CLI 的既有規劃已明文將「untracked 持續監控」劃歸本 checker，
       理由是 CLI 單次呼叫做不到持續狀態驗證，且會使 list-artifacts
       從純讀 body 變成依賴 git 工作區狀態、職責混合。
    3. 呼叫 `ticket` CLI 而非直接 import ticket_system.lib：後者的
       package __init__ 會 eager-import 需要 yaml 的模組鏈，Claude Code
       以系統 python3（無 yaml）執行 .py hook 會 ModuleNotFoundError
       （`children_checker.py` 模組註解已記載同一失效模式的實測次數）；
       CLI 走獨立安裝環境不受此限制（`dispatch-identity-bind-hook.py`
       已有同型態的 `ticket track` subprocess 呼叫先例）。
    4. 基礎設施故障（git / ticket CLI 本身失敗）一律 fail-open：
       本檢查的職責是抓真實存在的殘留，不是驗證 git/CLI 是否可用；
       讓不相關的基礎設施故障連帶擋下所有 complete 呼叫，代價遠高於
       偶爾漏掉一次偵測（fail-open 失敗以 logger.warning 留痕，符合
       quality-baseline 規則 4 可觀測性要求）。

已知邊界（未承載）：
    盲測型器材（依規範免檔名前綴標示）不在本掃描範圍內——掃描機制正是
    以檔名前綴 `experiment-<ticket-id>-` 判定候選檔案，盲測型器材刻意不
    帶此前綴以避免介入被觀測對象（見 parallel-dispatch.md「器材分兩型」
    節）。規範已將盲測型器材的收尾責任限定為「放置方同一 session 親自
    收尾」，此邊界不需本 checker 補強，僅在阻擋訊息中提示讀者知悉。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

# 逾時秒數：與 hook_base.py GIT_TOPLEVEL_TIMEOUT（git）/
# dispatch-identity-bind-hook.py TICKET_CLI_TIMEOUT（ticket CLI）同數量級慣例
_GIT_STATUS_TIMEOUT = 10
_LIST_ARTIFACTS_TIMEOUT = 15

_EXPERIMENT_PREFIX = "experiment-"


class _ArtifactEntry(NamedTuple):
    """`ticket track list-artifacts --json` 單筆登記條目（僅取用本模組需要的欄位）。"""

    label: str
    path: str
    status: str


class _ResidualFile(NamedTuple):
    """git 工作區偵測到的殘留實驗器材檔案。"""

    path: str
    kind: str  # "unresolved_active" | "status_removed_but_present" | "unregistered"
    matched_label: Optional[str]


def _run_git_status_untracked(project_dir: Path, logger) -> List[str]:
    """執行 git status --porcelain --untracked-files=all，回傳 untracked 檔案路徑清單。

    只取 `??`（untracked）狀態列：規範條件二要求器材維持 untracked，
    已被 git add 或已提交的檔案不屬於本檢查的殘留定義範圍。
    """
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=all"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_STATUS_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git status 執行失敗，本次略過實驗器材殘留掃描（fail-open）: %s", exc)
        return []

    if result.returncode != 0:
        logger.warning(
            "git status 回傳非 0，本次略過實驗器材殘留掃描（fail-open）: %s",
            result.stderr.strip(),
        )
        return []

    paths = []
    for line in result.stdout.splitlines():
        if len(line) < 4 or line[:2] != "??":
            continue
        paths.append(line[3:].strip())
    return paths


def _list_registered_artifacts(
    ticket_id: str, project_dir: Path, logger
) -> Optional[List[_ArtifactEntry]]:
    """呼叫 `ticket track list-artifacts <id> --json` 取得已登記器材
    （既有的實驗器材登記 CLI 提供的讀取 API）。

    Returns:
        list：CLI 成功執行（含回傳空清單，代表確認無登記）。
        None：CLI 執行失敗（binary 不存在／逾時／輸出非合法 JSON），
            呼叫端須視為「無法確認」而非「確認無登記」，兩者處置不同
            （見模組 docstring 設計決策 4）。
    """
    try:
        result = subprocess.run(
            ["ticket", "track", "list-artifacts", ticket_id, "--json"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_LIST_ARTIFACTS_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(
            "ticket track list-artifacts 執行失敗，本次略過殘留阻擋判定（fail-open）: %s", exc
        )
        return None

    if result.returncode != 0:
        logger.warning(
            "ticket track list-artifacts 回傳非 0（rc=%s），本次略過殘留阻擋判定（fail-open）: %s",
            result.returncode,
            result.stderr.strip(),
        )
        return None

    try:
        raw = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "ticket track list-artifacts 輸出非合法 JSON，本次略過殘留阻擋判定（fail-open）: %s",
            exc,
        )
        return None

    if not isinstance(raw, list):
        logger.warning("ticket track list-artifacts 輸出格式非預期（非 list），視為無登記資料")
        return []

    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entries.append(
            _ArtifactEntry(
                label=item.get("label", "?"),
                path=item.get("path", ""),
                status=item.get("status", ""),
            )
        )
    return entries


def _normalize_path(path: str) -> str:
    return path.strip().lstrip("./")


def _match_registration(
    file_path: str, entries: List[_ArtifactEntry]
) -> Optional[_ArtifactEntry]:
    """比對 git 偵測到的檔案路徑與登記條目。

    登記路徑書寫方式可能與 git status 輸出不完全一致（如是否帶前導
    `./`），優先比對正規化後全路徑，找不到再退回比對檔名。
    """
    norm_file = _normalize_path(file_path)
    for entry in entries:
        if _normalize_path(entry.path) == norm_file:
            return entry
    for entry in entries:
        if Path(entry.path).name == Path(file_path).name:
            return entry
    return None


def _classify_status(status: str) -> str:
    """依 `resolve-artifact` 寫入的 status 值分類。

    值不在預期的 removed/kept 前綴時（含空字串、非預期文字），fail-closed
    視為 "active"——與 spawn_request_checker 對無法解析狀態的處置原則一致
    （寧可多问一次收尾方，不放行未確認的殘留）。
    """
    s = status.strip().lower()
    if s.startswith("removed"):
        return "removed"
    if s.startswith("kept"):
        return "kept"
    return "active"


def find_residual_experiment_artifacts(
    ticket_id: str, project_dir: Path, logger
) -> List[_ResidualFile]:
    """掃描工作區，找出屬於本 ticket 的實驗器材殘留。

    掃描範圍：檔名含 `experiment-<ticket_id>-` 前綴的 untracked 檔案
    （規範條件一的檔名軌，見模組 docstring）。刻意以本票 ID 限定範圍，
    使其他票的實驗器材不落入本次判定——那是各自票在自己 complete 時的
    責任，不應互相阻擋。
    """
    untracked = _run_git_status_untracked(project_dir, logger)
    prefix = f"{_EXPERIMENT_PREFIX}{ticket_id}-"
    candidates = [p for p in untracked if Path(p).name.startswith(prefix)]

    if not candidates:
        logger.debug("Ticket %s：工作區無符合前綴 %s 的 untracked 檔案", ticket_id, prefix)
        return []

    entries = _list_registered_artifacts(ticket_id, project_dir, logger)
    if entries is None:
        # 無法確認登記狀態（CLI 故障），fail-open：不對候選檔案下阻擋判定。
        return []

    residuals: List[_ResidualFile] = []
    for file_path in candidates:
        entry = _match_registration(file_path, entries)
        if entry is None:
            residuals.append(_ResidualFile(path=file_path, kind="unregistered", matched_label=None))
            continue

        kind = _classify_status(entry.status)
        if kind == "kept":
            continue  # 已顯性保留且指名接手者，非殘留
        if kind == "removed":
            residuals.append(
                _ResidualFile(
                    path=file_path, kind="status_removed_but_present", matched_label=entry.label
                )
            )
            continue
        residuals.append(
            _ResidualFile(path=file_path, kind="unresolved_active", matched_label=entry.label)
        )

    return residuals


def check_experiment_artifact_residual(
    ticket_id: str, project_dir: Path, logger
) -> Tuple[bool, Optional[str]]:
    """對外主 API，供 acceptance-gate-hook 呼叫。

    Returns:
        (True, message)：偵測到未妥善處置的實驗器材殘留，應阻擋 complete。
        (False, None)：無殘留，或掃描基礎設施故障已 fail-open 略過本次判定。
    """
    residuals = find_residual_experiment_artifacts(ticket_id, project_dir, logger)
    if not residuals:
        return False, None

    logger.warning(
        "Ticket %s 偵測到 %d 個未妥善處置的實驗器材，阻擋 complete", ticket_id, len(residuals)
    )
    return True, _format_block_message(ticket_id, residuals)


def _format_block_message(ticket_id: str, residuals: List[_ResidualFile]) -> str:
    lines = [
        "[BLOCKED] Acceptance Gate: 偵測到未妥善處置的實驗器材殘留",
        "",
        f"Ticket: {ticket_id}",
        "",
    ]
    for r in residuals:
        if r.kind == "unregistered":
            lines.append(f"  - {r.path}  [未登記殘留]")
        elif r.kind == "status_removed_but_present":
            lines.append(f"  - {r.path}  [{r.matched_label} 登記為 removed，但檔案仍在工作區]")
        else:
            lines.append(f"  - {r.path}  [{r.matched_label} 登記為 active，尚未處置]")

    lines.extend(
        [
            "",
            "請對每個殘留擇一處置後再重試 complete：",
            f"  - 移除：ticket track resolve-artifact {ticket_id} <EXP-N> --status removed",
            f"  - 保留：ticket track resolve-artifact {ticket_id} <EXP-N> --status kept "
            "--successor <接手 ticket ID>",
            "  - 未登記者：先 register-artifact 補登記，再依上述擇一處置",
            "",
            "已知邊界：盲測型器材（依規範免檔名前綴標示）不在本掃描範圍內，"
            "由放置方於同一 session 親自收尾。",
            "",
            "參考：.claude/pm-rules/parallel-dispatch.md"
            "「跨 session 實驗器材的自我標示與存活期治理」",
        ]
    )
    return "\n".join(lines) + "\n"
