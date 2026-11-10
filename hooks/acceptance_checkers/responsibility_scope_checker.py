"""
Responsibility Scope Checker - Ticket 職責邊界判準（0.2.1-W3-052.1 由 C3 移植）

移植自 `.claude/lib/ticket_quality/detectors.py` 的 C3 Ambiguous Responsibility
檢測。原始四項判準（層級標示 / 職責描述清晰度 / 檔案範圍對齊層級 / 驗收條件對齊
層級關鍵詞）全數依賴 `[Layer X]` / `Layer X:` 標示格式，該格式在現行 154+ 既有
ticket 語料普及度 0（父票 Problem Analysis 盤點結論），無法直接沿用。

重寫依據（實測，見 0.2.1-W3-052.1 Test Results）：
1. **職責描述清晰度**（原 BR-C3.2，連接詞/收斂關鍵詞啟發式）：改讀 frontmatter
   `why` 欄位後實測 unclear 率 53%（184/347），改讀 `what` 欄位在
   connectors>=1 門檻下 false-positive 24%、connectors>=2 門檻下偵測率 0%。
   兩者皆無可用中間值 —— 本專案 `why` 欄位慣例為敘事型根因論證而非宣告式範圍
   聲明，原啟發式的「連接詞多寡」假設不成立。**結論：不移植**，此維度風險
   高於收益（如需了解職責描述是否存在，five_w1h_checker 已檢查 why/what
   非空，只是不含「清晰度」語意，本檢查器不重複造輪）。
2. **檔案範圍明確性**（原 BR-C3.3，檔案是否屬宣告層級）：宣告層級（`[Layer X]`）
   已不存在；改以「`where.files` 涵蓋的頂層路徑 domain 數」取代「是否對齊單一
   宣告層級」，語意由「對齊某個宣告值」轉為「範圍是否分散到過多互不相關的
   domain」，兩者共同意圖皆為偵測職責邊界擴散。閾值沿用
   `.claude/rules/core/cognitive-load.md`「任務拆分閾值」表既有 SSOT：
   「跨架構層級數 > 2 層：必須拆分」。實測 domain 數分佈 1:221 / 2:35 / 3:4
   （n=260 IMP/ADJ），> 2 門檻命中率 1.5%，屬合理的低雜訊警告範圍。
3. **驗收條件對齊層級關鍵詞**（原 BR-C3.4）：依賴同一組已棄用的層級關鍵詞表
   （UI/Controller/UseCase/Event/Domain），且該表格為 Flutter 5 層架構特化，
   不適用本框架泛用 ticket（多數為 `.claude/` 框架基礎設施票）。**不移植**。

Type-aware：與 `god_ticket_scale_checker` 一致，ANA/DOC 豁免（沿用
ticket-body-schema.md「Type-aware Quality Gate」既有慣例）。

`where.files` 讀取正規化（list vs 換行字串雙型別容忍）與 `god_ticket_scale_checker`
共用 `ticket_parser.extract_where_files`，見該函式 docstring 說明 runtime hook
輕量解析器的已知限制。
"""

from typing import List

from acceptance_checkers.ticket_parser import extract_where_files

# SSOT: .claude/rules/core/cognitive-load.md 任務拆分閾值表「跨架構層級數 > 2 層：必須拆分」
_DOMAIN_COUNT_THRESHOLD = 2

_EXEMPT_TYPES = {"ANA", "DOC"}


def check_file_scope_diversity(frontmatter: dict, logger) -> List[str]:
    """
    檢查 ticket 的 `where.files` 是否涵蓋過多互不相關的頂層路徑 domain
    （C3 職責邊界判準移植，以 domain 分散度取代已棄用的層級對齊判準）。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        List[str] - 違規項目清單（空清單表示通過）。超標時內容為
        `["domain_count:{實際數}>{閾值}（domains: d1, d2, ...）"]`。
    """
    ticket_type = (frontmatter.get("type") or "").upper()
    if ticket_type in _EXEMPT_TYPES:
        logger.info(f"ticket type={ticket_type} 豁免職責邊界檢查（ANA/DOC 不適用）")
        return []

    domains = _extract_domains(frontmatter, logger)
    domain_count = len(domains)

    if domain_count > _DOMAIN_COUNT_THRESHOLD:
        domain_list = ", ".join(sorted(domains))
        violation = f"domain_count:{domain_count}>{_DOMAIN_COUNT_THRESHOLD}（domains: {domain_list}）"
        logger.info(f"職責邊界檢查未通過: {violation}")
        return [violation]

    logger.info(f"職責邊界檢查通過（domain 數 {domain_count} <= {_DOMAIN_COUNT_THRESHOLD}）")
    return []


def _extract_domains(frontmatter: dict, logger) -> set:
    """從 frontmatter.where.files 萃取頂層路徑 domain 集合。

    `.claude/` 下取次一層作為 domain（如 `.claude/hooks`、`.claude/pm-rules`），
    避免同一子系統內的正常耦合（如 hook 本體 + 對應測試同屬
    `.claude/hooks`）被誤判為跨 domain。其餘路徑取頂層目錄名（如 `lib`、
    `test`、`docs`）。
    """
    valid_files = extract_where_files(frontmatter, logger)
    domains = set()
    for stripped in valid_files:
        domain = _domain_of(stripped)
        if domain:
            domains.add(domain)
    return domains


def _domain_of(path: str) -> str:
    """單一路徑的 domain 分類（見 `_extract_domains` docstring 分類規則）。

    僅剝除字面 `./` 前綴（可重複，如 `././foo`），不可用 `str.lstrip("./")`
    ——後者以字元集合逐字剝除，會把 `.claude/...` 的開頭 `.` 誤剝成
    `claude/...`（單元測試曾實測命中此問題，見對應測試檔）。
    """
    p = path
    while p.startswith("./"):
        p = p[2:]
    if not p:
        return ""
    parts = p.split("/")
    if parts[0] == ".claude" and len(parts) > 1:
        return f".claude/{parts[1]}"
    return parts[0]
