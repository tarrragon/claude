# Skip-gate 實施檢查清單

本文件提供 Skip-gate 防護機制各層級的實施檢查清單。

---

## Level 1 檢查清單

**使用時機**：每次錯誤發生時

執行規則 3（必須遵循的修復流程）時，確認以下各項：

- [ ] 是否執行了 `/pre-fix-eval`？
- [ ] 是否派發了 incident-responder？
- [ ] incident-responder 是否完成了 Incident Report？
- [ ] 是否建立了對應的 Ticket？
- [ ] 派發的代理人是否正確？
- [ ] 修復是否在 Ticket 範圍內？

---

## Level 2 檢查清單

**使用時機**：每次接收開發/修改命令時

執行規則 4（開發命令執行前的驗證）時，確認以下各項：

- [ ] 是否識別出開發/修改命令？
- [ ] 是否查詢到待處理的 Ticket？
- [ ] Ticket 是否已被認領？
- [ ] 是否檢視了命令入口驗證閘門的警告訊息？
- [ ] 是否在派發前完成了所有前置驗證？
- [ ] 派發代理人是否與 Ticket 內容相符？

---

## Level 3 檢查清單

**使用時機**：每次主線程嘗試編輯檔案時

執行規則 5（主線程編輯限制）時，確認以下各項：

- [ ] 編輯的檔案路徑在允許範圍內？
- [ ] 是否為以下允許路徑：
  - [ ] `.claude/plans/*`（計畫文件）
  - [ ] `.claude/rules/*`（規則、流程）
  - [ ] `.claude/methodologies/*`（方法論）
  - [ ] `.claude/hooks/*`（Hook 系統）
  - [ ] `.claude/skills/*`（Skill 工具）
  - [ ] `docs/work-logs/*`（工作日誌，含 tickets/）
  - [ ] `docs/todolist.yaml`（結構化版本索引）
- [ ] 是否嘗試編輯禁止檔案：
  - [ ] `lib/*`（程式碼）？
  - [ ] `test/*`（測試）？
  - [ ] `.dart` 檔案？
  - [ ] `pubspec.yaml`？
- [ ] 如編輯被阻止，是否已遵循建議派發對應代理人？

---

**Last Updated**: 2026-02-06
**Version**: 1.0.0
