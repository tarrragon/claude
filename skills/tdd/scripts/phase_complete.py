#!/usr/bin/env python3
"""
phase_complete.py

整合 Phase Contract 驗證至 /tdd next 命令

執行流程：
1. 載入 contracts.yaml
2. 執行 PhaseContractValidator.validate()
3. 輸出驗證結果（errors 以 [ERROR] 前綴，warnings 以 [WARNING] 前綴）
4. 將驗證結果透過 `ticket track append-log` 寫入 Ticket 的 Test Results 章節
5. 若 errors 存在，返回 False（阻止後續 Phase 轉移）
6. 若僅有 warnings，顯示提示並繼續（返回 True）

消費端無 .claude/lib/phase_contract_validator.py 時優雅降級（portability-allow:
選用性依賴，缺件優雅降級，非可攜性違規）：印出 [WARNING] 並跳過驗證（視同
通過），不中斷指令碼本身。消費端無 `ticket` 指令（未安裝 .claude/skills/ticket，portability-allow: 選用性依賴，缺件優雅降級，非可攜性違規）
時同樣優雅降級：印出 [WARNING] 並跳過寫入，不阻擋 Phase 轉移（見
_write_validation_log）。
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import subprocess
import sys
from pathlib import Path

# 正確的跨層導入：使用相對路徑而非 sys.path.insert（架構層級邊界，見 IMP-045）
# .claude/skills/tdd/ → .claude/lib/ 導入共用驗證器（portability-allow: 架構性橋接至框架共用模組，consumer 端結構相同）
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "lib"))

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
    4. 將驗證結果透過 `ticket track append-log` 寫入 Ticket 的 Test Results 章節
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

    # 將驗證結果透過 ticket CLI 寫入 Test Results 章節
    _write_validation_log(ticket_id, result)

    # 根據驗證結果決定是否允許 Phase 轉移
    if result.can_proceed:
        return True
    else:
        print("\n[ACTION REQUIRED]")
        print("Please fix the above errors and try again.")
        return False


def _write_validation_log(ticket_id: str, result: ValidationResult) -> None:
    """
    將驗證結果寫入 Ticket 的 Test Results 章節

    透過 `ticket track append-log <id> --section "Test Results"` CLI 寫入
    ——不再自行解析 markdown 找插入點。原邏輯搜尋 "## Execution Log"，但
    本專案所有 ticket 的實際標題是 "# Execution Log"（H1），此比對永遠不會
    命中，插入行為從未真正發生，經調查後確認並移除該死碼。改寫入 Test
    Results 而非 Execution Log：後者是否該支援直接寫入尚未定案，前者是
    既有 schema 章節，現在就能用，讀者也知道去哪裡找。

    消費端未安裝本框架的 ticket 系統（`ticket` 指令不存在）時優雅降級：
    印出 [WARNING] 並跳過，不阻擋 Phase 轉移、不崩潰（同既有的 lib 缺件
    降級模式）。
    """
    lines = []
    if result.errors:
        lines.append("**Phase Contract Validation:** FAILED")
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"- {e}" for e in result.errors)
    else:
        lines.append("**Phase Contract Validation:** PASSED")
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {w}" for w in result.warnings)
    content = "\n".join(lines)

    try:
        proc = subprocess.run(
            ["ticket", "track", "append-log", ticket_id, "--section", "Test Results", content],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, OSError) as e:
        print(
            f"[WARNING] Phase Contract 驗證結果未寫入 ticket：找不到 `ticket` "
            f"指令（{type(e).__name__}），此為消費端需自行安裝的框架工具"
            "（.claude/skills/ticket）。驗證本身已完成，僅日誌未寫入。",
            file=sys.stderr,
        )
        return

    if proc.returncode != 0:
        print(
            f"[WARNING] Phase Contract 驗證結果寫入 ticket 失敗（exit "
            f"{proc.returncode}）：{(proc.stderr or proc.stdout).strip()}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("使用方式：python phase_complete.py <ticket_id> <phase> <ticket_dir>")
        sys.exit(1)

    ticket_id = sys.argv[1]
    phase = sys.argv[2]
    ticket_dir = sys.argv[3]

    success = complete_phase(ticket_id, phase, ticket_dir)
    sys.exit(0 if success else 1)
