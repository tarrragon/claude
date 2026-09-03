"""主題中央清單的 append-only 讀寫層。

背景（主題化排程系列 ANA 結論）：主題歸屬的六條自動推導候選（血緣、
`blockedBy`/`relatedTo` 邊、commit 共現、標題識別符共現等）在真實
pending 母體上實測 ARI 近乎隨機水準（0.005~0.036），唯一產生足夠訊號
的是「建票時顯式標記存中央清單」。同一份分析同時決定形態為「常駐
清單 + 建票時標記」（非一次性快照——pending 母體半衰期僅約 1.6 天；
非週期性掃描——邊際成本高於建票當下判斷）。本模組即該中央清單的讀寫
層，供後續的建票整合與存量回填共用，避免兩者各自定義格式產生不相容
的寫入路徑。

清單檔路徑與格式決策（Solution 記錄理由）：
    路徑：docs/work-logs/topics-registry.txt

    Why 這個路徑：
    - 主題不隸屬單一版本（常駐清單累積於建票時，新主題可能被任何
      版本的票首次使用），故不放在 `docs/work-logs/v{version}/` 之
      下，而放在 work-logs 根目錄，與版本目錄同層但不從屬任一版本。
    - `docs/` 下的檔案隨 commit 進版本控制，符合「進版控」要求。
    - 純文字檔案，`git log -p` 可直接閱讀每次新增的主題行，符合
      「人可讀」要求（相較 JSON/YAML，diff 最小且無需解析即可讀）。

    Why 這個格式（換行分隔、每行一個主題名，無其他 metadata）：
    - Append-only 語意在格式層面成立的前提是「新增一筆資料只需在檔尾
      加一行，不需重寫任何既有行」。純文字換行分隔天然滿足此性質；
      JSON 陣列或 YAML list 若要維持合法語法，每次新增都需要重寫檔案
      結構（至少是收尾符號），格式本身無法保證既有內容逐字不變。
    - 主題名本身即所需的全部資訊（無需 slug/id/建立時間等欄位）：
      下游用途是「建票時從既有主題名選取」與「回填時比對是否已有
      同義主題」，兩者都只需要主題名文字。

    正規化規則（決定同一主題是否裂成多個條目）：
    - 用途限定為「重複判定」與「防止大小寫/空白差異裂成兩個條目」，
      不用於改寫使用者輸入的顯示文字——清單檔保留使用者輸入的原始
      形式，正規化只作為比對 key。
    - 正規化步驟：Unicode NFKC normalize（CJK 全形/半形與相容字形
      統一比較基準）→ strip 首尾空白 → 內部連續空白 collapse 為單一
      空白 → casefold（ASCII 部分不分大小寫，CJK 部分 casefold 為
      no-op，不影響中文主題名）。
    - 不做的正規化：不轉 slug（不移除中文字元、不轉連字號）、不做
      同義詞/近義詞合併——上游分析只要求「相同主題名的大小寫與空白
      差異視為同一主題」，未要求語意層級的同義判定，避免本模組在
      未有驗證資料下引入額外的誤判風險。

Public API:
    list_topics() -> list[str]
        回傳清單檔中所有主題名（依正規化 key 去重，保留首次出現的
        原始形式）。清單檔不存在時回傳空 list，不拋錯。
    append_topic(name: str) -> bool
        將主題名追加至清單檔尾端。若正規化後已存在同義項則不重複
        寫入（回傳 False，冪等）；否則寫入新行並回傳 True。
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

from ticket_system.lib.paths import get_ticket_state_root

# 清單檔相對於專案根目錄的路徑（詳細路徑決策見模組 docstring）。
TOPICS_REGISTRY_RELATIVE_PATH = "docs/work-logs/topics-registry.txt"


def _registry_path() -> Path:
    """取得清單檔的絕對路徑（不保證檔案存在）。

    根目錄改用 `get_ticket_state_root()`（非 `get_project_root()`，
    2026-09-03，比照姊妹檔 `topic_assignments.py` 的既有修復模式）：本
    清單是 ticket 狀態的一部分（`topic_assignments._append_line` 會呼叫
    `append_topic` 同步註冊主題名），在 linked worktree 內執行時必須統一
    寫入主倉庫，理由與票面 md、assignment log 統一寫入主倉庫相同（見
    `get_ticket_state_root` docstring）——否則 worktree 清理前若未察覺，
    此檔的主題登記行會隨 worktree 一併遺失。
    """
    return get_ticket_state_root() / TOPICS_REGISTRY_RELATIVE_PATH


def normalize_topic_name(name: str) -> str:
    """將主題名正規化為比對用 key（不用於改寫顯示文字）。

    步驟：NFKC normalize -> strip 首尾空白 -> 內部空白 collapse 為單一
    空白 -> casefold。詳細理由見模組 docstring「正規化規則」段。

    Args:
        name: 原始主題名。

    Returns:
        正規化後的比對 key。
    """
    normalized = unicodedata.normalize("NFKC", name).strip()
    collapsed = " ".join(normalized.split())
    return collapsed.casefold()


def list_topics() -> list[str]:
    """列出中央清單中所有既有主題名。

    清單檔不存在時視為空清單而非錯誤（常駐清單起始於首次建票標記，
    回填前尚未有任何主題屬正常初始狀態）。

    Returns:
        主題名列表，依正規化 key 去重（保留每個主題首次出現的原始
        形式），維持檔案內出現順序。
    """
    path = _registry_path()
    if not path.exists():
        # 缺檔為正常初始狀態（尚未有任何主題被標記），非異常，故不記
        # 日誌、直接回傳空清單。
        return []

    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        # I/O 失敗（權限、檔案系統異常等）非正常初始狀態，屬需可見的
        # 異常；依 observability-rules 規則 1 寫入 stderr 後以空清單
        # 降級，不中斷呼叫端（list API 的失敗不應阻塞讀取路徑）。
        sys.stderr.write(
            f"[topic_registry] 讀取清單檔失敗，視為空清單降級處理: "
            f"{path} ({exc})\n"
        )
        return []

    seen_keys: set[str] = set()
    topics: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        key = normalize_topic_name(stripped)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        topics.append(stripped)
    return topics


def append_topic(name: str) -> bool:
    """將主題名追加至中央清單尾端（append-only）。

    若正規化後與既有主題同義則不重複寫入（冪等），既有檔案內容在
    任何情況下逐字不變——本函式只以 append 模式開檔，從不讀取後重寫
    整個檔案。

    Args:
        name: 欲新增的主題名（原始形式，未 strip 前的輸入亦可）。

    Returns:
        True 表示已寫入新行；False 表示正規化後已存在同義項，未寫入。

    Raises:
        ValueError: name 正規化後為空字串（空白或全空白輸入）。
    """
    stripped = name.strip()
    key = normalize_topic_name(stripped)
    if not key:
        raise ValueError("主題名不可為空白字串")

    existing_keys = {normalize_topic_name(topic) for topic in list_topics()}
    if key in existing_keys:
        return False

    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # 既有檔案若非空且末位元組不是換行（外部手動編輯所致），先補一個
    # 換行再寫新行，否則新行會與既有末行黏合為單一條目。補行本身仍是
    # append（讀 1 byte 判斷，不重寫既有內容），故 append-only 性質不變。
    needs_leading_newline = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("rb") as rf:
            rf.seek(-1, 2)
            needs_leading_newline = rf.read(1) != b"\n"

    with path.open("a", encoding="utf-8") as f:
        if needs_leading_newline:
            f.write("\n")
        f.write(f"{stripped}\n")
    return True
