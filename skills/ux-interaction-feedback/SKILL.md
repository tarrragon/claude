---
name: ux-interaction-feedback
description: "UX 互動回饋設計規範（按鈕級 + 畫面級）。Use for: (1) 審查按鈕回饋完整性（三層模型：點擊確認/等待指示/結果通知）, (2) 判斷 loading indicator 時機（100ms/400ms/1s/10s 時間門檻）, (3) 設計非同步按鈕生命週期（idle/loading/result）和 debounce, (4) 設計畫面級非同步狀態轉換（連線/配對/同步流程的中間狀態 UI 和退出路徑）, (5) spinner vs skeleton 選擇判準。Use when: 實作非同步操作、設計連線/配對/同步流程 UI、審查 loading 回饋缺口。"
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
---

# UX 互動回饋設計規範

## 核心原則

**每個使用者動作都需要即時、誠實的系統回應。** 沒有回饋的按鈕等同壞掉的按鈕。

理論基礎：
- Nielsen 十大可用性啟發法 #1（系統狀態可見性）
- Doherty Threshold（400ms 回應門檻，Doherty & Thadani, IBM, 1982）
- Nielsen 回應時間三門檻（100ms / 1s / 10s）

## 三層回饋模型（概念：使用者需要什麼回饋）

| 層級 | 時間點 | 回答 | 實作 |
|------|--------|------|------|
| 1. 點擊確認 | 0-100ms | 「收到操作了」 | 視覺狀態變化 / ripple / 觸覺 |
| 2. 等待指示 | 100ms-10s | 「正在處理」 | spinner / loading 狀態 / 進度條 |
| 3. 結果通知 | 操作完成 | 「結果是什麼」 | 畫面更新 / SnackBar / 錯誤訊息 |

結果通知的形式選擇：操作結果改變當前畫面內容 → 畫面直接更新（如列表新增一筆）；不改變當前畫面 → SnackBar / Toast 短暫提示；嚴重錯誤需用戶決策 → Dialog。

## 時間門檻與回饋策略（實作：依延遲選擇回饋形式）

| 等待時間 | 門檻名稱 | 回饋策略 |
|---------|---------|---------|
| 0-100ms | 即時感知 | 點擊確認即可，不需 loading |
| 100-400ms | Doherty Threshold | 動畫過渡掩蓋等待 |
| 400ms-1s | 心流維持 | Spinner / 按鈕 loading 狀態 |
| 1-10s | 明顯等待 | 進度指示 + spinner |
| > 10s | 注意力上限 | 進度百分比 + 預估時間 + 取消選項 |

## 兩層回饋粒度

### 按鈕級回饋（單一操作）

#### 非同步按鈕（API / DB / 權限）

```
[idle] → 點擊 → [loading: disabled + spinner] → 完成 → [idle + 結果通知]
```

- loading 期間按鈕 **disabled**（防重複提交）
- 按鈕文字可變（「送出」→「送出中...」）
- 結束後**必須**恢復 idle 狀態

#### 同步按鈕（導航 / 切換 / 開關）

```
[idle] → 點擊 → [視覺回饋] → [完成]
```

- 加入 **debounce**（300ms）防連點（業界常見範圍 200-500ms，300ms 平衡防連點與操作響應感）
- 不需 loading 狀態

### 畫面級回饋（多步驟流程）

按鈕級回饋處理單一操作，但有些流程涉及**整個畫面的狀態轉換**（連線、配對、同步）。畫面級回饋的每個狀態都需要獨立的 UI 呈現和退出路徑。

典型模式（以連線流程為例）：

```
[idle: 連線按鈕] → 點擊 → [connecting: spinner + 取消按鈕] → 成功 → [connected: 功能畫面]
                                    │                              │
                                    └─ 失敗 → [error: 錯誤訊息 + 重連/返回]
                                                                   │
                                                            [disconnected: 斷線提示 + 重連按鈕]
```

設計要點：
- 每個狀態都是獨立 UI（非按鈕內 spinner，而是整頁替換）
- 每個狀態**必須有退出路徑**（對應畫面狀態矩陣設計方法）
- connecting 狀態提供取消操作
- error / disconnected 提供重連**和**返回兩條路徑

### Spinner vs Skeleton 選擇判準

| 條件 | 用 Spinner | 用 Skeleton Screen |
|------|-----------|-------------------|
| 結果形狀已知（列表 / 卡片） | | 適合（佔位形狀接近最終結果） |
| 結果形狀不確定（連線 / 計算） | 適合 | |
| 等待時間可預測（< 2s） | 適合 | |
| 等待時間較長（2-10s） | | 適合（降低焦慮感） |
| 首次載入（無歷史資料） | | 適合（給畫面結構預期） |
| 操作觸發的等待（按鈕後） | 適合（按鈕內 spinner） | |
| 重新載入（已有舊資料） | 適合（保留舊內容 + 頂部 spinner） | |

## 六種按鈕狀態

| 狀態 | 傳達訊息 | 何時觸發 |
|------|---------|---------|
| Default | 可以按 | 無互動 |
| Hover | 可互動的元素 | 游標懸停（桌面端） |
| Active | 收到點擊 | 手指按住 |
| Focus | 焦點在此 | 鍵盤 Tab（WCAG 要求） |
| Disabled | 現在不能按 | 前置條件未滿足 / loading 中 |
| Loading | 正在處理 | 非同步操作執行中 |

## 反模式速查

| 反模式 | 使用者後果 | 技術後果 |
|--------|-----------|---------|
| 按鈕無視覺回饋 | 重複點擊 | 多次觸發 onPressed callback |
| 非同步不禁用按鈕 | 重複提交 | HTTP POST 重複送出 / DB 重複寫入 |
| loading 結束不恢復按鈕 | 以為介面當掉 | Future 完成但 setState 未呼叫 |
| 只有 loading 無結果通知 | 不確定是否成功 | 狀態已更新但 UI 未反映 |
| 同步按鈕無 debounce | 導航堆疊混亂 | Navigator push 多次同一路由 |
| 每個操作都全螢幕 loading | 打斷心流 | 所有互動被 modal barrier 阻斷 |
| spinner 閃爍（顯示後立即消失） | 視覺雜訊 | 缺 minimum display duration |
| 畫面級狀態轉換無退出路徑 | 使用者被卡在中間狀態（UX 死胡同） |
| connecting 用 skeleton 而非 spinner | 結果形狀不確定時 skeleton 佔位無意義 |
| 斷線只有重連、沒有返回 | 使用者被鎖在錯誤迴圈 |

## 設計檢查清單

### 按鈕級

- [ ] 點擊有視覺回饋（ripple / 狀態變化 / 觸覺）？
- [ ] 非同步操作：按鈕有 loading 狀態？
- [ ] 非同步操作：loading 期間 disabled？
- [ ] 非同步操作：完成後恢復 idle？
- [ ] 操作結果有通知（成功 / 失敗 / 空）？
- [ ] 失敗時有可執行下一步？
- [ ] 同步按鈕有 debounce（300ms）？
- [ ] loading 有 timeout 機制？

### 畫面級

- [ ] 多步驟流程的每個中間狀態都有獨立 UI？
- [ ] 每個中間狀態都有退出路徑（返回 / 取消）？
- [ ] 等待狀態選擇正確（spinner vs skeleton，依結果形狀判斷）？
- [ ] 錯誤 / 斷線狀態同時提供重試**和**返回兩條路徑？
- [ ] 長時間連線提供取消操作？
- [ ] 等待狀態有 timeout 機制（超時自動轉 error + 恢復可操作）？

## 參考來源

- Nielsen Norman Group (1994) — 十大可用性啟發法
- Doherty & Thadani (1982) — IBM Systems Journal, 400ms 門檻
- Nielsen (1993) — Usability Engineering, 100ms/1s/10s 三門檻
- Material Design 3 — Interaction States + Loading Indicator
- Apple HIG — Feedback 章節
- Laws of UX (lawsofux.com) — Doherty Threshold 現代整理

## 教學文章

完整設計理論與範例見 blog UX 設計系列模組六「互動回饋設計」（三篇：三層回饋模型、按鈕狀態設計、時間感知與回應策略）。
