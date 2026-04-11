#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook 系統統一常數定義

集中管理所有 Hook 相關常數，包含派發計數、日誌、檔案路徑等。
"""

# ============================================================================
# 派發計數驗證 Hook（dispatch-count-guard-hook.py）
# ============================================================================

# 派發計數相關的關鍵字清單
# 用於在 Agent prompt/description 中偵測多人派發意圖
DISPATCH_MULTI_KEYWORDS = [
    "三人組",
    "多視角",
    "固定三人組",
    "parallel-evaluation",
    "並行評估",
    "Agent Teams",
    "3-4x",
    "double-track",
    "dual-track",
]

# 派發計數狀態檔路徑模板
# {ppid} 會被替換為父進程 ID，以識別當前 session
DISPATCH_BATCH_STATE_TEMPLATE = "/tmp/claude-dispatch-batch-{ppid}.json"

# 派發計數狀態檔過期時間（秒）
# 超過此時間的狀態檔視為已過期，不再累加計數
DISPATCH_BATCH_STATE_TIMEOUT_SECS = 300  # 5 分鐘

# 派發計數檢查日誌識別符
DISPATCH_COUNT_CHECK_LOG_MARKER = "[dispatch-count-check]"

# ============================================================================
# Session 上下文守衛 Hook（session-context-guard-hook.py）
# ============================================================================

# Session 完成計數輕度提醒閾值
SESSION_SOFT_WARN_THRESHOLD = 2

# Session 完成計數強烈建議閾值
SESSION_STRONG_WARN_THRESHOLD = 3

# Session 完成計數檔路徑模板
SESSION_COMPLETED_TICKETS_COUNTER_TEMPLATE = "/tmp/claude-session-completed-tickets-{ppid}"

# ============================================================================
# Handoff 自動接手 Hook（handoff-prompt-reminder-hook.py）
# ============================================================================

# Handoff 已提醒標誌檔路徑模板
HANDOFF_REMINDED_FLAG_TEMPLATE = "/tmp/claude-handoff-reminded-{ppid}"

# Handoff session 狀態檔路徑模板
HANDOFF_SESSION_STATE_TEMPLATE = "/tmp/claude-handoff-state-{ppid}.json"

# ============================================================================
# 通用常數
# ============================================================================

# Hook 執行成功碼
EXIT_SUCCESS = 0

# Hook 執行失敗碼
EXIT_ERROR = 1

# Hook 日誌根目錄
HOOK_LOG_DIR = ".claude/hook-logs"

# 專案根目錄標誌檔
PROJECT_ROOT_MARKER = ".claude"
