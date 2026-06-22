# Dimension：Deployment Platform（部署平台與網路入口）

本維度處理「程式碼怎麼變成持續運作的服務、流量怎麼安全地進來」。任何對外 SaaS 都必展開。平台選型的核心取捨是控制力 vs 維運負擔：越接近裸機控制力越高、團隊要承擔的維運面也越寬；定錨階段的團隊能力答案在這個維度權重最高 — 平台選錯的代價以天為單位持續支付、且更換成本隨時間累積。

---

## 訪談問題

| 問題                                                 | 為什麼問                                                               |
| ---------------------------------------------------- | ---------------------------------------------------------------------- |
| 團隊有人管過 production 主機 / container 平台嗎？    | 平台選型上限由維運能力決定、不由技術潮流決定                           |
| 服務有沒有長連線需求（WebSocket、SSE）？             | 長連線排除部分 serverless 方案、影響 LB 設定與 graceful shutdown 設計  |
| 有沒有常駐背景工作（worker、排程）？                 | 純 request-response 平台（部分 PaaS / serverless）跑常駐 worker 要繞路 |
| 部署頻率預期多高？誰負責部署？                       | 高頻部署 → CI/CD 自動化權重高；「誰部署」決定權限與紀錄設計            |
| 停機的容忍度？（深夜維護窗可接受、還是要零停機部署） | 決定 rolling update / health check 的投資等級                          |

**反向問**：「部署出去發現壞了、退回上一版要按哪個鍵、誰會按？」— 回滾路徑在第一次壞版本前演練過、跟事故當下現查文件、是兩種完全不同的事故時長。

### 語言選型（部署約束驅動）

多數 SaaS 的語言選擇由團隊熟悉度決定（定錨 Stage 0 已問）。但部署形態帶來語言約束的場景需要額外確認：

| 部署約束                                           | 語言影響                                                 | 追問                                             |
| -------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------ |
| 零 runtime 依賴（開源工具讓使用者 download + run） | 需要靜態連結的 compiled language（Go / Rust / C）        | 「開源使用者部署你的工具時、要不要裝 runtime？」 |
| Serverless（AWS Lambda / Cloud Functions）         | 冷啟動時間敏感 → Go / Rust 優於 Python / Java            | 「冷啟動延遲對你的 use case 重要嗎？」           |
| 團隊能力限定                                       | 如果團隊只會一種語言、強迫換語言的代價高於語言帶來的效益 | 不追問、定錨已答                                 |

如果語言選擇不影響部署形態（PaaS / container 跑什麼語言都行）、這段直接跳過。

---

## 候選類型差異

| 類型                                          | 適合                                                | 代價                                                       |
| --------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| PaaS（Heroku / Render / Fly / Railway 類）    | 小團隊、快上線、標準 web + worker 形態              | 單位運算成本最高、平台限制（長連線、特殊網路）要先確認     |
| VM + systemd                                  | 成本敏感、形態簡單、團隊有 Linux 經驗               | 主機更新、安全補丁、開機自復原全部自己扛                   |
| 單機 / 少機 container（compose 類）           | 想要環境一致性、還不需要編排                        | 跨機擴展與自動復原要自己補                                 |
| Managed Kubernetes                            | 多服務、多團隊、需要自動擴縮與自癒                  | 認知負擔大；MVP 階段引入、維運成本先於收益到來             |
| Serverless（functions 類）                    | 事件驅動、流量極度間歇                              | 冷啟動、執行時長上限、長連線與常駐 worker 不合             |
| Outbound tunnel（cloudflared / Tailscale 類） | 自架但不暴露公網入口、家用 / 自用服務、本機主動外連 | 依賴 tunnel 供應商;tunnel 網址非密碼、前面必須再疊認證閘道 |

### Container 部署的效能取捨

Container 提供環境隔離和部署便利（`docker run` 一行啟動），但引入效能開銷。效能敏感的選型需要評估這個開銷是否在可接受範圍。

| 面向                       | 影響                                            | 何時重要                                         |
| -------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| **Overlay filesystem I/O** | 寫入經過 overlay 層，比直接寫 host 慢 20-40%    | 服務有嵌入式 DB（SQLite / BoltDB）或高頻磁碟寫入 |
| **Network namespace**      | 跨 namespace 的封包有微小延遲（< 1ms）          | 高頻低延遲 RPC（通常可忽略）                     |
| **Memory overhead**        | Container runtime + overlay metadata 約 10-30MB | 記憶體極度受限的環境（< 256MB）                  |

**Volume mount 繞過 overlay**：嵌入式 DB 的資料目錄用 `-v /host/path:/container/path` 掛載，直接讀寫 host 檔案系統，I/O 效能和 bare-metal 一致。Container 內的 overlay 只影響 binary 和 config 等不頻繁寫入的檔案。

**快速部署模組模式**：部分服務適合打包成「一個 container = 完整的功能模組」— binary + 嵌入式 DB + config，使用者 `docker run` 即用、不需要額外建 DB 或設定外部依賴。這個模式犧牲水平擴展（嵌入式 DB 不支援多 instance）換取部署極簡。升級時切換到外部 DB（PostgreSQL）+ 多 container 架構。

**選型問題**：「這個服務的磁碟 I/O 模式是否被 overlay 影響？如果是，volume mount 能解決嗎？還是應該直接用 bare-metal 部署？」

**SaaS day one 預設**：PaaS 或單機 container。理由：把 LB、TLS、部署管線、health check 整合外包、團隊專注產品。Kubernetes 的進入條件寫成 tripwire（多服務 + 部署互相阻擋 + 有人能維運它）、而不是 day one 的預設 — 使用者點名 k8s 時、確認三個條件是否已成立。

**入口層**：不論平台、入口統一收斂到一個 LB / reverse proxy：TLS 終止、基本限流、請求大小上限、health check 探測。PaaS 內建即用；自管平台用 nginx / caddy 類補齊。CDN / 邊緣層在靜態資源流量成為主要成分時引入（tripwire）。自架而不想暴露公網入口時、入口形態改為 **outbound tunnel**（cloudflared / Tailscale）：本機主動外連、路由器零開 port、對公網零入站面；代價是 tunnel 網址只是位址不是密碼、前面必須疊認證閘道（service token / 反向代理驗密鑰）、且 tunnel 對外宣告 ready 要 gate 在後端 readiness 之後。

---

## 防護底線（non-negotiable）

1. **部署可回滾**：保留上一版 artifact、回滾指令文件化、上線前演練一次。
2. **Health check 接入部署流程**：新版本通過探測才接流量、失敗自動停止 rollout。
3. **Graceful shutdown**：收到終止訊號先停收新請求、處理完在途請求再退出；缺了它每次部署都是一批使用者的失敗請求。
4. **環境變數注入 secret**：部署設定與 secret 分離、設定進 repo、secret 進平台注入機制。
5. **Production 與開發環境隔離**：分開的資料庫、分開的憑證、分開的第三方 API key（sandbox）。

---

## 延後與 tripwire

| 可延後項                  | 建議重評條件                                         |
| ------------------------- | ---------------------------------------------------- |
| Kubernetes                | 服務數 > 3、部署互相阻擋、且團隊有人能值它的 on-call |
| CDN / 邊緣層              | 頻寬 / 連線數在流量高峰先於 CPU 撞頂                 |
| 多區域部署                | 合約 SLA 或主要市場延遲要求出現                      |
| 藍綠 / canary 部署        | 部署事故率讓 rolling update 的保護不夠用             |
| Outbound tunnel 改公網 LB | 入口數 / 流量成長到需要多入口或正式反向代理          |

---

## 決策記錄要記什麼

平台選型與理由（回指團隊能力定錨）、入口層構成（TLS / 限流 / health check 位置）、回滾路徑與演練狀態、防護底線段各條的狀態、k8s 與 CDN 的觸發條件。
