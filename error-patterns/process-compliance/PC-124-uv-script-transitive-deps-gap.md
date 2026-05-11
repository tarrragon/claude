---
id: PC-124
title: uv script header transitive 依賴未宣告 — `lib/` 共用模組引入的 yaml 不會自動安裝
category: process-compliance
severity: medium
status: active
created: 2026-05-05
related:
- IMP-049
- hook-system-design
---

# PC-124: uv script header transitive 依賴未宣告 — `lib/` 共用模組引入的 yaml 不會自動安裝

## 問題描述

Hook 使用 `#!/usr/bin/env -S uv run --quiet --script` shebang 時，uv 會根據 `# /// script` block 內的 `dependencies = [...]` 建立 ephemeral venv。若 hook 自己 `import` 沒列在 deps（例如 yaml）會被檢出；但若透過 `lib/framework_paths.py` 等共用模組「間接」`import yaml`，**uv 不會自動拉 transitive 依賴**。

結果：hook 每次觸發都拋 `ModuleNotFoundError: No module named 'yaml'`，crash exit 1，CC 顯示「PostToolUse:Write hook error: Failed with non-blocking status code: Traceback (most recent call last)...」。操作不被擋（hook 屬事後驗證型），但每次 Write 都會閃錯。

**Why**：uv `# /// script` 設計上是 hook script 自身的依賴隔離，不掃描其 import 鏈。共用模組（`lib/framework_paths.py`）是 framework 內部結構，uv 視為 user-space 邏輯，不會代為解析。

**Consequence**：違規累積後，每次寫入觸發此 hook 都會在用戶端 console 留下 traceback 噪音，掩蓋真正需要關注的 hook 警告（IMP-048 設計的「stderr 警告 = hook error 提示」機制）。用戶疲勞於忽略 hook error，最終把真正的設計性警告也濾掉。

**Action**：

凡 hook 使用 `uv run --script` 且 import 鏈中（含 transitive）會碰到 `pyyaml`、`tomli` 等非 stdlib 套件，**必須在 `# /// script` block 顯式宣告**：

```python
#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]   # 含 transitive 依賴必列
# ///
```

**禁止**：以「我的 hook 自己沒 import yaml」為由省略宣告；以「上次跑得起來」為證據略過——uv ephemeral env 每次重建，跨 hook 不共用 cache，不會幫你補缺。

**檢測指令**：

```bash
for h in $(grep -l "uv run" .claude/hooks/*.py 2>/dev/null); do
  uses_yaml=$(grep -l "framework_paths\|^import yaml\|from yaml" "$h" 2>/dev/null)
  if [ -n "$uses_yaml" ]; then
    deps=$(awk '/dependencies = \[/,/\]/' "$h" | tr -d '\n' | head -c 200)
    has_yaml=$(echo "$deps" | grep -i "pyyaml\|yaml")
    [ -z "$has_yaml" ] && echo "GAP: $h"
  fi
done
```

可加入 hook-completeness-check 流程作週期性掃描。

---

## 觸發案例

### 案例：W10-098.X 系列 PostToolUse:Write 反覆閃錯（2026-05-05）

W10-098 系列拆 11 子 ticket 期間，每次 Write 操作（doc-thyme-prop.yaml / memory file / PC-123 file 等）後，CC 用戶端顯示「PostToolUse:Write hook error: Failed with non-blocking status code: Traceback (most recent call last):」。

#### 重現步驟

1. 觸發任一 PostToolUse:Write 事件（例：`Write tool 寫入任意檔案`）
2. uv 為 `layer-boundary-validator-hook.py` 建立 ephemeral venv，依 `dependencies = []` 只裝零依賴
3. Hook `from lib.framework_paths import ...` → `framework_paths.py` 第 41 行 `import yaml` → `ModuleNotFoundError`
4. `run_hook_safely` 捕獲 → exit 1 → CC stderr 顯示 traceback

#### 受影響 hook

| Hook | shebang | dependencies | 是否引 yaml |
|------|---------|--------------|-----------|
| `layer-boundary-validator-hook.py` | `uv run --quiet --script` | `[]`（修前）/ `["pyyaml"]`（修後） | 透過 `lib/framework_paths.py` |
| `doc-sync-check-hook.py` | `uv run --script` | `[]`（修前）/ `["pyyaml"]`（修後） | 同上 |
| `agent-dispatch-validation-hook.py` | `python3` | `[]` | 系統 python yaml 已裝，不受 uv ephemeral 影響 |

#### 修復

兩個 hook 各加一行 `dependencies = ["pyyaml"]`。修後重跑 `echo "$JSON" | .claude/hooks/layer-boundary-validator-hook.py` → exit 0 + clean output。

#### 為何過去未爆發

可能原因（未求證）：
1. 早期 layer-boundary-validator 直接 `import yaml`（被列在 deps）；後來重構抽到 `lib/framework_paths.py` 時遺漏 transitive 同步
2. 開發期間 hook 多以 `python3` shebang 運行測試，系統 python yaml 已裝；切換到 production uv ephemeral 才暴露
3. CC 顯示 hook error 為「non-blocking」，使用者習慣性忽略

---

## 預防措施

| 層次 | 角色 | 落地 |
|------|------|------|
| 規則層 | 開發者撰寫 hook 自律 | 本 PC + framework-asset-separation 補章節 |
| 工具層 | hook-completeness-check.py 加 transitive deps scan | 待建 follow-up ticket |
| Hook 層 | hook PreCommit / pre-test 拒收 deps gap | 待 framework-rule-edit-skill-trigger-hook 評估 |
| 案例累積 | 每次發現 transitive gap 補本 PC 觸發案例 | 持續 |

---

## 與其他 PC 的關係

| PC | 相關性 |
|------|------|
| IMP-049 | run_hook_safely exit 1 在 CLI 顯示「hook error」（已知 CLI bug，不繞過）。本 PC 是該機制的合理觸發源之一 |
| IMP-048 | stderr 警告 = hook error 設計（事後品質警示）。transitive deps gap 會偽造此訊號，污染真實警告判讀 |

---

## 長期方向

研究是否可在 hook 框架層引入「auto-detect transitive deps」工具：掃描 hook 的 import 鏈，比對 `# /// script` 宣告，缺料時自動補。短期內以本 PC + 一次性 grep 校準替代。
