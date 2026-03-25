"""
Worktree SKILL 常數定義

集中管理所有魔法數字、字面值和配置常數。
"""

# ===== 分支前綴常數 =====

# feat/ 前綴長度，用於 extract_ticket_id_from_branch 中去掉前綴
FEAT_PREFIX = "feat/"
FEAT_PREFIX_LEN = len(FEAT_PREFIX)  # 5




# ===== Ticket ID 正則表達式 =====

# ===== Ticket ID 正則表達式 =====
#
# M8 修復：本地定義 TICKET_ID_PATTERN 的原因說明
#
# 來源：.claude/skills/ticket/ticket_system/lib/constants.py
# 版本要求：v0.31.0 及更高版本
#
# 為何需要本地定義（不能引用）：
#   1. ticket_system 位於 .claude/skills/ticket/，距離此處相對路徑複雜
#   2. 避免循環依賴：ticket_system 內部可能引用 worktree_manager
#   3. worktree SKILL 需要獨立執行，不依賴其他 SKILL 的初始化
#   4. 正則表達式為常數，複製開銷低，修改時需同步兩處
#
# 支援的格式：
#   - 無限深度子任務：seq.seq.seq...
#   - 可選描述性後綴：-phase1-design, -analysis 等
#
# 範例：
#   0.31.0-W3-001              (根任務)
#   0.31.0-W3-001.1            (子任務)
#   0.31.0-W3-001.1.1          (孫任務)
#   0.1.0-W11-004-phase1-design (TDD Phase 文件)
#   0.1.0-W25-005-analysis     (分析文件)
#
# 維護建議：
#   如果修改正則表達式邏輯，請同時更新：
#   - .claude/skills/ticket/ticket_system/lib/constants.py
#   - .claude/skills/worktree/scripts/constants.py （本檔）
TICKET_ID_PATTERN = r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"


# ===== Worktree 相關常數 =====

WORKTREE_STATUS_OUTPUT_WIDTH = 50  # 狀態輸出寬度（分隔線）
DEFAULT_BASE_BRANCH = "main"  # create 子命令預設基礎分支


# ===== merge 子命令常數 =====

# ticket track 查詢超時秒數（避免 merge 流程卡住）
TICKET_QUERY_TIMEOUT = 5

# Ticket 已完成的狀態值
TICKET_COMPLETED_STATUS = "completed"


# ===== cleanup 子命令常數 =====

# cleanup 輸出寬度（與 status 使用相同常數）
CLEANUP_OUTPUT_WIDTH = WORKTREE_STATUS_OUTPUT_WIDTH

# git branch -d 失敗時，提示使用者的強制刪除指令中的 flag
BRANCH_FORCE_DELETE_FLAG = "-D"
