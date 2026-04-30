#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Agent Dispatch Validation Hook - PreToolUse Hook

功能：強制實作代理人使用 isolation: "worktree" 派發，並對主 repo .claude/ 路徑
提供 target-based 判斷（ARCH-015 2026-04-18 修正版）。

Hook 類型：PreToolUse
匹配工具：Agent
退出碼：0 = 放行，2 = 阻擋（stderr 回饋給 Claude）

派發位置決策（對應 ARCH-015 2026-04-18 W5-050 重驗版）：

| Prompt 路徑分類 | isolation=worktree | Hook 行為 |
|---------------|--------------------|----------|
| 僅主 repo .claude/ | 不要求 | 放行（豁免 worktree） |
| 主 repo .claude/ + 非 .claude/ | 要求 | 放行（W5-050 新發現） |
| 主 repo .claude/ + 非 .claude/ | 無 | 阻擋（強制 worktree） |
| 僅非 .claude/ | 要求 | 放行 |
| 僅非 .claude/ | 無 | 阻擋（強制 worktree） |
| 含外部 .claude/（/tmp/ 等） | 任何 | 阻擋（runtime 必拒） |
"""

import json
import os
import re
import sys
from pathlib import Path
import logging
from typing import Callable, Dict, List, Optional, Tuple

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    extract_where_files,
)

# 需要 worktree 隔離的實作代理人
IMPLEMENTATION_AGENTS = frozenset({
    "parsley-flutter-developer",
    "fennel-go-developer",
    "thyme-python-developer",
    "cinnamon-refactor-owl",
    "pepper-test-implementer",
    "mint-format-specialist",
})

# 偵測 prompt 中相對路徑 .claude/ 提及（預設視為主 repo 內）
_RELATIVE_CLAUDE_PATTERN = re.compile(r"(?<![/\w])\.claude/")

# 偵測 prompt 中絕對路徑 .claude/（/xxx/.../.claude/）
# 用於區分主 repo 內外：比對匹配字串是否以主 repo root 為前綴
_ABSOLUTE_CLAUDE_PATTERN = re.compile(r"(/[^\s]+?)/\.claude/")

# 偵測 prompt 中非 .claude/ 的實作目標路徑
# 策略：匹配常見專案路徑開頭（避免誤判 `.claude/docs` 這類巢狀路徑為 docs/）
_NON_CLAUDE_PATH_PATTERN = re.compile(
    r"(?<![./\w])(?:src|tests?|lib|app|assets|scripts|public|bin|cmd)/"
)

# W5-047.2: 廣域 staging 偵測（PC-092 防護）
# 匹配 `git add .` / `git add -A` / `git add --all`（允許額外空白）
# 排除 `git add --`（具體路徑引導符）、`git add src/x` 等精準路徑
_WIDE_STAGING_PATTERN = re.compile(
    r"\bgit\s+add\s+(?:\.(?=\s|$)|-A\b|--all\b)"
)


def _has_wide_staging(prompt: str) -> bool:
    """偵測 prompt 是否含廣域 git staging 指令（git add . / -A / --all）。"""
    if not prompt:
        return False
    return bool(_WIDE_STAGING_PATTERN.search(prompt))


def _count_active_dispatches() -> int:
    """讀取 .claude/dispatch-active.json 的 dispatches 條目數量。

    回傳：條目數；檔案不存在、解析失敗、格式異常皆回傳 0。
    """
    try:
        project_root = get_project_root()
    except Exception:
        return 0

    state_file = project_root / ".claude" / "dispatch-active.json"
    if not state_file.exists():
        return 0

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    dispatches = data.get("dispatches") if isinstance(data, dict) else None
    if not isinstance(dispatches, list):
        return 0
    return len(dispatches)


_WIDE_STAGING_WARNING = """[警告] 並行派發場景偵測到廣域 git staging（git add . / -A / --all）

為什麼警告：
  PC-092（並行代理人 git index 競爭）：並行派發時 `git add .` 會暫存所有未追蹤/已修改檔案，
  包含其他並行代理人尚未 commit 的產物，造成 commit 邊界混亂與 index.lock 競爭。

建議修正：
  改用精準路徑 staging，例如 `git add src/foo.py tests/test_foo.py`
  派發 prompt 應明示各代理人負責的具體檔案路徑。

詳見：.claude/error-patterns/process-compliance/PC-092-parallel-agents-git-index-race.md
      .claude/pm-rules/parallel-dispatch.md（派發 prompt 必含精準 git staging 章節）

本訊息為警告（非阻擋），派發將繼續進行。"""


def _emit_wide_staging_warning_if_parallel(prompt: str, logger) -> None:
    """並行場景 + 廣域 staging → stderr 印警告（非阻擋）。"""
    if not _has_wide_staging(prompt):
        return
    active = _count_active_dispatches()
    if active < 2:
        logger.debug(
            "廣域 staging 但單一派發場景（active=%d），不警告",
            active,
        )
        return
    print(_WIDE_STAGING_WARNING, file=sys.stderr)
    logger.info(
        "警告：並行場景（active=%d）偵測到廣域 staging（PC-092）",
        active,
    )


# Ticket ID 偵測：0.18.0-W17-015.2、W17-015.2、0.18.0-W17-015 等格式
_TICKET_ID_PATTERN = re.compile(
    r"(?<![.\w])(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)(?![\w])"
)


def _extract_ticket_ids(prompt: str) -> List[str]:
    """從 prompt 擷取所有 ticket ID（完整格式 X.Y.Z-WN-NNN[.N]）。"""
    if not prompt:
        return []
    return list(dict.fromkeys(_TICKET_ID_PATTERN.findall(prompt)))


def _load_ticket_where_files(ticket_id: str) -> List[str]:
    """讀 ticket md 的 frontmatter where.files 欄位。

    W11-004.7.2：改用 hook_utils.hook_ticket.extract_where_files 共用 helper，
    消除與 file-ownership-guard / parallel-dispatch-verification 的重複實作。

    Returns:
        檔案路徑清單（原始字串、未規範化）；ticket 不存在或無 where.files 時回傳 []。
    """
    return extract_where_files(ticket_id)


def _classify_paths(paths: List[str], project_root_str: str) -> Tuple[bool, bool, bool]:
    """把路徑清單分類為 (main_repo_claude, external_claude, other)。"""
    has_main = False
    has_ext = False
    has_other = False
    for p in paths:
        # 絕對路徑 .claude/ 判斷主 repo vs 外部
        abs_match = _ABSOLUTE_CLAUDE_PATTERN.search(p)
        if abs_match:
            if project_root_str and p.startswith(project_root_str):
                has_main = True
            else:
                has_ext = True
            continue
        # 相對路徑 .claude/ → 主 repo
        if p.startswith(".claude/") or "/.claude/" in p:
            has_main = True
            continue
        # 其他路徑 → has_other（不過濾特定 prefix，ticket where.files 已是具體路徑）
        has_other = True
    return has_main, has_ext, has_other


def _classify_prompt_paths(prompt: str) -> Tuple[bool, bool, bool]:
    """分類 prompt 中的路徑提及。

    回傳：(has_main_repo_claude, has_external_claude, has_other)

    策略：
    - has_main_repo_claude：相對路徑 .claude/ 或絕對路徑 .claude/ 落在主 repo 樹內
    - has_external_claude：絕對路徑 .claude/ 不落在主 repo 樹內（例 /tmp/xxx/.claude/）
    - has_other：常見專案路徑（src/, tests/, lib/, app/...）

    設計決策：相對路徑 .claude/ 預設視為主 repo 內（符合 PM 派發主流慣例）。
    若實際在 worktree 下執行而失敗，由 CC runtime 直接回饋，非 Hook 層誤判。
    """
    if not prompt:
        return False, False, False

    # 偵測絕對路徑 .claude/ 並比對主 repo 前綴
    has_main_repo_claude = False
    has_external_claude = False

    try:
        project_root = get_project_root()
        project_root_str = str(project_root.resolve())
    except Exception:
        project_root_str = None

    for match in _ABSOLUTE_CLAUDE_PATTERN.finditer(prompt):
        # match.group(0) 形如 "/xxx/.../.claude/"
        abs_path = match.group(0)
        if project_root_str and abs_path.startswith(project_root_str + "/"):
            has_main_repo_claude = True
        else:
            has_external_claude = True

    # 偵測相對路徑 .claude/（需排除已被絕對路徑涵蓋者）
    # 簡化策略：找到任一相對路徑匹配（非絕對路徑前綴）即視為主 repo
    for match in _RELATIVE_CLAUDE_PATTERN.finditer(prompt):
        start = match.start()
        # 確認不是絕對路徑的一部分（前面不是 / 或 word char，已由 lookbehind 保證）
        # 相對路徑視為主 repo 內
        has_main_repo_claude = True
        break

    has_other = bool(_NON_CLAUDE_PATH_PATTERN.search(prompt))
    return has_main_repo_claude, has_external_claude, has_other


def _merge_ticket_scope(ticket_ids: List[str]) -> Tuple[bool, bool, bool]:
    """合併多個 ticket 的 where.files 分類為 (m, e, o) tuple（OR 合併）。

    讀取每個 ticket 的 where.files，逐路徑用 _classify_paths 取得 (m, e, o)，
    再 OR 合併。任一 ticket 載入失敗或無 where.files 時跳過。

    回傳：(has_main_repo_claude, has_external_claude, has_other)
    """
    try:
        project_root_str = str(get_project_root().resolve())
    except Exception:
        # 規則 4 雙通道：靜默降級為空字串可接受，因 _classify_paths 對空 root
        # 退化為「全部當作非主 repo」的保守判斷（has_main=False），不會誤豁免
        # worktree 強制；此處不寫 stderr 以免污染 hook 輸出，呼叫端日誌已足夠。
        project_root_str = ""

    has_main = False
    has_ext = False
    has_other = False
    for tid in ticket_ids:
        files = _load_ticket_where_files(tid)
        if not files:
            continue
        tm, te, to = _classify_paths(files, project_root_str)
        has_main = has_main or tm
        has_ext = has_ext or te
        has_other = has_other or to
    return has_main, has_ext, has_other


def _resolve_path_classification(
    prompt: str,
    ticket_ids: List[str],
    *,
    logger: Optional[logging.Logger] = None,
) -> Tuple[bool, bool, bool]:
    """統一決議 prompt 的路徑分類結果（W11-004.7）。

    依序套用三層規則並回傳合併後的 (has_main_repo_claude, has_external_claude, has_other)：

    L1. 從 prompt 抽取分類（沿用 _classify_prompt_paths）
    L2. W17-018 fallback：若 L1 全 False 且有 ticket_ids → 從 where.files 補分類
    L3. W11-004.7 覆蓋：若 L1 has_other=True 且 ticket scope 純 .claude/
        → 將 has_other 降為 False、has_main_repo_claude 升為 True
        理由：ticket where.files 是 scope 的 source of truth；prompt 內出現的
        tests/、src/、lib/ token 在純 .claude/ ticket 下視為 .claude/ 巢狀路徑
        引用（如 `.claude/skills/ticket/tests/`），不應觸發 worktree 強制。

    L2 / L3 互斥（elif）：L1 全 False 走 L2；L1 有 has_other 才走 L3。

    Args:
        prompt: 派發 prompt 全文
        ticket_ids: 已抽出的 ticket ID 清單（可為空）
        logger: 用於記錄 L2/L3 觸發的 logger；None 時不輸出日誌

    Returns:
        (has_main_repo_claude, has_external_claude, has_other) tuple
    """
    # L1: prompt 直接分類（總是執行）
    # 狀態：(m, e, o) 反映 prompt 內實際出現的路徑訊號
    m, e, o = _classify_prompt_paths(prompt)

    # 入口前置呼叫 _merge_ticket_scope 一次（W11-004.7.1 polish）：
    # L2/L3 都需要 ticket scope 分類，前置呼叫消除重複 I/O 與重複解析。
    # ticket_ids 為空時不呼叫，保留 (False, False, False) 預設值。
    ticket_m = ticket_e = ticket_o = False
    if ticket_ids:
        ticket_m, ticket_e, ticket_o = _merge_ticket_scope(ticket_ids)

    # L2: W17-018 fallback（prompt 全空 → 用 ticket scope 補分類）
    # 觸發條件：L1 三欄全 False AND ticket_ids 非空
    # 狀態轉換：(False, False, False) → (ticket_m, ticket_e, ticket_o)
    if not m and not e and not o and ticket_ids:
        m = m or ticket_m
        e = e or ticket_e
        o = o or ticket_o
        if logger is not None and (m or o or e):
            logger.info(
                "W17-018 fallback：prompt 路徑不明，由 ticket where.files 補分類："
                "ids=%s main_claude=%s external=%s other=%s",
                ticket_ids, m, e, o,
            )
    # L3: W11-004.7 覆蓋（has_other=True 但 ticket scope 純 .claude/）
    # 觸發條件：L1 含 has_other AND 無 external_claude AND ticket_ids 非空
    #          AND ticket scope 為純 .claude/（m=True, e=False, o=False）
    # 狀態轉換：(*, False, True) → (True, False, False)
    #
    # WARNING（假設邊界）：本層假設「ticket where.files 為 scope 的 source of truth」，
    # 故將 prompt 內的 src/tests/lib/ token 視為 .claude/ 巢狀路徑（如
    # `.claude/skills/ticket/tests/`）。若 ticket where.files 漏填或未涵蓋
    # 真正的非 .claude/ 變更目標，此層會誤豁免 worktree 強制。
    # 防護依賴：ticket 建立時的 where.files 完整性（PC-040 規範）。
    elif o and ticket_ids and not e:
        # 純 .claude/ 條件：ticket_m=True AND ticket_e=False AND ticket_o=False
        if ticket_m and not ticket_e and not ticket_o:
            if logger is not None:
                logger.info(
                    "W11-004.7 覆蓋：ticket scope 純 .claude/（ids=%s），"
                    "prompt 內 src/tests/lib/ token 視為 .claude/ 巢狀路徑",
                    ticket_ids,
                )
            o = False
            m = True

    return m, e, o


BLOCK_MESSAGE_TEMPLATE = """錯誤：實作代理人 {agent} 必須使用 isolation: "worktree" 派發

為什麼阻止：
  實作代理人會修改檔案和執行 git 操作，在主倉庫工作會污染 .git/HEAD。
  使用 worktree 隔離可從物理上防止分支切換影響主線程。

修復方式：
  在 Agent 呼叫中加入 isolation: "worktree" 參數

詳見: .claude/pm-rules/parallel-dispatch.md（Worktree 隔離章節）"""

EXTERNAL_CLAUDE_BLOCK_MESSAGE = """錯誤：實作代理人 {agent} 的 prompt 指向外部 .claude/ 路徑

為什麼阻止：
  ARCH-015（2026-04-18 重驗）：CC runtime 對外部 worktree 內 .claude/ Write/Edit
  硬編碼拒絕（如 /tmp/ 下的 worktree）。subagent 即使在對的 cwd 下也會被擋。
  主 repo 樹內的 .claude/ 可派發成功，但外部 .claude/ 無法。

修復方式：
  1. 若目標 .claude/ 檔案應在主 repo，改用相對路徑或主 repo 絕對路徑
  2. 若目標是外部 .claude/，改由 PM 前台處理，或搬檔到主 repo 再派發

詳見: .claude/error-patterns/architecture/ARCH-015-subagent-claude-dir-hardcoded-protection.md"""


# ============================================================================
# W5-045：Agent 禁止行為關鍵字衝突掃描
# ============================================================================
#
# 解析 agent .md 的「## 禁止行為」區塊，提取 `**禁止XX**` 標籤作為 prohibited
# actions；再以 FORBIDDEN_KEYWORD_MAP 把每條 prohibited action 映射為 prompt
# 偵測用 regex，對派發 prompt 進行子字串/regex 匹配。
#
# 策略（Warn vs Block）：初版一律 warn（exitcode 0 + stderr），累積 pattern
# 資料後再評估升級為 block。依賴 W5-043 標準化結構確保每個 agent 皆有此區塊。

# 定位 agent .md 中的 `## 禁止行為` 區塊（下一個 `## ` 為結尾，或 EOF）
_PROHIBITED_SECTION_PATTERN = re.compile(
    r"^## 禁止行為\s*$(.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)

# 抽取 `**禁止XX**` 中的 XX 內容（避免跨行；capture group 取冒號前的標籤）
# 範例匹配："**禁止實作程式碼**"、"**禁止 git commit**"
_PROHIBITED_LABEL_PATTERN = re.compile(r"\*\*禁止([^\*\n]+?)\*\*")

# 關鍵字 → prompt 偵測 regex 清單映射。
# 初版聚焦 W5-001 派發 sage 越界案例的常見衝突樣態。
# 擴充原則：發現誤報率可控（<5%）的新 pattern 時加入；高誤報者先保留測試。
FORBIDDEN_KEYWORD_MAP: Dict[str, List[re.Pattern]] = {
    "實作": [
        re.compile(r"實作"),
        re.compile(r"編寫[^\n]{0,10}程式碼"),
        re.compile(r"撰寫[^\n]{0,10}程式碼"),
        re.compile(r"\bimplement\b", re.IGNORECASE),
        re.compile(r"Write[^\n]{0,20}\.(?:py|js|ts|dart|go)", re.IGNORECASE),
        re.compile(r"寫入[^\n]{0,20}\.(?:py|js|ts|dart|go)"),
    ],
    "修改檔案": [
        re.compile(r"Edit[^\n]{0,20}\.(?:py|js|ts|dart|go)", re.IGNORECASE),
        re.compile(r"修改[^\n]{0,20}\.(?:py|js|ts|dart|go)"),
        re.compile(r"修正[^\n]{0,20}\.(?:py|js|ts|dart|go)"),
    ],
    "git commit": [
        re.compile(r"git\s+commit", re.IGNORECASE),
        re.compile(r"提交[^\n]{0,10}commit", re.IGNORECASE),
    ],
    "設計功能規格": [
        re.compile(r"設計[^\n]{0,10}規格"),
        re.compile(r"撰寫[^\n]{0,10}規格"),
    ],
    "直接執行測試修復": [
        re.compile(r"修復[^\n]{0,10}測試"),
        re.compile(r"fix[^\n]{0,10}test", re.IGNORECASE),
    ],
    "執行測試": [
        re.compile(r"執行[^\n]{0,10}測試"),
        re.compile(r"\brun\s+tests?\b", re.IGNORECASE),
        re.compile(r"\bpytest\b", re.IGNORECASE),
    ],
    # W11-004.1.2：新增 A-F 六類 pattern（擴充 keyword map 覆蓋 W5-001 以降新型越界）
    # 類別 A：Ticket CLI 操作（rosemary/incident-responder 禁止直接執行）
    "ticket CLI": [
        re.compile(r"\bticket\s+(?:track|create|migrate|handoff|claim|complete)\b", re.IGNORECASE),
        re.compile(r"/ticket\s+\w+"),
    ],
    # 類別 B：規格/文件修改（lavender/oregano/star-anise 禁止越權）
    "修改規格": [
        re.compile(r"(?:修改|編輯|Edit)[^\n]{0,20}(?:spec|規格|需求|use-?case)", re.IGNORECASE),
        re.compile(r"(?:更新|改寫)[^\n]{0,10}規格"),
    ],
    # 類別 C：Git 寫入（非 commit）
    "git 寫入": [
        re.compile(r"git\s+(?:push|merge|rebase|cherry-pick)", re.IGNORECASE),
        re.compile(r"git\s+reset\s+--hard", re.IGNORECASE),
        re.compile(r"(?:推送|合併|變基)[^\n]{0,10}(?:分支|branch|PR)"),
    ],
    # 類別 D：重構/移除（linux「只分析不修改」、pepper「只規劃不實作」）
    "執行重構": [
        re.compile(r"(?:執行|進行)[^\n]{0,10}重構"),
        re.compile(r"(?:移除|刪除)[^\n]{0,20}\.(?:py|js|ts|dart|go)"),
        re.compile(r"\brefactor\b", re.IGNORECASE),
    ],
    # 類別 E：系統級審查（lavender 禁止系統級審查）
    "系統審查": [
        re.compile(r"系統級?審查"),
        re.compile(r"(?:盤點|審計)[^\n]{0,10}(?:系統|架構|全專案)"),
    ],
    # 類別 F：分支/worktree 操作
    "分支操作": [
        re.compile(r"git\s+(?:checkout|branch|switch)\b", re.IGNORECASE),
        re.compile(r"\bworktree\s+(?:add|remove|prune)\b", re.IGNORECASE),
    ],
}


def _extract_prohibited_actions(agent_md_path: Path) -> List[str]:
    """解析 agent .md 檔的「## 禁止行為」區塊，回傳 `**禁止XX**` 標籤清單。

    回傳：prohibited action 標籤（XX 部分，已去除前後空白）。
    若檔案不存在、無法讀取、或無「## 禁止行為」區塊則回傳空 list。
    """
    try:
        content = agent_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    section_match = _PROHIBITED_SECTION_PATTERN.search(content)
    if not section_match:
        return []

    section_body = section_match.group(1)
    labels = [
        m.group(1).strip()
        for m in _PROHIBITED_LABEL_PATTERN.finditer(section_body)
    ]
    return labels


# W11-004.1.1：events.jsonl 路徑（與 dispatch_stats.py 必須一致）
try:
    _EVENTS_JSONL_PATH = (
        get_project_root()
        / ".claude/hook-logs/agent-dispatch-validation/events/events.jsonl"
    )
except Exception:
    _EVENTS_JSONL_PATH = (
        Path.cwd()
        / ".claude/hook-logs/agent-dispatch-validation/events/events.jsonl"
    )


def _make_excerpt(prompt: str, start: int, end: int, padding: int = 20) -> str:
    """取命中片段前後 padding 字元作上下文，換行替換為空白。"""
    lo = max(0, start - padding)
    hi = min(len(prompt), end + padding)
    return prompt[lo:hi].replace("\n", " ").replace("\r", " ")


# ============================================================================
# W11-004.1.3：白名單過濾 - 合法引用情境排除誤觸
# ============================================================================
#
# 設計：四條白名單規則（純函式 + WHITELIST_RULES 清單），在 _detect_keyword_conflicts
# 內部套用，命中任一規則則跳過該衝突。
#
# 規則 A：引號包圍偵測（『』「」"" '' `` ** **）
# 規則 B：否定前綴偵測（不要/請勿/禁止/避免/不得/不可/勿/don't/avoid/...）
# 規則 C：路徑/檔名上下文偵測（.claude/ docs/ src/ tests/ ... .md .py ...）
# 規則 D：Meta-task prompt 偵測（修改 .claude/rules/ / 編輯規則文件 / 更新 FORBIDDEN_KEYWORD_MAP）

# 引號配對：開 → 閉（成對引號）；同字元 → 同字元（對稱引號）
_QUOTE_PAIRS: Dict[str, str] = {
    "『": "』",
    "「": "」",
    '"': '"',
    "'": "'",
    "`": "`",
}

# Markdown 粗體包圍 **...**
_MD_BOLD = "**"

# 中文否定詞（在匹配位置前 10 字元內出現即視為否定前綴）
_NEGATION_WORDS_ZH = ("不要", "請勿", "禁止", "避免", "不得", "不可", "切勿", "勿")
# 英文否定詞（case-insensitive，以 regex 檢查）
_NEGATION_PATTERN_EN = re.compile(
    r"\b(?:don'?t|do\s+not|avoid|forbid(?:den)?|must\s+not|never)\b",
    re.IGNORECASE,
)

# 句子邊界字元（跨越則不算前綴）
# W11-004.1.3.3：加入 `，`、`！`、`？`，配合視窗擴至 20，讓逗號分隔的長句
# 不會把跨子句的否定詞誤判為前綴。
_SENTENCE_BOUNDARY_CHARS = set("。；;.\n\r，,！!？?")

# W11-004.1.3.3：否定詞視窗字元數（由 10 擴至 20，涵蓋「請不要在這個 ticket 裡面實作」
# 這類常見中文長句型。跨句邊界仍會被 _SENTENCE_BOUNDARY_CHARS 裁切）。
_NEGATION_WINDOW_SIZE = 20

# 路徑前綴（向前 30 字內出現視為檔案路徑上下文）
_PATH_PREFIXES = (".claude/", "docs/", "src/", "tests/", "test/", "lib/", "app/",
                  "scripts/", "bin/", "cmd/", "assets/", "public/")
# 副檔名（向後 15 字內出現視為檔案路徑上下文）
_FILE_EXTENSIONS = (".md", ".py", ".js", ".ts", ".dart", ".go", ".json", ".yaml", ".yml")

# W11-004.1.3.3：路徑合法字元正向 token（僅 ASCII；CJK 等非 ASCII 字元視為非路徑內容）
# 刻意不用 \w（Python 預設 \w 涵蓋 CJK，會把 `禁止`、`實作` 等關鍵字誤判為路徑字元）。
_PATH_TOKEN_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_/.-"
)


def _is_path_token(text: str) -> bool:
    """判斷字串是否完全由合法路徑字元組成。

    用於規則 C：正向驗證匹配字串與前後片段是否可構成延續的路徑 token。
    空字串視為合法（代表「無額外字元阻斷」）。
    """
    if not text:
        return True
    return all(ch in _PATH_TOKEN_CHARS for ch in text)
# Ticket ID 模式（如 0.18.0-W11-004.1.2）
_TICKET_ID_PATTERN = re.compile(r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*")

# Meta-task 宣告關鍵字（prompt 前 100 字元內出現任一即視為 meta-task）
_META_TASK_PATTERNS = (
    re.compile(r"修改\s*\.claude/(?:rules|agents|hooks|pm-rules|skills|references)/"),
    re.compile(r"編輯\s*\.claude/(?:rules|agents|hooks|pm-rules|skills|references)/"),
    re.compile(r"編輯規則文件"),
    re.compile(r"修改規則文件"),
    re.compile(r"更新\s*FORBIDDEN_KEYWORD_MAP"),
    re.compile(r"新增\s*FORBIDDEN_KEYWORD_MAP"),
)


def _is_quoted_match(prompt: str, start: int, end: int) -> Tuple[bool, str]:
    """規則 A：判斷匹配片段是否被引號/粗體包圍。

    回傳：(is_whitelisted, reason)。未命中回傳 (False, "")。
    策略：從 start 向前 50 字元掃描開引號，從 end 向後 50 字元掃描對應閉引號，
    中間不跨越換行。
    """
    if not prompt or start < 0 or end > len(prompt) or start >= end:
        return False, ""

    window_before = prompt[max(0, start - 50):start]
    window_after = prompt[end:min(len(prompt), end + 50)]

    # 禁跨行：若 window_before 或 window_after 含換行，裁切到最近換行後/前
    if "\n" in window_before:
        window_before = window_before.rsplit("\n", 1)[-1]
    if "\n" in window_after:
        window_after = window_after.split("\n", 1)[0]

    # 檢查成對/對稱引號
    for open_q, close_q in _QUOTE_PAIRS.items():
        # 向前找最近的 open_q
        open_idx = window_before.rfind(open_q)
        if open_idx == -1:
            continue
        # 對稱引號：open_q == close_q，需確認 open_q 出現次數為奇數
        if open_q == close_q:
            # 向後找 close_q 即可
            if close_q in window_after:
                return True, f"quoted_by_{open_q}{close_q}"
        else:
            # 成對引號：確認 window_before 在 open_idx 之後無閉引號
            tail = window_before[open_idx + len(open_q):]
            if close_q in tail:
                continue  # 這對引號已在匹配前閉合
            if close_q in window_after:
                return True, f"quoted_by_{open_q}{close_q}"

    # Markdown 粗體 **...**
    bold_open = window_before.rfind(_MD_BOLD)
    if bold_open != -1:
        tail = window_before[bold_open + len(_MD_BOLD):]
        if _MD_BOLD not in tail and _MD_BOLD in window_after:
            return True, "quoted_by_md_bold"

    return False, ""


def _has_negation_prefix(prompt: str, start: int, end: int = None) -> Tuple[bool, str]:
    """規則 B：判斷匹配位置前 _NEGATION_WINDOW_SIZE 字元內是否含否定詞（同句內）。

    回傳：(is_whitelisted, reason)。
    參數 end 為簽名統一用（與 per-match 規則 A/C 一致），此規則不消費 end。

    W11-004.1.3.3 調校：視窗由 10 擴至 20（_NEGATION_WINDOW_SIZE），配合句子邊界
    新增逗號/驚嘆/問號，涵蓋「請不要在這個 ticket 裡面實作」這類中長距否定句。
    """
    _ = end  # 簽名統一：per-match 規則共同接收 (prompt, start, end)，此規則忽略 end
    if not prompt or start <= 0:
        return False, ""

    window_start = max(0, start - _NEGATION_WINDOW_SIZE)
    window = prompt[window_start:start]

    # 檢查句子邊界：若 window 含句號/分號/換行，從最後一個邊界之後重新切
    last_boundary = -1
    for i, ch in enumerate(window):
        if ch in _SENTENCE_BOUNDARY_CHARS:
            last_boundary = i
    if last_boundary != -1:
        window = window[last_boundary + 1:]

    # 中文否定詞
    for word in _NEGATION_WORDS_ZH:
        if word in window:
            return True, f"negation_prefix_{word}"

    # 英文否定詞（用 regex）
    if _NEGATION_PATTERN_EN.search(window):
        return True, "negation_prefix_en"

    return False, ""


def _is_in_path_context(prompt: str, start: int, end: int) -> Tuple[bool, str]:
    """規則 C：判斷匹配位置是否落在檔案路徑/ticket ID 上下文內。

    W11-004.1.3.3 調校：改用正向 token 驗證取代「無空白」反向判斷。
    匹配字串本身必須全由 _PATH_TOKEN_CHARS 組成（ASCII 路徑字元），CJK 關鍵字
    如「禁止」「實作」即使緊接 `.claude/xxx` 之後也不會被誤判為路徑內容。

    條件（任一命中且匹配字串為路徑 token 即視為白名單）：
      1. 匹配落在 ticket ID 模式內（最優先，允許 CJK 以外結構）
      2. 匹配字串為合法路徑 token，且向前 30 字內含路徑前綴，之間字元皆為路徑 token
      3. 匹配字串為合法路徑 token，且向後 15 字內含副檔名，之間字元皆為路徑 token
    """
    if not prompt or start < 0 or end > len(prompt) or start >= end:
        return False, ""

    # Ticket ID 檢查（保留原行為，不受正向 token 限制）
    for m in _TICKET_ID_PATTERN.finditer(prompt):
        if m.start() <= start and end <= m.end():
            return True, "ticket_id_context"

    # 正向 token 調校核心：匹配字串必須為 ASCII 路徑字元
    # CJK 關鍵字（如「禁止」「實作」）即使緊接路徑前綴也不視為路徑內容
    matched = prompt[start:end]
    if not _is_path_token(matched):
        return False, ""

    # 路徑前綴檢查（向前 30 字內，且前綴與匹配之間字元皆為路徑 token）
    before = prompt[max(0, start - 30):start]
    for prefix in _PATH_PREFIXES:
        idx = before.rfind(prefix)
        if idx == -1:
            continue
        between = before[idx + len(prefix):]
        if _is_path_token(between):
            return True, f"path_prefix_{prefix.rstrip('/')}"

    # 副檔名檢查（向後 15 字內，且匹配與副檔名之間字元皆為路徑 token）
    after = prompt[end:min(len(prompt), end + 15)]
    for ext in _FILE_EXTENSIONS:
        idx = after.find(ext)
        if idx == -1:
            continue
        between = after[:idx]
        if _is_path_token(between):
            return True, f"file_ext_{ext.lstrip('.')}"

    return False, ""


def _is_meta_task_prompt(prompt: str) -> Tuple[bool, str]:
    """規則 D：判斷 prompt 是否為 meta-task（修改規則/agent 定義/FORBIDDEN_KEYWORD_MAP）。

    W11-004.1.3.3 調校：視窗由固定 100 字改為「第一段語意邊界或前 500 字」。
    典型 Ticket prompt 第一行為 `Ticket: 0.18.0-W...` 標題，meta-task 動詞描述
    出現在空行後第二段；原本 100 字視窗無法涵蓋會漏判。

    規則：
      - 若 prompt 無段落邊界或第一段長度 >= 100 字，取第一段
      - 否則擴至前 500 字作 fallback（涵蓋 ticket 標題 + 描述段落）
    """
    if not prompt:
        return False, ""
    # 以空行（\n\n）切段
    first_para = prompt.split("\n\n", 1)[0]
    if len(first_para) >= 100:
        head = first_para
    else:
        head = prompt[:500]
    for pat in _META_TASK_PATTERNS:
        m = pat.search(head)
        if m:
            return True, f"meta_task_{m.group(0)[:20]}"
    return False, ""


# 白名單規則清單（可擴充，拆兩層抽象）。
#
# PER_MATCH 層：每個 regex match 套用，簽名 (prompt, start, end) -> (bool, str)
#   - 規則 A 引號、規則 B 否定前綴、規則 C 路徑上下文。
#   - 命中任一 → 直接跳過該 conflict（不記錄）。
#
# PROMPT_LEVEL 層：整個 prompt 套用一次，簽名 (prompt) -> (bool, str)
#   - 規則 D meta-task。
#   - 命中 → 搭配 _META_TASK_VERBS 為特定 verb keyword 標 whitelist_reason
#     （per-match 降級，不整體豁免；見 _detect_keyword_conflicts）。
#
# 擴充即生效：新增規則只需 append 到對應清單，無需修改 _detect_keyword_conflicts。
PER_MATCH_WHITELIST_RULES: List[Callable[[str, int, int], Tuple[bool, str]]] = [
    _is_quoted_match,
    _has_negation_prefix,
    _is_in_path_context,
]

PROMPT_LEVEL_WHITELIST_RULES: List[Callable[[str], Tuple[bool, str]]] = [
    _is_meta_task_prompt,
]

# Backward-compat alias：保留既有 WHITELIST_RULES 名稱供外部/測試引用。
WHITELIST_RULES: List[Callable] = [
    *PER_MATCH_WHITELIST_RULES,
    *PROMPT_LEVEL_WHITELIST_RULES,
]


def _detect_keyword_conflicts(
    prompt: str, prohibited_actions: List[str]
) -> List[Dict[str, str]]:
    """掃描 prompt 是否命中 prohibited_actions 對應的關鍵字 pattern。

    回傳：衝突 dict 清單，每筆含 action / keyword / matched_pattern / prompt_excerpt。
    無衝突時回傳空 list。

    匹配策略：prohibited action 標籤若「包含」FORBIDDEN_KEYWORD_MAP 某個 key
    （子字串比對），則以該 key 的 patterns 掃描 prompt。
    """
    if not prompt or not prohibited_actions:
        return []

    # 規則 D（TD-2 修復，W11-004.1.3.2）：
    # Meta-task prompt 不再整體豁免，改為 per-match 降級。
    # 若 prompt 為 meta-task，對於命中 meta-task 相關關鍵字（「修改」「編輯」「更新」
    # 等通常用於描述規則文件變更的動詞）的 conflict，附帶 whitelist_reason，
    # 由呼叫端（_emit_keyword_conflict_warning_if_any）降級為 logger.debug，
    # 不寫 events.jsonl。
    #
    # 關鍵變更：真違規（git commit / git push / 實作 等動作，且該關鍵字匹配
    # 位置不在 meta-task pattern 涵蓋的前 100 字元範疇內，或該關鍵字本身
    # 不屬 meta-task 動詞）仍會產生 real conflict（無 whitelist_reason）。
    # Prompt-level 規則（清單驅動）：整個 prompt 套用一次，收集 reason 供 per-match 降級使用。
    # 當前僅規則 D（meta-task）會產生 reason；新增規則時直接 append 到 PROMPT_LEVEL_WHITELIST_RULES 即生效。
    prompt_level_reason = ""
    for rule in PROMPT_LEVEL_WHITELIST_RULES:
        is_matched, reason = rule(prompt)
        if is_matched:
            prompt_level_reason = reason or "prompt_level"
            break

    # meta-task 動詞集合：這些關鍵字在 meta-task prompt 中屬於規則文件編輯語境，
    # 不視為真違規，標 whitelist_reason。其他關鍵字（git commit/push/實作 等
    # 動作性越界）即使出現在 meta-task prompt 中，仍視為真違規。
    _META_TASK_VERBS = {"修改檔案", "編輯檔案", "更新檔案", "修改", "編輯", "更新"}

    conflicts: List[Dict[str, str]] = []
    for action in prohibited_actions:
        for keyword, patterns in FORBIDDEN_KEYWORD_MAP.items():
            if keyword not in action:
                continue
            for pattern in patterns:
                m = pattern.search(prompt)
                if not m:
                    continue
                # Per-match 白名單過濾（清單驅動）：命中任一規則即跳過。
                whitelisted = False
                for per_match_rule in PER_MATCH_WHITELIST_RULES:
                    if per_match_rule(prompt, m.start(), m.end())[0]:
                        whitelisted = True
                        break
                if whitelisted:
                    continue

                conflict: Dict[str, str] = {
                    "action": action,
                    "keyword": keyword,
                    "matched_pattern": pattern.pattern,
                    "prompt_excerpt": _make_excerpt(
                        prompt, m.start(), m.end(), padding=20
                    ),
                }
                # Prompt-level per-match 降級：僅對 meta-task 動詞類 keyword 標記
                if prompt_level_reason and keyword in _META_TASK_VERBS:
                    conflict["whitelist_reason"] = prompt_level_reason
                conflicts.append(conflict)
                break  # 同一 keyword 命中一次即可
    return conflicts


def _write_event_jsonl(
    subagent_type: str,
    prompt: str,
    conflicts_detail: List[Dict[str, str]],
    logger,
) -> None:
    """寫一行 event 到 events.jsonl，flock 並發安全，失敗不 raise。"""
    if not subagent_type or not prompt:
        return
    if not conflicts_detail:
        return

    import hashlib
    from datetime import datetime, timezone

    # 跨平台 file lock：Windows 下無 fcntl，降級為「不加 lock 寫入」
    # 理由：這是 event log append，極偶發 race 不會資料遺失，只會行交錯
    try:
        import fcntl as _fcntl
    except ModuleNotFoundError:
        _fcntl = None

    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    now = datetime.now(timezone.utc)
    ts_compact = now.strftime("%Y%m%dT%H%M%SZ")
    event_id = f"{ts_compact}-{prompt_hash[:8]}"
    timestamp_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    event = {
        "event_id": event_id,
        "timestamp": timestamp_iso,
        "subagent_type": subagent_type,
        "conflicts": conflicts_detail,
        "prompt_hash": prompt_hash,
        "prompt_length": len(prompt),
    }
    line = json.dumps(event, ensure_ascii=False) + "\n"

    try:
        _EVENTS_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_EVENTS_JSONL_PATH, "a", encoding="utf-8") as f:
            if _fcntl is not None:
                _fcntl.flock(f.fileno(), _fcntl.LOCK_EX)
            f.write(line)
    except OSError as e:
        msg = f"dispatch_stats: write event failed: {e}"
        if logger is not None:
            try:
                logger.warning(msg)
            except Exception:
                pass
        print(msg, file=sys.stderr)
        return


def _agent_md_path(subagent_type: str) -> Path:
    """回傳 agent .md 檔的主 repo 路徑（可能不存在）。"""
    try:
        project_root = get_project_root()
    except Exception:
        project_root = Path.cwd()
    return project_root / ".claude" / "agents" / f"{subagent_type}.md"


# ============================================================================
# W11-004.1.4：分層判決（high-confidence block / low-confidence warn / bypass）
# ============================================================================
#
# 設計依據：W11-004.1.1 Phase A 建立 annotate/stats 機制量化誤報率。
# 分層策略：
#   - HIGH_CONFIDENCE_KEYWORDS（直接可執行的 git/CLI 動詞，語意明確，FP 低）
#     → 阻擋（exit 2）
#   - 其他 keyword（實作/修改/設計等描述性動詞，語意模糊，FP 較高）
#     → 維持 warn（exit 0 + stderr）
#   - BYPASS：env var AGENT_DISPATCH_BYPASS=1 或 prompt 含 [BYPASS-DISPATCH-VALIDATION]
#     → 降級為 warn，PM 強制覆寫通道
#
# 高信心分類理由（對應父 ticket AC3「發現明顯越界時 block」）：
#   - git commit / git 寫入 / ticket CLI / 分支操作：具體命令，極難合法引用（
#     除非白名單 C/D 命中已被過濾），剩餘真命中基本皆為越界。
# 低信心保留 warn 理由：
#   - 實作 / 修改檔案 / 設計規格 等為 natural language 描述，白名單難以窮盡
#     所有合法引用（如說明文案、meta-task 外溢），維持 warn 避免誤阻塞。

HIGH_CONFIDENCE_KEYWORDS = frozenset({
    "git commit",
    "git 寫入",
    "ticket CLI",
    "分支操作",
})

_BYPASS_ENV_VAR = "AGENT_DISPATCH_BYPASS"
_BYPASS_PROMPT_MARKER = "[BYPASS-DISPATCH-VALIDATION]"


def _is_bypass_requested(prompt: str) -> Tuple[bool, str]:
    """判斷是否觸發 bypass（env var 或 prompt marker）。

    回傳：(bypassed, reason)。未觸發回傳 (False, "")。
    """
    if os.environ.get(_BYPASS_ENV_VAR) == "1":
        return True, f"env:{_BYPASS_ENV_VAR}=1"
    if prompt and _BYPASS_PROMPT_MARKER in prompt:
        return True, f"prompt_marker:{_BYPASS_PROMPT_MARKER}"
    return False, ""


def _partition_by_confidence(
    conflicts: List[Dict[str, str]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """依 HIGH_CONFIDENCE_KEYWORDS 分離 high/low 信心衝突。

    回傳：(high_conflicts, low_conflicts)。
    """
    high: List[Dict[str, str]] = []
    low: List[Dict[str, str]] = []
    for c in conflicts:
        if c.get("keyword") in HIGH_CONFIDENCE_KEYWORDS:
            high.append(c)
        else:
            low.append(c)
    return high, low


_KEYWORD_CONFLICT_BLOCK_TEMPLATE = """錯誤：派發 {agent} prompt 含高信心越界動作，已阻擋

為什麼阻止（W11-004.1.4 分層判決）：
  下列關鍵字屬直接可執行的 git/CLI 動作，與 {agent} 的「## 禁止行為」宣告衝突。
  誤報率極低（已排除引號引用/否定前綴/路徑上下文/meta-task 白名單）。

偵測到的高信心衝突：
{conflicts}

Agent 職責摘要：
  {agent} 的「## 禁止行為」明列不可執行此類動作。請改派適合的代理人：
  - 需要 git commit / 分支操作：派發實作代理人（parsley/thyme/fennel/cinnamon）
  - 需要 ticket CLI 操作：由 PM 前台執行

繞過方式（僅限 PM 確認合法情境後使用）：
  方法 1：export AGENT_DISPATCH_BYPASS=1 後重新派發
  方法 2：在 prompt 加入標記 [BYPASS-DISPATCH-VALIDATION]
  兩者皆會降級為 warn，仍會寫入 events.jsonl 供審計。

詳見：.claude/rules/core/agent-definition-standard.md
      .claude/error-patterns/process-compliance/（W5-001 派發越界學習）"""


_KEYWORD_CONFLICT_WARNING_TEMPLATE = """[警告] 派發 {agent} 偵測到 prompt 與 agent 禁止行為衝突

為什麼警告：
  W5-001 派發 sage 越界事件：PM prompt 要求 agent 執行其「## 禁止行為」區塊宣告
  不可做的動作（如實作、git commit、修改規格）。本 Hook 掃描 agent 宣告的禁止
  項，與 prompt 內關鍵字比對，發現潛在越界時提示。

偵測到的衝突：
{conflicts}

建議檢查：
  1. 確認派發對象正確（是否應改派實作代理人？）
  2. 若 prompt 合法（例如引用 agent 定義中的禁止詞彙作為說明），請忽略本警告
  3. 若 prompt 要求越界，請改派適合的代理人或拆分任務

詳見：.claude/rules/core/agent-definition-standard.md
      .claude/error-patterns/process-compliance/（W5-001 派發越界學習）

本訊息為警告（非阻擋），派發將繼續進行。"""


def _emit_keyword_conflict_warning_if_any(
    subagent_type: str, prompt: str, logger
) -> str:
    """掃描 agent 禁止行為與 prompt 衝突。

    W11-004.1.4：分層判決
      - 回傳 "block"：偵測到高信心衝突且未 bypass → 呼叫端應 exit 2
      - 回傳 "warn"：僅低信心衝突、或高信心但已 bypass → 已印 stderr 但放行
      - 回傳 "pass"：無衝突、或輸入無效

    stderr 輸出：block 印 _KEYWORD_CONFLICT_BLOCK_TEMPLATE；warn 印
    _KEYWORD_CONFLICT_WARNING_TEMPLATE。
    """
    if not subagent_type or not prompt:
        return "pass"

    agent_md = _agent_md_path(subagent_type)
    if not agent_md.exists():
        logger.debug("agent .md 不存在：%s（略過關鍵字掃描）", agent_md)
        return "pass"

    prohibited = _extract_prohibited_actions(agent_md)
    if not prohibited:
        logger.debug(
            "%s agent 無『## 禁止行為』區塊或解析為空（略過掃描）",
            subagent_type,
        )
        return "pass"

    conflicts = _detect_keyword_conflicts(prompt, prohibited)
    if not conflicts:
        return "pass"

    # W11-004.1.3.2（TD-2 修復）：per-match 降級
    meta_filtered = [c for c in conflicts if c.get("whitelist_reason")]
    real_conflicts = [c for c in conflicts if not c.get("whitelist_reason")]

    if meta_filtered:
        logger.debug(
            "%s prompt 有 %d 項 meta-task 白名單化關鍵字（降級不噴 stderr）：%s",
            subagent_type,
            len(meta_filtered),
            [c.get("whitelist_reason") for c in meta_filtered],
        )

    if not real_conflicts:
        return "pass"

    # W11-004.1.4：分層判決 + bypass
    high_conflicts, low_conflicts = _partition_by_confidence(real_conflicts)
    bypassed, bypass_reason = _is_bypass_requested(prompt)

    # 高信心衝突 + 未 bypass → block
    if high_conflicts and not bypassed:
        conflict_lines = "\n".join(
            f"  - 禁止行為『{c['action']}』命中關鍵字『{c['keyword']}』"
            f"（片段：{c['prompt_excerpt']!r}）"
            for c in high_conflicts
        )
        message = _KEYWORD_CONFLICT_BLOCK_TEMPLATE.format(
            agent=subagent_type, conflicts=conflict_lines
        )
        print(message, file=sys.stderr)
        logger.warning(
            "阻擋：%s prompt 偵測到 %d 項高信心關鍵字衝突（W11-004.1.4）",
            subagent_type, len(high_conflicts),
        )
        # 仍寫入 events.jsonl 供誤報率統計
        _write_event_jsonl(subagent_type, prompt, real_conflicts, logger)
        return "block"

    # 有衝突但走 warn 路徑（低信心、或高信心被 bypass）
    # 訊息內容維持原 warn template；bypass 時加註降級原因
    conflict_lines = "\n".join(
        f"  - 禁止行為『{c['action']}』命中關鍵字『{c['keyword']}』"
        f"（片段：{c['prompt_excerpt']!r}）"
        for c in real_conflicts
    )
    message = _KEYWORD_CONFLICT_WARNING_TEMPLATE.format(
        agent=subagent_type, conflicts=conflict_lines
    )
    if bypassed and high_conflicts:
        message += (
            f"\n\n[BYPASS] 高信心衝突已由 {bypass_reason} 降級為警告；"
            f"仍寫入 events.jsonl 供審計。"
        )
    print(message, file=sys.stderr)
    if bypassed and high_conflicts:
        logger.warning(
            "bypass：%s 高信心衝突 %d 項被 %s 降級（W11-004.1.4）",
            subagent_type, len(high_conflicts), bypass_reason,
        )
    else:
        logger.info(
            "警告：%s prompt 偵測到 %d 項關鍵字衝突（W5-045 低信心）",
            subagent_type, len(real_conflicts),
        )
    _write_event_jsonl(subagent_type, prompt, real_conflicts, logger)
    return "warn"


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("agent-dispatch-validation")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Agent":
        return 0

    # Claude Code PreToolUse hook 的 tool_input 可能以 JSON 字串或 dict 傳入
    raw_input = input_data.get("tool_input") or "{}"
    if isinstance(raw_input, str):
        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            logger.warning("tool_input JSON 解析失敗，放行")
            return 0
    else:
        tool_input = raw_input
    subagent_type = tool_input.get("subagent_type", "")

    prompt = tool_input.get("prompt", "") or ""

    # W5-045 + W11-004.1.4：agent 禁止行為關鍵字衝突掃描
    # 分層判決：高信心衝突 block（exit 2），低信心/bypass 僅 warn。
    # 不受 IMPLEMENTATION_AGENTS 限制：W5-001 派發 sage 越界事件中 sage 非
    # 實作代理人，但 prompt 要求實作而觸發越界，正需此掃描防護。
    verdict = _emit_keyword_conflict_warning_if_any(subagent_type, prompt, logger)
    if verdict == "block":
        return 2

    # 無 subagent_type 或非實作代理人 → 放行（worktree 強制邏輯僅對實作代理人）
    if not subagent_type or subagent_type not in IMPLEMENTATION_AGENTS:
        logger.info("放行：subagent_type=%s", subagent_type or "(empty)")
        return 0

    # Target-based 分類

    # W5-047.2：並行場景廣域 staging 警告（PC-092 防護，非阻擋）
    _emit_wide_staging_warning_if_parallel(prompt, logger)

    # W11-004.7：統一路徑分類 helper，整合 L1 prompt + L2 W17-018 fallback
    # + L3 純 .claude/ ticket 覆蓋（防止 prompt tests/ token 誤觸 worktree 強制）。
    ticket_ids = _extract_ticket_ids(prompt)
    has_main_repo_claude, has_external_claude, has_other = _resolve_path_classification(
        prompt, ticket_ids, logger=logger
    )

    # 優先順序判斷：

    # (1) 外部 .claude/ → 一律阻擋（runtime 必拒）
    if has_external_claude:
        message = EXTERNAL_CLAUDE_BLOCK_MESSAGE.format(agent=subagent_type)
        print(message, file=sys.stderr)
        logger.warning(
            "阻擋：%s prompt 含外部 .claude/ 路徑（runtime 必拒）",
            subagent_type,
        )
        return 2

    isolation = tool_input.get("isolation", "")

    # (2) 僅主 repo .claude/ 且無其他路徑 → 放行（ARCH-015 豁免 worktree）
    #     條件：has_main_repo_claude=True 且 has_other=False
    if has_main_repo_claude and not has_other:
        logger.info(
            "放行：%s 目標僅在主 repo .claude/（ARCH-015 豁免 worktree）",
            subagent_type,
        )
        return 0

    # (3) 已使用 worktree → 放行
    #     涵蓋：主 repo .claude/ + 非 .claude/ + worktree（W5-050 新發現）
    #           僅非 .claude/ + worktree
    if isolation == "worktree":
        logger.info("通過：%s 使用 worktree 隔離", subagent_type)
        return 0

    # (4) 其餘情況（has_other 無 worktree、空 prompt 無 worktree）→ 阻擋
    message = BLOCK_MESSAGE_TEMPLATE.format(agent=subagent_type)
    print(message, file=sys.stderr)
    logger.warning(
        "阻擋：%s 未使用 worktree（isolation=%s）",
        subagent_type, isolation or "(none)",
    )
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-dispatch-validation"))
