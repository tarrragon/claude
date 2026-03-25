#!/usr/bin/env python3
"""
phase-contract-validator-hook.py

TDD Phase Contract 四層驗證 Hook

Hook 入口點，使用 phase_contract_validator 中的共用驗證邏輯。

驗證邏輯說明：
- 四層驗證：存在性 → 格式 → 結構 → 內容
- Legacy 文件自動降級：Layer 2/3 的 ERROR 降級為 WARNING
- 具體實作見：.claude/lib/phase_contract_validator.py

使用方式：
    from phase_contract_validator import PhaseContractValidator, ValidationResult

    validator = PhaseContractValidator(contracts_path=".claude/tdd/contracts.yaml")
    result = validator.validate(
        ticket_id="0.1.2-W1-002",
        phase="1",
        ticket_dir="docs/work-logs/v0.1.2/tickets/"
    )

    if result.can_proceed:
        print("Phase 轉移允許")
    else:
        print("Phase 轉移被阻止，錯誤：", result.errors)
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import sys
from pathlib import Path

# 添加 .claude/lib 到 Python path，以便導入共用模組
lib_path = Path(__file__).parent.parent / "lib"
sys.path.insert(0, str(lib_path))

from phase_contract_validator import PhaseContractValidator, ValidationResult


def format_validation_result(result) -> str:
    """格式化驗證結果為輸出字串"""
    lines = []

    for error in result.errors:
        lines.append(f"[ERROR] {error}")

    for warning in result.warnings:
        lines.append(f"[WARNING] {warning}")

    return "\n".join(lines) if lines else "驗證通過"


if __name__ == "__main__":
    # 測試用途
    if len(sys.argv) < 4:
        print("使用方式：python phase-contract-validator-hook.py <ticket_id> <phase> <ticket_dir>")
        sys.exit(1)

    ticket_id = sys.argv[1]
    phase = sys.argv[2]
    ticket_dir = sys.argv[3]

    validator = PhaseContractValidator()
    result = validator.validate(ticket_id, phase, ticket_dir)

    print(format_validation_result(result))
    sys.exit(0 if result.can_proceed else 1)
