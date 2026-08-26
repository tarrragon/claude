---
# 領域事件（Event）模板
# 複製本檔案並重新命名為 EVT-{DOMAIN}-{NNN}-{簡短描述}.md
# 存放於 docs/events/{domain}/

id: EVT-DOMAIN-NNN
name: "{事件名稱}"
canonical_name: "MODULE.ACTION.STATE"  # 規範化事件名：模組.動作.狀態，如 BackupTracker.Snapshot.Incremented
category: domain_event           # domain_event（業務狀態變更）/ process_event（流程/系統事件）
status: draft                    # draft / review / approved / deprecated
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"

# 負載結構（選填；內部 schema 待首個真實 EVT 實例定案後補齊）
payload: null

# 交叉驗證核心欄位（選填於建立時，但 `doc validate` 對已存在文件強制檢查
# 兩者皆非空——缺一端代表事件的發送方或接收方未被記錄，見 SKILL why）
producers: []                    # 發送此事件的 domain/service，如 [BackupTracker]
consumers: []                    # 接收此事件的 domain/service，如 [SnapshotCounter]

# 關聯
related_usecases: []             # 相關用例，如 [UC-01]
related_specs: []                # 相關規格，如 [SPEC-001]
---

# EVT-{DOMAIN}-{NNN}: {事件名稱}

## 基本資訊

| 項目 | 值 |
|------|-----|
| 事件 ID | EVT-{DOMAIN}-{NNN} |
| 規範化名稱 | {MODULE.ACTION.STATE} |
| 分類 | domain_event / process_event |
| 狀態 | draft |

## 事件描述

{一段話描述此事件代表的業務意義：什麼情況下發生、代表什麼狀態變化。}

## 負載（Payload）

{事件攜帶的資料結構描述；本欄若無定案可留空待後續補齊。}

## Producers（發送方）

{列出發送此事件的 domain/service，以及觸發時機。}

## Consumers（接收方）

{列出接收此事件的 domain/service，以及各自的處理行為。}

## 相關文件

- 相關用例：{UC-XX}
- 相關規格：{SPEC-XXX}
