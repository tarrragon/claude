# PC-065: PM 並行派發多代理人時 prompt 模板遺漏 Ticket ID 格式

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-065 |
| 類別 | process-compliance |
| 風險等級 | 低 |
| 相關 Hook | agent-ticket-validation-hook |

### 症狀

1. PM 一次並行派發 2+ 個代理人（如 Phase 4 三視角評估、並行審查）
2. 每個 prompt 使用類似模板，但開頭皆未含 `Ticket: {id}` / `#Ticket-{id}` / `[Ticket {id}]` 格式
3. agent-ticket-validation-hook 全部 block，訊息：「派發任務必須引用有效的 Ticket ID」
4. PM 需逐一修改每個 prompt 的開頭重新派發
5. 失敗的 Hook 觸發會在 `.claude/hook-logs/` 累積 N 筆錯誤記錄（N = 並行派發數）

### 與「僅文內提及 Ticket ID」的區別

| 情境 | Hook 行為 | 原因 |
|------|----------|------|
| `Ticket: 0.18.0-W5-042\n你是...` | 通過 | 符合合法格式 |
| `你是 [Ticket 0.18.0-W5-042] 的...` | 通過 | 方括號格式合法 |
| `本次 W5-042 的 Phase 4 評估...` | block | 僅內文提及，非明確格式 |
| `[Ticket 0.18.0-W5-042] 實作了...` | 通過 | 方括號格式合法 |

### 根本原因

1. **Prompt 模板起草順序慣性**
   - PM 草擬 prompt 時先聚焦於任務敘述、評估重點、產出要求
   - Ticket ID 格式是機器可解析的元資料，易被當成「事後補上」反而遺漏

2. **並行派發的放大效應**
   - 若單一派發遺漏格式，受害 1 次
   - 並行派發時若模板共用錯誤結構，N 個代理人全數被 block
   - Hook error 記錄會同時累積 N 筆

3. **Hook 格式嚴格度**（設計使然，非 bug）
   - agent-ticket-validation-hook 為確保機器可解析，只接受三種明確格式
   - 對「內文提及」寬容會降低 Hook 防護效力

### 常見陷阱模式

| 陷阱表述 | 為何仍構成違規 |
|---------|--------------|
| 「我 prompt 內文都有提到 W5-042」 | Hook 要求三種合法格式之一，非文字出現即可 |
| 「只派發一個代理人不算並行不會放大」 | 放大效應只影響損害規模，單一派發一樣會 block |
| 「三次重試才成功是正常摩擦」 | 可透過固定模板第一行避免重試，屬可預防成本 |

### 防護措施

| 層級 | 措施 | 適用時機 |
|------|------|---------|
| Prompt 模板 | **第一行永遠是 `Ticket: {id}`**，任務敘述從第二行起 | 每次派發 |
| 並行派發前 | 自我檢查每個 prompt 第一行是否含 Ticket 格式 | 2+ 代理人同批派發 |
| 重試時 | 若首批被 block，確認所有並行 prompt 一起修正（避免只修一個又派） | Hook block 後 |
| 自動防護 | agent-ticket-validation-hook 已存在 | 框架已提供 |

### 檢查清單（派發 Agent 前自我檢查）

- [ ] 準備派發的每個 prompt 第一行是否為 `Ticket: {id}` / `#Ticket-{id}` / `[Ticket {id}]` 其中一種？
- [ ] 並行派發時，是否每個 prompt 都獨立含 Ticket ID 格式（非只第一個有）？
- [ ] 若 prompt 內文有提到「本 Ticket」「本次 W5-xxx」等表述，是否也另外在開頭加了合法格式？

### 教訓

Hook 的格式嚴格度是為確保機器可解析與防護效力，**PM 必須將「Ticket ID 格式開頭」建立為 prompt 模板的慣例**，而非任務敘述後再補。

並行派發時，若採用共用模板結構，錯誤會線性放大：一次疏忽 = N 個 Hook error。固定模板第一行格式可一次防護所有並行派發場景。

### 象限歸類

本模式的防護屬**摩擦力管理 A 象限（降低摩擦）**：透過固定 prompt 模板前綴避免 Hook block 重試迴圈，降低 PM 派發工作的往返成本。代價（模板養成）低，收益（避免 N 次 Hook block + hook-logs 污染）高。

---

## 相關文件

- `.claude/hooks/agent-ticket-validation-hook.py` — 執行 Hook 的檢查邏輯
- `.claude/pm-rules/parallel-dispatch.md` — 並行派發流程
- `.claude/methodologies/friction-management-methodology.md` — 摩擦力管理方法論（A 象限）
