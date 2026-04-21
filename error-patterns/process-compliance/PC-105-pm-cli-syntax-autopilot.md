# PC-105: PM 對 SKILL CLI 語法的 autopilot 假設

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-105 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-04-21（W17-036 session 連續多次觸發 SKILL 引導品質回饋 hook） |
| 姊妹模式 | PC-066（decision-quality autopilot）— 本模式為「CLI 語法領域的 autopilot」專項 |

---

## 症狀

同一 session 內，PM 對 SKILL CLI 語法反覆使用「看似合理」但**未實際查閱**的參數格式，撞到 hook 「SKILL 引導品質回饋」或 CLI 語法錯誤後，繼續嘗試類似變體，而非停下來 `--help` 查詢正確語法。

**典型訊號**：

- 同一 session 出現 ≥ 2 次 `unrecognized arguments` / `invalid choice` / `error: argument` 類 CLI 錯誤
- Hook 「SKILL 引導品質回饋」重複觸發
- PM 在錯誤後嘗試「相似變體」（換 flag 名、換位置）而非先 `--help`

---

## 案例（W17-036 session 實證）

| # | 嘗試命令 | 錯誤 | 根因 |
|---|---------|------|------|
| 1 | `ticket track create --help` | `invalid choice: 'create'` | PM 將 create 放在 track 下；應為 `ticket create` |
| 2 | `ticket track append-log <id> --section "X" --content "..."` | `unrecognized arguments: --content` | PM 假設 `--content` 是 flag；實際 content 是位置參數 |
| 3 | `ticket track claim <id> --agent rosemary` | `unrecognized arguments: --agent rosemary` | PM 假設 claim 可指定 agent；實際無此參數，應用 `set-who` 補 |

**共通模式**：PM 依「主觀直覺」使用參數，未主動 `ticket <cmd> --help` 或 `ticket --help` 查閱。

---

## 根本原因

### 已驗證事實

1. Hook `skill-cli-error-feedback-hook.py` 已在每次 CLI 錯誤後輸出「SKILL 引導品質回饋」提醒
2. Hook 訊息包含「查閱完整語法：執行 `ticket --help`」明確指引
3. PM 看到 hook 輸出後，未執行 --help 查詢，而是直接嘗試「相似變體」

### 真根因

**PM 工作記憶將「看似合理語法」優先於「查詢文件」**：

- 壓力下（多 ticket 並行、context 已滿）PM 傾向依賴記憶而非查詢
- 類比鄰近 CLI（argparse flag 慣例如 `--content`）讓「看似合理」比「文件真實」更容易被選擇
- Hook 回饋未強制打斷 → PM 可跳過提醒繼續嘗試

這與 PC-066（decision-quality autopilot）同構：**自律提醒在最需要它的場景負相關於被採納率**。

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成問題 |
|---------|--------------|
| 「我記得 X 是 flag 名」 | 記憶未必對齊 CLI 實際演化；每次 CLI 升級記憶都可能過時 |
| 「試試看 --Y 應該也行」 | 二次嘗試仍是 autopilot，未切換查詢模式 |
| 「Hook 只是警告，我可以繼續」 | Hook 無強制攔截時訊號被滑過（warning fatigue） |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 即時反射 | 看到 CLI 錯誤後 **第一反應是 --help**，禁止直接二次嘗試 | 規則層（本 PC） |
| SKILL.md 覆蓋 | 補完常見誤用（append-log 位置參數、create 為頂層命令、claim 無 --agent） | 待追蹤（可與 W17-008 相關項合併） |
| Hook 強化 | 連續 ≥ 2 次同類 CLI 錯誤時升級為 block（非 warning） | 待評估 |

---

## 教訓

1. **CLI 語法是可查詢資訊，不是可推論資訊**：每個 `--help` 呼叫成本約 1 次 Bash，遠低於連續 3 次錯誤嘗試的成本。
2. **autopilot 的對稱性**：PC-066 談決策，PC-105 談語法，本質都是「壓力下自律失效」。防護方向相似（強制查詢前置 + Hook 升級）。
3. **Hook warning 必須能升級為 block**：warning fatigue 讓訊號被滑過；連續同類錯誤應升級阻斷。

---

## 檢查清單（PM 執行 CLI 命令前）

- [ ] 本 session 是否已看過此 CLI 的 `--help` 輸出？
- [ ] 若未，是否先執行 `<cmd> --help`？
- [ ] 若已，語法是否精確對齊（位置參數 vs flag）？
- [ ] 若 CLI 錯誤出現，是否先 `--help` 再重試，而非直接嘗試變體？

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-066-decision-quality-autopilot.md` — 姊妹模式（決策領域的 autopilot）
- `.claude/hooks/skill-cli-error-feedback-hook.py` — 現有 warning hook
- `.claude/skills/ticket/SKILL.md` — 需補完常見誤用章節

---

**Last Updated**: 2026-04-21
**Version**: 1.0.0 — W17-036 session 連續三次 CLI 誤用觸發，提煉為通用模式
**Source**: PM 自我觀察（同一 session 多次撞 skill-cli-error-feedback-hook 後，發現「相似變體重試」為共通行為）
