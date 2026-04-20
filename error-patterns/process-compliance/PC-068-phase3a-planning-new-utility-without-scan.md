# PC-068: Phase 3a 規劃新建既有 utility 而未先掃描重用

**觸發日期**: 2026-04-15
**類型**: Process Compliance
**嚴重度**: 高（DRY 違反會放大到 Phase 3b 實作，造成多個並存的重複實作）

---

## 症狀

TDD Phase 3a（pepper-test-implementer）在「模組結構建議」章節決策「自寫小型 utility 模組」時，未先執行 grep/glob 確認 `lib/`、`hook_utils/` 或既有 skills 中是否有可重用的實作。決策理由若在本專案現有 utility 已滿足時，自寫方案不成立。

## 典型表徵

- Phase 3a §模組結構建議 出現「自寫 lib/xxx.py」「避免 subprocess 延遲」「避免循環依賴」等理由
- 多視角審查（特別是語言代理人如 thyme-python-developer、code-explorer）發現同目錄或相鄰模組已有等價實作
- Phase 3b 代理人若按原計劃實作，會建立 N+1 個功能重疊的 utility

## 發現管道

通常由以下其中之一發現：

- Phase 3b 前多視角審查（parallel-evaluation 情境 G）
- 實作期間 agent 發現 import path 已存在等價工具
- Code review 中看到同名函式並存

不主動檢查就會直接進入 Phase 3b 實作，DRY 違反成為既成事實。

## 結構性本質

此錯誤模式的核心機制與語言/框架/專案無關：

> 「規劃決策包含『新建工具』時，未執行存在性驗證即進入實作排程。」

跨專案可重現場景：

- Flutter 專案的 Phase 3a 規劃「自寫 JSON serializer helper」而未查 project 內既有 `lib/core/json_utils.dart`
- Go 專案的 Phase 3a 規劃「自寫 log wrapper」而未查 `internal/log/`
- Python 專案的 Phase 3a 規劃「自寫 config loader」而未查 `hooks/hook_utils/`

## 根本原因

1. **規劃專注於邏輯**：pepper 模式聚焦於「這個功能怎麼做」而非「是否已有人做過」
2. **決策理由未交叉驗證**：「避免循環依賴」「無 subprocess」等理由聽起來合理，但未與實際既有模組的特性比對
3. **Phase 3a 缺乏強制的 existence-check 步驟**：流程沒有規定「規劃新建 utility 前必須執行 grep/glob」
4. **語言代理人未參與 Phase 3a**：若只 pepper 單視角規劃，無人從語言慣例視角質疑「真的需要自寫嗎？」

## 防護措施

### 措施 1：Phase 3a 產出規格新增「既有工具掃描」必填章節

規劃任何新建 utility（函式、模組、class）前，必須：

```bash
# 在「模組結構建議」章節前先執行
grep -rn "def parse_\|def read_\|def load_\|class TicketData" <lang-root>/lib/ <lang-root>/utils/ 2>&1 | head -30
# 或依專案結構調整路徑
```

並在 Phase 3a Solution 中列「既有工具掃描結果」小節，說明：
- 搜尋範圍
- 找到的候選工具與其能力
- 若決定不用某候選，說明具體阻礙（接口不符 / 依賴衝突 / 維護狀態）

### 措施 2：Phase 3b 前多視角審查強制納入語言代理人

對 Phase 3a 產出的規劃，必須派發對應語言代理人（parsley-flutter-developer / thyme-python-developer / fennel-go-developer 等）作為審查委員。語言代理人能即刻識別「這個專案已經有 X」的情境。

### 措施 3：Worth-It Filter 將「規劃新建既有工具」列為 HIGH 嚴重度

任何審查發現「Phase 3a 規劃新建的 utility 已在既有 codebase 存在」，一律升級為 HIGH，強制要求修正 Phase 3a 決策後才能進入 Phase 3b。

## 類似案例

- **0.18.0-W10-009 Phase 3a**：規劃 `.claude/hooks/lib/ticket_frontmatter.py` 自寫 parser，但 hooks 目錄已存在 `hook_utils/hook_ticket.py:parse_ticket_frontmatter()`（10+ hooks 使用）和 `lib/frontmatter_parser.py`（含 TicketData dataclass）。三委員（linux + thyme-python + code-explorer）審查識破，Context Bundle 強制修正為「重用 hook_utils」。

## 相關文件

- `.claude/references/quality-common.md` §1.4 DRY 原則
- `.claude/skills/parallel-evaluation/SKILL.md` 情境 G 系統設計
- `.claude/methodologies/multi-perspective-analysis-methodology.md` 語言代理人加入規則

---

**Last Updated**: 2026-04-15
**Version**: 1.0.0 — 初始建立
