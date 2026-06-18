# 決策閘門預算 + 退場機制（詳細 SOP）

本檔為 `rules/README.md`「決策閘門預算原則」的按需讀取詳細版。涵蓋退場判準、Hook 執法檢查、降級程序、熱路徑前移指引。

> **來源**：1.2.0-W1-009 ANA（WRAP 全程量測）。pm-rules 決策檔複雜度由 incident 防禦增生驅動（量測：46 種 PC、259 次引用），非樹結構深度。對應概念為中介層鏈的短路求值 + 快取退場，非樹平衡演算法。

---

## 為何需要這條原則（Why）

每次 incident（PC-XXX）發生後，防護機制傾向在決策 routing 檔留下一段 inline prose 守衛。這個生長是單向的——加進去容易，沒有任何機制把它移出去。

**量測證據**：`decision-tree.md` 的 PC 引用數（22）超過其決策分支數（17）；`ticket-lifecycle.md` 防禦引用（26）是決策邏輯（7 分支）的 3.7 倍；`completion-checkpoint-rules.md` 零分支卻有 11 次 PC 引用。複雜度與防禦引用密度正相關、與樹深反相關。

**Consequence（不治理的後果）**：routing 檔持續膨脹，每則訊息都要穿越所有累積的防禦閘門，才到達真正的決策點；auto-load 預算被防禦 prose 擠佔；最高頻決策（如「問題 vs 命令」）被埋在防禦層之後。最終決策變慢，且重構一次後會以同速率重新增生（生長機制未變）。

---

## 規則一：inline 防禦引用預算上限

**Action**：單一 routing 檔的 inline PC 防禦引用上限為 8。超過時，將最舊的、或已被 Hook 強制執法的防禦段外移至 `references/`，routing 檔保留一行指標（路由表一列）。

**驗證指令**：

```bash
grep -oE 'PC-[0-9]+' <routing-file>.md | wc -l    # 引用次數
grep -oE 'PC-[0-9]+' <routing-file>.md | sort -u  # 不重複種類
```

> 上限 8 為經驗值，依專案 routing 檔規模調整。重點是「有上限且觸頂觸發外移」，而非數字本身。

---

## 規則二：退場判準（核心）

退場判準綁定一個客觀事實——**該 PC 是否已有 Hook 強制執法**——而非主觀的「是否還重要」。

| 防禦型態 | 判定 | 處置 |
|---------|------|------|
| 該 PC 已有 PreToolUse / PostToolUse / SessionStart Hook 強制 | prose 屬「文件」，執法歸 Hook | 降級至 `references/`，routing 留一行指標 |
| 純人工判斷、無 Hook 可強制 | prose 是唯一防線 | 保留精簡 inline（仍受規則一上限約束） |

**Why（為何綁 Hook 存在性）**：Hook 是執法層，routing prose 是文件層。當 Hook 已強制某防護，inline prose 只是重述已被自動執行的規則——它是 documentation，不是 enforcement。降級它不削弱防護（Hook 仍執法），只是把文件移到按需層。這同時規避 `quality-baseline.md` 規則 6「流程瑕疵不回退」的衝突：執法不消失，僅 prose 位置改變。

**Hook 執法檢查指令**：

```bash
# 確認某 PC 是否已有對應 Hook 強制
grep -rln "PC-XXX" .claude/hooks/
grep -rln "PC-XXX" .claude/settings.json   # 確認該 hook 已註冊
```

兩者皆命中 → 該 PC 已 Hook 化，prose 可降級。

**Consequence（綁主觀判準的後果）**：若退場判準是「是否還重要」，等同沒有判準——任何防禦都能被論證為「還重要」，閘門永不退場。綁客觀的 Hook 存在性使退場可驗證、可自動偵測。

---

## 規則三：熱路徑前移 + 防禦閘門 lazy 化

**Action**：

1. 最高頻 discriminator（如「問題 vs 命令」「Skill 匹配」）置於決策漏斗最前，使常見決策最快到達。
2. 防禦閘門改為 lazy——只在其觸發訊號實際出現時才評估，而非每則訊息無條件穿越。

**對應概念**：短路求值（short-circuit evaluation）。守衛條件廉價可跳過時，不對每個輸入支付完整守衛成本。

**Why**：防禦閘門多為低頻情境（如並行 session 衝突、AC 漂移），但若置於漏斗前段且無條件評估，會讓 100% 的訊息為 < 5% 的情境付出穿越成本。前移高頻 discriminator + lazy 化低頻守衛，使平均決策路徑長度大幅下降。

---

## 與其他規則的邊界

| 規則 | 分工 |
|------|------|
| `auto-load-stub-conventions.md` | 處理「auto-load 層 token 預算」的外移 SOP；本檔處理「決策 routing 檔的防禦增生預算」，兩者同構但作用對象不同 |
| `quality-baseline.md` 規則 6 | 流程瑕疵不回退；本檔退場判準綁 Hook 執法存在性，確保退場不削弱防護，與規則 6 不衝突 |
| `decision-trigger-binding.md` | 延後決策須綁 ticket trigger；本檔退場是「已決策的降級動作」，非延後 |

---

**Last Updated**: 2026-06-18 | **Version**: 1.0.0 — 從 1.2.0-W1-009 ANA 落地（決策閘門預算 + 退場機制）。**Source**: WRAP 全族量測（46 PC / 259 引用）。
