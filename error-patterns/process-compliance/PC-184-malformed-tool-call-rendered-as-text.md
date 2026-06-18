> **編號溯源（native intruder 讓位）**：本 pattern 為本專案原生（非框架 canonical）。先前不對稱 push 誤把它推上框架 PC-177 號，使上游 PC-177 同時承載框架 canonical（defensive-rule-mechanical-overapplication）與本 native intruder 兩 slug。本專案於 1.2.0-W1-039 將本 pattern 讓位重編為 PC-184（全索引對照確認 184 為 next-free canonical）。上游殘留的 `PC-177-malformed-tool-call-rendered-as-text.md` 為應清除的孤兒（canonical 是 defensive，PC-177 不該由本 native 佔用）；上游 PC-177-defensive 由本地 PC-181（lineage 認領）保護，不受本讓位影響。

# PC-184: malformed tool-call 被當文字渲染而未執行

## 症狀

工具呼叫標記寫壞被當純文字渲染，工具靜默未執行——使用者只看到一段標記文字，需手動喊重送。成因為模型於 invoke 標記前混入游離 token（本案反覆為字面 count）或漏 antml 命名空間前綴，harness 無法解析成 tool call。重發常二次失敗，使單步反覆卡住。0.20.0 W2 session 重現 15 次以上。

## 根因

輸出層機率性 token 故障，非邏輯錯誤，無法靠規則或心智自律根除。

關鍵時序：失敗發生在 tool call 存在之前。PreToolUse 觸發點在已解析 tool call 即將執行之後，壞掉的呼叫從未成為 tool 事件，PreToolUse 結構上接不到。常見錯誤直覺是想用 PreToolUse 攔，必須破除此直覺。

## 案例

0.20.0-W2-011：Tag model TDD 途中反覆於 invoke 標記前混入游離 token，使用者要求先修；嘗試 PreToolUse 被否決，改 Stop hook 成功。

## 防護

不處理則工作流靜默中斷，commit／派發／驗證自動化在不知根因下失敗，使用者反覆人工介入。

修法用 Stop hook：回合結束讀 transcript 最後一則 assistant 訊息，剝除 fenced code block、inline code 與縮排 code block 避免誤判，偵測未解析標記簽章，命中即 exit 2 阻擋並要求重發；hook 需 shebang 與 exec bit（缺二者會 Permission denied）。正常討論本失敗形態的散文，可放顯式 exempt marker 整段豁免。人工修法：重發時標記前無游離字、用正確 antml 前綴。實作見 .claude/hooks/malformed-tool-call-detector-hook.py。

## 相關

- 失敗模式的個人經驗教訓與重發要點：memory feedback_malformed_tool_call_text_render
- 偵測器實作與簽章邏輯（含 strip 範圍、內嵌 self-test、meta-context 豁免 marker）：.claude/hooks/malformed-tool-call-detector-hook.py

---

Last Updated: 2026-06-06 | Source: 0.20.0-W2-011
