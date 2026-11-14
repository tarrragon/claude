# dart-comment-traceability 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.0.1
**Last Updated**: 2026-11-14
- 修正 linked worktree 下的讀寫位置：`comment-qa-hook.py` 的日誌與報告目錄改由框架
  lib 的 `get_hook_log_dir` 解析（落在主 checkout 的 hook-logs）；`comment-qa-config.yaml`
  與 parser 改從程式碼所在的 checkout 載入；查找相關工作日誌改讀共用狀態根（主 checkout
  的 `docs/work-logs`）。框架 lib 缺席時的降級路徑不變。檢查規則不變。

**Version**: 1.0.0
**Last Updated**: 2026-09-07
- 新建：自 `compositional-writing` 遷入 `comment-qa-hook.py`，架構文件引用
  （`docs/event-driven-architecture-design.md`）改為可省略，缺該文件時報告不列出
  該引用，其餘檢查照常執行。hook 檔名維持原名不改。
