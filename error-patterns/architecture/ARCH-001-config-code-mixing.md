# ARCH-001: 配置與程式碼混合

## 基本資訊

- **Pattern ID**: ARCH-001
- **分類**: 架構設計
- **來源版本**: v0.28.0
- **發現日期**: 2026-01-19
- **風險等級**: 高

## 問題描述

### 症狀

單一檔案超過 800 行，其中約一半是硬編碼的配置資料：

```python
# 800+ 行的 Hook 檔案
PROTECTED_BRANCHES = ["main", "master", "develop"]
ALLOWED_PATTERNS = ["feat/*", "fix/*", "chore/*"]
ERROR_MESSAGES = {
    "branch_not_allowed": "分支名稱不符合規範",
    "missing_ticket": "缺少 Ticket 引用",
    # ... 更多配置
}

def check_branch():
    # 實際邏輯只有幾十行
    pass
```

### 根本原因 (5 Why 分析)

1. Why 1: 單一檔案包含大量配置資料和程式邏輯
2. Why 2: 開發時為求快速，直接在程式碼中定義配置
3. Why 3: 缺乏配置管理策略和標準化做法
4. Why 4: Hook 系統初期設計未考慮配置分離
5. Why 5: **缺乏明確的架構原則指導配置與程式碼分離**

## 解決方案

### 正確做法

將配置分離到 YAML 檔案，建立統一的配置載入機制：

```yaml
# config/branch_rules.yaml
protected_branches:
  - main
  - master
  - develop

allowed_patterns:
  - "feat/*"
  - "fix/*"
  - "chore/*"
```

```python
# hooks/branch_guardian.py
from lib.config_loader import load_config

config = load_config("branch_rules.yaml")

def check_branch():
    if branch in config["protected_branches"]:
        # 處理邏輯
        pass
```

### 配置分離原則

| 資料類型 | 放置位置 | 範例 |
|---------|---------|------|
| 業務規則配置 | YAML 檔案 | 分支規則、檔案類型限制 |
| 錯誤訊息 | YAML 或 i18n | 多語言訊息 |
| 常數定義 | Python 常數檔 | TIMEOUT = 30 |
| 程式邏輯 | Python 檔案 | 核心處理邏輯 |

### 錯誤做法 (避免)

```python
# 錯誤：配置硬編碼在程式碼中
BRANCH_RULES = {
    "protected": ["main", "master"],
    "patterns": ["feat/*", "fix/*"],
    "messages": {
        "error_1": "錯誤訊息 1",
        "error_2": "錯誤訊息 2",
        # ... 數十行配置
    }
}

def main():
    # 實際邏輯被配置淹沒
    pass
```

## 重構範例

### 重構前

```
hooks/
└── user_prompt_submit.py  # 847 行，配置佔 400+ 行
```

### 重構後

```
hooks/
├── user_prompt_submit.py  # 約 200 行純邏輯
└── config/
    ├── workflow_checks.yaml
    ├── error_messages.yaml
    └── file_patterns.yaml

lib/
└── config_loader.py       # 統一配置載入
```

## 檢測方法

```bash
# 檢查超長檔案
find .claude/hooks -name "*.py" -exec wc -l {} \; | awk '$1 > 500'

# 檢查配置行數佔比
grep -c "^\s*[A-Z_]*\s*=" hooks/*.py
```

## 相關資源

- Commit: 60f1b95 (Hook 系統共用程式庫重構)
- 工作日誌: docs/work-logs/v0.28.0-hook-refactoring.md
- 參考原則: Linux Good Taste 原則

## 標籤

`#架構` `#配置管理` `#程式碼品質` `#Hook系統` `#重構`
