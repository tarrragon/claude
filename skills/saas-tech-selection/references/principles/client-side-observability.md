# Client-Side Observability

> **角色**：本卡是 `saas-tech-selection` 的支撐型原則（principle）、被 `dimensions/observability.md` 引用。
>
> **何時讀**：observability 維度展開時、且產品有 client-side 元件（mobile app / SPA / desktop app）— server-side observability 是必展開、client-side 是觸發展開。

## 觸發條件

產品有 mobile app、SPA（Single Page Application）、desktop app、或任何在使用者裝置上執行的 client-side 程式碼時觸發。純 API 服務（沒有自有 client）不需要。

## 四類事件分類

Client-side 的監控資料分成四類，每類回答不同問題：

- **Event**：使用者做了什麼（按鈕點擊、頁面瀏覽）→ 行為分析、funnel、debug context
- **Error**：什麼出了問題（例外、非預期狀態）→ 告警、根因分析
- **Metric**：系統狀態的數值（frame rate、回應時間）→ 效能監控
- **Lifecycle**：系統經歷了什麼（app 啟動、前後景切換、連線斷開）→ session 分析、環境資訊

## 自架 vs 商業方案

| 條件                          | 方案                                            |
| ----------------------------- | ----------------------------------------------- |
| 使用者在同網路、開發者自用    | 自架（HTTP POST → JSONL + grep）                |
| 使用者在外部網路、< 100 人    | 商業免費額度（Sentry Developer / PostHog free） |
| 使用者 > 1000 人、需要 funnel | 商業方案（Mixpanel / Amplitude / Datadog RUM）  |

## SDK 設計要點

Client-side SDK 的公開 API 是 init / event / error / metric / flush / close。設計時要考慮：離線 buffer（網路不可用時暫存事件）、攢批送出（不每個事件發一次 HTTP）、redaction（敏感資料在離開 client 前遮罩）。

## 和 server-side observability 的分工

Server-side observability 是必展開、回答「服務掛了怎麼知道」。Client-side observability 是觸發展開、回答「使用者的裝置上發生了什麼」。兩者獨立設計但共用 correlation 機制（request ID、session ID 在 client 產生、server 端記錄）。
