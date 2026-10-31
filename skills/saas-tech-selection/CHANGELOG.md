# saas-tech-selection 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.13.0 — security〈管理通道〉「建立主機之前的檢查」的讀官方文件那一項補作業系統版本這一層的支援檢查：文件只寫到作業系統時，用映像的作業系統版本欄位的值查業者依版本查詢的工具；同時拿不存在的版本值查一次當對照，結果跟對照不同才採用，相同時改從逐版本的文件或建好的主機確認；建好之後代理程式設定裡啟用、回報的元件清單裡沒有這一項時，多半是這個版本不提供它，查證之後改走另一條路徑或換版本重建。容量稀缺那一項的「作業系統」改成「作業系統與版本」。來源是重建一台 A1 Oracle Linux 10.2 主機的實測：Known Issues 只寫到 Arm 主機要跑 Oracle Linux；查詢工具在版本 10 回傳少了 Bastion 的清單，在 9、8 與不存在的版本回傳同一份全部清單，所以 9 與 8 分不出來。

**Version**: 1.12.0 — security〈管理通道〉的追問與判讀要點新增「建立主機之前的檢查」：找出只能建立時決定的設定、對登入路徑上每個服務讀支援清單與 Known Issues 與前置條件（元件狀態 running 不是支援的證據、換機型演練驗不出機型特有的問題）、兩條登入路徑逐項列出各自依賴的元件（代理程式型的工作階段有的經過 sshd、有的自己開 shell；第二條可以就是救援入口）、第二條路徑用自己公鑰時是暫時的、容量稀缺時選補救代價低的設定（跟機型無關的先在容易重建的機型上驗）與重送腳本重啟前再對一次；訪談階段的產出是決策記錄裡的兩列。來源是一次 A1 加 Ubuntu 主機建好之後登不進去的實測：managed SSH session 是官方列的不支援組合、Run Command 的 `ocarun` 沒有 sudo、建立時沒放公鑰而公鑰欄位建立後不能改。

**Version**: 1.11.1 — implementations/gcp-spend-kill-switch.md 依測試專案上的第二次實跑補正：建立預算的兩道權限檢查（serviceusage 再帳單帳戶）、從既有預算拿掉 topic 要用預算 API PATCH、通知管道只接受電子郵件且 webhook 被拒時不說原因、抵免類型的寫法與 FREE_TIER 的推論、跨 zone 停 VM 的做法與角色、Policy Troubleshooter 的指令、心跳監看（日誌指標加缺席條件、時間窗上限 23 小時 30 分）、管理專案與帳單停用期間撤銷金鑰的實測結果、同專案函式停用後約一分鐘內仍會執行。

**Version**: 1.11.0 — 新增 references/implementations/：gcp-spend-kill-switch.md（預算、Pub/Sub、函式部署、判斷規則、驗收、停用後的恢復）與 gcp-management-access.md（IAP 與 OS Login 的設定指令、舊規則的停用與回退、由 template 建的主機、GKE 控制平面與節點除錯、稽核紀錄、人員離職）。capacity-performance〈支出停損〉與 security〈管理通道〉只留決策點、三層表與平台無關的判讀要點，GCP 實作外移（兩段各約佔原檔四成，訪談時每次都載入）。SKILL.md 路由表兩列改成訪談讀維度檔、實際建置時再讀實作檔；目錄樹補 implementations/。

**Version**: 1.10.4 — 多輪審查 Round 4 修正：〈支出停損〉的決策點改成依停機影響誰與資料能否重建判斷，補上只停止花錢的資源那一格；驗收改成排在停機可接受的時段、有不能遺失的資料才用分段驗證，複本要換函式名稱與 topic，寫出 Policy Troubleshooter 要查的兩個權限；「已實測」標籤改成寫明哪些未實跑。baseline-protections 的管理 port 列縮短並指向 security。觸發詞拿掉 IAP、OS Login、救援入口（排查連線改由 linux-install-debug 承接）。principle 卡：完整證據、合成觸發的時機改成停機可接受的時段、中途注入一列標明是推導、靜默監看改名心跳監看。

**Version**: 1.10.3 — 多輪審查 Round 3 修正：〈支出停損〉示範改成另建接停損的預算（create，不接到既有警示預算）、一個 topic 只接一個預算、金額扣掉延遲期間的花費；驗收分成 topic 之前（第一則真實通知對照帳單報表）與 topic 之後兩段，超出預算那一則只在未上線專案做、已上線改用可拋棄複本，測完重新連結。〈管理通道〉：外部 IP 只在管理用途時移除；底線第 8 條與 baseline-protections 的 Kubernetes API 改用 IAM 端點或只列維運與 CI 的 authorized networks；舊規則停用前先觀察、盤點 metadata 金鑰、寫出回退指令；離職移出群組而非移除群組綁定；救援入口測完關回；logging 初期的假陰性註解。principle 卡補上第四個位置「測試從中途注入」、處置指令的假陰性、事件型觸發來源的靜默監看與合成觸發有損害時的分段驗證。觸發詞的 IAP 改成 GCP IAP。

**Version**: 1.10.2 — 多輪審查 Round 2 修正：capacity-performance〈支出停損〉補上接停損的預算要用 --filter-projects 限定單一專案、金額設成能承受的上限、大額抵免時用 exclude-all-credits；指令補 --billing-project、--condition=None、--max-instances=1、TARGET_PROJECT_ID 與 run.invoker 的 --region；實測段壓成三個可執行的結論並補上超支停用後的恢復順序。security〈管理通道〉：OS Login 範例先綁登入角色再啟用；Kubernetes 節點除錯另立一條、分開 debug profile 與 PSA 兩個同名的 baseline；離職完成判斷指名 pgrep。

**Version**: 1.10.1 — capacity-performance〈支出停損〉依多輪審查與官方文件查證修正：強制執行支出上限一個只涵蓋一個專案的一項服務、暫停到預算期間結束、持續性資源的固定費用不暫停；停用帳單時雲端文件警告資源可能被永久刪除；部署指令明確指定 --trigger-service-account（gcloud 說明的預設值與實測不同）並補齊必填旗標；測試訊息給出 publish 指令；預算門檻統一成 50% / 90% / 100%；花費為 0 也可能來自抵免。security〈管理通道〉：kubectl debug 只有 general 與 sysadmin profile 掛節點目錄、authorized networks 寫明更新時整組取代、IAM Condition 的期限格式、撤銷角色只擋住之後的新登入、救援入口補英文錨點。principle 卡 protection-proves-itself-by-firing 同 system-design 0.13.1 的修正。

**Version**: 1.10.0 — security 維度新增「管理通道（主機與叢集的管理存取）」子領域：網路可達性、通道授權、主機登入驗證三層加救援入口的 day one 預設，GCP 的防火牆規則、帶 Condition 的 IAP 角色與 OS Login 設定範例（已實測），舊規則的停用順序、由 template 建的主機、Kubernetes 控制平面與 `kubectl debug node` 的權限、稽核紀錄的類型（IAP 開通道是 `ADMIN_READ`）、離職時結束既有工作階段；防護底線加第 8 條、tripwire 補 SSH 憑證與組織層級護欄兩列。capacity-performance 修正反向問的「預算 alert 讓你當天發現」為計費資料的延遲，day one 的預算 alert 加預測花費一檔，防護底線寫明警示不停止扣款；新增「支出停損」段（何時值得建、GCP 的 Pub/Sub 加 function 做法與三個實測踩到的設定：`run.invoker`、`billing.projectManager` 讀不到帳單狀態要加 `browser`、預設不重試要加 `--retry`；實測反應時間與計費延遲、帳單停用期間資源清單為空、驗收要合成觸發），tripwire 與決策記錄各補一項。baseline-protections 的入口段加「管理 port 只放行身分感知代理或 VPN」、觀測段加「防護機制實際觸發過一次」。新增 principle 卡 `protection-proves-itself-by-firing`。SKILL.md 補兩條路由、目錄索引與觸發詞。來源是一次 GCP 測試專案上的管理通道與帳單停損開關實機驗證。

**Version**: 1.9.2 — 多輪審查 Round 3（誤用梯度）：約束驗證腳本從 `pg_constraint` 檢查涵蓋全部約束、改壞預期的結束碼寫進決策記錄；schema 規格在空資料庫跑的指令與結束碼寫進決策記錄；多套實作的 dump 差異逐項處理到空，常見差異清單不是放行清單

**Version**: 1.9.1 — state-storage 的「下一條」改為指名「只有一份語言中立的產生器」；observability 的連續失敗次數補換算依據

**Version**: 1.9.0 — deployment-platform 訪談新增同一台主機上放了哪些服務、尖峰是否重疊，compose 類的代價補同機互相搶資源、一起出事；observability 的存活探測只看回應碼與連線並連續失敗才發，新增「掛了」與「變慢」分成兩個判斷

**Version**: 1.8.0 — 〈種子資料與 schema 規格的驗證〉：違規寫入的驗證寫成獨立腳本（比對約束名稱、非 0 結束、自帶前置資料、故意改壞確認會失敗）；「關鍵寫入用正式語句」限於單一實作；新增多個實作共用資料庫時只有一份語言中立的產生器（不同語言的亂數序列不同、效能比較要同一份資料、集合寫入快），各實作的測試資料不在此列

**Version**: 1.7.0 — state-storage 新增〈種子資料與 schema 規格的驗證〉：合格 seeder 的判斷標準（經過全部約束並逐條驗違規寫入、可重現、在執行映像裡跑得起來、指定主鍵後校正序號、不產生衍生資料、關鍵寫入用正式語句、涵蓋邊界形態、量測資料照容量估算的比例），schema 規格要能依序執行，多套實作以規格建出的 schema 為比對基準並連同框架表的 sequence 排除；決策記錄補兩欄

**Version**: 1.6.0 — state-storage 訪談新增「哪些資料永遠不刪、每年增加多少列」（不刪除的表的查詢讀的量、索引與清理成本、批次共用欄位的存放時機）；分片 / 分區的重評條件改以刪除耗時、索引放不放得進記憶體與清理耗時為訊號、補依時間分區的唯一約束前提

**Version**: 1.5.0 — async-queue：idempotency key 由產生端給（寫入時配的序號擋不住重送）、排程工作的最後成功時間記在共用儲存、分散式排程鎖要放在每種實作都看得到的地方；state-storage：訪談新增報表的一天依哪個時區切與事件最晚多晚寫入（摘要以 UTC 時段存、依時區組日、粒度與重算範圍由此決定），延後表新增熱點計數列拆開與摘要改寫入時累加

**Version**: 1.4.1 — 術語校正：「判準」全數改為「判斷標準」（「停止判準」改「停止條件」）。上一輪全站替換之後這個縮寫又回流，詞面在工程讀者端讀不出來

**Version**: 1.4.0 — 清掉可攜性閘門標的 5 條消費端路徑與 1 條 blog 路由。5 條全指向同一份上游專案的方法論檔，而文字明寫「不重述」「不在本維度」，判準確實不在句內——屬真依賴而非出處引用。修法不是標記也不是內聯（判準是固定方法論、不是各專案自訂的值），而是**改用語意名稱指稱**：`.claude/methodologies/event-flow-load-arbitration-methodology.md` 改成「事件流負載仲裁方法論」。這是同庫 `event-flow-arbitration-design` skill 既有的寫法（它的 `references/interview-questions.md` 指同一份方法論時就只寫名稱不寫路徑），而閘門比對的是 `.claude/` 開頭的路徑樣式，名稱不含路徑因此不需要任何豁免標記。章節名〈到達類別〉〈級別〉〈讓步與卸載順序〉保留——那是方法論自己的章節名，且在該 sibling skill 裡逐字查對過，非憑記憶反推。另移除 `references/dimensions/state-storage.md` 的 blog 路由（AGENTS.md §9 禁 blog-internal route，閘門抓不到這一類），改成描述該去哪類教材查。<!-- portability-allow: 版本歷史陳述被換掉的是什麼，路徑是史實的一部分 -->

**Version**: 1.3.0 — 事件流負載仲裁整合（先前已落地但版號未遞增，本次補記）。event catalog 表在 `references/decision-record-template.md` 與 `references/domain-event-modeling.md` 兩處各補「到達類別（等待型／自發型／推送型）」與「級別（不可棄／須留痕／可棄）」兩欄，判準指向事件流負載仲裁方法論、不在本 skill 複述。三個維度各補一段路由：async-queue（多條事件流競爭同一 worker pool／連線池時誰讓步、誰被丟、丟了怎麼留痕，並補「同一 partition 是否混流不同級別」訪談問題）、capacity-performance（降級預案的「先停哪些請求」順序判準依到達類別 × 級別，並補連線池分池／擴容的觸發條件列）、observability（進入卸載時的額外訊號——仲裁決策的可觀測事件、被丟棄請求的留痕粒度、告警綁狀態變遷而非佔用量高）。訪談流程與產出物範本一律指向 `event-flow-arbitration-design` skill。

**Version**: 1.2.3 — 清理 1 處 language-constraints.md 規則 2 禁用詞基線債務（`低代碼` → 低程式碼），純用語修正，指令內容與判準未改。

**Version**: 1.2.2 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 1.2.1 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 1.2.0 — 多輪審查修正。鏈路實證抓到「流入 proposal 驗收條件」是缺映射列的宣稱：文件維護承諾改列入 reliability 防護底線第 5 條（搭上既有「§4/5 底線→驗收條件」移交列、鏈路在檔案層閉合、只照模板填的人也不會漏）。兩處轉述失真修正：語意級假後端改標「分層之外」（v1.1.0 誤塞進 protocol integration 層、與上游教材及同段「名稱含 integration 但依賴全 fake 要辨識」自相矛盾——該層的真實服務互動由週期性真實後端驗證承擔）；適用情境「對方行為常變」刪除（上游教材裡那是重評 tripwire、搬成適用條件是方向顛倒）、改為「已出現假設錯誤型的漏網 bug」。decision-record「中途改決策回到記錄改對應段落」改為追加補記段（修掉與 append-only 宣告的檔內矛盾）。防護型測試補定義 gloss、判斷標準句補「答不出」分支的行動、訪談表 fmt 重排。冷讀輪另修：判斷標準段拆兩段（判斷標準 + 下限、後端不可控 variant）、「假設錯誤型漏網 bug」補行內 gloss、「從權威來源生成」補例、「一次性 scaffold」改「一次性產出（scaffold）」避免與 repo scaffold 語意碰撞、決策記錄模板補「## 補記」段格式示意（append-only 慣例的落地格式、免得各專案自己發明）。
**Version**: 1.1.0 — 提案階段承接「程度決策」的補強。reliability 維度：訪談問句加「還打算把哪些文件維護到最新、誰守著」（答案決定文件分級——活文件配機制、其餘明示為一次性 scaffold 或時點記錄、流入 proposal 驗收條件）；「測試寫到什麼程度」補防護視角判斷標準（每條測試答得出「未來哪種改壞要被擋」、程度下限是核心操作的改壞在合併前發聲）與語意級假後端選項（後端不可控時 stub 回放自己的假設、驗不出假設錯誤）；決策記錄要記什麼同步兩項。decision-record-template：明示決策記錄是 append-only 時點記錄、重評走新記錄不回改。references/principles/ 四張卡補「自成權威」宣告——它們是上游教材的語境化快照、消滅無機制的同步期待。
**Version**: 1.0.0 — 版號基線補標（既有內容首次標版、依版號規則）。
