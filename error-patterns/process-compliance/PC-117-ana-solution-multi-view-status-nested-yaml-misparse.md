# PC-117: ANA Solution multi_view_status Nested YAML 結構誤判

**Category**: process-compliance
**Severity**: Medium
**Status**: Tracked（W17-111 ANA 評估 hook UX 改善方向；過渡期靠本 PC 防護）
**Created**: 2026-05-02
**Source**: W17-095 ANA 收尾事件 — PM 寫 `multi_view_status:` 換行接 `  status: skipped` 的 nested YAML 結構，hook regex 跨行抓到 `status: skipped` 字串並判定值非法。

**Related Ticket**: `0.18.0-W17-111`（ANA，評估 multi_view_status hook UX 改善方向）

---

## 症狀

ANA Ticket complete 時 acceptance-gate-hook 警告 multi_view_status 值非法，但用戶肉眼檢查 YAML 內容包含合法值（reviewed / skipped / n_a）：

```
[WARNING] Acceptance Gate: ANA Ticket multi_view_status 值非法

Ticket: 0.18.0-W17-095
目前值: status: skipped
合法值: reviewed, skipped, n_a
```

訊號特徵：

| 訊號 | 說明 |
|------|------|
| 「目前值」含 `:` 字元（如 `status: skipped`） | 實為 nested YAML 第一行被 regex 跨行抓取 |
| 用戶 YAML 寫成 `multi_view_status:` 換行縮排 `  status: skipped` | nested 結構不符 schema 範例 |
| Hook 訊息只說「值非法」未提示結構問題 | UX 不足以引導用戶修正 |

---

## 根因

### Hook regex 跨行匹配行為

`.claude/hooks/acceptance_checkers/multi_view_checker.py:89` 的 `_parse_field` 使用：

```python
pattern = rf"^\s*{re.escape(field_key)}\s*:\s*(.+?)\s*$"
match = re.search(pattern, section, re.MULTILINE | re.IGNORECASE)
```

Python re 的 `\s` 預設包含 `\n`，且 `re.MULTILINE` 不影響 `\s` 行為。當 YAML 寫成：

```yaml
multi_view_status:
  status: skipped
  reason: "..."
```

regex 行為：
1. `^\s*multi_view_status` 匹配第一行開頭
2. `\s*:\s*` 中第二個 `\s*` 跨行吞掉 `\n` + 縮排
3. `(.+?)` 從下一行 `status: skipped` 開始非貪婪匹配
4. `\s*$`（多行模式）匹配下一行行尾
5. value = `"status: skipped"`，不在 allowed_values

### Schema 文件未明示禁 nested

`.claude/config/ana-solution-schema.yaml` 行 33-45 的 examples 全部展示 flat 結構：

```yaml
example_skipped: |
  multi_view_status: skipped
  reason: 本 ANA 僅彙整既有資料，無新設計決策
```

但未明示「禁用 nested 結構」，PM 從規則 5 的「reviewers 子欄位 / conclusion 子欄位」描述容易聯想成 nested object 結構。

---

## 防護（用戶側 — 寫 ANA Solution multi_view_status 前必查）

| 規則 | 正確 | 錯誤 |
|------|------|------|
| 必用 flat YAML（key-value 同層） | `multi_view_status: skipped`<br>`reason: ...` | `multi_view_status:`<br>`  status: skipped`<br>`  reason: ...` |
| 子欄位（reason / reviewers / conclusion）與 multi_view_status 同層 | 縮排 0 | 縮排 2 |
| 寫完後執行 `grep -nE "^multi_view_status:" <ticket.md>` | 行內含值 | 行末為 `:` |

---

## 防護（系統側 — W17-111 ANA 待評估）

W17-111 將評估三方案：

| 方案 | 改動 | 成本 |
|------|------|------|
| A. 改 hook 訊息 | 偵測值含 `:` 時提示「可能寫成 nested 結構」 | 低 |
| B. 改 schema 範例 | examples 加 `# 禁止 nested 結構` 註解 | 極低 |
| C. 改 hook 邏輯 | 自動扁平化 nested YAML | 中（需測試覆蓋） |

過渡期（W17-111 落地前）：本 PC 條目為唯一防護，依靠 PM 在寫 multi_view_status 時先讀本檔案。

---

## 暫時應變（complete 已成功但格式錯）

W17-095 案例：complete 已成功（hook 為 warning 不阻擋），但 ticket body 留 nested YAML 對未來閱讀者誤導。

| 動作 | 方法 |
|------|------|
| 修正 ticket body | `Edit` 工具改 nested 為 flat |
| 不可重 complete | ticket 已 status=completed，frontmatter 不可回退（規則 6 失敗案例學習：不回退既成工作） |
| commit | `fix(W17-XXX): multi_view_status flat 格式` |

---

## 相關文件

- `.claude/config/ana-solution-schema.yaml` — schema 單一事實來源
- `.claude/hooks/acceptance_checkers/multi_view_checker.py` — validator 實作
- `.claude/error-patterns/process-compliance/PC-110-body-check-false-negative-via-schema-separator.md` — 同類「validator 與用戶寫法分歧」反模式
- `.claude/rules/core/quality-baseline.md` — 規則 6 失敗案例學習原則（不回退、提煉、固化）
