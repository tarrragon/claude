# DOC-002: 衛星文件引用不存在

## 基本資訊

- **Pattern ID**: DOC-002
- **分類**: 文件規範
- **來源版本**: v0.28.0
- **發現日期**: 2026-01-19
- **風險等級**: 中

## 問題描述

### 症狀

方法論或核心文件引用的衛星文件實際上不存在：

```markdown
<!-- 在某方法論文件中 -->
## 相關資源

- 詳細範例：[進階使用指南](./advanced-guide.md)  <!-- 不存在 -->
- 參考實作：[範例程式碼](./examples/)           <!-- 目錄不存在 -->
- 深入閱讀：[原理說明](./theory.md)            <!-- 不存在 -->
```

### 根本原因 (5 Why 分析)

1. Why 1: 方法論引用的衛星文件實際上不存在
2. Why 2: 規劃文件結構時先寫引用，但未同步建立文件
3. Why 3: 文件移除或重命名時未更新引用
4. Why 4: 缺乏文件連結完整性檢查機制
5. Why 5: **文件管理流程缺乏「引用驗證」步驟**

## 解決方案

### 正確做法

#### 方法 1：先建立再引用

```bash
# 確認文件存在後再添加引用
ls -la ./examples/
# 確認存在後，再在文件中添加引用
```

#### 方法 2：使用引用檢查腳本

```python
#!/usr/bin/env python3
"""檢查 Markdown 文件中的內部連結是否有效。"""

import re
import os
from pathlib import Path

def check_links(file_path: Path) -> list[str]:
    """檢查單一檔案中的失效連結。"""
    broken = []
    content = file_path.read_text()

    # 找出所有 Markdown 連結
    links = re.findall(r'\[.*?\]\((\..*?)\)', content)

    for link in links:
        # 移除錨點
        link_path = link.split('#')[0]
        if link_path:
            full_path = file_path.parent / link_path
            if not full_path.exists():
                broken.append(f"{file_path}: {link}")

    return broken
```

#### 方法 3：移除無效引用

如果決定不建立衛星文件，應移除引用：

```markdown
<!-- 移除前 -->
## 相關資源

- 詳細範例：[進階使用指南](./advanced-guide.md)
- 核心概念：[基礎介紹](./basics.md)

<!-- 移除後 -->
## 相關資源

- 核心概念：[基礎介紹](./basics.md)
```

### 預防措施

1. **建立前檢查**: 添加引用前先建立目標文件
2. **定期驗證**: 執行連結檢查腳本
3. **刪除時更新**: 刪除文件時搜尋並更新所有引用
4. **PR 檢查**: 在 CI 中加入連結檢查

### 錯誤做法 (避免)

```markdown
<!-- 錯誤：規劃了但未實作 -->
## 相關資源

- [使用指南](./guide.md)           <!-- TODO: 待建立 -->
- [API 文件](./api-reference.md)   <!-- TODO: 待建立 -->
- [常見問題](./faq.md)             <!-- TODO: 待建立 -->
```

## 檢測方法

```bash
# 找出所有相對路徑引用
grep -rn "\]\(\.\.\?/" .claude/methodologies/*.md

# 驗證引用是否存在（簡易版）
for f in $(grep -oh "\]\(\./[^)]*\)" .claude/methodologies/*.md | sed 's/](\.\///' | sed 's/)//'); do
    if [ ! -f ".claude/methodologies/$f" ]; then
        echo "Missing: $f"
    fi
done
```

## 重構範例

### v0.28.0 處理方式

發現方法論引用了不存在的衛星文件後，採取以下處理：

1. 刪除了多個備份文件（*.backup.md）
2. 移除了引用不存在文件的連結
3. 建立了新的 LSP 方法論來補充缺失內容

## 相關資源

- Commit: 2d4b2ca (方法論文件清理)
- 工作日誌: docs/work-logs/v0.28.0-methodology-cleanup.md

## 標籤

`#文件` `#引用完整性` `#方法論` `#文件維護` `#Dead Link`
