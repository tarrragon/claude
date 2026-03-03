# 建立流程決策樹

此決策樹描述 Ticket 建立的完整流程。

## 主流程判斷

```
[任務開始]
    |
    v
┌─ 是新任務? ─┐
│             │
是            否
│             │
v             v
[建立流程]    ┌─ 是繼續任務? ─┐
              │               │
              是              否
              │               │
              v               v
              [執行流程]      [查詢流程]
```

## 建立流程決策樹

```
[建立流程]
    |
    v
┌─ 版本目錄存在? ─┐
│                 │
否                是
│                 │
v                 v
/ticket init      ┌─ 是子任務? ─┐
                  │             │
                  是            否
                  │             │
                  v             v
/ticket create-child    /ticket create
                              │
                              v
                        [Ticket 建立完成]
                              │
                              v
                        [進入執行流程]
```

**覆蓋指令**：

- [x] `/ticket init <version>` - 初始化版本目錄
- [x] `/ticket create ...` - 建立根任務
- [x] `/ticket create-child ...` - 建立子任務
