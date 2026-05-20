# IMP-074: Skill 同時用 scripts.* package 入口 + sys.path-mode 測試導致 import 雙模式衝突

## 基本資訊

- **Pattern ID**: IMP-074
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-17
- **風險等級**: 中
- **影響範圍**: 任何 `.claude/skills/<name>/scripts/` 結構 + `pyproject.toml` 入口點宣告為 `scripts.X:Y` 的 skill

---

## 問題描述

### 症狀

- `uv run <skill-entry>` 安裝後執行拋 `ModuleNotFoundError: No module named '<sibling-module>'`
- 同 skill 的 `pytest tests/` 全綠
- 兩個訊號矛盾：CI 與本地測試都通過，但實際 CLI 入口無法執行

### 表現形式

| 執行情境 | scripts/ 的角色 | 模組內 `from X import` 是否找得到？ |
|---------|----------------|----------------------------------|
| `uv tool install` / `uv run <entry>` | Python package（`scripts.*`） | **找不到**（X 不在頂層命名空間，須寫 `from scripts.X` 或 `from .X`） |
| `pytest tests/`（測試端 `sys.path.insert(scripts_dir)`） | 頂層 sys.path 條目 | **找得到**（X 在頂層命名空間） |

兩種模式對 import 風格要求**相反**，導致看似測試完備的 skill 在實際安裝執行時崩潰。

---

## W11-031 案例

### 時序

1. worktree skill 用 `scripts/` 結構放 `worktree_manager.py` / `constants.py` / `messages.py`
2. `pyproject.toml` 宣告入口 `worktree = "scripts.worktree_manager:main"`（package 模式）
3. `worktree_manager.py` 內用 `from constants import ...` / `from messages import ...`（裸 import）
4. 11 個 test 檔以 `sys.path.insert(0, scripts_dir)` + `from worktree_manager import ...` 撰寫
5. `pytest tests/` 全綠（81 個）→ 開發者誤判 skill 健康
6. 實際執行 `uv run worktree create <id>` → `ModuleNotFoundError: No module named 'constants'`
7. 同 commit 還連帶一個 `Path(__file__).parent` 計數少一層的 bug，因為 git_utils import 永遠失敗、走 fallback `get_project_root() = os.getcwd()`，路徑錯誤被掩蓋直到 fallback 機制本身被檢視才暴露

### 證據

- W11-031 commit `6b1d235d`
- 修復前 `uv run worktree create 0.18.0-W11-018 --dry-run` 拋 ModuleNotFoundError
- 修復前 `pytest tests/` 81 passed → 雙訊號矛盾

---

## 根因分析

### 直接原因

`scripts/` 同時被當作 Python package（entry point `scripts.X:Y`）和頂層 import root（測試 `sys.path.insert`）。兩種模式對裸 import `from constants import` 的解讀完全不同：

- Package 模式：`from constants` 解析為頂層 `constants` 模組 → 不存在
- sys.path 模式：scripts/ 在 sys.path 中，`from constants` 找到 `scripts/constants.py` → 成功

### 為何測試沒抓到

測試端用 sys.path 模式 import 模組，繞過了入口點實際使用的 package 解析路徑。**測試成功 ≠ entry point 成功**——因為兩條路徑解析模組的方式不同。

### 為何 fallback 機制使情況變糟

worktree_manager.py 對 `from git_utils import ...` 包了 try/except 並提供 fallback（如 `get_project_root() = os.getcwd()`）。fallback 設計意圖是「優雅降級」，實際後果是讓上游路徑計算 bug（`parent.parent.parent.parent` 應為 5 層 `.parent`）永遠走 fallback 路徑，路徑錯誤永遠不抛出來。

---

## 解決方案

### 立即修復

採 try/except dual import，兩種情境都相容：

```python
try:
    from .constants import (...)  # package 模式（entry point）
    from .messages import (...)
except ImportError:
    # Fallback for sys.path mode（測試端與直接執行）
    from constants import (...)
    from messages import (...)
```

### 預防措施

| 措施 | 行動 |
|------|------|
| 統一 import 模式 | skill 規劃階段就決定 `scripts.*` package 或 sys.path 二選一，全程一致 |
| Entry point smoke test | 新增 `pytest` 案例：`subprocess.run(['uv', 'run', '<entry>', '--help'])` 確保 entry point 可載入 |
| 警惕 fallback 設計 | 對 git_utils / 共用 lib 的 ImportError fallback，要嚴格區分「環境缺失」（合理 fallback）與「自身路徑錯誤」（應 fail loud），後者不該走 fallback |
| Path.parent 計數註解 | 計算 project_root 時加註層級註解（例：`# worktree_manager.py -> scripts -> worktree -> skills -> .claude -> <root>`），避免後人少數一層 |

---

## 相關案例

- 同類 path-structure mismatch 家族；與 PC-115（ARCH-015 worktree boundary）為不同 layer（PC-115 是 cc runtime 限制；本 pattern 是 skill 自身設計）
- W11-031 commit `6b1d235d`

---

## 驗證

修復後同時通過：

- `uv run --directory .claude/skills/worktree worktree create <id> --dry-run` → 正確輸出，無 warning
- `pytest tests/` → 81/81

兩個訊號收斂才能視為健康。
