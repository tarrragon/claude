---
id: PC-145
title: Stale CLI install 偽裝為 validator bug — 修改源碼後未 reinstall 導致誤判修復未生效
category: process-compliance
severity: medium
created: 2026-05-13
related:
 - IMP-023
 - ARCH-020
 - W10-125
---

# PC-145: Stale CLI install 偽裝為 validator bug

## 症狀

修改 `ticket_system/` 源碼後立即執行 `ticket track complete` 仍命中既有 validator false positive。檢查源碼確認修復已生效（pytest 全綠），但 CLI 端仍回報舊 validator 行為，造成「修復沒落地」的錯覺。

`uv run python -c "from ticket_system.lib.ticket_validator import _is_placeholder ..."` 直接呼叫源碼會正常通過；唯獨 `ticket` 全局命令使用舊版。

## 觸發情境

| 條件 | 說明 |
|------|------|
| 修改 `.claude/skills/ticket/ticket_system/` 內 Python 源碼 | 主要修復點 |
| 未執行 `uv tool install .claude/skills/ticket --reinstall` | CLI 仍指向先前安裝版 |
| 立即執行全局 `ticket` 命令驗證修復 | 看到「舊行為」 |

## 根因

### 根因一：uv tool install 不自動偵測源碼變動

`uv tool install` 將套件複製到 `~/.local/share/uv/tools/` 並建立 entry-point shim 在 `~/.local/bin/`。後續 `ticket` 命令固定指向已安裝版本，不會 reload 原始碼。

### 根因二：IMP-023 規則文件存在但易忘記

IMP-023 已記「修改原始碼後必須重新安裝」(`uv tool install . --reinstall`)，但 PM 在 TDD 流程中常專注於測試 / commit，未在 commit 後或 complete 前回顧此規則。

### 根因三：症狀偽裝為 validator bug

```
[Error] body 未依 IMP schema 填寫必填章節
   未填寫的必填章節：- Test Results
```

訊息層次：CLI 報「validator 邏輯」結論，但實際底層是 stale install 的 CLI 仍呼叫舊 validator。PM 第一反應是檢查源碼 / pytest（皆通過），易陷入「找不到原因」的調試循環。

## 防護措施

### Layer A：作者端 SOP（觀察可行）

ticket_system 源碼修改 → commit 前 SOP：

```bash
# 1. 改源碼 + 寫測試 + RED-GREEN
uv run pytest ...  # 確認測試綠

# 2. 重新安裝 CLI（IMP-023 強制）
uv tool install .claude/skills/ticket --reinstall

# 3. 用全局 ticket CLI 端到端驗證
ticket track ...  # 不再撞牆

# 4. commit
git commit -m "..."
```

### Layer B：CLI 端 fallback（治本待落地）

選項一：在 `ticket` 入口加 source freshness check（比對 entry-point 安裝時間 vs ticket_system 源碼 mtime），若源碼較新發出警告。

選項二：將 ticket 改為 `uv run` 模式（每次執行重讀源碼），但啟動成本上升。

### Layer C：PM 端 debug 順序（撞牆時 fast diagnosis）

當看到 validator 報告與直觀矛盾的結論時，先做以下三步：

1. `(cd .claude/skills/ticket && uv run python -c "from ticket_system.lib.ticket_validator import _is_placeholder; ...")` 直接測源碼
2. 比對 `which ticket` 指向位置與源碼 mtime
3. 若直測通過但 CLI 不通過 → `uv tool install --reinstall` 必為下一步

## 歷史案例

- 2026-05-13 W10-125（首例）：W10-125 修復 `_is_placeholder` 表格情境豁免，源碼測試全綠，CLI complete 仍報「Test Results 未填寫」誤判（CLI 用舊 validator）；`uv tool install --reinstall` 後解決。
- IMP-023（前置案例）：歷史已記錄此規則但未專項命名 PC，現補建 PC-145 作為偵測 + SOP 雙通道。

## 與相關 error-pattern 的差異

| Pattern | 性質 | 場景 |
|---------|------|------|
| IMP-023 | implementation rule | 修改源碼必須 reinstall（陳述規則） |
| **PC-145（本）** | process compliance / debug 模式 | 撞 stale install 時的偽裝症狀與 fast diagnosis |
| ARCH-020 | architecture pattern | 跨進程同源邏輯漂移（不同模組各自重寫） |

PC-145 與 IMP-023 互補：IMP-023 告訴 PM「該做什麼」（強制 reinstall），PC-145 告訴 PM「忘做時看起來如何」（症狀偵測 + Layer C debug 順序）。

## Action

| 情境 | 建議動作 |
|------|---------|
| 撞到 validator 與源碼矛盾 | 立即執行 Layer C 三步 fast diagnosis |
| 修源碼 + commit 流程 | 套用 Layer A SOP，commit 前必先 reinstall + 端到端測試 |
| 系統性根除 | 推進 Layer B（CLI source freshness check） |

---

**Last Updated**: 2026-05-13
**Version**: 1.0.0 - 初次記錄（W10-125 首例觸發 + 補 IMP-023 配套防護）
