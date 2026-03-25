"""
Protocol Version 遷移邏輯

提供 ticket frontmatter 版本遷移的核心功能，支援從舊版本（1.0）向後相容升級至新版本（2.0）。
"""
from typing import Any, Dict, List, Tuple

from .constants import (
    PROTOCOL_VERSION_CURRENT,
    PROTOCOL_VERSION_DEFAULT,
    PROTOCOL_VERSION_MIGRATIONS,
    PROTOCOL_VERSION_RE,
)


class ProtocolVersionError(Exception):
    """Protocol version 相關錯誤"""
    pass


def is_valid_version_format(version_string: str) -> bool:
    """
    驗證版本格式是否為 Major.Minor 形式。

    Args:
        version_string: 要驗證的版本字串

    Returns:
        bool: 格式有效則返回 True，否則返回 False

    範例：
        >>> is_valid_version_format("2.0")
        True
        >>> is_valid_version_format("v2.0")
        False
    """
    return PROTOCOL_VERSION_RE.fullmatch(version_string) is not None


def migrate_ticket(ticket_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """
    將 ticket data 從任意版本遷移至最新版本。

    此函式實作向後相容的遷移邏輯，支援從 v1.0 升級至 v2.0 以及未來的版本擴展。

    Args:
        ticket_data: dict，ticket frontmatter 資料

    Returns:
        tuple: (migrated_data, migration_history)
        - migrated_data: 遷移後的資料，符合最新 schema
        - migration_history: 遷移步驟記錄，每項為 {"from": "1.0", "to": "2.0", "status": "success", "handler": "..."}

    Raises:
        ProtocolVersionError: 版本格式無效或無遷移路徑或環形遷移路徑

    設計原則：
        - 所有現有欄位完全保留（100% 無資訊遺失）
        - 新增可選欄位時添加預設值
        - 遷移過程記錄完整歷史，支援審計追蹤
        - 防護環形遷移路徑（超過 10 步上限）

    範例：
        >>> ticket = {"id": "0.1.0-W1-001", "title": "Test"}
        >>> migrated, history = migrate_ticket(ticket)
        >>> migrated["protocol_version"]
        '2.0'
        >>> history[0]["from"]
        '1.0'
    """
    # 步驟 1：偵測當前版本
    current_version = ticket_data.get("protocol_version", PROTOCOL_VERSION_DEFAULT)

    # 步驟 2：版本驗證
    if not is_valid_version_format(current_version):
        raise ProtocolVersionError(
            f"無效版本格式: {current_version}（期望格式：Major.Minor，如 '2.0'）"
        )

    # 步驟 3：初始化遷移歷史
    migration_history: List[Dict[str, str]] = []

    # 步驟 3.5：初始化迴圈計數器防護
    migration_step_count = 0
    max_migration_steps = 10

    # 步驟 4：逐步遷移至最新版本
    while current_version != PROTOCOL_VERSION_CURRENT:
        # 檢查是否超出遷移步數上限（防護環形遷移路徑）
        migration_step_count += 1
        if migration_step_count > max_migration_steps:
            raise ProtocolVersionError(
                f"遷移步數超出上限（{max_migration_steps}），可能存在環形遷移路徑"
            )

        if current_version not in PROTOCOL_VERSION_MIGRATIONS:
            raise ProtocolVersionError(
                f"無遷移路徑：{current_version} → {PROTOCOL_VERSION_CURRENT}"
            )

        # 取得遷移規則
        migration_rule = PROTOCOL_VERSION_MIGRATIONS[current_version]
        target_version = migration_rule["target"]
        handler_name = migration_rule["handler"]

        # 執行遷移
        ticket_data = migrate_v1_to_v2(ticket_data)

        # 更新版本欄位
        ticket_data["protocol_version"] = target_version

        # 記錄遷移步驟
        migration_history.append({
            "from": current_version,
            "to": target_version,
            "status": "success",
            "handler": handler_name,
        })

        current_version = target_version

    # 步驟 5：返回遷移結果和歷史
    return ticket_data, migration_history


def migrate_v1_to_v2(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    v1.0 → v2.0 遷移函式（向後相容）。

    此遷移函式實作從舊版 ticket schema（無 protocol_version 欄位）向新版升級的邏輯。
    遷移過程是完全向後相容的：所有現有欄位保留，僅新增可選欄位的預設值。

    新增欄位及其預設值：
        - creation_accepted: false  （Ticket 是否已通過建立審核）
        - tdd_phase: null           （當前 TDD 階段，如 "phase1"）
        - tdd_stage: []             （TDD 階段進度清單）

    Args:
        ticket_data: dict，v1.0 schema 的 ticket 資料

    Returns:
        dict，v2.0 schema 的 ticket 資料，包含所有原始欄位 + 新欄位預設值

    設計決策（無資訊遺失）：
        - 使用 .copy() 保留所有原有欄位
        - 新增欄位時檢查是否已存在（避免覆蓋）
        - 預設值選擇考慮語義正確性：
          - creation_accepted: false（新 ticket 視為未審核）
          - tdd_phase: null（尚未開始 TDD）
          - tdd_stage: []（尚無進度記錄）

    範例：
        >>> v1_data = {"id": "0.1.0-W1-001", "title": "Old Ticket", "status": "pending"}
        >>> v2_data = migrate_v1_to_v2(v1_data)
        >>> v2_data["creation_accepted"]
        False
        >>> v2_data["id"]
        '0.1.0-W1-001'
    """
    # 保留所有原有欄位（100% 無資訊遺失）
    migrated_data = ticket_data.copy()

    # 新增 v2.0 的可選欄位預設值（只在欄位不存在時添加）
    if "creation_accepted" not in migrated_data:
        migrated_data["creation_accepted"] = False

    if "tdd_phase" not in migrated_data:
        migrated_data["tdd_phase"] = None

    if "tdd_stage" not in migrated_data:
        migrated_data["tdd_stage"] = []

    return migrated_data
