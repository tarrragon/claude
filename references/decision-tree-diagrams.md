# 決策樹 Mermaid 圖表

本文件包含主線程決策樹的 Mermaid 視覺化圖表，供需要圖形化理解時參考。

> 決策樹規則本體：@.claude/rules/core/decision-tree.md

---

## 主流程圖（第負一層至第七層）

```mermaid
flowchart TD
    START[接收訊息] --> LN1{可並行拆分?}

    %% 第負一層：並行化評估
    LN1 -->|是| SPLIT[任務拆分]
    SPLIT --> DEP{有依賴關係?}
    DEP -->|否| PARALLEL[並行派發多個代理人]
    DEP -->|是| BATCH[按依賴批次派發]
    LN1 -->|否| LN1_SELF{必須親自處理?}
    LN1_SELF -->|是| SELF[處理:用戶溝通/最終決策]
    LN1_SELF -->|否| DISPATCH[派發給代理人]
    DISPATCH --> L0_ERR

    %% 第零層
    L0_ERR{包含錯誤關鍵字?}
    L0_ERR -->|是| L6[第六層:事件回應]
    L0_ERR -->|否| L0_UNC{包含不確定性詞彙?}
    L0_UNC -->|是| CONFIRM[確認機制]
    L0_UNC -->|否| L0_CMP{複雜需求?}
    L0_CMP -->|是| CONFIRM
    L0_CMP -->|否| L1
    CONFIRM --> L1

    %% 第一層
    L1{是問題?}
    L1 -->|是| L2[第二層:問題處理]
    L1 -->|否| L3[第三層:命令處理]

    %% 第二層
    L2 --> L2_Q{是查詢類?}
    L2_Q -->|是| QUERY_AGENT[派發代理人查詢]
    L2_Q -->|否| CONSULT[派發諮詢代理人]

    %% 第三層
    L3 --> L3_DEV{是開發命令?}
    L3_DEV -->|是| L3_TKT{有對應 Ticket?}
    L3_DEV -->|否| L3_DBG{是除錯命令?}
    L3_DBG -->|是| INCIDENT[派發 incident-responder]
    L3_DBG -->|否| OTHER[其他命令]

    L3_TKT -->|是| L3_CLAIM{已認領?}
    L3_TKT -->|否| WARN1["警告: ticket-create"]
    L3_CLAIM -->|是| L4[第四層:Ticket執行]
    L3_CLAIM -->|否| WARN2["警告: ticket-track claim"]

    %% 第四層
    L4 --> L4_P{pending?}
    L4_P -->|是| CLAIM[claim 後執行]
    L4_P -->|否| L4_IP{in_progress?}
    L4_IP -->|是| L5[第五層:TDD階段]
    L4_IP -->|否| L4_C{completed?}
    L4_C -->|是| ASK[詢問後續]
    L4_C -->|否| ESCALATE[blocked→升級PM]
    CLAIM --> L5

    %% 第五層
    L5 --> L5_SA{需SA審查?}
    L5_SA -->|是| SA[system-analyst]
    L5_SA -->|否| TDD[TDD階段派發]
    SA --> TDD

    %% 第七層（完成判斷）
    TDD --> L7[第七層:完成判斷]
    L7 --> ACC[acceptance-auditor<br/>完整或簡化驗收]
    ACC --> L7_PASS{驗收通過?}
    L7_PASS -->|否| FIX[回到執行修正]
    L7_PASS -->|是| L7_TD{技術債務?}
    L7_TD -->|是| TECHDEBT["tech-debt-capture"]
    L7_TD -->|否| L7_RULE{規則變更?}
    L7_RULE -->|是| SYNC[檢查SKILL/方法論同步]
    L7_RULE -->|否| L7_LEARN{學習經驗?}
    SYNC --> L7_LEARN
    L7_LEARN -->|是| MNB[memory-network-builder]
    L7_LEARN -->|否| L7_NEXT{後續階段?}
    L7_NEXT -->|是| NEXT[下一個Ticket]
    L7_NEXT -->|否| L7_VER{版本完成?}
    L7_VER -->|是| RELEASE["version-release"]
    L7_VER -->|否| WAIT[等待其他Ticket]
```

---

## 第六層：錯誤分類決策樹

```mermaid
flowchart TD
    L6[錯誤發生] --> PREFIX["pre-fix-eval"]
    PREFIX --> IR[incident-responder分析]

    IR --> E1{編譯錯誤?}
    E1 -->|是| E1A{依賴問題?}
    E1A -->|是| SE1[system-engineer]
    E1A -->|否| PARSLEY1[parsley-flutter-developer]

    E1 -->|否| E2{測試失敗?}
    E2 -->|是| E2A{測試本身問題?}
    E2A -->|是| SAGE[sage-test-architect]
    E2A -->|否| E2B{設計邏輯錯誤?}
    E2B -->|是| SA[system-analyst]
    E2B -->|否| PARSLEY2[parsley-flutter-developer]

    E2 -->|否| E3{執行時錯誤?}
    E3 -->|是| E3A{環境問題?}
    E3A -->|是| SE2[system-engineer]
    E3A -->|否| E3B{資料問題?}
    E3B -->|是| DBA[data-administrator]
    E3B -->|否| PARSLEY3[parsley-flutter-developer]

    E3 -->|否| E4{效能問題?}
    E4 -->|是| GINGER[ginger-performance-tuner]
    E4 -->|否| SECURITY[security-reviewer]
```

---

## TDD 階段流程

```mermaid
flowchart LR
    SA[SA審查] --> P1[Phase 1<br/>lavender]
    P1 --> P2[Phase 2<br/>sage]
    P2 --> P3A[Phase 3a<br/>pepper]
    P3A --> P3B[Phase 3b<br/>parsley]
    P3B --> P4[Phase 4<br/>cinnamon]
    P4 --> DONE[完成判斷]
```

---

**Last Updated**: 2026-02-06
**Source**: 從 decision-tree.md v4.3.0 附錄移出
