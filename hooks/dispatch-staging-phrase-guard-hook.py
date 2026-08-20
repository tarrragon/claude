#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Dispatch Staging Phrase Guard Hook - PreToolUse Hook（Layer 2，軟提示）

功能：
  Agent/Task 派發涉及 git commit 工作、但 prompt 缺「精準 staging 制式句」
  （權威版見 .claude/references/agent-dispatch-template.md「精準 staging
  制式句（權威版）」節）關鍵片語時，輸出軟提示到 stderr，仍放行（exit 0）。

  制式句對齊 agent-dispatch-template.md 權威版（v1.29.0 起）涵蓋三類獨立
  根因，本 hook 以三類 OR 片語各自獨立判定（缺一不足，任一類別缺失皆
  觸發提示；早期版本曾折衷收攏為兩類，導致「add 精準」與「commit 無
  pathspec」兩證據可互相頂替而漏判，見 CATEGORY_C_PHRASES 註解）：
    - Category A（precise git add）：防廣域 `git add .` / `git add -A`
      併入其他並行代理人尚未 commit 的變更（PC-092）
    - Category B（git diff --cached --name-only / restore --staged 核對）：
      防他人已 stage 在共用 index 的內容被動吸收，須 `git diff --cached
      --name-only` 核對後 `git restore --staged` 排除（PC-BAL-008）
    - Category C（bare commit, no pathspec）：防 pathspec 裸 commit 丟棄
      既有 index、無條件從 working tree 重建指定路徑內容，即使 add 已
      精準也會被此步驟清空防護意義（`.claude/rules/core/
      bash-tool-usage-rules.md` 規則七）

比對方式：關鍵片語（非全文逐字比對）。理由見下方「比對方式選擇理由」。

定位聲明（多視角審查後下修，避免後人誤以為本 hook 覆蓋 PC-092/PC-BAL-008
執行期防護）：
  本 hook 是 t0 派發期的 proxy 攔截——檢查的是 PM 寫在 prompt 裡「描述未來
  行為的文字」，不是 agent 在 t1 實際執行的 git 指令。兩者之間沒有因果強制：
  prompt 寫對不保證 agent 照做，prompt 沒寫也不代表 agent 會做錯。且判準與
  風險負相關——越簡短、越省略 staging 指示的 prompt 越不含 `commit` 字面，
  越容易命中豁免 4（無 commit 意圖）而完全跳過檢查，提示反而在最需要提醒的
  派發上保持沉默。
  執行期（t1，agent 實際下 git 指令時）的防護是另一條獨立防線：現有
  `bash-git-protected-branch-guard-hook.py` 服務於保護分支判定但無法涵蓋
  path-limited add 語意；完整的執行期守衛屬獨立追蹤議題（見同批多視角審查
  分派出的「Bash 執行期 add 守衛」ticket），本 hook 不宣稱、也不應被當作
  PC-092 / PC-BAL-008 的執行期防線。

Hook 類型：PreToolUse
匹配工具：Agent, Task
退出碼：0 = 放行（含軟提示），本 hook 永不回傳 2（Layer 2 定位，commit 與否
        無法從 prompt 可靠推斷，硬擋誤報成本高於漏報）

跳過判準（正向錨點；下列任一為真即跳過提示，不進入片語檢查）：
  1. prompt 為空
  2. `isolation == "worktree"`（跨 repo 邊界，不共用主 repo 工作區 index）
  3. prompt 首行為 `Dispatch-Mode: readonly`
  4. `subagent_type`/`name` 屬 READONLY_AGENT_TYPES（唯讀派發，無 commit 副作用）
  5. prompt 未偵測到 commit 意圖（見 `_has_commit_intent`）
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # .claude/ — for `from lib import ...`

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin  # noqa: E402

# ----------------------------------------------------------------------------
# 比對方式選擇理由
# ----------------------------------------------------------------------------
# 全文逐字比對 vs 制式句權威版（agent-dispatch-template.md）的證據：目前僅有
# 一筆自然觀測樣本（n=1，某次實際派發中 PM 中文改寫句與英文權威版逐字重疊
# 接近零，但該次派發實質合規，僅 add 少量自有檔案）。單一樣本不足以推論
# 母體誤報率，證據強度有限；若未來累積更多樣本顯示全文逐字比對實際誤報率
# 偏低，應重新評估（此重新評估已獨立追蹤，待量測實際 prompt 分布後三方案
# 擇一）。基於目前僅有的證據，本版選擇片語比對而非逐字比對。
#
# 改採「兩類關鍵片語」比對：Category A、Category B 各自為 OR 清單，任一
# 未被否定語境包圍的片語命中即該類別視為已涵蓋。兩類別分開判定（而非合併
# 成單一清單），因為觀測案例證實 PM 改寫可能只涵蓋其中一類而遺漏另一類
# （涵蓋 A 缺 B），若合併判定會讓「只涵蓋 A」被誤判為完整合規，掩蓋
# PC-BAL-008 的實際暴露面。
#
# 漏報/誤報取捨（Layer 2 軟提示定位）：
#   - 片語清單涵蓋常見改寫變體（中英文皆有），降低誤報。
#   - 片語清單不做同義詞全集，容忍一定漏報——Layer 2 為軟提示不阻擋，漏報
#     成本僅為「少一次提醒」；清單過廣則誤報會在高頻派發場景（多數 prompt
#     涉及 commit）產生雜訊，使 PM 學會忽略提示（訊號劣化，
#     opinionated-default-design 原則之教訓）。
#   - 僅在 prompt 涉及 commit 相關工作時才檢查，避免對純讀取/分析派發
#     產生不相關提示。
# ----------------------------------------------------------------------------

# Dispatch-Mode: readonly 首行協議。
#
# 須保持一致：本常數須與
# .claude/skills/ticket/hooks/agent-dispatch-validation-hook.py 的同名協議
# 常數語意一致。目前無自動偵測兩處是否漂移，修改任一側須手動同步——完整
# 上移為共用模組（消除雙寫）為獨立追蹤議題（未在本次修正範圍）。
DISPATCH_MODE_PREFIX = "Dispatch-Mode:"
DISPATCH_MODE_READONLY_VALUE = "readonly"

# 唯讀派發代理人類型。
#
# 須保持一致：本清單須與
# .claude/skills/ticket/hooks/agent-ticket-validation-hook.py 的
# TICKET_EXEMPT_AGENT_TYPES 同步（此清單不會產生 git commit 副作用，檢查
# 制式句無意義）。目前無自動偵測兩清單是否漂移，修改任一側須手動同步——
# 完整上移為共用模組（消除三處唯讀判定副本）為獨立追蹤議題（未在本次修正
# 範圍）。
READONLY_AGENT_TYPES = frozenset({
    "Explore",
    "claude-code-guide",
    "general-purpose",
    "Plan",
    "feature-dev:code-explorer",
    "basil-writing-critic",
    "linux",
})

# 否定語境標記（中英文皆有），用於排除「片語雖命中但語意被否定」的假陽性
# （Category B 原僅純子字串比對，"不需要 git status" 會被誤判為已涵蓋；
# 同一問題套用於 Category A 亦一併防護）。
NEGATION_MARKERS = (
    "不需要", "不用", "無需", "不必", "免了",
    "skip", "don't", "do not", "no need", "not need",
)

# 否定語境掃描視窗（片語前後各 N 字元內出現否定詞即視為被否定）。窗寬為
# 經驗值，涵蓋「不需要 git status」「git status 不用做」等常見中文語序，
# 未做過大範圍分布驗證。
NEGATION_WINDOW_CHARS = 15

# 涉及 commit 意圖的標記。`git add` / `git push` 為強訊號直接視為涉及；
# 裸 `commit` 需另過否定/詞界檢查（見 `_has_commit_intent`），避免
# "do not commit"、"committee" 之類誤判。
COMMIT_STRONG_MARKERS = ("git add", "git push")
_COMMIT_WORD_RE = re.compile(r"\bcommit\b")

# Category A：precise git add（防廣域 add 併入他人變更）
#
# 僅收錄「正面表述要求精準做法」的片語，不收錄 "git add ." / "git add -A"
# 之類的子字串。原因：這兩個子字串在權威版中只出現於禁令位置
# （Forbidden: git add . / git add -A），單純子字串比對無法區分它在受測
# prompt 中是被禁止還是被要求——反向探針證實會讓「教 agent 做廣域 add」的
# 違規 prompt 因命中禁令詞面而誤判為 A 類已滿足，比不提示更誤導（PM 讀到
# 「缺 Category B」會誤以為 A 類無虞）。
#
# 取捨：改為僅正面片語計入命中，代價是「只寫禁令、不寫正面做法」的 prompt
# 會被判定缺 A 類——此非誤報，因為權威版本身就要求正面做法與禁令並存，
# 只寫禁令不算已涵蓋 A 類語意。
#
# 與 Category C 的分工邊界：早期版本曾把「bare commit no pathspec」的正面
# 片語（"bare commit" / "no pathspec" / "verified bare commit"）併入本類
# OR 清單——導致 prompt 只要命中 "exact files"（僅證明 add 精準）即可讓
# 整個 Category A 判定已涵蓋，完整貼上舊版含 pathspec commit 語法的四行
# 制式句因此會被靜默放行（"add 精準" 與 "commit 無 pathspec" 兩獨立證據
# 可互相頂替）。現已拆分：本類僅保留 add 精準片語，"bare commit" 等三個
# 片語移至獨立的 CATEGORY_C_PHRASES，兩類分開判定，缺一不足，見下方
# CATEGORY_C_PHRASES 註解。
CATEGORY_A_PHRASES = (
    "精準 staging",
    "精準的 staging",
    "exact files",
    "只實際修改的檔案",
    "只修改的檔案",
)

# Category B：git diff --cached --name-only / restore --staged 核對（防
# 共用 index 混入他人變更）
#
# 與 Category A 同樣僅收錄正面片語；額外套用 NEGATION_MARKERS 否定語境
# 排除，因為這些片語本身是中性動作描述，不像 Category A 的禁令子字串在
# 權威版中有固定的負面出處，需要在比對時動態判斷語境而非靜態排除詞面。
#
# "git diff --cached --name-only" 為權威版現行核對指令（取代舊版
# "git status"）；"git status" 仍保留為寬鬆別名——它並非禁用語法，只是
# 精確度較低的替代做法，保留不影響規則七的核心訴求（僅 Category A 的
# pathspec 才是危險語法需要移除，見上方 Category A 移除紀錄）。
CATEGORY_B_PHRASES = (
    "git diff --cached --name-only",
    "git status",
    "restore --staged",
)

# Category C：bare commit, no pathspec（防 pathspec 裸 commit 丟棄既有
# index、無條件從 working tree 重建）
#
# 獨立於 Category A（見上方 "與 Category C 的分工邊界" 段）：add 精準與
# commit 無 pathspec 是兩個各自成立的正面表述，即使 add 已精準，commit
# 行仍寫 pathspec 語法（`git commit -- <paths>`）會丟棄既有 index、無條件
# 從 working tree 重建指定路徑內容，等同清空 add 精準帶來的防護意義——
# 兩者缺一不足，不得互相頂替，故拆為獨立類別分開判定。
#
# 不收錄 "-- <paths>" / "git commit -- " 之類 pathspec 子字串本身：這兩個
# 子字串只出現於權威版的 Forbidden 子句中，與 Category A 排除 "git add ."
# 同型——單純子字串比對無法區分是被禁止還是被要求，僅收錄正面表述片語。
CATEGORY_C_PHRASES = (
    "bare commit",
    "no pathspec",
    "verified bare commit",
)

# 每個類別對應的具體後果，補在軟提示訊息中（原本只在本檔案頂部 docstring
# 說明根因，實際會被讀到的輸出裡沒有，讀者看不到「為什麼」）。
CATEGORY_CONSEQUENCES = {
    "A": "PC-092：廣域 `git add .`/`git add -A` 會併吞其他並行代理人尚未 commit 的變更",
    "B": "PC-BAL-008：跳過 `git diff --cached --name-only` 核對會被動吸收他人已 stage 在共用 index 的內容",
    "C": "規則七：pathspec 裸 commit 會丟棄既有 index、無條件從 working tree 重建，即使 add 已精準也會被清空防護意義",
}

CATEGORY_LABELS = {
    "A": "Category A（precise git add）",
    "B": "Category B（git diff --cached --name-only/restore --staged 核對）",
    "C": "Category C（bare commit, no pathspec）",
}

# 制式句每一行對應的類別標記（建議貼入內容隨 missing 收斂：在全文中標出
# 缺的是哪幾行，而非讓 PM 每次都要自行比對哪幾行分別對應哪個類別）。
#
# 內容對齊 agent-dispatch-template.md「精準 staging 制式句（權威版）」節
# 現行逐字文本（v1.29.0 起，本檔內嵌副本不改動該文件本體，僅供展示 +
# self-check 判準比對用）；`git diff --cached --name-only` 的兩處出現皆標
# B（核對步驟，非 add 步驟本身）。Forbidden 行同時禁止廣域 add（A）與
# pathspec commit（C）兩個獨立禁令，標記為 tuple ("A", "C") 而非拆成兩行
# 顯示——拆行會使建議複製貼入的文字與權威版原文分歧，改用資料結構支援
# 多類別標記以維持逐字一致；`_line_missing_codes()` 負責展開 tuple。
AUTHORITATIVE_LINES = (
    ("Use precise staging + verified bare commit only (no pathspec):", None),
    ('  git add {exact files}', "A"),
    ('  git diff --cached --name-only   # confirm index contains ONLY {exact files}', "B"),
    ('  git commit -m "..."             # bare commit; no -- <paths> / --only / -o / -a', "C"),
    ("Forbidden: git add . / git add -A; git commit -- <paths> / --only / -o / -a", ("A", "C")),
    ("Before commit: git diff --cached --name-only to check staged scope; git restore --staged <path> for any non-owned file", "B"),
)


def _has_negation_free_hit(prompt_lower: str, phrase: str) -> bool:
    """phrase 是否在 prompt_lower 中至少出現一次、且該次出現未被否定語境包圍。

    僅檢查片語「前方」視窗（與 `_has_commit_intent` 採同一方向限定，理由
    相同）：中文否定詞（不需要、不用、無需、跳過、免）與英文
    （no need to、skip、without）幾乎都前置於被否定對象，後置否定罕見。

    前後夾（雙向）視窗曾是本函式的第一版實作，但與 `_has_commit_intent`
    犯了同型錯誤——兩句相鄰時，後一句開頭的否定詞會落入前一句片語的
    掃描視窗，把不相關的否定語境錯配給前一句的片語（例：「用 path-limited
    commit，不需要 git status 核對」，「不需要」實際否定 git status，卻因
    落在 path-limited 後方 15 字元內，被雙向視窗誤判為也否定了
    path-limited）。這與 `_has_commit_intent` 原始的雙向視窗缺陷同形——
    同一 hook 內同一類錯誤重演兩次，教訓：新增任何「鄰近上下文」判定時，
    須逐一檢查所有呼叫該判定的位置，不能只修先發現的那一處。
    """
    search_from = 0
    while True:
        idx = prompt_lower.find(phrase, search_from)
        if idx == -1:
            return False
        ctx_start = max(0, idx - NEGATION_WINDOW_CHARS)
        preceding = prompt_lower[ctx_start:idx]
        if not any(neg in preceding for neg in NEGATION_MARKERS):
            return True
        search_from = idx + len(phrase)


def _category_has_positive_hit(prompt_lower: str, phrases) -> bool:
    """任一片語有未被否定語境包圍的出現，即視為該類別已涵蓋。"""
    return any(_has_negation_free_hit(prompt_lower, phrase) for phrase in phrases)


def _is_dispatch_mode_readonly(prompt: str) -> bool:
    """偵測 prompt 首行是否為 `Dispatch-Mode: readonly` 結構化宣告。

    與 agent-dispatch-validation-hook.py 判斷邏輯一致：首行 + 固定前綴 +
    固定值三條件 AND，非全文關鍵字掃描。
    """
    stripped = prompt.strip()
    if not stripped:
        return False
    first_line = stripped.splitlines()[0]
    if not first_line.startswith(DISPATCH_MODE_PREFIX):
        return False
    value = first_line[len(DISPATCH_MODE_PREFIX):].strip()
    return value.lower() == DISPATCH_MODE_READONLY_VALUE


def _has_commit_intent(prompt_lower: str) -> bool:
    """prompt 是否涉及 commit 相關工作（僅此時才需要檢查制式句）。

    `git add` / `git push` 為強訊號直接視為涉及。裸字 `commit` 需通過
    詞界（`\\bcommit\\b`，排除 "committee" 之類子字串誤判）與否定語境
    （排除 "do not commit"）雙重檢查。

    否定語境僅檢查 `commit` 詞前方（非前後夾）：中英文的「否定 commit 這個
    動作」語序固定在其前（"don't commit"、"不要 commit"），若改採前後夾
    檢查，會與句中其他無關動作的否定詞產生假陰性交叉污染——例如「commit
    後不需要 git status 檢查」的「不需要」是在否定 git status，不是在否定
    commit，但落在 commit 詞後方的掃描視窗內，前後夾檢查會誤判整句無 commit
    意圖而完全跳過制式句檢查（此為本函式與 Category B 否定語境檢查刻意採不同
    掃描方向的原因，兩者否定對象不同：本函式否定對象固定是 commit 動作本身，
    Category 判準否定對象是各別片語，語序無固定方向，故沿用前後夾檢查）。

    已知殘留誤報（接受，未修）：prompt 若僅在 ticket 標題或無關敘述中提到
    "commit" 一詞（如「修 commit message hook 的 bug」），仍會被判定涉及
    commit 意圖並進入片語檢查。Layer 2 軟提示成本低（僅多一次可能不相關的
    提示，不阻擋），與精確排除此類語意所需的額外複雜度（需要語意層面的
    intent 分類，非字面比對能可靠達成）不成比例，故此殘留誤報視為可接受
    取捨，不在本次修正範圍內收斂。
    """
    if any(marker in prompt_lower for marker in COMMIT_STRONG_MARKERS):
        return True
    for match in _COMMIT_WORD_RE.finditer(prompt_lower):
        start, _end = match.span()
        ctx_start = max(0, start - NEGATION_WINDOW_CHARS)
        preceding = prompt_lower[ctx_start:start]
        if not any(neg in preceding for neg in NEGATION_MARKERS):
            return True
    return False


def _missing_categories(prompt_lower: str) -> list:
    """回傳缺少的類別代碼清單（"A" / "B" / "C"），皆涵蓋則回傳空清單。

    三類各自獨立判定，缺一不足：任一類別的 OR 清單無片語命中即該類別
    列入 missing，不因其他類別已滿足而互相頂替。
    """
    missing = []
    if not _category_has_positive_hit(prompt_lower, CATEGORY_A_PHRASES):
        missing.append("A")
    if not _category_has_positive_hit(prompt_lower, CATEGORY_B_PHRASES):
        missing.append("B")
    if not _category_has_positive_hit(prompt_lower, CATEGORY_C_PHRASES):
        missing.append("C")
    return missing


def _line_missing_codes(code, missing: list) -> list:
    """展開 AUTHORITATIVE_LINES 一行的類別標記（None / 單一代碼 / tuple），
    回傳其中目前缺失的代碼清單（保持宣告順序）。"""
    if code is None:
        return []
    codes = code if isinstance(code, tuple) else (code,)
    return [c for c in codes if c in missing]


def _build_soft_hint(missing: list) -> str:
    """依缺少的類別動態組出軟提示：標題只列缺的類別 + 各自後果一行；
    貼入區塊保留完整制式句（三類別互為前提，仍需完整制式句），但在每行
    標註該行對應哪個/哪些類別，缺的類別行加註提醒。
    """
    header_lines = ["提示：Agent/Task prompt 涉及 commit 但缺精準 staging 制式句片語："]
    for code in missing:
        header_lines.append(f"  - 缺 {CATEGORY_LABELS[code]}：{CATEGORY_CONSEQUENCES[code]}")

    snippet_lines = ["", "制式句權威版：.claude/references/agent-dispatch-template.md",
                      "  「精準 staging 制式句（權威版）」節", "", "建議複製貼入 prompt："]
    for text, code in AUTHORITATIVE_LINES:
        hit_missing = _line_missing_codes(code, missing)
        if hit_missing:
            tag = "/".join(f"Category {c}" for c in hit_missing)
            snippet_lines.append(f"  {text}    <-- 缺 {tag}")
        else:
            snippet_lines.append(f"  {text}")

    footer_lines = ["", "本提示為 Layer 2 軟提示，不阻擋派發。"]
    return "\n".join(header_lines + snippet_lines + footer_lines) + "\n"


def _self_check_soft_hint_covers_categories() -> None:
    """啟動時 self-check：AUTHORITATIVE_LINES 內嵌的權威句副本必須仍命中
    Category A、B、C 判準，防止未來編輯 AUTHORITATIVE_LINES 時措辭漂移
    導致範例本身也被判定缺句（本檔內嵌的權威句副本是第三份硬編副本，
    需要防措辭漂移的斷言）。
    """
    sample = "\n".join(text for text, _ in AUTHORITATIVE_LINES).lower()
    assert _category_has_positive_hit(sample, CATEGORY_A_PHRASES), (
        "AUTHORITATIVE_LINES 內嵌權威句副本未命中 Category A 判準，措辭已漂移"
    )
    assert _category_has_positive_hit(sample, CATEGORY_B_PHRASES), (
        "AUTHORITATIVE_LINES 內嵌權威句副本未命中 Category B 判準，措辭已漂移"
    )
    assert _category_has_positive_hit(sample, CATEGORY_C_PHRASES), (
        "AUTHORITATIVE_LINES 內嵌權威句副本未命中 Category C 判準，措辭已漂移"
    )


_self_check_soft_hint_covers_categories()


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("dispatch-staging-phrase-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.info("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Agent", "Task"):
        return 0

    raw_input = input_data.get("tool_input") or "{}"
    if isinstance(raw_input, str):
        try:
            tool_input = json.loads(raw_input)
        except json.JSONDecodeError:
            logger.info("tool_input JSON 解析失敗，放行")
            return 0
    else:
        tool_input = raw_input

    prompt = tool_input.get("prompt", "")
    if not prompt:
        return 0

    # 豁免 1：worktree 隔離派發（isolation == "worktree"）
    if tool_input.get("isolation", "") == "worktree":
        logger.debug("放行：isolation=worktree 豁免（跨 repo 邊界，不共用主 repo 工作區 index）")
        return 0

    # 豁免 2：Dispatch-Mode: readonly 首行宣告
    if _is_dispatch_mode_readonly(prompt):
        logger.debug("放行：Dispatch-Mode: readonly 豁免")
        return 0

    # 豁免 3：subagent_type / name 屬唯讀派發代理人類型
    subagent_type = tool_input.get("subagent_type") or tool_input.get("name") or ""
    if subagent_type in READONLY_AGENT_TYPES:
        logger.debug("放行：subagent_type=%s 屬唯讀派發類型豁免", subagent_type)
        return 0

    prompt_lower = prompt.lower()

    # 豁免 4：prompt 未涉及 commit 相關工作，檢查制式句無意義
    if not _has_commit_intent(prompt_lower):
        logger.debug("放行：prompt 未偵測到 commit 意圖標記，跳過制式句檢查")
        return 0

    missing = _missing_categories(prompt_lower)
    if missing:
        hint = _build_soft_hint(missing)
        print(hint, file=sys.stderr)
        logger.info(
            "軟提示：prompt 涉及 commit 但缺制式句片語 missing=%s subagent_type=%s",
            missing, subagent_type,
        )
        return 0

    logger.debug("通過：prompt 已涵蓋 Category A/B/C 制式句片語")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "dispatch-staging-phrase-guard"))
