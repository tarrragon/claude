# 裝飾符號掃描：emoji 與視覺記號是輪 8 keyword bank 的盲點

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 `writing-articles.md` 輪 8 keyword bank 與 `SKILL.md` 第 6 原則引用。
>
> **何時讀**：寫完文章、跑 multi-pass review 輪 8 keyword bank 時、要把裝飾符號加入 grep 掃描清單；或檢視當前專案規範對裝飾符號的政策。

## 為什麼這是基本 5 輪 frame 抓不到的盲點

裝飾符號（emoji / 裝飾性 unicode）對寫作者來說有「**結構化視覺輔助**」的心理範疇 — 寫的時候是「我用 ✅ ❌ 讓表格更清楚」的好用工具、不會自動分類成「字句層 issue」。基本 5 輪 frame（生成 / 對意圖 / 機會成本 / grep-ability / 反例）跟其他輪 8 keyword bank（口語修辭 / 廢話前綴 / 地區漂移 / 依賴 code）的設計都沒涵蓋到這類「自以為是結構、實際是裝飾」的符號。

要靠輪 8 的「**換工具、不依賴記憶**」設計 — 把 emoji 列進 grep keyword pattern、強制每次跑。

## 掃描清單

寫完每篇 production 文章後、跑這個 grep：

```bash
rg "✅|❌|⚠️|🚨|🟡|🟢|🔴|🟠|🔵|⭐|📌|💡|⚡|🎯|✨|📝|🔍|🛠|⛔|✓|✗|✘" path/to/article.md
```

涵蓋三類符號：

| 類別         | 範例           | 為什麼進清單                      |
| ------------ | -------------- | --------------------------------- |
| 狀態 emoji   | ✅ ❌ ⚠️        | 表格 status 最常用、最容易遺漏    |
| 強調 emoji   | 🚨 🔴 ⭐ 📌 💡 | 行內 / 段首視覺強調、心理範疇模糊 |
| 裝飾 unicode | ✓ ✗ ✘          | 看起來像 typography、實際是符號   |

## 各專案規範不同、依本地 spec 判定

裝飾符號的可接受度跨專案差異大、本 principle 不主張禁用、只主張**強制掃描 + 依規範判定**：

| 專案類型                     | 常見規範                                                   |
| ---------------------------- | ---------------------------------------------------------- |
| 技術文章 / 工程 blog         | 通常禁用（grep-ability、CLI 相容、語意結構優先於視覺裝飾） |
| 教學部落格 / 科普內容        | 可能鼓勵用（降低閱讀門檻、增加親和力）                     |
| 內部 worklog / lint pipeline | 因 multi-byte CLI parser bug（Rust panic）通常禁用         |
| API / SDK 文件               | 通常禁用（讀者可能用 plain-text 終端機 / screen reader）   |

跑 grep 列出所有位置後、依該專案的 SSoT（AGENTS.md / markdown spec / style guide）判定：

- **「禁用」場景** → 全部替換（替換策略見下節）
- **「允許」場景** → 確認沒有過度使用、不依賴 emoji 承載語意（去掉 emoji 後段落仍能讀懂）

## 替換策略（禁用場景）

**核心原則**：emoji 承載的語意要回到文字結構、不是純粹拿掉符號。直接 `sed` 刪除會讓「✅ 不需 CRL infrastructure」變「不需 CRL infrastructure」、讀者無法判斷這是優點還缺點。

| 原寫法                                              | 改成                                                        |
| --------------------------------------------------- | ----------------------------------------------------------- |
| 表格 status `\| ✅ 解了 \|`                         | 純文字描述：「解了」/「是」/「適用」                        |
| 表格 status `\| ❌ 漏 \|`                           | 純文字描述：「漏」/「否」/「不適用」                        |
| 表格 status `\| ⚠️ 部分 \|`                          | 純文字描述：「部分」/「條件性」/「視情境」                  |
| 列表優缺點 `- ✅ 簡單` / `- ❌ 慢`                  | 拆成 `**優點**：簡單` / `**缺點**：慢` 段落或標題段         |
| 列表錯誤示範 `- ❌ 把 key 寄 email` / `- ✅ 用 CSR` | 拆成 `**錯誤做法**：` / `**正確做法**：` 標題段             |
| 行內視覺強調 `🚨 critical`                          | markdown 粗體 `**critical**` 或引用塊 `> **critical**：...` |

## 移除後要驗證結構完整

emoji 移除後、要 re-read 每一處替換、確認：

1. **語意是否完整**：讀者不看上下文、能否知道這段是「優點 / 缺點 / 錯誤示範 / 正確做法」？
2. **表格對齊是否歪掉**：emoji 寬度通常算 2 個 ASCII char、移除後右半邊變短、需要重跑對齊工具（mdtools fmt / prettier）
3. **空 cell 是否補回**：若 emoji 是該 cell 唯一內容（如「❌」單獨一格）、移除後變空、要補回文字描述（「不支援」/「漏」）

## 跟相關 principle 的關係

- 跟 [colloquial-rhetoric-erodes-technical-precision](colloquial-rhetoric-erodes-technical-precision.md)：同屬輪 8 keyword bank 的 catch、但 colloquial 抓「文字選詞」、本卡抓「符號選擇」
- 跟 [multi-pass-review-frame-granularity](multi-pass-review-frame-granularity.md)：本卡是「換工具」這個 frame 機制的具體應用、補強基本 5 輪沒涵蓋的字句層 pattern
- 跟 writing-articles.md 「層次意識」段（emoji 當視覺修補的反例）：那段討論「emoji 蓋語意問題 = false confidence」的反模式、屬語意層；本卡聚焦於「字句層的純掃描與替換」、屬字句層工具
