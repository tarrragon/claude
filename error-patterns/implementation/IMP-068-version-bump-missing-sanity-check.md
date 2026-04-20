---
id: IMP-068
title: sync-push 版號 bump 缺 sanity check 導致異常跳躍靜默 push
category: implementation
severity: high
status: active
created: 2026-04-20
related:
- IMP-067
---

# IMP-068: sync-push 版號 bump 缺 sanity check 導致異常跳躍靜默 push

## 問題描述

`sync-claude-push.py` 的版號 bump 流程：
1. clone remote repo 到 temp_dir
2. 讀 `temp_dir/VERSION` → `remote_version`
3. `bump_version(remote_version, bump_suggestion)` 算 `new_version`
4. 寫 `new_version` 到 `temp_dir/VERSION`
5. git add / commit / push

若上游或 local state 異常（BOM、CHANGELOG 污染、local `.claude/VERSION` 來自其他來源）導致 `new_version` 實際寫入值偏離 remote + 1 級 bump，整個流程**不會發現**——`new_version` 靜默 push 到 remote，污染下游所有專案的 sync-pull。

### 具體觸發案例

Remote repo `tarrragon/claude.git` 曾發生：
- v1.17.0 單次 commit 直接跳至 **v1.36.2**（跨 19 個 minor + 2 patch）
- CHANGELOG 有完整線性 1.17 → 1.36.2 歷史，但 git log 僅存在 v1.17.0 和 v1.36.2 兩個 commit
- 無任何攔截、警告或 fail-fast

## 根本原因

### 缺防護點

1. **`bump_version` 無上限**：`re.match` 失敗 fallback `"1.0.1"`，但成功 match 時不驗證結果合理性
2. **`write_text` 無前置檢查**：line 550 直接寫 `new_version`，不驗證相對 `remote_version` 的 delta
3. **`git commit` 無 version 驗證**：commit hook 不檢查 VERSION 變更幅度
4. **`git push` 無 version 驗證**：push hook 亦無
5. **`extract_version_string` 無 BOM strip**：Windows VERSION 檔案含 BOM 時 `re.match(r"(\d+)\.(\d+)\.(\d+)", "\ufeff1.17.0")` fail，bump fallback 到 `1.0.1`

### 驗證真空

整個版號管理流程從 read → bump → write → commit → push 五步驟，**無一步驟驗證最終 new_version 的合理性**。只要寫入就會被 commit 並 push。

## 受影響行為

- remote repo 版號累積「跨代跳躍」commit（CHANGELOG 假線性、git log 真斷層）
- 下游 sync-pull 拉到異常版號，本地 `.claude/VERSION` 被污染
- 後續 sync-push 以異常版號為 `remote_version` 起點，誤差持續放大
- 版號追蹤失效（無法用版號推斷實際 feature 進度）

## 正確做法

### 在 bump 後 commit 前加 `validate_version_bump()`

```python
def validate_version_bump(remote_version: str, new_version: str) -> None:
    """版號 bump 必須恰好滿足三種合法型態之一。"""
    r = re.match(r"(\d+)\.(\d+)\.(\d+)", remote_version)
    n = re.match(r"(\d+)\.(\d+)\.(\d+)", new_version)
    if not r or not n:
        sys.exit(1)
    rM, rm, rp = (int(x) for x in r.groups())
    nM, nm, np = (int(x) for x in n.groups())
    valid = (
        (nM == rM + 1 and nm == 0 and np == 0)   # major
        or (nM == rM and nm == rm + 1 and np == 0)  # minor
        or (nM == rM and nm == rm and np == rp + 1)  # patch
    )
    if not valid:
        print(f"[FAIL] 版號跳躍異常: {remote_version} -> {new_version}")
        sys.exit(1)
```

呼叫時機：`bump_version` 後、`write_text` 前。

### `extract_version_string` 加 BOM strip

```python
line = line.strip().lstrip("\ufeff")  # 清 UTF-8 BOM
```

### 非必要但建議的進階防護

- push 失敗時 dump diagnostics 到 log（remote_version / new_version / bump_suggestion）
- `copy_filtered` 前從 EXCLUDE 排除 `VERSION`、`CHANGELOG.md`，避免 local 版本污染 temp_dir
- push 前比對 local `.claude/VERSION` 與 remote `VERSION` 差距 > 1 patch 時警告

## 預防清單

- [ ] 任何版號自動 bump 邏輯都要有 sanity check（不僅限於 sync-push）
- [ ] 讀取 VERSION 檔案一律 strip BOM
- [ ] 失敗時輸出可診斷的資訊（非只 sys.exit(1)）
- [ ] 寫入版號前 assert 合理性，寫入後立即 verify

## 來源

- W16-004.2 Ticket 實證分析（`docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W16-004.2.md`）
- v1.17.0 → v1.36.2 事件（單次 Windows push 產生的 CHANGELOG 假線性）
