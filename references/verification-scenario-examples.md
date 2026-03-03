# 驗證場景範例

本文件包含驗證框架的常見場景和處理流程範例。

> 主文件：@.claude/rules/core/verification-framework.md

---

## 場景 1：用戶嘗試開發，但沒有 Ticket

**驗證點**：Level 1（入口層）

**流程**：
```
用戶: 實作新功能
    ↓
Hook: 識別開發命令
    ↓
Hook: 檢查 Ticket
    ↓
Hook: 找不到 pending Ticket
    ↓
Hook: 提示執行 /ticket create
    ↓
用戶: 建立 Ticket
    ↓
用戶: 認領 Ticket
    ↓
繼續執行
```

---

## 場景 2：代理人開始執行，缺少前置條件

**驗證點**：Level 2（執行層）

**流程**：
```
代理人: 開始 Phase 3b
    ↓
檢查: Phase 3a 完成？
    ↓
發現: Phase 3a 未完成
    ↓
行動: 升級 PM
    ↓
PM: 重新安排優先級或拆分任務
```

---

## 場景 3：Phase 完成，但工作日誌不完整

**驗證點**：Level 3（完成層）

**流程**：
```
代理人: 更新 worklog
    ↓
Hook: 識別 Phase 完成報告
    ↓
Hook: 檢查 worklog 結構
    ↓
發現: 缺少 Test Results 部分
    ↓
Hook: 警告訊息
    ↓
代理人: 補充 Test Results
    ↓
Hook: 驗證通過
    ↓
允許 /ticket track complete
```

---

## 場景 4：PM 驗收，發現品質問題

**驗證點**：Level 4（驗收層）

**流程**：
```
PM: 驗收 Ticket
    ↓
檢查: Dart analyze 結果
    ↓
發現: 有 3 個 warnings
    ↓
決定: 需要修正
    ↓
建立: 修正 Ticket
    ↓
派發: parsley-flutter-developer
    ↓
修正後: 重新驗收
```

---

**Last Updated**: 2026-02-06
**Version**: 1.0.0
