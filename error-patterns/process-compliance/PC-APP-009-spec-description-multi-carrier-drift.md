---
id: PC-APP-009
title: 規範描述多載體雙寫漂移——方案變更後人工同步只掃部分載體
severity: medium
category: process-compliance
created: "2026-07-13"
source_tickets: [0.38.0-W10-002, 0.38.0-W10-003]
related_patterns: [PC-093]
---

# PC-APP-009: 規範描述多載體雙寫漂移

## 症狀

同一方案/決策描述存在於 4+ 載體（提案 frontmatter 標題、In Scope、驗收條件、tracking.yaml 標題副本、影響範圍表、轉化記錄），方案在評估後變更（如生成方案 → 校驗層方案），同步 commit 只改寫部分載體，殘留載體仍是舊方案語意，與新方案正面矛盾。

**識別特徵**：提案「討論記錄」已記載新方案結論，但 AC / In Scope / 索引檔標題仍描述舊方案；讀者（尤其跨 session AI agent）依殘留舊語意執行會走已否決的方案。

## 實證案例（2026-07-11 ~ 07-13，雙 repo 各漏一次）

| Repo | 提案 | 同步時改了 | 漏掉的載體 |
|------|------|-----------|-----------|
| book_overview_app | PROP-018 | In Scope、討論記錄 | AC 第 2 項（仍寫「值由中介格式生成」）、proposals-tracking.yaml 標題（仍寫「雙端生成」） |
| book_overview_v1 | PROP-014 | 討論記錄、多視角審查記錄 | In Scope 項 3（生成 pipeline 改造）、AC 第 2 項、影響範圍表、轉化記錄（W6-007/008 已完成仍標 pending） |

諷刺點：漏掉的提案正是要解決「token 值雙寫無校驗必漂移」的提案——提案文件自身重現了它要解的病，反向佐證「人工同步必漏」的提案主張。

## 根因

1. **多載體無清單**：方案描述寫入了哪些載體沒有登記，同步時靠記憶枚舉，必漏。
2. **索引檔是隱形副本**：tracking.yaml 的標題在 create 時複寫，之後與提案本體無任何機制關聯，最易被遺忘。
3. **AI 維護放大**：跨 session 的 AI agent 以文件為 ground truth，殘留舊語意會被當現行方案執行（非人類讀者可憑上下文察覺矛盾）。

## 解決方案

方案變更後的同步作業，先 grep 枚舉再逐一改寫：

```bash
# 以舊方案的關鍵詞（如「生成」「JSON SSOT」）全量枚舉殘留載體
grep -rn "舊方案關鍵詞" docs/proposals/<PROP>.md docs/proposals-tracking.yaml
# 改寫後以同 grep 驗證：所有命中應屬「否決記錄/歷史描述」，無規範性殘留
```

sibling 提案（雙 repo）場景：兩端各執行一輪，並在 Completion Info 互相登記對端 commit hash 供追溯。

## 預防措施

1. **方案收斂 commit 的檢查清單**：改寫 In Scope 時同步檢查 AC、影響範圍、轉化記錄、tracking.yaml 標題、sibling 提案對應章節（六載體固定清單）。
2. **grep 驗證取代人工掃描**：以舊方案關鍵詞 grep 全文，命中逐項分類（規範性殘留 → 改；否決記錄 → 留）。
3. **結構性解**：載體越少漂移面越小——索引檔標題等可推導欄位，長期應由工具從提案 frontmatter 生成（structured-content-generation 原則）。

## 關聯

- 0.38.0-W10-002 / W10-003（APP 端修正）、1.5.0-W6-027（V1 端修正）
- PC-093（無 trigger 延後——轉化記錄 stale 的近親：狀態欄位無人負責回填）
- `.claude/rules/core/structured-content-generation.md`（第三層防護：確定性欄位工具生成）
