# 5w1h-decision 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.3.2 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 1.3.1 — portable 修復：Related Files 的 Output Style 從 markdown 連結改為純路徑——目標檔在本專案就不存在、連結承諾了一個打不開的東西。同步補上 frontmatter 的 metadata.version（原本只有文末版本紀錄、兩個住址不一致）

**Version**: 1.3.0 — 聯動改成觸發式：協作觸發點接進 neurodivergent-output 的帳本規則（每則都跑）、5W1H rows 跟著帳本自動出現、不是獨立附錄靠記憶（對應 #239 修法從「事後偵測」升級為「預防：接到會觸發的行為上」）。
**Version**: 1.2.0 — Collaboration 段加「驗證它真的現形、別只宣告」：兩 skill 同開時逐則檢查帳本決策行是否真用壓縮 5W1H、費力那半會靜默掉（對應 report 卡 #239 宣告的組合≠執行的組合、從 neurodivergent-output + 5w1h 同開卻漏跑 5w1h 的自我示範抽出）。
**Version**: 1.1.0 — 新增 Collaboration 段：當 neurodivergent-output 也啟用時，決策以壓縮形式進其跨訊息帳本、遵守帳本的認知負荷規則（不傾倒全 6 欄 / token / agent 鷹架）、避風港語言偵測範圍限決策內容不管輸出形狀、PDA mode 開時 gate 轉成邀請。單獨運行不受影響、互不依賴。
**Version**: 1.0.0
