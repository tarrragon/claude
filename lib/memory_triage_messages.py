"""Memory 分流指引訊息 SSOT（0.2.1-W3-196，Phase 4 第二輪修正）

三處消費端：
- memory-write-guard-hook.py 的 DENY_REASON（拒絕語氣）
- memory-dir-audit-hook.py 的 AUDIT_MESSAGE（偵測語氣）
- lib/ask_user_question_reminders.py 的
  AskUserQuestionReminders.COMMIT_HANDOFF_REMINDER（PM 執行時指引）

三者曾各自複製同一份判別問句、排除理由、三分流判準，已實測發生複本漂移
（多一逗號、字詞誤植）。本模組收斂三塊共用內容，三方平行 import——
`memory_triage_messages` 不放進 `lib/hook_messages.py`（該檔職責是「簡短
訊息常數」）或 `lib/ask_user_question_reminders.py`（該檔 docstring 自述
「這些不是簡短的訊息常數，是執行時指引文件」，兩者的職責宣稱都與本模組
不符），獨立成檔避免放錯地方，也避免與 `ask_user_question_reminders.py`
互相 import 造成循環。

各消費端保留各自的語氣前綴／結尾句——guard 是拒絕語氣（寫入被擋下）、
audit 是偵測語氣（寫入已發生）、COMMIT_HANDOFF_REMINDER 是 PM 執行指引
語氣，這個差異是刻意設計，不可合併。

`COMMIT_HANDOFF_REMINDER` 過去只消費 `TRIAGE_QUESTION`，三個目的地是另一
套措辭重寫——語意重複的漂移風險與逐字重複相同，故一併改為直接組合
`THREE_WAY_GUIDANCE`，不再各寫各的。
"""

TRIAGE_QUESTION = "另一個專案的 session 讀到這段，能用嗎"  # i18n-exempt


class MemoryTriageMessages:  # i18n-exempt
    """Memory 分流指引訊息常數集合。"""

    TRIAGE_QUESTION = TRIAGE_QUESTION

    # guard 與 audit 逐字相同的排除理由（本框架為何不用原生 memory 作知識
    # 載體）。呼叫端須自行在其後接語氣結尾句（guard：「記錯地方可以搬，
    # 不記錄就永久遺失。」；audit：「此訊息為事後稽核，寫入已發生，請
    # 評估是否需搬遷內容。」），語氣結尾句刻意不併入本常數。
    EXCLUSION_RATIONALE = (
        "本框架排除 Claude Code 原生 memory 作為知識載體：memory 存於使用者 "  # i18n-exempt
        "home 目錄，不隨 .claude/ sync 到其他專案，寫在這裡的跨專案經驗會在"  # i18n-exempt
        "別的專案消失。"  # i18n-exempt
    )

    THREE_WAY_GUIDANCE = (
        f"判別問句：「{TRIAGE_QUESTION}」\n"  # i18n-exempt
        "\n"
        "三個目的地：\n"  # i18n-exempt
        "  - 框架相關（換個專案名稱與路徑仍成立）→ 錯誤學習類直接執行 "  # i18n-exempt
        "`/error-pattern add`；其他性質（通用品質／PM 行為／方法論／Skill 引導）"  # i18n-exempt
        "依升級路徑表選 `.claude/rules/` `.claude/pm-rules/` "  # i18n-exempt
        "`.claude/methodologies/` `.claude/references/`\n"  # i18n-exempt
        "  - 專案相關（僅本專案成立：架構、領域規則、工具鏈）→ `docs/` 或 `CLAUDE.md`\n"  # i18n-exempt
        "  - 兩者皆非（僅當前 session 成立）→ 不記錄，ticket md 已承載執行脈絡\n"  # i18n-exempt
        "\n"
        "完整分流判準（含根因成熟度門檻、升級路徑表，權威來源）見 "  # i18n-exempt
        ".claude/pm-rules/pm-quality-baseline.md 規則 7。"  # i18n-exempt
    )
