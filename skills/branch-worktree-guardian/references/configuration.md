# 配置說明

## settings.json 配置

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {"type": "command", "command": ".claude/hooks/branch-verify-hook.py"}
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {"type": "command", "command": ".claude/hooks/branch-verify-hook.py"}
        ]
      }
    ]
  }
}
```

## 保護分支自訂

修改 `branch-verify-hook.py` 中的 `PROTECTED_BRANCHES` 列表：

```python
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "release/*",
    # 添加更多保護分支...
]
```

### 保護分支列表

預設保護分支：
- `main`
- `master`
- `develop`
- `release/*`

在這些分支上嘗試編輯時，Hook 會詢問是否繼續或建立新分支。

## 常見配置調整

### 新增自訂保護分支

```python
PROTECTED_BRANCHES = [
    "main",
    "master",
    "develop",
    "release/*",
    "hotfix/*",  # 新增
    "stable",    # 新增
]
```

### 移除保護分支

從 `PROTECTED_BRANCHES` 列表中刪除對應項目。

---

**Last Updated**: 2026-03-02
