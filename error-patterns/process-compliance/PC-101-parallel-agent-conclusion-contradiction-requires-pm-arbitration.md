# PC-101: 並行代理人結論矛盾時 PM 必須實證仲裁

## 基本資訊

- **Pattern ID**: PC-101
- **分類**: 流程合規（process-compliance）
- **風險等級**: 中（僅在並行派發多 subagent 的多視角審查情境出現）
- **相關 Pattern**: PC-050（premature agent completion judgment）、PC-066（decision quality autopilot）

---

## 問題描述

### 症狀

多個 subagent 並行分析同一系統，結論彼此矛盾。PM 若不察覺或不仲裁，會直接整合為錯誤結論。

### 典型場景

- PM 並行派發 N 個 Explore 做多視角分析
- N 個代理人各自 tool budget 有限（~20 tool calls），只看系統局部
- LLM 推理為填補缺口，可能產生虛構結論
- N 個代理人 return 時，PM 假設「多視角必然收斂」，直接綜合

---

## 根因分析

### 直接原因

Subagent tool budget 限制導致每個只能掃部分檔案；LLM 在資訊不足時傾向 hallucinate 補齊結論，且語氣自信。

### 深層原因

| 類型 | 說明 |
|------|------|
| A 並行假設錯誤 | PM 預期「多視角 = 多個真實視角交叉驗證」，實際是「多個局部視角獨立推理」 |
| B 缺結論衝突偵測 | PM 整合時未系統性對照各 agent 結論是否互斥 |
| C 缺實證通道 | PM 讀完 agent 報告直接整合，未自己跑 CLI / 讀檔驗證關鍵斷言 |
| D 未記錄 dissenting view | 最終結論單向收斂，矛盾證據消失於整合過程 |

---

## 防護措施

### 整合前三點對照

PM 讀完並行 subagent 報告後，**綜合進 Solution 前**必須回答：

| 問題 | 處理 |
|------|------|
| Q1: 各 agent 結論是否彼此互斥？ | 若否，正常綜合；若是，進 Q2 |
| Q2: 哪個 agent 有直接證據（引用具體 line / 實測指令）？ | 以有證據的為權威，無證據的記為虛構風險 |
| Q3: 證據皆間接時，PM 自己跑 CLI / 讀檔實證 | 仲裁結論必須在 Solution 含「PM 實證仲裁」段落 |

### Solution 必要結構

並行多視角 ANA 的 Solution 必須含：

```yaml
multi_view_status:
  status: reviewed
  reviewers: [...]
  conclusion: "..."
  dissenting_view: "若無矛盾填 none；若有矛盾記錄 agent 間差異與 PM 仲裁依據"
```

`dissenting_view` 欄位強制存在，即使無矛盾也要填 `none` —— 逼 PM 主動檢查。

---

## 觸發案例

### W17-004 多視角並行分析（本 Pattern 發現案例）

PM 並行派發 3 個 Explore：
- W17-004.1：POSIX 成功模式研究
- W17-004.2：CLI 三向對齊審計
- W17-004.3：結構性深度分析

**衝突**：W17-004.2 結論「`create --source-ticket` 存在但副作用未文件化」；W17-004.3 結論「--source-ticket 缺席，PM 被迫用 --parent 繞路」。兩者互斥。

**PM 仲裁**：本 session 實際用 `ticket create --source-ticket 0.18.0-W17-001` 成功建 W17-004（實證參數存在）。仲裁：004.3 誤判；真痛在副作用未文件化（004.2 結論正確）。

**若無仲裁**：PM 可能取 004.3 結論，衍生出「新增 --source-ticket 參數」的 IMP ticket，浪費資源修不存在的問題。

---

## 與其他 Pattern 關係

| Pattern | 關係 |
|---------|------|
| PC-050 | 類似情境（PM 判斷 agent 狀態），PC-101 聚焦「結論整合階段」而非「完成判斷階段」 |
| PC-066 | 決策品質自動駕駛—— context 重時 PM 可能跳過仲裁，直接整合；PC-101 是其具體子型態 |
| PC-100 | 若多視角分析產出用於建衍生 IMP，矛盾不仲裁會讓 spawned ticket 的 Context Bundle 繼承錯誤結論 |

---

**Last Updated**: 2026-04-20
**Version**: 1.0.0 — 從 W17-004 並行 Explore 結論矛盾案例建立
