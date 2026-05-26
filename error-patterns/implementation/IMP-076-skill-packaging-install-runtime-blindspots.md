# IMP-076: Skill packaging install/runtime 二態盲點（auto-discover 配置缺失 + __file__ 上溯失效）

## 基本資訊

- **Pattern ID**: IMP-076
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.19.0
- **發現日期**: 2026-05-25
- **風險等級**: 中
- **影響範圍**: 任何 `.claude/skills/<name>/` 設計為 `uv tool install` 入口的 skill，且
  (1) `pyproject.toml` 採 setuptools backend 但未明示 packages/py-modules，或
  (2) Python 程式碼用 `Path(__file__).parent.parent...` 推導 project root

**相關 Pattern**：IMP-074（scripts.* package 入口 + sys.path-mode 測試 import 衝突）。三者同屬「skill packaging install vs runtime 設計盲點」家族。

---

## 問題描述

### 症狀

設計階段在 dev mode（直接 `uv run scripts/<entry>.py`）測試正常，install 後出現以下任一現象：

**變體 A**：`uv tool install .` 失敗
```
error: Multiple top-level packages discovered in a flat-layout: ['templates', 'references'].
```

**變體 B**：install 成功但 runtime 找不到專案資源
```
[FAIL] 找不到 docs/<config>.yaml
```
或更隱蔽：路徑解析回到 `~/.local/share/uv/tools/<name>/` 上層而非專案 root，後續 file IO 全部 fail。

### 訊號矛盾

| 階段 | dev mode (`uv run`) | installed mode (`uv tool install`) |
|------|---------------------|-----------------------------------|
| 變體 A install | N/A | FAIL（auto-discover 撞 flat-layout） |
| 變體 B runtime | PASS（`__file__` 在 source tree） | FAIL（`__file__` 在 site-packages） |

---

## 根本原因

### 變體 A：setuptools auto-discover 撞 flat-layout 多目錄

`pyproject.toml` 僅宣告 `[project]` 區段、無 `[build-system]` 或 `[tool.setuptools]` 配置時：
- setuptools 預設使用 `auto-discover`（PEP 621 + setuptools 行為）
- skill 目錄常有 `templates/`、`references/`、`scripts/`、`tests/` 等子目錄
- auto-discover 將任何含 `*.py` 或可被視為 package 的目錄都當候選
- 多個 top-level 候選同時存在 → setuptools 拒絕 build（避免誤包含）

### 變體 B：`__file__` 上溯邏輯假設 source-tree 結構

```python
def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent
```

設計假設：`__file__` 在 `.claude/skills/<name>/scripts/<entry>.py`，parent x5 = project root。

實際 installed mode：`__file__` 在 `~/.local/share/uv/tools/<name>/lib/python3.X/site-packages/<entry>.py`，parent x5 進入 `~/.local/share/` 上層，與專案 root 完全無關。

任何後續 `root / "docs" / "<config>.yaml"` 或 `root / "package.json"` 都 fail。

### 設計階段為何不會發現

- 開發測試多用 `uv run <entry>.py`，`__file__` 在 source tree → 路徑正常
- `uv tool install` 通常等到「跨機器分發」或「sync-pull 後驗證」階段才執行
- 開發者誤以為「local 測過 = installed 可用」，缺少 installed mode 的最小驗證

---

## 受影響行為

- 其他專案 sync-pull 取得 skill 後，第一次 `uv tool install` 即失敗（變體 A）
- 或 install 成功但 CLI 啟動後找不到專案資源（變體 B）
- 跨專案 sync 信任崩壞：使用者不確定哪些 skill 真的可用
- 阻擋依賴此 skill 的下游 ticket（如 W1-072 → W1-073 → W3-042 連鎖）

---

## 正確做法

### 變體 A：pyproject.toml 明示 packages 配置

**選項 1**：改用 hatchling backend（與既有 `ticket` skill pattern 對齊）
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "<skill-name>"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = ["pyyaml>=5.0"]

[project.scripts]
<cli-name> = "<entry-module>:main"

[tool.hatch.build.targets.wheel]
sources = ["scripts"]
only-include = ["scripts/<entry>.py"]
```

**選項 2**：明示 setuptools packages
```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
package-dir = {"" = "scripts"}
py-modules = ["<entry-module>"]
```

### 變體 B：get_project_root() 三層 fallback

```python
def get_project_root() -> Path:
    """取得專案根目錄。

    優先順序：
    1. cwd 含 .git 或 package.json → 用 cwd（installed mode 主路徑）
    2. cwd parents 向上找 .git → 用該 ancestor（從子目錄執行的情境）
    3. dev fallback：__file__ 上溯（假設 source 在 .claude/skills/<name>/scripts/）
    4. 最後 fallback：cwd（後續檔案存取會 fail 並回報明確錯誤）

    Why: 原版用 Path(__file__).parent x5，假設 source tree 結構；
    uv tool install 後 __file__ 位於 site-packages，parent x5 進入 ~/.local/share/ 上層
    導致 docs/<config>.yaml 等檔案存取失敗。
    """
    cwd = Path.cwd()
    if (cwd / ".git").exists() or (cwd / "package.json").exists():
        return cwd
    for parent in cwd.parents:
        if (parent / ".git").exists():
            return parent
    dev_fallback = Path(__file__).parent.parent.parent.parent.parent
    if (dev_fallback / ".git").exists() or (dev_fallback / "package.json").exists():
        return dev_fallback
    return cwd
```

---

## 預防清單

設計新 skill 或 PR 審查時：

- [ ] `pyproject.toml` 明示 `[build-system]` + `[tool.<backend>]` packages/sources 配置
- [ ] **設計階段強制驗證**：`uv tool install . --force --reinstall` + 從**專案 root cwd** 執行 CLI 至少一次
- [ ] Python code 內無 `Path(__file__).parent.parent...` 寫死層數的 path 推導（用 marker file 偵測）
- [ ] 若 skill 需 access 專案資源（docs/、package.json 等），用 cwd 優先 + .git/marker fallback 模式
- [ ] CI 加入 `installed-mode-smoke-test`：模擬 install + 跨目錄執行（避免回歸）

---

## 來源

- 0.19.0-W3-042（version-release skill 兩個 bug 同時暴露）
  - pyproject.toml setuptools auto-discover 撞 templates/references
  - scripts/version_release.py:184 `get_project_root()` installed mode 失效
- IMP-074（scripts.* package 入口 + sys.path-mode 測試衝突；同家族不同根因）
- W1-072 → W1-073 → W3-042 連鎖：W1-072 ANA 結論派 W1-073 執行 version bump，撞此 framework bug 阻擋
