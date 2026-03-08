# PC-011: Ticket 版本歸屬錯誤（ccsession 任務誤放 Claude 框架版本）

## 基本資訊

| 項目 | 說明 |
|------|------|
| **編號** | PC-011 |
| **類別** | 流程合規（Process Compliance） |
| **嚴重度** | 中 |
| **發現版本** | 0.1.0 |
| **相關 Ticket** | 0.1.1-W1-004（原 0.1.0-W16-004），遷移 9 個 Ticket |

---

## 症狀

- Ticket 描述的任務內容（Go Backend 實作、Flutter Frontend、UC 設計）與版本目標（Claude 框架）不一致
- `ticket track summary` 顯示特定版本的任務包含兩種不同性質的工作
- 版本完成統計失真：ccsession 任務尚未開始，但計入 Claude 框架版本的完成進度

---

## 根因

**版本語義未明確文件化，導致建立 Ticket 時以「當前版本」為準而非「任務歸屬」為準。**

具體情境：
1. 0.1.0 版本初期同時進行「UC 規格設計（ccsession）」和「Claude 框架改進」兩種工作
2. `current_version: 0.1.0` 使得新建 Ticket 預設歸入 0.1.0
3. 缺乏「版本語義聲明」文件，導致代理人建立 Ticket 時未意識到歸屬問題
4. 版本推進調整（0.1.0/0.1.1 重新定義）後，未同步遷移已建立的 ccsession Ticket

---

## 解決方案

1. 使用 `ticket migrate <old_id> <new_id>` 逐一遷移錯誤版本的 Ticket
2. 移動附屬分析報告等檔案（migrate 指令不會移動附屬 .md 文件）
3. 確認每個遷移 Ticket 的 `version` 欄位已更新
4. 更新 `todolist.yaml` 的 `current_version` 反映版本調整（如需要）

---

## 預防措施

### 1. 版本語義聲明（建議加入 worklog）

每個版本的 worklog 應明確聲明版本邊界：

```markdown
## 版本語義

| 版本 | 定位 | 包含工作 | 排除工作 |
|------|------|---------|---------|
| 0.1.0 | Claude 框架 | Hooks/Rules/Ticket CLI | ccsession 應用 |
| 0.1.1 | ccsession MVP | Go Backend/Flutter UI | 框架工具 |
```

### 2. Ticket 建立前確認版本歸屬

在 `/ticket create` 前問自己：

> 這個任務的目標是「Claude 開發框架本身」還是「使用此框架開發的專案」？

| 任務性質 | 版本歸屬 |
|---------|---------|
| Hook/Skill/Rule 改進 | 當前 Claude 框架版本 |
| 應用程式功能實作 | 應用程式專屬版本 |
| 工具 CLI 修復 | 工具的版本 |

### 3. Wave 命名暗示版本性質

若 Wave 名稱包含應用功能關鍵字（Go Backend、Flutter、UC、session）→ 高機率是應用程式版本任務，需確認版本歸屬。

---

## 關聯錯誤模式

- **PC-003**（cross-version-task-silent-omission）：版本邊界的跨版本任務遺漏問題

---

**記錄時間**: 2026-03-08
**來源**: 0.1.1-W1-004 執行期間發現（原 0.1.0-W16-004 版本歸屬錯誤）
