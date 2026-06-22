# Dimension：Observability（觀測底線）

本維度處理「系統壞了怎麼知道、知道了怎麼定位」。必展開、但 day one 的形態是底線集合而不是平台選型 — MVP 階段的觀測問題是「有沒有訊號」、不是「用哪家平台」。本維度同時是其他維度 tripwire 的基礎設施：規模撞牆訊號全部依賴這裡建立的訊號源、觀測缺口會讓所有 tripwire 失明。

---

## 訪談問題

| 問題                                                   | 為什麼問                                                          |
| ------------------------------------------------------ | ----------------------------------------------------------------- |
| 服務掛了、你希望多久內知道？透過什麼管道？             | 偵測延遲目標決定 uptime 監控與 alert 路由的設計                   |
| 使用者回報「很慢」、你打算看什麼來判斷慢在哪？         | 暴露 latency 訊號的需求：request log 的 duration 欄、依賴呼叫計時 |
| 一個錯誤發生、你要能回答哪些問題？（誰、何時、做什麼） | 決定 log 的最小欄位集：request id、user / tenant id、錯誤分類     |
| 誰看這些訊號？多常看？                                 | 兩人團隊的 dashboard 沒人看、alert 才是真正的觀測入口             |

**反向問**：「凌晨三點掛了、誰的手機會響？」— 答案是「沒人」的話、uptime 監控 + 手機層級通知是本維度第一個建立的東西。

---

## Day one 最小集

| 訊號            | 最小實作                                                                  |
| --------------- | ------------------------------------------------------------------------- |
| 活著沒有        | 外部 uptime 監控（打 health endpoint）+ alert 到手機層級管道              |
| Request log     | structured JSON：request id、路由、狀態碼、duration、user / tenant id     |
| 錯誤分類        | 4xx（client 問題）/ 5xx（自己的 bug）/ 依賴失敗（DB、第三方）三類分開計數 |
| 錯誤聚合        | error tracking 服務（Sentry 類）：同錯誤聚合、新錯誤通知、帶 stack trace  |
| 主機 / 平台訊號 | CPU、記憶體、磁碟、連線數 — 託管平台多半內建、確認打開並設基本 alert      |

這個集合的設計原則：每個訊號都直接回答一個事故當下的問題。「掛了嗎」→ uptime；「誰受影響」→ request log 的 user 欄；「是我的 bug 還是依賴掛了」→ 錯誤分類；「哪行程式」→ error tracking。訊號回答不了任何具體問題的、不進 day one 集合。

**外部託管判讀**：觀測的買 vs 建關鍵在計費怎麼隨資料量放大 —— observability SaaS 的帳單跟著 metrics cardinality 與保留期長（見 `principles/capability-outsourcing-depth.md`）。day-one 最小集本身偏外包：uptime 監控、error tracking（Sentry 類）、平台內建主機訊號都是 feature SaaS / 平台原生、零自建。真正的買 vs 建出現在延後項那一層：metrics 趨勢、log 聚合、tracing 要嘛買 observability SaaS（Datadog / Grafana Cloud 類、把存儲與查詢外包），要嘛自建 stack（Prometheus / Loki / Tempo、省授權費但扛維運與容量）。小團隊預設買 SaaS 到「帳單成長超過自建維運成本」的 tripwire 觸發為止；cardinality 與保留期是計費的主要放大器、納入規模 tripwire。

---

## Observability 工具的自我監控（bootstrapping problem）

產品本身是 observability 工具（監控 SDK、collector、log 聚合器）時，會遇到 bootstrapping 問題：如果 monitor 掛了，誰監控 monitor？用自己監控自己會形成循環依賴 — monitor 掛掉時它自己的告警也跟著掛。

解法是**外部層級隔離**：用一個結構上獨立於 monitor 的機制監控 monitor 本身。

| 機制                    | 做法                                                         |
| ----------------------- | ------------------------------------------------------------ |
| 外部 uptime check       | cron + curl health endpoint、失敗時用系統通知（mail / ntfy） |
| Collector 的 stderr log | collector 自己的錯誤寫 stderr、systemd journal 收            |
| Process 存活監控        | systemd watchdog / supervisor 重啟                           |

原則：monitor 不用自己的 SDK 監控自己的 collector。Health endpoint + process supervisor + 系統級 log 是三層獨立的自我監控、不依賴 monitor 的事件收集管線。

---

## 防護底線（non-negotiable）

1. **掛了有人知道**：uptime 監控 + 會吵醒人的通知管道。使用者比團隊先發現停機、每次都在消耗信任。
2. **Structured log + request id**：純文字 log 在事故當下無法聚合與關聯；request id 讓一次請求跨 log 行可追。
3. **PII 不進 log**：log serializer 層遮罩個資欄位 — log 平台的存取控制與保留期限通常比 DB 鬆、個資進去等於繞過全部資料保護。
4. **錯誤分類三分**：自己的 bug、client 的問題、依賴的失敗、三者的處理路徑完全不同、混在一起的錯誤率沒有行動價值。

---

## 延後與 tripwire

| 可延後項                      | 建議重評條件                                     |
| ----------------------------- | ------------------------------------------------ |
| Metrics 平台（Prometheus 類） | 需要容量趨勢與自訂業務指標、平台內建訊號不夠用   |
| Distributed tracing           | 服務數 > 2、跨服務延遲無法用 log 定位            |
| Log 聚合平台                  | 多實例 / 多服務、ssh 看 log 開始出現在排障流程裡 |
| On-call 輪值與 escalation     | 團隊 > 3 人、單一接收者成為單點                  |

Tracing 與 metrics 延後的前提是 request log 欄位齊全 — duration 與依賴計時欄位在 log 裡、單體階段足以定位多數慢問題。

---

## Client-Side Observability（觸發展開）

產品有 mobile app、SPA、desktop app 等 client-side 元件時觸發。純 API 服務不需要。

Client-side 的監控資料分四類：event（使用者操作）、error（例外和非預期狀態）、metric（frame rate / 回應時間）、lifecycle（app 啟動 / 前後景切換 / 連線斷開）。四類各自回答不同問題、收集策略從需求推導（debug 需求、行為分析需求、效能需求、合規需求）。

Day one 方案依使用者位置選擇：同網路自用工具 → 自架 HTTP endpoint + JSONL + grep（零成本）；外部使用者 < 100 人 → 商業免費額度（Sentry Developer / PostHog free）；使用者 > 1000 + 需要 funnel → 商業方案。

Client-side SDK 的設計要點：離線 buffer（網路斷開時暫存）、攢批送出（降低 HTTP 次數）、redaction（敏感資料離開 client 前遮罩、見 security 維度的 PII 底線）。

完整判讀見 `principles/client-side-observability.md`。

---

## 決策記錄要記什麼

偵測延遲目標、alert 管道與接收者、log 欄位集與 PII 遮罩位置、error tracking 服務選擇、client-side observability 方案（自架 / 商業 / 無）、防護底線段各條的狀態、延後項觸發條件。
