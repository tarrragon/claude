"""
Ticket ID 解析模組

提供統一的 Ticket ID 解析功能，包括提取元件、序號轉換、Chain 資訊計算。
"""

import re
from typing import Optional, Dict, Any, List

from .constants import TICKET_ID_RE, KNOWN_TICKET_SUFFIXES


def extract_core_ticket_id(raw_id: Optional[str]) -> Optional[str]:
    """
    從可能帶描述後綴的 ID 字串中提取核心 Ticket ID。

    核心 ID 定義：符合 {version}-W{wave}-{sequence} 格式的部分，
    不含描述後綴。

    使用場景：
    - 從帶後綴的檔名提取可比較的 ID（用於鏈式計算、關聯查詢）
    - 驗證帶後綴 ID 是否對應有效的核心 ID

    Args:
        raw_id: 原始 ID 字串，可能帶描述後綴
                範例：
                - "0.1.0-W11-004-phase1-design"（帶後綴）
                - "0.1.0-W11-004"（標準格式）
                - "invalid"（無效格式）

    Returns:
        str: 核心 Ticket ID（不含後綴），如無法解析則返回 None
             範例：
             - "0.1.0-W11-004-phase1-design" -> "0.1.0-W11-004"
             - "0.1.0-W11-004" -> "0.1.0-W11-004"
             - "invalid" -> None

    Raises:
        None（不拋異常，有效的 raw_id 類型檢查）

    Examples:
        >>> extract_core_ticket_id("0.1.0-W11-004-phase1-design")
        '0.1.0-W11-004'
        >>> extract_core_ticket_id("0.1.0-W11-004")
        '0.1.0-W11-004'
        >>> extract_core_ticket_id("invalid")
        None
        >>> extract_core_ticket_id(None)
        None
    """
    # 防守式編程：None 檢查
    if raw_id is None:
        return None

    # 正則匹配
    match = TICKET_ID_RE.match(raw_id)
    if not match:
        return None

    # 群組提取和重組（不取 group(4)，即後綴部分）
    version = match.group(1)
    wave = match.group(2)
    sequence = match.group(3)
    core_id = f"{version}-W{wave}-{sequence}"
    return core_id


def has_description_suffix(raw_id: Optional[str]) -> bool:
    """
    判斷 ID 是否帶有描述後綴。

    快速布林判斷，用於區分帶後綴 ID 和標準 ID。

    Args:
        raw_id: 原始 ID 字串（可能為 None）

    Returns:
        bool: 是否有描述後綴
              True: 帶後綴且正則匹配
              False: 無後綴或無法匹配

    Examples:
        >>> has_description_suffix("0.1.0-W11-004-phase1-design")
        True
        >>> has_description_suffix("0.1.0-W11-004")
        False
        >>> has_description_suffix("invalid")
        False
        >>> has_description_suffix(None)
        False
    """
    if raw_id is None:
        return False

    match = TICKET_ID_RE.match(raw_id)
    if not match:
        return False

    suffix = match.group(4)
    return suffix is not None


def extract_id_components(ticket_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    提取 Ticket ID 的元件。

    從標準格式的 Ticket ID 提取版本、Wave 號和序號。

    格式規則：
    - 基本格式: {version}-W{wave}-{sequence}
    - 版本: 數字.數字.數字（如 0.31.0）
    - 波次: 整數（如 3, 9）
    - 序號: 整數序列，支援無限深度（如 001, 001.1, 001.1.2）

    Args:
        ticket_id: Ticket ID（格式: {version}-W{wave}-{seq}），可為 None

    Returns:
        Dict: {version, wave, sequence} 或 None 如果格式無效或輸入為 None

    Examples:
        >>> extract_id_components("0.31.0-W3-001")
        {'version': '0.31.0', 'wave': 3, 'sequence': '001'}
        >>> extract_id_components("0.31.0-W3-001.1.2")
        {'version': '0.31.0', 'wave': 3, 'sequence': '001.1.2'}
        >>> extract_id_components("invalid")
        None
        >>> extract_id_components(None)
        None
    """
    # 防守式編程：None 檢查
    if ticket_id is None:
        return None

    match = TICKET_ID_RE.match(ticket_id)
    if not match:
        return None

    return {
        "version": match.group(1),
        "wave": int(match.group(2)),
        "sequence": match.group(3),
    }


def parse_sequence(sequence_str: str) -> List[int]:
    """
    解析序號字串為整數列表。

    將點號分隔的序號字串轉換為整數列表。支援無限深度的序號結構。

    Args:
        sequence_str: 序號字串（如 "1" 或 "1.2.3"）

    Returns:
        List[int]: 序號列表

    Examples:
        >>> parse_sequence("001")
        [1]
        >>> parse_sequence("001.1")
        [1, 1]
        >>> parse_sequence("001.1.2")
        [1, 1, 2]
    """
    return [int(x) for x in sequence_str.split(".")]


def format_sequence(sequence_list: List[int]) -> str:
    """
    格式化序號列表為字串。

    將序號整數列表轉換為點號分隔的字串格式。

    Args:
        sequence_list: 序號列表

    Returns:
        str: 格式化的序號字串

    Examples:
        >>> format_sequence([1])
        '1'
        >>> format_sequence([1, 1])
        '1.1'
        >>> format_sequence([1, 1, 2])
        '1.1.2'
    """
    return ".".join(str(x) for x in sequence_list)


def calculate_chain_info(target_id: str) -> Dict[str, Any]:
    """
    根據目標 ID 計算 Chain 資訊。

    計算 Ticket 在任務鏈中的位置資訊，包括根 ID、父 ID、深度和序號列表。

    任務鏈結構：
    - 根任務：序號深度為 0（如 0.1.0-W3-001）
    - 子任務：序號深度 > 0（如 0.1.0-W3-001.1）
    - 孫任務：序號深度 > 1（如 0.1.0-W3-001.1.1）

    Args:
        target_id: 目標 Ticket ID

    Returns:
        Dict: {root, parent, depth, sequence}
            - root: 根任務 ID（該任務鏈的第一個任務）
            - parent: 父任務 ID（None 表示此任務是根任務）
            - depth: 任務深度（0 = 根任務，1 = 一級子任務，以此類推）
            - sequence: 序號整數列表

    Examples:
        >>> info = calculate_chain_info("0.1.0-W3-001")
        >>> info['root']
        '0.1.0-W3-001'
        >>> info['parent']
        None
        >>> info['depth']
        0
        >>> info['sequence']
        [1]

        >>> info = calculate_chain_info("0.1.0-W3-001.1")
        >>> info['root']
        '0.1.0-W3-001'
        >>> info['parent']
        '0.1.0-W3-001'
        >>> info['depth']
        1
        >>> info['sequence']
        [1, 1]

        >>> info = calculate_chain_info("0.1.0-W3-001.1.2")
        >>> info['root']
        '0.1.0-W3-001'
        >>> info['parent']
        '0.1.0-W3-001.1'
        >>> info['depth']
        2
        >>> info['sequence']
        [1, 1, 2]
    """
    components = extract_id_components(target_id)
    if not components:
        return {}

    sequence_list = parse_sequence(components["sequence"])
    depth = len(sequence_list) - 1

    # 計算根 ID
    root_id = f"{components['version']}-W{components['wave']}-{sequence_list[0]}"

    # 計算父 ID
    parent_id = None
    if depth > 0:
        parent_sequence = format_sequence(sequence_list[:-1])
        parent_id = f"{components['version']}-W{components['wave']}-{parent_sequence}"

    return {
        "root": root_id,
        "parent": parent_id,
        "depth": depth,
        "sequence": sequence_list,
    }


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
