# PC-033: 工作日誌未隨版本演進更新導致發布阻塞

## 症狀

執行 `/version-release check` 時，v0.2.0 工作日誌被判定 Phase 0-4 未完成。實際上版本早已完成 128 個 Ticket，但工作日誌仍停留在初始規劃狀態（只記錄 Wave 1-3、版本目標描述過時、無完成標記）。

## 根因

工作日誌在版本初期建立後，隨著版本範圍擴大（從 3 Wave 擴展到 8 Wave、從純 Backend 擴展到含 Frontend），未同步更新。PM 在每個 Wave 完成時更新 Ticket 狀態，但忽略了主工作日誌的維護。

## 行為模式

「文件作為計畫工具」 vs 「文件作為紀錄工具」的認知落差。工作日誌在初期被視為計畫，版本範圍擴大後計畫已過時，但沒有人負責將計畫文件轉為完成紀錄。version-release 腳本依賴工作日誌的完成標記，造成阻塞。

## 解決方案

1. 每個 Wave 完成時（多視角審查後），同步更新主工作日誌的 Wave 清單和進度
2. 版本範圍擴大時（如新增 Wave、新增功能模組），更新版本目標和概要
3. 版本發布前，確認工作日誌含有 `status: completed` 或 Phase 完成標記

## 防護措施

- Wave 收尾 AskUserQuestion 中增加「工作日誌是否已更新」提醒
- version-release check 支援 `status: completed` 標記跳過 Phase 檢查（適用於多 Wave 版本）

## 相關 Ticket

- 0.2.0-W8-001（發現時的 session）

## 發現日期

2026-03-27
