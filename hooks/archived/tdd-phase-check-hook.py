#!/usr/bin/env python3
"""
TDD Phase 完整性檢查 Hook
確保 TDD 四階段完整執行，不可跳過或簡化
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 添加 hooks 目錄到 path 以便導入 common_functions
sys.path.insert(0, str(Path(__file__).parent))

try:
    from lib.common_functions import setup_project_environment, log_with_timestamp
except ImportError:
    def setup_project_environment():
        project_dir = Path(__file__).parent.parent.parent
        logs_dir = project_dir / '.claude' / 'hook-logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        return project_dir, None, logs_dir

    def log_with_timestamp(log_file, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        if log_file:
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
            except IOError:
                pass


def get_latest_work_log(project_dir: Path) -> Path:
    """取得最新的工作日誌檔案"""
    work_log_dir = project_dir / 'docs' / 'work-logs'

    if not work_log_dir.exists():
        return None

    # 找出最新修改的 v*.md 檔案
    log_files = list(work_log_dir.glob('v*.md'))
    if not log_files:
        return None

    return max(log_files, key=lambda p: p.stat().st_mtime)


def check_tdd_phases(work_log: Path, log_file: Path) -> int:
    """檢查工作日誌是否包含所有四個 Phase"""
    if not work_log or not work_log.exists():
        log_with_timestamp(log_file, "[WARNING] 找不到工作日誌檔案")
        return 0

    log_with_timestamp(log_file, f"[CHECK] 檢查工作日誌: {work_log.name}")

    content = work_log.read_text(encoding='utf-8')

    # 檢查是否有 Phase 1-4 的標記
    phase1 = len(re.findall(r'Phase 1|Phase 1.*功能設計', content))
    phase2 = len(re.findall(r'Phase 2|Phase 2.*測試', content))
    phase3 = len(re.findall(r'Phase 3|Phase 3.*實作', content))
    phase4 = len(re.findall(r'Phase 4|Phase 4.*重構', content))

    log_with_timestamp(log_file, "[STAT] Phase 狀態統計:")
    log_with_timestamp(log_file, f"   Phase 1 (功能設計): {phase1} 次提及")
    log_with_timestamp(log_file, f"   Phase 2 (測試驗證): {phase2} 次提及")
    log_with_timestamp(log_file, f"   Phase 3 (實作執行): {phase3} 次提及")
    log_with_timestamp(log_file, f"   Phase 4 (重構優化): {phase4} 次提及")

    # 檢查是否有 Phase 缺失
    if phase1 > 0 and phase2 > 0 and phase3 > 0:
        if phase4 == 0:
            log_with_timestamp(log_file, "[WARNING] 發現 Phase 1-3 已執行，但缺少 Phase 4")
            log_with_timestamp(log_file, "[ALERT] 違反 TDD 四階段完整執行鐵律")
            log_with_timestamp(log_file, "[OK] 正確做法: 分派 cinnamon-refactor-owl 執行 Phase 4 評估")
            return 1
        else:
            log_with_timestamp(log_file, "[OK] TDD 四階段都有記錄")
    else:
        log_with_timestamp(log_file, "[INFO] TDD 流程尚未完成或正在進行中")

    return 0


def check_avoidance_language(work_log: Path, log_file: Path) -> int:
    """檢測逃避語言"""
    if not work_log or not work_log.exists():
        return 0

    log_with_timestamp(log_file, "[CHECK] 檢測 Phase 4 逃避語言")

    content = work_log.read_text(encoding='utf-8')

    # 定義逃避語言模式
    avoidance_patterns = [
        r"跳過.*Phase 4",
        r"Phase 4.*跳過",
        r"輕量.*檢查",
        r"簡化.*重構",
        r"Phase 4.*可選",
        r"看起來.*不用.*重構",
        r"品質.*好.*跳過",
        r"不需要.*Phase 4"
    ]

    found_avoidance = 0
    for pattern in avoidance_patterns:
        if re.search(pattern, content):
            log_with_timestamp(log_file, f"[ALERT] 檢測到逃避語言: 符合模式 \"{pattern}\"")
            found_avoidance = 1

    if found_avoidance == 0:
        log_with_timestamp(log_file, "[OK] 未檢測到 Phase 4 逃避語言")
    else:
        log_with_timestamp(log_file, "[WARNING] 發現 Phase 4 逃避語言")
        log_with_timestamp(log_file, "[REMIND] 提醒: TDD 四階段是強制性的，不可基於任何理由跳過")

    return found_avoidance


def check_phase3_to_phase4_transition(work_log: Path, log_file: Path) -> int:
    """檢查 Phase 3 完成後是否建議跳過 Phase 4"""
    if not work_log or not work_log.exists():
        return 0

    log_with_timestamp(log_file, "[CHECK] 檢查 Phase 3 -> Phase 4 轉換")

    content = work_log.read_text(encoding='utf-8')

    # 檢查是否有 Phase 3 完成的標記
    if re.search(r'Phase 3.*完成|實作執行.*完成', content):
        log_with_timestamp(log_file, "[INFO] 檢測到 Phase 3 完成標記")

        # 檢查是否有建議跳過 Phase 4 的語言
        if re.search(r'建議.*跳過|選項.*跳過.*Phase 4|可以.*不用.*Phase 4', content):
            log_with_timestamp(log_file, "[ALERT] 發現 Phase 3 完成後建議跳過 Phase 4")
            log_with_timestamp(log_file, "[ERROR] 這違反了 TDD 四階段強制執行鐵律")
            log_with_timestamp(log_file, "[OK] 正確做法: 立即分派 cinnamon-refactor-owl 執行 Phase 4")
            return 1
        else:
            log_with_timestamp(log_file, "[OK] Phase 3 -> Phase 4 轉換正常")

    return 0


def main():
    # 設定專案環境
    result = setup_project_environment()
    if result[0] is None:
        print("錯誤: 無法設定專案環境")
        sys.exit(1)

    project_dir, _, logs_dir = result

    # 日誌檔案
    log_file = logs_dir / f"tdd-phase-check-{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    log_with_timestamp(log_file, "[START] TDD Phase 完整性檢查 Hook: 開始執行")

    # 取得最新工作日誌
    latest_log = get_latest_work_log(project_dir)

    if not latest_log:
        log_with_timestamp(log_file, "[INFO] 未找到工作日誌，跳過檢查")
        log_with_timestamp(log_file, "[OK] TDD Phase 檢查完成")
        sys.exit(0)

    # 執行檢查
    phases_result = check_tdd_phases(latest_log, log_file)
    avoidance_result = check_avoidance_language(latest_log, log_file)
    transition_result = check_phase3_to_phase4_transition(latest_log, log_file)

    # 總結檢查結果
    if phases_result != 0 or avoidance_result != 0 or transition_result != 0:
        log_with_timestamp(log_file, "[WARNING] TDD Phase 檢查發現問題")
        log_with_timestamp(log_file, "[REMIND] 請確保遵循 TDD 四階段完整執行鐵律")
    else:
        log_with_timestamp(log_file, "[OK] TDD Phase 檢查通過")

    log_with_timestamp(log_file, "[END] TDD Phase 完整性檢查 Hook: 執行完成")

    # 不阻止執行，只提供警告
    sys.exit(0)


if __name__ == "__main__":
    main()
