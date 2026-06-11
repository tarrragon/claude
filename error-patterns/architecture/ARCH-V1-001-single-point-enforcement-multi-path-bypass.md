# ARCH-V1-001: 同一不變量單點執法、多入口繞過（前門裝鎖、側門敞開）

## 錯誤症狀

一個業務不變量（必填欄位、格式規則、權限檢查等）的驗證只綁在「主要入口」（如主命令層），但系統存在多條**其他寫入路徑**繞過該入口直接落地，造成執法不一致：

- 主入口擋得住殘缺資料，側門路徑卻能建出殘缺物件
- 無 hook / 安全網接住側門（驗證未綁在所有寫入路徑的共同瓶頸）
- 不變量升級（如必填欄位擴充）時只改主入口，側門靜默失守

典型表現（本專案案例，1.0.0-W1-027 對抗性複審發現）：

- `validate_create_checklist`（5W1H 必填驗證）原僅在 `create.py` 命令層執行（W11-003.5 升級為阻擋）
- `bulk_create.py`（batch-create）與 `ticket_generator.py`（generate）直接 `save_ticket`，零驗證
- 兩條側門的 config 預設值（`who="pending"` / `why=""` / `where_files=[]`）本身即殘缺，卻能建票成功

## 與 ARCH-020 的區別

| 模式 | 本質 | 失效形態 |
|------|------|---------|
| ARCH-020 | 同一驗證**兩處重複**實作 | duplication drift（修一邊漏一邊） |
| ARCH-V1-001 | 同一驗證**單點綁定**單一入口 | enforcement gap（側門完全無驗證） |

兩者互補：ARCH-020 防「重複漂移」，本模式防「單點執法的覆蓋缺口」。共同根因方向均為「驗證應下沉至所有路徑的共同瓶頸（SSOT）」。

## 根因分析

### 根因 1：驗證邏輯與「主要入口」耦合

驗證函式定義在主命令模組內（`create.py` 私有函式），其他入口模組不 import 它，導致「驗證 = 主入口專屬」的隱性耦合。新增寫入路徑時無機制提醒「此路徑也需驗證」。

### 根因 2：驗證未放在寫入瓶頸

所有路徑最終都呼叫 `save_ticket`，但驗證綁在 `save` 之前的「主入口流程」而非 `save` 本身或其上游共同層。側門繞過主流程即繞過驗證。

### 根因 3：schema 形態在不同階段不一致（放置陷阱）

驗證函式讀 flat config key（`who` / `where_files`），但同一資料經轉換後變巢狀 frontmatter（`who.current` / `where.files`）。若把驗證誤放在轉換後階段，key 不符會全部誤判或全部漏判——驗證必須綁在 flat config 階段。

## 解決方案

### 步驟 1：驗證下沉至共同層

把驗證函式從主命令模組移至所有入口都 import 的共用層（如 `lib/ticket_builder.py`，`TicketConfig` 定義處），公開為穩定 API；主入口保留向後相容別名。

### 步驟 2：各入口在正確階段複用

每條寫入路徑在 **flat config 階段**（save 前、轉換前）呼叫共用驗證：

```python
missing = validate_create_checklist(config, config["ticket_type"])
```

### 步驟 3：依路徑性質決定阻擋強度

- 主入口（互動建票）：缺失阻擋（既有行為）
- 批次 / 自動路徑：warning 級不阻擋（Never break userspace），列全缺欄位提醒

## 預防措施

| 機制 | 說明 |
|------|------|
| 驗證下沉 SSOT | 不變量驗證放在所有寫入路徑的共同上游，禁止綁單一入口 |
| 新增寫入路徑檢查清單 | 新增「直接 save」的路徑時，必須確認是否複用共用驗證 |
| 提前退出 vs 匯總列全一致性 | 多欄位缺失應一次列全（避免跨階段分批試錯），見 1.0.0-W1-029 |
| 空字串 vs 哨兵值判定 | 驗證「未填」應涵蓋 falsy（`""` / `None`）與哨兵值（「待定義」），見 1.0.0-W1-043 |

## 相關 Ticket

- 1.0.0-W1-027（驗證下沉 + batch-create/generate warning 接線，本模式主案例）
- 1.0.0-W1-043（空字串 why/how_strategy 漏判，判定完整性缺口）
- 1.0.0-W1-029（decision-tree 提前退出併入 checklist，匯總列全一致性）
- source ANA 1.0.0-W1-024（對抗性複審挑戰 4 發現側門繞過）

## 相關模式

- ARCH-020（duplicate validation across validator and hook）——重複漂移的近親模式
