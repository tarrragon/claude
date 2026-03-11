# 通用品質基線 — 詳細指引和範例

本文件包含 quality-common.md 的操作指引、程式碼範例和詳細檢查清單。

> 核心規則定義：.claude/rules/core/quality-common.md

---

## 1.2 函式設計 — Guard Clause 範例

### 正確做法：提前返回

```python
# 正確：提前返回
if not user: return
if not user.is_admin: return
if not has_permission: return
do_something()
```

### 錯誤做法：深層巢狀

```python
# 錯誤：深層巢狀
if user:
    if user.is_admin:
        if has_permission:
            do_something()
```

---

## 1.2.1 作用域變更防護 — 詳細檢查清單

### 場景範例

**錯誤案例（IMP-003）**：

```python
# v1：logger 在模組級定義
logger = setup_logger(__name__)

def create_ticket():
    logger.info("Creating...")

def validate_input():
    logger.warning("Invalid input")

# 重構：logger 移至 main()
def main():
    logger = setup_logger(__name__)
    # 但 validate_input() 仍依賴全域 logger → NameError
```

### 完整檢查清單（修改作用域前必須完成）

1. **列出所有引用該變數的函式**
   ```bash
   grep -rn "logger" src/
   # 找出所有使用 logger 的地方
   ```

2. **逐一檢查每個函式**
   - 透過參數接收？
   - 依賴全域？
   - 由類別管理？

3. **對於依賴全域的函式，新增參數**
   ```python
   # 之前
   def validate_input(data):
       logger.warning("Invalid")

   # 之後
   def validate_input(data, logger):
       logger.warning("Invalid")
   ```

4. **修改所有呼叫端**
   ```python
   # 之前
   validate_input(user_data)

   # 之後
   validate_input(user_data, logger)
   ```

### 驗證優先級說明

| 方式 | 優勢 | 劣勢 |
|------|------|------|
| AST 分析 | 能精確定位作用域邊界；適合大規模重構 | 實作複雜 |
| 實際執行 | 最直接的反饋；確認真實問題 | 需測試覆蓋 |
| py_compile | 快速 | 無法偵測作用域問題 |

**推薦組合**：AST 分析 + 實際執行

---

## 1.2.2 欄位格式溯源 — 詳細檢查清單

### 場景範例

**錯誤案例（IMP-011）**：

```python
# 消費端假設 direction 是簡單字串
def should_preserve(direction: str) -> bool:
    return direction in {"to-sibling", "to-parent", "to-child"}

# 但生產端實際輸出格式帶後綴
# handoff.py:
handoff["direction"] = f"to-sibling:{target_id}"

# 結果：should_preserve("to-sibling:W3-002") → False（誤判）
```

### 完整檢查清單（寫修復程式碼前必須完成）

1. **列出修復程式碼讀取的所有欄位**
   - 從程式碼審閱識別
   - 包括直接讀取和間接使用

2. **找到每個欄位的生產者**
   ```bash
   grep -rn 'direction\s*=' src/
   # 找出所有賦值位置
   ```

3. **確認欄位的完整格式**
   - 閱讀生產者程式碼
   - 檢查所有可能的變體
   - 記錄所有分支邏輯

4. **在程式碼註解中記錄格式規格**
   ```python
   def should_preserve(direction: str) -> bool:
       """判斷是否保留。

       direction 格式（來源：handoff.py._resolve_direction_from_args）：
       - "to-parent"（無後綴）
       - "to-sibling:{target_id}"（帶目標 ID）
       - "context-refresh"（非任務鏈）
       """
   ```

5. **測試案例覆蓋所有格式變體**
   ```python
   def test_should_preserve():
       assert should_preserve("to-parent")  # 無後綴
       assert should_preserve("to-sibling:W3-002")  # 有後綴
       assert should_preserve("context-refresh")  # 特殊格式
       assert not should_preserve("unknown")  # 不符合
   ```

### 正確做法（前綴匹配）

```python
def should_preserve(direction: str) -> bool:
    """判斷是否保留。

    direction 格式（來源：handoff.py._resolve_direction_from_args）：
    - "to-parent"（無後綴）
    - "to-sibling:{target_id}"（帶目標 ID）
    - "context-refresh"（非任務鏈）
    """
    # 使用前綴匹配，容許後綴變化
    direction_type = direction.split(":")[0]
    return direction_type in {"to-sibling", "to-parent", "to-child"}
```

---

## 1.2.3 破壞性操作設計防護 — 詳細檢查清單

### 場景範例

**錯誤案例（IMP-010）**：

```python
# 簡單的 GC 邏輯
def gc_stale_files(project_root):
    for file_path in pending_files:
        ticket_id = extract_ticket_id(file_path)
        if is_ticket_completed(project_root, ticket_id, logger):
            file_path.unlink()  # 一律刪除

# 但沒考慮 handoff 的 direction 欄位
# 對於任務鏈 handoff（"to-sibling:xxx"），
# completed 是正常狀態，不應刪除
```

### 完整設計檢查清單（寫破壞性操作程式碼前必須完成）

1. **刪除條件依賴的狀態值，在所有上下文中語義是否一致？**
   - 在不同場景下，同一狀態值是否有不同含義？
   - 範例：completed 在 Ticket 和 handoff 中語義不同

2. **是否需要額外欄位（上下文）才能做出正確的刪除決策？**
   - 需要什麼額外資訊？
   - 這些資訊是否可用？

3. **清理操作是否覆蓋所有儲存層？**
   - 快取層
   - 註冊層（已知實例列表）
   - 目錄層
   - 配置層

4. **不確定時，預設行為是什麼？（必須為保留）**
   - 刪除是破壞性的、不可逆的
   - 保守起見，不確定時必須保留

### 正確做法（結合上下文）

```python
def gc_stale_files(project_root, logger):
    for file_path in pending_files:
        ticket_id = extract_ticket_id(file_path)
        if is_ticket_completed(project_root, ticket_id, logger):
            # 需要檢查 handoff 的 direction
            handoff_data = load_handoff(file_path)
            direction = handoff_data.get("direction", "")
            direction_type = direction.split(":")[0]

            if direction_type in ("to-sibling", "to-parent", "to-child"):
                # 任務鏈 handoff，completed 是預期狀態，保留
                logger.info(f"保留 {direction_type} handoff: {ticket_id}")
                continue

            # 非任務鏈類型，completed 表示 stale，可清理
            file_path.unlink()
            logger.info(f"清理過期檔案: {ticket_id}")
```

---

## 1.2.4 未使用程式碼處理 — 詳細檢查清單

### 場景範例

**問題案例（IMP-013）**：

```python
# Phase 4 發現未使用的參數
class SessionManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger  # ← 從未被方法使用

    def get_session(self, session_id):
        # 只使用 config，從未使用 self.logger
        return self.config.sessions.get(session_id)
```

### 完整檢查清單（發現 unused code 時必須完成）

1. **追溯原始目的：為什麼存在？**
   ```bash
   git log -p -- SessionManager.py | grep -A5 -B5 "logger"
   git blame SessionManager.py | grep logger
   ```

2. **判斷類型**
   - 曾經有用但不再需要？
   - 設計意圖未實現？
   - 對照需求文件和設計規格

3. **根據判斷結果處理**

   **情況 A：曾經有用但不再需要**
   ```python
   # 記錄移除理由，安全移除
   # worklog 記錄：
   # - 移除 SessionManager.logger 參數
   # - 理由：W34-010 重構後 logging 改由 session layer 統一管理
   # - 確認：所有呼叫端都不依賴此參數
   ```

   **情況 B：設計意圖未實現**
   ```python
   # 補上實作
   # worklog 記錄：
   # - 發現設計意圖（在 logger 中記錄 session 操作）未實現
   # - 建立 Ticket 追蹤：修復程式碼實作缺失的 logger 呼叫
   # - 禁止直接刪除未使用參數
   ```

4. **記錄到工作日誌**
   ```markdown
   ## Phase 4 發現

   ### 未使用程式碼 - SessionManager.logger

   - 發現時機：Phase 4 重構評估，function 引用掃描
   - 原始設計意圖：記錄 session 操作日誌
   - 現狀：無呼叫點
   - 判斷：設計意圖未實現
   - 行動：建立 Ticket 實作 logger 呼叫，不直接刪除參數
   ```

### 禁止行為

| 禁止 | 正確做法 |
|------|---------|
| `# TODO: 移除未使用 logger` | 建立 Ticket 追蹤，確認實作意圖 |
| 依賴 linter 自動移除 | 人工審查，理解原始設計 |
| 即刻刪除 unused code | 先記錄原始意圖，再建立追蹤 |

---

## 1.3.1 訊息常數管理 — 目錄結構組織

### 組織方式

```
module/
├── commands/
│   ├── __init__.py
│   ├── create.py          # 使用 CreateMessages
│   ├── track.py           # 使用 TrackMessages
│   └── create_messages.py # CreateMessages 定義
│
└── lib/
    ├── __init__.py
    ├── messages.py         # 共用訊息（所有模組可用）
    ├── commands_messages.py # 命令專用訊息基類
    └── error_messages.py   # 錯誤訊息集合
```

### 定義範例

```python
# ticket/commands/create_messages.py
class CreateMessages:
    SUCCESS = "Ticket {ticket_id} 建立成功"
    MISSING_TITLE = "缺少必填欄位：title"
    TITLE_TOO_LONG = "title 長度超過 {max_length} 字元（目前 {current_length}）"
    INVALID_TYPE = "type 必須為 {valid_types} 之一，接收 '{received}'"

# 使用
print(CreateMessages.SUCCESS.format(ticket_id=tid))
```

### 命名規範

| 訊息類型 | 命名 | 範例 |
|---------|------|------|
| 成功訊息 | SUCCESS / `{ACTION}_SUCCESS` | `SUCCESS`, `CREATE_SUCCESS` |
| 錯誤訊息 | `MISSING_{FIELD}` / `INVALID_{FIELD}` | `MISSING_TITLE`, `INVALID_TYPE` |
| 提示訊息 | `{ACTION}_PROMPT` | `ENTER_NAME_PROMPT` |
| 驗證錯誤 | `VALIDATION_{ERROR_TYPE}` | `VALIDATION_EMAIL_FORMAT` |

### 允許的例外

| 例外 | 原因 | 範例 |
|------|------|------|
| 日誌訊息 | 供開發者閱讀 | `logger.info("Session started")` |
| 測試斷言 | 測試專用 | `assert status == "pending"` |
| 技術標識 | 程式碼內部 | `_FORMAT_PREFIX = "TC"` |

---

## 1.6 註解標準 — 詳細指引

### 標準格式

```python
def calculate_discount_price(base_price: float, user_tier: str) -> float:
    """計算折扣價格。

    需求：UC-042 按用戶等級進行折扣

    用戶等級對應折扣率：
    - gold: 20%
    - silver: 10%
    - standard: 0%

    約束：
    - base_price 必須 >= 0
    - 折扣後價格 >= 0
    - 若等級不存在，使用 standard 等級

    維護指引：
    - 若要新增等級，需同時更新 UserTierEnum
    - 折扣率變更需通知財務團隊（見 SR-2024-001）
    """
    tier_discounts = {"gold": 0.2, "silver": 0.1, "standard": 0.0}
    discount_rate = tier_discounts.get(user_tier, 0.0)
    return base_price * (1 - discount_rate)
```

### 各程式碼類型的註解要求

| 類型 | 需求 | 說明 |
|------|------|------|
| 業務邏輯函式 | 是（100%） | 必須有 UC/BR 編號 |
| 純技術工具函式 | 否 | 例：`sorted()`, `parse_json()` |
| 值物件建構式 | 是（約束） | 記錄不變式和驗證規則 |
| Domain 模型方法 | 是（規則） | 記錄業務規則 |
| 工具函式 | 視情況 | 若有複雜邏輯則需要 |

### 禁止的註解

| 類型 | 禁止例 | 正確做法 |
|------|--------|---------|
| 程式碼翻譯 | `# 將計數器加 1; count += 1` | 移除註解，改善變數名稱 |
| 技術實作描述 | `# 用 Dict 做快速查找` | 改用自說明命名：`fast_lookup_dict` |
| 過時 TODO | `# TODO: 之後加驗證` | 建立 Ticket，刪除註解 |
| 狀態記錄 | `# 已完成 UI 設計` | 移至工作日誌，不在程式碼中 |

### 註解語氣建議

```python
# 不好：命令式，不專業
# 計算用戶在本次購物的折扣

# 好：陳述式，說明設計意圖
# 根據 UC-042，按用戶會員等級應用折扣率
```

---

## 品質檢查清單 — 操作指引

### 命名檢查清單（執行步驟）

1. **函式命名審查**
   ```python
   # 逐一檢查每個函式定義
   def validate_input():      # ✓ 動詞開頭
   def get_user():            # ✓ 明確動作
   def process():             # ✗ 模糊，改為 process_payment
   def user():                # ✗ 名詞，改為 get_user
   ```

2. **變數命名審查**
   - 布林變數是否以 is/has/can 開頭？
   - 集合使用複數？（users, sessions）
   - 是否避免模糊詞（data, temp, info, flag）？

3. **類別命名審查**
   - 名稱是否描述業務責任？
   - 避免 Manager, Helper, Util 等泛稱？

### 結構檢查清單（執行步驟）

1. **計算函式長度**
   ```
   - <= 10 行：優秀
   - 11-20 行：合格
   - 21-30 行：需考慮拆分
   - > 30 行：必須拆分
   ```

2. **檢查巢狀深度**
   ```python
   # 掃描最深的 if/for 嵌套層級
   # 目標：<= 2 層（正常），3 層（臨界），> 3 層（必須改）
   ```

3. **檢查參數數量**
   - 1-2 個：理想
   - 3 個：接受
   - 4+ 個：考慮封裝物件

4. **評估認知負擔指數**
   ```
   = 變數數 + 分支數（if/elif/for） + 巢狀深度 + 依賴數

   結果：
   - 1-5：優良，維持
   - 6-10：可接受，考慮優化
   - 11-15：需重構，建立 Ticket
   - > 15：必須重構，立即處理
   ```

### 常數管理檢查清單（執行步驟）

1. **掃描硬編碼字串**
   ```bash
   grep -rn '"[A-Z][a-z]*"' src/
   # 審視每個字面字串，確認是否應提取為常數
   ```

2. **掃描魔法數字**
   ```bash
   grep -rn '\b[0-9]\+\b' src/
   # 檢查是否應使用具名常數替代
   ```

3. **驗證常數定義位置**
   - 單檔使用：檔案頂部
   - 多檔使用：constants.py
   - 相關常數群組：IntEnum 或常數類別

### 註解檢查清單（執行步驟）

1. **掃描業務邏輯函式**
   ```python
   # 每個業務邏輯函式應有 UC/BR 編號
   def calculate_pricing(quantity, user_tier):
       # 應有 UC-042 的參考
   ```

2. **檢查禁止的註解**
   - 程式碼翻譯？
   - 技術實作描述？
   - 過時的 TODO？

3. **驗證維護指引**
   - 複雜邏輯是否有維護建議？
   - 依賴關係是否記錄？

---

## 相關文件

- .claude/rules/core/quality-common.md - 核心規則定義
- .claude/methodologies/comment-writing-methodology.md - 註解方法論

---

**Last Updated**: 2026-03-11
**Version**: 1.0.0 - 從 quality-common.md 分離操作指引和詳細範例
