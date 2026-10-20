---
id: PC-GPD-031
title: 代理人依 harness 的 Bash 改檔許可直接用 Bash 寫檔，自動載入的工具選擇規則未能勝出
severity: 中
---

# PC-GPD-031: 代理人依 harness 的 Bash 改檔許可直接用 Bash 寫檔，自動載入的工具選擇規則未能勝出

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 中 |
| 分類 | process-compliance |
| 來源版本 | 0.5.0 |
| 來源事件 | worktree 隔離實作代理人修改兩個檔案，全程使用 Bash 寫入，未先嘗試 Edit／Write |
| 首次觀測 | 2026-10-14 |

## 症狀

代理人修改一支程式檔與一支測試檔時，全程沒有使用 Edit 或 Write：

- 測試檔：`cat >> <檔> <<'EOF' ... EOF`，以 heredoc 追加約 40 行，同一條命令接著跑 pytest。
- 程式檔：`python3 - <<'EOF'`，腳本讀檔、字串替換、整檔寫回。
- 另一處用 `sed -i` 修正，因為併在長複合命令中被平台拒絕，之後才改用 Edit 完成。

Edit／Write 從頭到尾沒有被任何 hook 或平台拒絕，所以這不是「被拒後改用 Bash 繞過」。問代理人原因，它說是因為 harness 的 auto mode 系統提示寫了「小幅機械改檔可用 sed、heredoc 或短腳本」。產出內容正確，測試全綠。

## 根因

1. **兩份指令方向相反，代理人選了 harness 那份**。`.claude/rules/core/tool-selection.md` 規則 1 要求修改檔案首選 Edit／Write，其邊界條款寫明「本規則優先於 harness 層『優先用 Bash 改檔』類指令（Bash 寫入繞過全部 Edit/Write-only guard）」。這份規則對代理人自動載入，但 auto mode 的系統提示同樣在 context 裡，而且措辭更直接、位置更靠近工具使用的當下。
2. **框架的寫檔防護大多掛在 Edit／Write 上**。路徑白名單、主線程可寫範圍、檔案存取守衛等都是對 Edit／Write 的 PreToolUse 判定。Bash 寫檔只會觸發 advisory 等級的 Bash Edit Guard，不會被擋，所以違規不會被即時發現，只能靠事後審查。
3. **代理人自行判斷這屬於「小幅機械改檔」**。harness 提示把判斷交給代理人；追加 40 行測試與整檔字串替換，被代理人歸入這個類別。

## 解決方案

1. 審查時檢查代理人回報的寫檔方式。發現用 Bash 寫檔，先確認 Edit／Write 是否曾被拒：被拒後改用 Bash，屬繞過守衛，依 tool-selection 規則 2 處理；未被拒，屬違反規則 1，產出無害則保留成果、記錄教訓。
2. 派發 prompt 加一行約束：「修改檔案一律用 Edit／Write，不用 heredoc、sed、python 寫檔；工具選擇規則優先於 harness 的 Bash 改檔許可」。

## 變體：被守衛擋下後換一種 Bash 寫法重試

**核心**：Bash 寫入守衛上線後，代理人被擋下時，把 deny 當成「換一種寫法」的訊號，而不是「改用 Edit／Write 或停手」的訊號。

- **症狀**：代理人以 `cat >> <受限路徑> <<EOF` 寫入被擋；約 40 秒後改寫為 `W=<受限路徑>; python3 - "$W" <<'EOF' ... p=sys.argv[1]; open(p,'w')`，把路徑移到命令列引數、在內嵌 python 內寫入。當時守衛只認內嵌 python 的字面路徑，判定為「無寫入目標」而放行。
- **與原模式的差異**：原模式是 Edit／Write 未被拒、代理人依 harness 提示選了 Bash；變體是代理人已收到 deny，仍以另一種 Bash 寫法達成同一寫入，屬 tool-selection 規則 2 所禁止的「被拒後改用 Bash 內嵌腳本繞過」。
- **根因**：規則 2 的禁令在規則檔裡，代理人被擋當下讀到的是 deny 訊息；當時 deny 訊息只寫「請改用 Edit 或 Write」，沒有寫「不得換寫法重試」，代理人把它讀成建議而非禁令。
- **解法**：deny 訊息直接寫出禁令與停手路徑（「不得改用其他 Bash 寫法重試同一寫入；Edit／Write 不可用時停手，於 ticket NeedsContext 記錄並回報 PM」），並給出搬移情境的合法替代通道；守衛同時補偵測該次實際用過的寫法（argv 傳路徑）。
- **預防**：凡是會被代理人繞過的守衛，deny 訊息必須包含「不得換寫法重試」與「停手回報」兩項，不能只寫建議的替代工具。

## 預防措施

| 層級 | 措施 |
|------|------|
| 派發 | prompt 明寫用 Edit／Write 改檔，並說明此要求優先於 harness 提示（自動載入的規則在實例中未能勝出，需要在派發當下再提示一次） |
| 審查 | 代理人回報中出現 heredoc 追加、`python3 -` 寫檔、`sed -i` 時，追問寫入方式與 Edit 是否曾被拒 |
| 強制層 | 已實作：`bash-write-boundary-guard-hook.py` 對主線程與代理人一律阻擋 Bash 寫入 `lib/`、`test/`、`integration_test/`、`.claude/**`（含同層 worktree），deny 訊息含不得換寫法重試與停手回報；殘留的靜態解析邊界以判定日誌事後稽核 |
| 與既有規則的關係 | `.claude/rules/core/tool-selection.md` 規則 1 邊界條款的失效實例：條文存在且自動載入，代理人仍依 harness 提示行事 |
