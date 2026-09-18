# event-flow-arbitration-design 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.2.0 — 多輪審查 Round 2 修正。分池判準與方法論對齊（訪談問句由「成本差幾個數量級」改為「兩種計法對現在該不該卸載給出同一個答案嗎」，數量級降為代理判準）；協調圖併入第一步產出物（落地表要求交出它而流程無一步產出）；訪談檔補「沒有受訪者時各步的查法」（問句原預設有受訪者，代理人對既有程式碼執行時不知答案在哪）；範本補「落點不存在時」的處置與仲裁器所在執行緒欄，末段補測試義務路由；範例檔的 isolate 場景改引通道表的事件迴圈列（原引 worker pool 的可中斷點規則，兩列是不同通道）、末節更名為「套用時的三個常見誤解」並把與方法論重複的條件清單改為路由；級別標定範例的依據文字改為與不可棄判準一致；標定表落點統一為 domain map 子表。

**Version**: 1.1.0 — 多輪審查 Round 1 修正。可變計數去實例化：〈六步流程〉標題改〈執行流程〉、「六份範本」「七項欄位」「每步 3-5 題」改引用權威名稱（規則 10，步數與欄位集合各自的權威是方法論〈執行步驟〉與〈可觀測性〉）。`worked-examples.md` 整檔重寫：刪去「初稿／定稿／審查」的過程敘事改條件視角（該敘事在 sync 至其他 consumer 後無對應歷史）、段標「當時卡住處」改「易誤套形態」、場景 (b) 標題移除產品身分與平台限定詞。`templates.md` 修兩處範例——級別標定依據由產生方視角改接收方丟棄後果（原值與〈級別〉的鍵相反，照抄即違反判準）、卸載閾值範例補來源標註並要求填表者寫出數字怎麼來；新增〈產出物落地〉節，補各產出物的落點與容量失敗訊號的交接內容。`interview-questions.md` 步驟 4 首問補齊自發型不可棄格（原宣告三格只交付兩格）。分工表對 domain-map 的路由補明確路徑與權威歸屬。

**Version**: 1.0.0 — 初版建立。SKILL.md 定位（方法論管判準、本 skill 管流程）、觸發條件、六步流程（對應事件流負載仲裁方法論〈執行步驟〉）、與 saas-tech-selection／foundation-design／doc domain-map 的分工；`references/interview-questions.md` 六步各 3-5 題訪談問句附「為什麼問」；`references/worked-examples.md` 三場景（HTTP API 共用連線池、Flutter 多 isolate、訊息消費者混流）各含套用結果／當時卡住處／方法論現行對應判準三段，改寫自方法論定稿前的高負載工程視角審查材料；`references/templates.md` 六份產出物範本，欄位與方法論條文一致。同時把 `saas-tech-selection` 的 async-queue／capacity-performance／observability 三維度與 `event-architect-reference` 的既有路由句改為同時指向方法論（判準）與本 skill（流程）。
