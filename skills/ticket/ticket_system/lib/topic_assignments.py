"""ticket_id -> topic 映射（assignment log）的讀寫層。

背景：`topic_registry.py` 的 `topics-registry.txt` 語意是「主題名去重
清單」（單欄，正規化去重比對主題名本身）。建票標記與既有票回填都需要
「ticket_id -> topic」的雙欄映射，兩者是不同維度的資料（一份是值域去重
清單，一份是鍵值對應表）。混入單欄清單會破壞其正規化去重邏輯對「一行
一主題名」的格式假設，故映射另立同層檔案，格式比照 `topics-registry.txt`
的 append-only 純文字設計（tab 分隔 `ticket_id\\ttopic`，人可讀、diff
最小）。

本模組原為 `commands/topic_backfill.py` 私有實作，因 `commands/create.py`
亦需在建票成功後寫入同一映射而下沉至 `lib/`：`commands/` 之間互相
import 屬跨命令模組依賴，違反既有分層（commands 依賴 lib，不互相依賴）。
`commands/topic_backfill.py` 保留對本模組的 re-export 以維持既有呼叫端
與測試的匯入路徑不變。

Public API:
    list_assignments() -> dict[str, str]
        讀取 assignment log，回傳 {ticket_id: topic}。同一 ticket_id 若有
        多筆（改派後的產物），回傳檔案中最後一筆——讀取語意本已如此
        （逐行迭代以 dict 賦值覆蓋，見函式實作），非本次新增。
    append_assignment(ticket_id: str, topic: str) -> bool
        單筆指派，寫入 assignment log 並同步註冊主題至中央主題清單。
        對已有指派的 ticket_id 拒絕寫入（回傳 False），維持既有行為不變
        ——改派請用 `reassign_assignment`。
    reassign_assignment(ticket_id: str, topic: str) -> bool
        顯式改派：對已有指派的 ticket_id 追加一筆新指派（不覆寫既有行，
        append-only），使 `list_assignments()` 回傳新主題。與
        `append_assignment` 是兩個不同函式，呼叫端必須顯式選擇，避免
        批次回填誤用改派語意覆蓋既有指派。
    list_assignment_history(ticket_id: str) -> list[str]
        依寫入順序回傳某 ticket_id 曾被指派過的所有主題名（含當前值，
        當前值為最後一項），改派前的主題名仍可查。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

from ticket_system.lib.paths import get_ticket_state_root
from ticket_system.lib.topic_registry import append_topic

# assignment log 相對於專案根目錄的路徑（與 topics-registry.txt 同層，
# 格式決策見模組 docstring）。
TOPIC_ASSIGNMENTS_RELATIVE_PATH = "docs/work-logs/topic-assignments.txt"


def _assignments_path() -> Path:
    """取得 assignment log 的絕對路徑（不保證檔案存在）。

    根目錄改用 `get_ticket_state_root()`（非 `get_project_root()`，
    2026-09-02）：assignment log 是 ticket 狀態的一部分（記錄
    ticket_id -> topic 映射），在 linked worktree 內執行時必須統一寫入主
    倉庫，理由與票面 md 統一寫入主倉庫相同（見 `get_ticket_state_root`
    docstring）——否則 worktree 清理前若未察覺，此檔登記行會隨 worktree
    一併遺失（實測：worktree 內建票並完成時，登記行留在 worktree 未提交，
    票面 md 卻已落在主倉庫）。
    """
    return get_ticket_state_root() / TOPIC_ASSIGNMENTS_RELATIVE_PATH


def list_assignments() -> Dict[str, str]:
    """讀取 assignment log，回傳 {ticket_id: topic}。

    log 檔不存在時視為空（尚未有任何映射的正常初始狀態），非異常。
    """
    path = _assignments_path()
    if not path.exists():
        return {}

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        sys.stderr.write(
            f"[topic_assignments] 讀取 assignment log 失敗，視為空清單降級處理: "
            f"{path} ({exc})\n"
        )
        return {}

    assignments: Dict[str, str] = {}
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or "\t" not in stripped:
            continue
        ticket_id, topic = stripped.split("\t", 1)
        ticket_id = ticket_id.strip()
        topic = topic.strip()
        if not ticket_id or not topic:
            continue
        assignments[ticket_id] = topic
    return assignments


def append_assignment(ticket_id: str, topic: str) -> bool:
    """將單筆 ticket_id -> topic 指派寫入 assignment log，並同步向中央
    主題清單註冊該主題名（`topic_registry.append_topic` 本身冪等）。

    Idempotent：若 ticket_id 已存在指派，不重複寫入，回傳 False。

    Args:
        ticket_id: 欲指派的 ticket id。
        topic: 欲指派的主題名。

    Returns:
        True 表示已寫入新的一筆指派；False 表示該 ticket_id 已存在指派。

    Raises:
        ValueError: ticket_id 或 topic 正規化後為空白字串。
    """
    ticket_id = ticket_id.strip()
    topic = topic.strip()
    if not ticket_id or not topic:
        raise ValueError("ticket_id 與 topic 皆不可為空白字串")

    if ticket_id in list_assignments():
        return False

    _append_line(ticket_id, topic)
    return True


def reassign_assignment(ticket_id: str, topic: str) -> bool:
    """顯式改派：對已有指派的 ticket_id 追加一筆新指派，取代
    `append_assignment` 的拒絕行為，使 `list_assignments()` 讀到新主題。

    與 `append_assignment` 是獨立函式（非旗標參數），呼叫端必須主動選用
    才會觸發改派語意，避免批次回填誤用改派覆蓋既有指派（acceptance 第
    2 條）。檔案層維持 append-only：既有行不被改寫，新指派以追加表示
    （acceptance 第 3 條）；改派前的主題名仍留在檔案中，可用
    `list_assignment_history` 查詢（acceptance 第 4 條）。

    Idempotent 對齊：若新主題與目前指派相同（正規化前的原始字串相同），
    視為無變化，不追加冗餘行，回傳 False；否則追加並回傳 True。

    Args:
        ticket_id: 欲改派的 ticket id。
        topic: 新主題名。

    Returns:
        True 表示已追加新指派；False 表示新主題與目前指派相同，未寫入。

    Raises:
        ValueError: ticket_id 或 topic 正規化後為空白字串。
    """
    ticket_id = ticket_id.strip()
    topic = topic.strip()
    if not ticket_id or not topic:
        raise ValueError("ticket_id 與 topic 皆不可為空白字串")

    current = list_assignments().get(ticket_id)
    if current == topic:
        return False

    _append_line(ticket_id, topic)
    return True


def list_assignment_history(ticket_id: str) -> list:
    """依寫入順序回傳某 ticket_id 曾被指派過的所有主題名（acceptance 第
    4 條：改派歷史可查）。當前指派為列表最後一項（若存在）；ticket_id
    從未出現於 log 時回傳空列表。
    """
    ticket_id = ticket_id.strip()
    path = _assignments_path()
    if not ticket_id or not path.exists():
        return []

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        sys.stderr.write(
            f"[topic_assignments] 讀取 assignment log 失敗，改派歷史查詢視為空: "
            f"{path} ({exc})\n"
        )
        return []

    history = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped or "\t" not in stripped:
            continue
        line_ticket_id, line_topic = stripped.split("\t", 1)
        if line_ticket_id.strip() == ticket_id:
            history.append(line_topic.strip())
    return history


def _append_line(ticket_id: str, topic: str) -> None:
    """將單行 `ticket_id\\ttopic` 追加至 assignment log，並同步向中央
    主題清單註冊該主題名（`topic_registry.append_topic` 本身冪等）。

    `append_assignment` 與 `reassign_assignment` 共用的寫入路徑（DRY），
    呼叫前提是兩者各自的驗證與拒絕/idempotent 判斷已通過。
    """
    # 先註冊主題名至中央主題清單（冪等，同義主題不重複寫入），再寫入
    # assignment log——確保任何已出現在 log 中的指派，其主題名必已存在
    # 於 topics-registry.txt。
    append_topic(topic)

    path = _assignments_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 既有檔案若非空且末位元組不是換行（外部手動編輯所致），先補一個
    # 換行再寫新行，否則新行會與既有末行黏合為單一條目——與
    # topic_registry.append_topic 相同的無尾換行防護。補行本身仍是
    # append（讀 1 byte 判斷，不重寫既有內容），append-only 性質不變。
    needs_leading_newline = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as rf:
            rf.seek(-1, 2)
            needs_leading_newline = rf.read(1) != b"\n"

    with path.open("a", encoding="utf-8") as f:
        if needs_leading_newline:
            f.write("\n")
        f.write(f"{ticket_id}\t{topic}\n")
