"""缺席斷言未查證提示模組（PC-BAL-053 承接）

建票時掃描 --why / --what 欄位：欄位文字含缺席斷言（「從未存在」「已移除」
等），且同一欄位內未見三層查證（尤其第三層反向搜尋層）痕跡時，於既有
checklist 區塊輸出提示，不阻擋建票。

動機：同一 session 內連續兩次以「同名檔案全庫搜尋不到」為前提直接判定
「功能缺口」，事後查證皆被推翻——兩次判斷共同漏掉的是 PC-BAL-053 記載的
第三層「反向搜尋層」：合併型遷移的接手者取新的上位語意名，按原檔名搜尋
必然落空，只有在候選接手者內部搜尋原檔名字串才能命中。定位為軟提示而非
硬閘門：缺席斷言有時是對的（同批次另一項腳本經三層查證確認確實從未
存在），以 exit code 表達強制力會讓代理人誤判建票失敗而重試，且對「這次
剛好對了」的缺席斷言會被當雜訊繞過，等於白白消耗一次阻擋額度換不到防呆
效果。
"""
if __name__ == "__main__":
    from .messages import print_not_executable_and_exit
    print_not_executable_and_exit()


from typing import Any, Dict, List

# 缺席斷言字樣：來源為 PC-BAL-053「症狀」章節與本模組派發文字所列範例。
_ABSENCE_ASSERTION_KEYWORDS = (
    "從未存在",
    "從未實作",
    "已移除",
    "無接手者",
    "查無",
    "不存在",
)

# 查證痕跡字樣：來源為 PC-BAL-053「判定『功能缺席』前的三層查證，缺一不可」
# 表。「全歷史」涵蓋「git log 全歷史」「git 全歷史」等寫法；「事件註冊」涵蓋
# 「settings.json 事件註冊」「settings.json 無事件註冊」等寫法。任一字樣出現
# 即視為該欄位已留下查證痕跡，不特別要求命中第幾層——本模組只在「完全無
# 痕跡」時提示，避免對已部分查證的文字誤報。
_VERIFICATION_TRACE_KEYWORDS = (
    "反向搜尋",
    "三層查證",
    "全歷史",
    "事件註冊",
)

# 掃描欄位：與 machine_path_detector 等模組不同，本模組刻意只掃 why / what，
# 不納入 acceptance 等其他自由文字欄位——缺席斷言的判定敘事集中在這兩個
# 欄位，擴大掃描範圍只會稀釋提示的精準度。
_SCANNED_FIELDS = ("why", "what")


def find_unverified_absence_claims(ticket_fields: Dict[str, Any]) -> List[str]:
    """回傳含未查證缺席斷言的欄位名稱清單（依 _SCANNED_FIELDS 順序）。

    判定以「同一欄位」為單位：欄位文字含缺席斷言關鍵字，且同一段文字內
    未見任何查證痕跡關鍵字，才視為命中。查證痕跡若寫在其他欄位不算數——
    讀者在缺席斷言出現的當下就該看到「這裡查過了嗎」，不該由讀者自行拼湊
    散落各欄位的線索。
    """
    if not isinstance(ticket_fields, dict):
        return []

    hit_fields: List[str] = []
    for field_name in _SCANNED_FIELDS:
        text = ticket_fields.get(field_name)
        if not isinstance(text, str) or not text:
            continue
        if not any(keyword in text for keyword in _ABSENCE_ASSERTION_KEYWORDS):
            continue
        if any(keyword in text for keyword in _VERIFICATION_TRACE_KEYWORDS):
            continue
        hit_fields.append(field_name)
    return hit_fields


def _build_hint(hit_fields: List[str]) -> str:
    """組裝提示文字：現象 + 三層查證清單（點名第三層反向搜尋層）+ 定位聲明。"""
    fields_label = "、".join(hit_fields)
    return (
        f"[提醒] {fields_label} 含缺席斷言（如「從未存在」「已移除」「查無」等），"
        "但未見查證痕跡。判定『功能缺席』前建議完成三層查證（PC-BAL-053）：\n"
        "   1. 原路徑是否存在\n"
        "   2. 同名檔是否只是搬了位置（全庫 find，排除 archived）\n"
        "   3. 反向搜尋層：在權威清單所列的現役元件（settings.json 事件註冊、"
        "skills/、hooks/ 等）內部搜尋原檔名字串，排除『合併』型遷移\n"
        "   缺席斷言有時是對的，本提醒不阻擋建票；三層皆無命中才可下『缺席』結論。"
    )


def detect_unverified_absence_claims(ticket_fields: Dict[str, Any]) -> List[str]:
    """建票用：偵測 --why / --what 缺席斷言且未見查證痕跡，回傳 0 或 1 則提示。

    Args:
        ticket_fields: 新建 ticket 的欄位字典（create 的 new_ticket）

    Returns:
        List[str]: 0 或 1 則提示訊息（單則含全部命中欄位）
    """
    hit_fields = find_unverified_absence_claims(ticket_fields)
    return [_build_hint(hit_fields)] if hit_fields else []
