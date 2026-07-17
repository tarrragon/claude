"""
SPEC 引用驗證模組

建票時掃描 title/what/why/where.layer/how.strategy 等欄位中的 SPEC-NNN
引用，對照 SPEC 登錄簿（docs/traceability.yaml + docs/proposals-tracking.yaml
聯集）已登錄編號，未登錄即輸出警告（不阻擋建立）。

動機（0.4.1-W2-001，F1）：SPEC-008 誤植跨票傳染（0.4.1-W1-001 →
0.4.1-W2-004），建票當下即時提示未登錄編號，可在源頭攔截誤植擴散，
不需等到後續 review 才發現。

登錄簿聯集設計（0.38.1-W1-107）：doc skill 的 traceability.yaml 為按需
建立檔（batch-init 產生），未執行過 batch-init 的專案改用
proposals-tracking.yaml 的 `specs:` 區段登錄 SPEC 編號。兩檔皆屬框架層
標準路徑（doc skill tracking_schema SSOT），聯集讀取兩者避免專案未初始化
其中一份時逐號誤報。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from .messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from ticket_system.constants import SPEC_REFERENCE_PATTERN
from ticket_system.lib.paths import get_project_root

_SPEC_REF_RE = re.compile(SPEC_REFERENCE_PATTERN)

# 掃描範圍：Ticket 中易攜帶 SPEC 引用的自由文字欄位（Solution 1.0.0-W1-001）
_SCANNED_TEXT_KEYS = ("title", "what", "why")


def extract_spec_references(text: str) -> List[str]:
    """從文字中擷取所有 SPEC-NNN 引用（去重，保留出現順序）。

    Args:
        text: 待掃描文字（可為 None 或非字串，回傳空清單）

    Returns:
        List[str]: 依出現順序去重後的 SPEC 編號清單（如 ["SPEC-008", "SPEC-002"]）
    """
    if not text or not isinstance(text, str):
        return []

    found: List[str] = []
    for match in _SPEC_REF_RE.finditer(text):
        ref = match.group(0)
        if ref not in found:
            found.append(ref)
    return found


def _collect_spec_ids(node: Any, found: Set[str]) -> None:
    """遞迴走訪 YAML 結構，從所有字串值中擷取 SPEC-NNN 編號。

    不假設固定 schema（如僅 spec_frs 欄位），避免 traceability.yaml 結構
    調整時登錄清單漂移（ARCH-020 同類防護：不散落平行實作各自假設欄位路徑）。
    """
    if isinstance(node, dict):
        for value in node.values():
            _collect_spec_ids(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_spec_ids(item, found)
    elif isinstance(node, str):
        for match in _SPEC_REF_RE.finditer(node):
            found.add(match.group(0))


# SPEC 登錄簿候選路徑（框架層標準路徑，非本專案識別符；reference-stability 規則 8）
_REGISTRY_RELATIVE_PATHS = (
    ("docs", "traceability.yaml"),
    ("docs", "proposals-tracking.yaml"),
)


def _registry_paths(root: Path) -> List[Path]:
    """回傳 SPEC 登錄簿候選路徑清單（依 root 展開）。"""
    return [Path(root) / Path(*parts) for parts in _REGISTRY_RELATIVE_PATHS]


def registries_uninitialized(project_root: Optional[Path] = None) -> bool:
    """判斷所有 SPEC 登錄簿候選路徑是否皆不存在。

    Args:
        project_root: 專案根目錄（測試可覆寫；預設用 get_project_root()）

    Returns:
        bool: True 表示所有登錄簿皆未初始化
    """
    root = project_root if project_root is not None else get_project_root()
    return all(not path.exists() for path in _registry_paths(root))


def _load_yaml_spec_ids(registry_path: Path) -> Set[str]:
    """讀取單一登錄簿檔案，回傳其中出現的 SPEC 編號集合。

    容錯設計：檔案不存在、無法解析或內容為空時回傳空集合，不拋出例外。
    """
    if not registry_path.exists():
        return set()

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        sys.stderr.write(
            f"[spec_reference_checker] 讀取 {registry_path} 失敗"
            f"（{type(e).__name__}）：{e}\n"
        )
        return set()

    if not data:
        return set()

    found: Set[str] = set()
    _collect_spec_ids(data, found)
    return found


def load_registered_spec_ids(project_root: Optional[Path] = None) -> Set[str]:
    """載入 SPEC 登錄簿（traceability.yaml + proposals-tracking.yaml）聯集。

    容錯設計：各檔案不存在、無法解析或內容為空時視為空集合，不拋出例外
    （與 registry_loader.load_registry 同一容錯策略，呼叫端不需 try/except）。

    Args:
        project_root: 專案根目錄（測試可覆寫；預設用 get_project_root()）

    Returns:
        Set[str]: 已登錄的 SPEC 編號集合（如 {"SPEC-002", "SPEC-013"}）
    """
    root = project_root if project_root is not None else get_project_root()

    found: Set[str] = set()
    for registry_path in _registry_paths(root):
        found |= _load_yaml_spec_ids(registry_path)
    return found


def _extract_scanned_text(ticket_fields: Dict[str, Any]) -> str:
    """從 Ticket 欄位字典組合出待掃描文字。

    掃描 title/what/why（自由文字欄位）+ where.layer + how.strategy
    （巢狀欄位，new_ticket 為完整 frontmatter dict 時存在）。
    """
    parts: List[str] = []
    for key in _SCANNED_TEXT_KEYS:
        value = ticket_fields.get(key)
        if isinstance(value, str):
            parts.append(value)

    where = ticket_fields.get("where")
    if isinstance(where, dict) and isinstance(where.get("layer"), str):
        parts.append(where["layer"])
    elif isinstance(where, str):
        parts.append(where)

    how = ticket_fields.get("how")
    if isinstance(how, dict) and isinstance(how.get("strategy"), str):
        parts.append(how["strategy"])

    return " ".join(parts)


def detect_unregistered_spec_references(
    ticket_fields: Dict[str, Any],
    project_root: Optional[Path] = None,
) -> List[str]:
    """偵測 Ticket 欄位中未登錄於 traceability.yaml 的 SPEC 引用。

    此函式僅用於建立時的輕量提示，不作為阻止建立的依據
    （與 acceptance_auditor.detect_srp_violations 同一設計原則）。

    Args:
        ticket_fields: Ticket 欄位字典（可為 create 的 config 或完整 frontmatter，
            至少需含 title/what/why 其中之一才有掃描意義）
        project_root: 專案根目錄（測試可覆寫）

    Returns:
        List[str]: 警告訊息清單（0 或 1 則，含所有未登錄編號）
        - []: 無 SPEC 引用，或引用皆已登錄
        - [warning]: 存在未登錄編號
    """
    if not ticket_fields:
        return []

    combined_text = _extract_scanned_text(ticket_fields)
    referenced = extract_spec_references(combined_text)
    if not referenced:
        return []

    # Lazy import：避免模組載入時的循環依賴（同下方 import 手法）
    from ticket_system.lib.command_lifecycle_messages import CreateMessages

    if registries_uninitialized(project_root):
        return [CreateMessages.SPEC_REGISTRY_UNINITIALIZED_WARNING]

    registered = load_registered_spec_ids(project_root)
    unregistered = sorted(
        {ref for ref in referenced if ref not in registered},
        key=lambda ref: int(ref.split("-", 1)[1]),
    )
    if not unregistered:
        return []

    # Lazy import：避免模組載入時的循環依賴（同 acceptance_auditor.detect_srp_violations 手法）
    from ticket_system.lib.command_lifecycle_messages import CreateMessages

    return [
        CreateMessages.UNREGISTERED_SPEC_REFERENCE_WARNING.format(
            spec_ids="、".join(unregistered)
        )
    ]
