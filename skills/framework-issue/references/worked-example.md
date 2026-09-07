# 完整走查

一個主題從查重到 check 的全程。票 ID 與 comment id 皆為示意值，issue 編號沿用框架 repo 已存在的張數以便對照。

- [情境](#情境)
- [查重輸出與關係判定](#查重輸出與關係判定)
- [sections.json](#sectionsjson)
- [init 與索引](#init-與索引)
- [ticket close](#ticket-close)
- [check 與 owner 更新](#check-與-owner-更新)

## 情境

主題「hook 註冊清單一致性」有四張 pending 票：兩張 ANA（分析三份註冊清單為何不同步、稽核豁免清單理由）、一張 IMP（對帳工具）、一張 DOC（補 hook 操作文件）。ANA 票的 Problem Analysis 各累積三輪，第二輪推翻了第一輪對「大小寫偵測永不觸發」的歸因。本 session 識別為 `flutter-balance-77`。

## 查重輸出與關係判定

```bash
python3 .claude/skills/framework-issue/scripts/section_comment.py dedup \
  --keywords "hook" "註冊" "settings.json" "豁免"
```

輸出（節錄）：

```
[framework-issue] 查重關鍵字集合（4 組）：['hook', '註冊', 'settings.json', '豁免']
## 關鍵字「註冊」（6 則命中）
  - #53 [open] hook 註冊清單三份不同步且偵測器自身失效：重複註冊、大小寫偵測永不觸發、豁免清單無對帳
  - #68 [open] sync-pull 對上游 hook 改名移位只 auto-register 新路徑、不移除舊註冊
  - #11 [open] settings.local.json 幽靈 hook 註冊阻擋所有 Agent 派發
...
查詢失敗略過的 token 數：0
```

關係判定（讀 body 與 comment，不看標題）：

| 命中 | 關係 | 依據 | 處置 |
|------|------|------|------|
| #53 | 重複 | 同一問題領域（三份清單不同步）、同一層級（hook 註冊機制） | 落點，`init` 於此 |
| #68 | 引用 | 領域是 sync-pull 的註冊處理，不是清單一致性 | 「問題清單與根因」內單向指向 |
| #11 | 切分 | 同領域（註冊），但層級是單一 consumer 的 local 設定殘留 | 本次不動，「當前結論」附一句分工 |

#53 是 body-only 舊 issue，尚無區段，可 `init`。

## sections.json

寫到 scratchpad（不入版控）。「當前結論」只留現在成立的：第一輪對大小寫偵測的歸因已被第二輪推翻，只留撤回記錄。四張票有徵狀、有方案取捨、有 IMP，三個區段都建；完整來源票對照住在派發票 Solution，issue 端只留一行指回。

```json
[
  {"name": "當前結論", "content": "## 當前結論\n\n三份 hook 註冊清單（settings.json、hook-exclude-list、completeness-check 的內建清單）各自維護，不同步的根因是沒有單一 SSOT，不是任一份寫錯。大小寫偵測永不觸發的原因是比對前先做了 lower()，與第一輪判定的「正則錯誤」無關（原判見來源票 <ana-1>，經 <ana-1> 第二輪實測推翻）。\n\n方案採 settings.json 為 SSOT，另兩份改為由它推導；豁免清單每條理由須指名對應 hook 檔名，否則對帳無法機械化。\n\n與 #11 分工：本 issue 管 canonical 三份清單，#11 管 consumer 端 settings.local.json 殘留。\n\n**狀態**：方案已定，對帳工具未做，見待辦與來源。"},
  {"name": "問題與方案", "content": "## 問題與方案\n\n| 徵狀 | 根因 | 實證 |\n|------|------|------|\n| 同一 hook 註冊兩次 | 三份清單無 SSOT | <ana-1> 對帳 112 筆 |\n| 大小寫偵測永不觸發 | 比對前 lower() | <ana-1> 第二輪 |\n| 豁免理由與 hook 對不上 | 理由為自由文字 | <ana-2> 稽核 37 條 |\n\n相關但不同領域：sync-pull 改名不移舊註冊見 #68。\n\n### 方案\n\n| 方案 | 取捨 |\n|------|------|\n| settings.json 為 SSOT（採） | 現有 hook 已讀它；代價是 exclude-list 要改成推導 |\n| 新建 registry.yaml | 多一份要同步的檔，與問題同形 |\n\n未驗證假設：推導後 SessionStart 耗時是否可接受，待對帳工具落地後量。"},
  {"name": "待辦與來源（flutter-balance）", "content": "## 待辦與來源（flutter-balance）\n\n| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n|--------|--------|----------------|--------|------|------|\n| <imp-1> | 對帳工具：讀三份清單輸出差集 | 4 | P1 | 本版 | 待裁票 |\n| <doc-1> | hook 操作文件補 SSOT 章節 | 2 | P2 | 對帳工具後 | 待裁票 |\n\n來源票對照：本 consumer 派發票 <dispatch-id> 的 Solution。"}
]
```

## init 與索引

```bash
python3 .claude/skills/framework-issue/scripts/section_comment.py init 53 \
  --owner flutter-balance-77 \
  --sections-file <scratchpad>/sections.json \
  --dedup-keywords "hook" "註冊" "settings.json" "豁免"
```

輸出是查重報告（與 `dedup` 相同）接一行回填結果；區段建立本身不逐段印訊息，成功與否看末行：

```
[framework-issue] 查重關鍵字集合（4 組）：['hook', '註冊', 'settings.json', '豁免']
...
查詢失敗略過的 token 數：0
body 區段索引已回填 @ 53
```

區段 comment 的 id 從 `show` 或 body 索引取得。

`init` 對 body-only 舊 issue 不補協定標記，補一次：

```bash
gh issue view 53 --repo tarrragon/claude --json body -q .body > body.md
printf '<!-- fw-issue-schema: comment-as-section v1 -->\n\n%s' "$(cat body.md)" > body2.md
gh issue edit 53 --repo tarrragon/claude --body-file body2.md
```

這是 body 唯一的第二次手動寫入，之後不再動 body。

## ticket close

四張票依序 close，父票或被 `blockedBy` 指向的票最後：

```bash
for t in <ana-1> <ana-2> <imp-1> <doc-1>; do
  ticket track close "$t" --resolved-by none \
    --reason not_executable_knowledge_captured \
    --reason-note "分析 context 已遷至 tarrragon/claude#53（區段：當前結論）"
done
```

reason-note 若寫成「移到 #53」會被拒：

```
[Error] resolved_by / reason_note 含延後語意（延後/移到/後續）。
```

## check 與 owner 更新

```bash
python3 .claude/skills/framework-issue/scripts/section_comment.py show 53
python3 .claude/skills/framework-issue/scripts/section_comment.py check 53
```

剛 init 完三項皆未命中。九天後另一 consumer 以 `observe` 附加「推導後 SessionStart 多 1.8 秒」，SessionStart hook 對本專案擁有的 issue 跑 `check`，主警訊輸出：

```
[警訊 B][主警訊] 觸發：「當前結論」updated_at=<T0> 落後最新觀測 <T0+9d>，超過設定期間 7 天
  當前結論之後新增的觀測 comment：
  - https://github.com/tarrragon/claude/issues/53#issuecomment-<id-9>
[警訊 A][輔助] comment 數 4 未超過閾值 30（略過）
[警訊 C] 索引一致：3 筆
```

owner 讀該觀測，把「未驗證假設」改為量測結果，以 `update <id-1>` 回寫「當前結論」；觀測 comment 本身不動。這一步是協定裡唯一會讓「當前結論」持續反映現況的動作。
