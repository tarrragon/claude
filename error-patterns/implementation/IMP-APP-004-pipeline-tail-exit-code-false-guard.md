---
id: IMP-APP-004
title: 防呆判斷取 pipeline 末端命令 exit code——head/tail 恆 0 使守衛必觸發或必靜默
severity: medium
category: implementation
created: "2026-07-14"
source_tickets: [0.38.1-W1-067]
related_patterns: [IMP-008, IMP-009]
---

# IMP-APP-004: pipeline 末端 exit code 假守衛

## 症狀

以 `cmd | filter && echo ALARM`（或 `|| echo OK`）形式撰寫的防呆檢查產生與事實相反的判定：無命中卻報警，或有命中卻靜默。

**識別特徵**：
- 判斷條件掛在 pipeline 之後（`&&` / `||` / `if`），而 pipeline 末端是 `head`、`tail`、`sed`、`awk` 等「無論輸入有無都 exit 0」的過濾器。
- 警報訊息與其上方實際輸出內容矛盾（如印出「!! 異常 !!」但其前無任何命中行）。

## 實證案例（0.38.1-W1-067 merge 防呆，2026-07-14）

```bash
git diff ... | grep -E '^\+' | grep -oE 'UC-10\.[0-9]|UC-[0-9]{3}' | head -3 && echo "!! 異常 !!"
```

實際無任何命中（grep exit 1），但 `head` 恆 exit 0，`&&` 必觸發——輸出「!! 異常 !!」誤報，PM 需額外一輪以計數邏輯重驗才排除。POSIX shell（非 pipefail）下 pipeline exit status 取**最後一個命令**，`grep` 的 0/1 語意被 `head` 吞掉。

## 根因

1. `grep` 的 exit code 語意（0=命中/1=無命中）只在 grep 是 pipeline 末端時可用；接上任何過濾器即失效。
2. 防呆指令通常是臨場手寫、未經測試——守衛本身沒有被驗證過「兩種輸入下是否給出兩種判定」。

## 解決方案

防呆判斷改用下列任一形式，使判定值不依賴 pipeline 末端 exit code：

```bash
# 1. 計數比較（首選：判定值是資料不是 exit code）
count=$(cmd | grep -oE 'PATTERN' | wc -l | tr -d ' ')
echo "count=${count}（應 0）"

# 2. grep 收尾（不接過濾器，-q 或 -c 直接當末端）
if cmd | grep -qE 'PATTERN'; then echo "!! 異常 !!"; fi

# 3. bash 限定：set -o pipefail（zsh 亦支援），使 pipeline 取第一個非零
```

## 預防措施

- 手寫防呆時自問：「此判斷取誰的 exit code？」pipeline 有過濾器則一律改計數比較。
- 守衛輸出設計為「印出判定依據的資料」（count=N）而非純布林警報——資料與警報矛盾時可即刻自我暴露（本案例即靠此發現誤報）。
- 對照 `.claude/rules/core/bash-tool-usage-rules.md` 規則二（輸出機制辨識）：該規則管輸出量，本 pattern 管 exit code 語意，兩者於「pipeline 尾端接 head/tail」場景疊加生效。
