"""
TDD Phase 自動推導（0.4.1-W2-009）

claim --as <agent> 時依 registry.yaml 的 agent -> tdd_phases 對應，自動推導
應寫入 ticket frontmatter 的 tdd_phase。同時定義 tdd_phase_source 兩種來源
枚舉，讓 `ticket track phase` 手動設定過的值不被此推導覆蓋。

背景：0.4.1-W2-004 ANA 結論——tdd_phase 推進機制存在但不在熱路徑，
0.4.0 十八票零呼叫。本模組把「agent 認領時應處於哪個 phase」接上 claim 熱路徑。
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from ticket_system.lib.paths import get_project_root
from ticket_system.lib.registry_loader import load_registry

REGISTRY_RELATIVE_PATH = Path(".claude") / "agents" / "registry.yaml"

# tdd_phase_source 枚举：manual = 經 `ticket track phase` 手動設定，claim 不覆蓋；
# auto = 經本模組推導寫入，後續 claim 仍可繼續推進。
TDD_PHASE_SOURCE_MANUAL = "manual"
TDD_PHASE_SOURCE_AUTO = "auto"


def _load_agent_tdd_phases(agent: str) -> List[str]:
    """讀取 registry.yaml 中指定 agent 宣告的 tdd_phases 清單。

    找不到 registry 檔案、agent 未登記、或 agent 沒有 tdd_phases 宣告時
    回傳空清單，呼叫端一律視為「無對應，不推導」（靜默略過）。

    Args:
        agent: agent 名稱（如 "fennel-go-developer"）。

    Returns:
        該 agent 宣告的 tdd_phases 清單，找不到對應時回傳空清單。
    """
    registry_path = get_project_root() / REGISTRY_RELATIVE_PATH
    registry = load_registry(registry_path)
    agents = registry.get("agents", {}) if isinstance(registry, dict) else {}
    config = agents.get(agent) or {}
    phases = config.get("tdd_phases") or []
    return [p for p in phases if isinstance(p, str)]


def infer_next_tdd_phase(ticket: Dict[str, Any], agent: str) -> Optional[str]:
    """依 agent 的 tdd_phases 對應與 ticket 自身 tdd_stage 推導下一個 tdd_phase。

    決策邏輯：
    - agent 在 registry 無 tdd_phases 對應 -> None（不推導）。
    - ticket 無 tdd_stage 序列時：agent 僅對應單一 phase -> 直接採用；
      對應多個 phase 因無法判斷順序 -> 放棄（回傳 None）。
    - 有 tdd_stage 時，以 ticket 目前 tdd_phase 在 tdd_stage 中的位置為起點
      （找不到則從序列開頭起算），取 agent tdd_phases 中最早出現於該起點
      （含起點）之後的 phase，即「該票 tdd_stage 中最早未完成 phase」。

    Args:
        ticket: 已載入的 ticket frontmatter（唯讀，不修改）。
        agent: claim --as 申報的 agent 名稱。

    Returns:
        推導出的 phase 字串；無法推導時回傳 None。
    """
    tdd_phases = _load_agent_tdd_phases(agent)
    if not tdd_phases:
        return None

    tdd_stage = ticket.get("tdd_stage")
    if not isinstance(tdd_stage, list) or not tdd_stage:
        return tdd_phases[0] if len(tdd_phases) == 1 else None

    current_phase = ticket.get("tdd_phase") or ""
    start_index = tdd_stage.index(current_phase) if current_phase in tdd_stage else 0

    for phase in tdd_stage[start_index:]:
        if phase in tdd_phases:
            return phase

    return None
