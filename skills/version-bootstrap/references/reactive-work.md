# 反應式工作（不納入 bootstrap）

> **什麼時候讀本檔**：規劃波過程中發生「既有測試回歸」「Spec 約束邊界發現」「流程改善發現」等非 pipeline 內工作時。SKILL.md 的九步表只涵蓋規劃 pipeline 本身，不涵蓋這類插入式工作的處理方式。
>
> 同目錄另有 `step-rationale.md`（各步驟為什麼存在）、`version-shift-sop.md`（移版硬耦合盤點 SOP）、`adjacent-assets-boundary.md`（與相鄰資產的交界）。

以下工作在規劃波過程中可能發生，但不屬於 bootstrap pipeline：

| 類型 | 處理方式 |
|------|---------|
| 既有測試回歸 | incident-responder 分析，建 ANA/IMP ticket |
| Spec 約束邊界發現 | 建 ANA ticket，可在 Step 2 填寫時順帶處理 |
| 流程改善發現 | 建 ANA ticket，排入後續 Wave |
