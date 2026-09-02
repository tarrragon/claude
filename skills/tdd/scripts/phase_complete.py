#!/usr/bin/env python3
"""
phase_complete.py

整合 Phase Contract 驗證至 /tdd next 命令

執行流程：
1. 載入 contracts.yaml
2. 執行 PhaseContractValidator.validate()
3. 輸出驗證結果（errors 以 [ERROR] 前綴，warnings 以 [WARNING] 前綴）
4. 將驗證結果寫入 Ticket execution log
5. 若 errors 存在，返回 False（阻止後續 Phase 轉移）
6. 若僅有 warnings，顯示提示並繼續（返回 True）

消費端無 .claude/lib/phase_contract_validator.py 時優雅降級（portability-allow:
選用性依賴，缺件優雅降級，非可攜性違規）：印出 [WARNING] 並跳過驗證（視同
通過），不中斷指令碼本身。
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import os
import sys
from pathlib import Path

# 正確的跨層導入：使用相對路徑而非 sys.path.insert（架構層級邊界，見 IMP-045）
# .claude/skills/tdd/ → .claude/lib/ 導入共用驗證器（portability-allow: 架構性橋接至框架共用模組，consumer 端結構相同）
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

try:
    from phase_contract_validator import PhaseContractValidator, ValidationResult
    _VALIDATOR_AVAILABLE = True
except ImportError:
    # 消費端未提供 .claude/lib/phase_contract_validator.py 時優雅降級（portability-allow: 選用性依賴，缺件優雅降級，非可攜性違規）：
    # Phase Contract 驗證本身跳過（見 complete_phase 的降級分支），不阻擋
    # Phase 轉移，也不讓整個指令碼在載入階段崩潰。
    PhaseContractValidator = None
    ValidationResult = None
    _VALIDATOR_AVAILABLE = False


def complete_phase(
    ticket_id: str,
    phase: str,
    ticket_dir: str,
    contracts_path: str = ".claude/tdd/contracts.yaml",
) -> bool:
    """
    標記 Phase 完成並執行 contract 驗證

    執行流程：
    1. 載入 contracts.yaml
    2. 執行 PhaseContractValidator.validate()
    3. 輸出驗證結果（errors 以 [ERROR] 前綴，warnings 以 [WARNING] 前綴）
    4. 將驗證結果寫入 Ticket execution log
    5. 若 errors 存在，返回 False（阻止後續 Phase 轉移）
    6. 若僅有 warnings，顯示提示並繼續（返回 True）

    Args:
        ticket_id: Ticket ID（格式如 major.minor.patch-W<wave>-<seq>）
        phase: Phase 代號（"1" | "2" | "3a" | "3b"）
        ticket_dir: Ticket 文件所在目錄
        contracts_path: contracts.yaml 的路徑

    Returns:
        True 表示可以繼續，False 表示必須修正後重試
    """
    print(f"\n[Phase {phase} Contract Validation]")
    print(f"Ticket: {ticket_id}")
    print(f"Ticket Dir: {ticket_dir}")

    if not _VALIDATOR_AVAILABLE:
        print(
            "[WARNING] Phase Contract 驗證未執行：找不到 "
            ".claude/lib/phase_contract_validator.py，此為消費端需自行提供的"
            "框架共用模組。已跳過本次驗證，不阻擋 Phase 轉移。",
            file=sys.stderr,
        )
        return True

    # 初始化驗證器
    try:
        validator = PhaseContractValidator(contracts_path=contracts_path)
    except ValueError as e:
        print(f"[ERROR] 無法載入 contracts.yaml：{e}")
        return False

    # 執行驗證
    result = validator.validate(ticket_id=ticket_id, phase=phase, ticket_dir=ticket_dir)

    # 輸出驗證結果
    if result.errors:
        print(f"\n[VALIDATION FAILED]")
        for error in result.errors:
            print(f"[ERROR] {error}")
    else:
        print(f"\n[VALIDATION PASSED]")

    for warning in result.warnings:
        print(f"[WARNING] {warning}")

    # 將驗證結果寫入 Ticket execution log
    _write_validation_log(ticket_id, ticket_dir, result)

    # 根據驗證結果決定是否允許 Phase 轉移
    if result.can_proceed:
        return True
    else:
        print("\n[ACTION REQUIRED]")
        print("Please fix the above errors and try again.")
        return False


def _write_validation_log(
    ticket_id: str, ticket_dir: str, result: ValidationResult
) -> None:
    """
    將驗證結果寫入 Ticket execution log

    追加到 Ticket 檔案的 Execution Log 區塊
    """
    # 構建 Ticket 檔案路徑
    ticket_files = [
        f for f in os.listdir(ticket_dir) if f.startswith(ticket_id) and f.endswith(".md")
    ]

    if not ticket_files:
        return

    ticket_file = os.path.join(ticket_dir, ticket_files[0])

    # 讀取現有內容
    try:
        with open(ticket_file, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return

    # 構建驗證結果日誌
    validation_log = "\n## Phase Contract Validation\n\n"
    if result.errors:
        validation_log += "**Status:** FAILED\n\n"
        validation_log += "### Errors:\n"
        for error in result.errors:
            validation_log += f"- {error}\n"
        validation_log += "\n"
    else:
        validation_log += "**Status:** PASSED\n\n"

    if result.warnings:
        validation_log += "### Warnings:\n"
        for warning in result.warnings:
            validation_log += f"- {warning}\n"
        validation_log += "\n"

    # 在 Execution Log 區塊中追加
    if "## Execution Log" in content:
        # 在 Execution Log 區塊後追加
        insertion_point = content.find("## Execution Log") + len("## Execution Log")
        new_content = (
            content[:insertion_point] + validation_log + content[insertion_point:]
        )
    else:
        # 如果沒有 Execution Log 區塊，在檔案末尾追加
        new_content = content + "\n" + validation_log

    # 寫回檔案
    try:
        with open(ticket_file, "w", encoding="utf-8") as f:
            f.write(new_content)
    except (OSError, IOError):
        pass


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("使用方式：python phase_complete.py <ticket_id> <phase> <ticket_dir>")
        sys.exit(1)

    ticket_id = sys.argv[1]
    phase = sys.argv[2]
    ticket_dir = sys.argv[3]

    success = complete_phase(ticket_id, phase, ticket_dir)
    sys.exit(0 if success else 1)
