---
id: IMP-LLM-002
title: "finally 區塊內的清理動作拋出例外，取代主流程的結果（綠燈、紅燈或原例外）"
severity: high
category: implementation
related: [IMP-LLM-001, IMP-BAL-010]
created: 2026-11-10
---

# IMP-LLM-002: finally 區塊內的清理動作拋出例外，取代主流程的結果（綠燈、紅燈或原例外）

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 高 |
| 分類 | implementation（例外傳遞與資源清理） |
| 來源版本 | 3.1.0 |
| 首次觀測 | 2026-11-10 |

## 症狀

合併閘門在臨時快照（detached worktree）內跑完套件後，回報的不是套件結果，而是清理命令的錯誤：

- 套件綠燈，合併卻以「合併前檢查執行失敗：Command '['git', 'worktree', 'prune']' timed out after 120 seconds」中止。
- 套件紅燈，回報原因同樣被換成上面的逾時訊息，失敗項與紅燈摘要消失。

使用者看到的是「閘門壞了」，看不到「哪個測試紅」或「其實已經綠了」。重送通常就會成功，所以容易被當成偶發而不追查。

## 根因

**Python 的 finally 內若拋出例外，該例外會取代 try 區塊原本的結果**：try 正常返回時，返回值被丟棄；try 拋出例外時，原例外降為 `__context__`，呼叫端 `except` 只會接到新的例外。

這次的結構是 contextmanager 的 `finally: _remove_snapshot(...)`，而 `_remove_snapshot` 本身又是 `try: git worktree remove ... finally: rmtree; git worktree prune`。兩層 finally 疊起來，任何一個清理用的 git 呼叫逾時（`subprocess.TimeoutExpired`），都會從最外層穿出，蓋掉閘門結果。

不易察覺的原因：

- 清理命令在正常負載下幾乎不會逾時，既有測試走過綠、紅、逾時、中斷四條路徑，每條都斷言「快照被移除」，卻沒有一條讓清理本身失敗。
- 被蓋掉的結果在輸出上和「閘門本身故障」同形，不會有人去找原本的結果。

## 解決方案

- finally 內的清理動作自行接住預期中的失敗（逾時、無法啟動的 OSError），寫 stderr 與日誌後返回，不往外拋。
- 清理的結果另外回報：例如清理完仍殘留資源時，印一行指名殘留路徑的 WARNING，不和主流程結果混在一起。
- 只接預期中的例外類型；`KeyboardInterrupt` 等中斷照常往外傳。

## 預防措施

- 寫 finally／`__exit__`／contextmanager 清理時自問：「清理失敗時，呼叫端應該看到主流程的結果，還是清理的錯誤？」答案幾乎都是前者，清理就不該往外拋。
- 清理的測試除了「各出口路徑都有清理」，再加一組讓清理本身失敗（monkeypatch 清理呼叫拋逾時）的案例，斷言主流程結果仍是原本的綠燈或紅燈原因。此組要先在未修正的程式上確認為紅（正向對照）。

## 實證（正向對照）

三個測試：清理逾時時綠燈仍合併、紅燈仍回報原原因、目錄殘留時另印「快照未移除」。只還原修法後三者全紅，錯誤訊息即上述 prune 逾時；放回修法後全綠。

## 關聯

- 本 repo 的修法與測試記錄在發現版本的票面（依框架禁引用專案識別符規則，此處不寫票號）。
- 涉及檔案：`.claude/skills/worktree/scripts/merge_gate.py`（`merge_snapshot`、`_remove_snapshot`）、`.claude/skills/worktree/tests/test_merge_gate.py`。
