# Error Pattern 編號區段 Policy（已退場）

本文件原本定義 error-pattern 流水號的編號區段：1–499 給框架共享 pattern，500+ 給專案專屬 pattern。**500+ 區段已退場，本 policy 不再定義任何編號區段。** 決定一則 pattern 該不該進框架知識庫、用什麼編號，改由下表兩份權威文件規定。

| 要決定的事 | 權威文件 |
|-----------|---------|
| 這則教訓要不要進 `.claude/error-patterns/`（框架相關或專案相關） | `.claude/pm-rules/pm-quality-baseline.md`〈規則 7：知識捕獲時分流〉內的「捕獲時分流判準」 |
| 進了知識庫之後編什麼號 | `.claude/methodologies/error-pattern-numbering-methodology.md`〈核心原則：凍結 flat base，新編號用來源前綴〉 |

---

## 退場理由

**Why**：500+ 區段要解決的問題是專案專屬 pattern 隨 sync 污染其他專案。這個問題已經在更早的環節處理掉，區段約定變成重複且無人使用的第二套規則。

- **分流在捕獲時完成**：捕獲時分流判準要求專案相關內容寫進 `docs/` 或 `CLAUDE.md`，不寫進 `.claude/error-patterns/`。依這個判準，專案專屬 pattern 根本不會出現在知識庫，也就不需要專屬編號區段。
- **來源已由前綴標示**：新編號採 `<CAT>-<PROJ>-NNN` 來源前綴，看編號就知道是哪個專案發現的。區段只能分出「框架或專案」兩類，前綴能分出具體專案，資訊比區段完整。
- **區段沒有現存使用**：2026-11-20 實測（量測環境：框架上游 repo），知識庫中流水號 500 以上的檔案為 0。
- **sync 不依區段過濾**：同步腳本依 `.claude/lib/sync_exclude_manifest.py` 的路徑分類決定傳不傳，不讀編號區段。所以區段約定即使被遵守，也不會改變 sync 的行為。

**Consequence**：若保留區段約定，建立 pattern 的人要同時套用兩套互相重疊的判準（區段三問、捕獲時分流），而且區段三問會把專案專屬內容導向知識庫的 500+，與捕獲時分流的「導向 `docs/`」方向相反。

**Action**：建立 error-pattern 前，先依捕獲時分流判準確認內容屬於框架相關，再依來源前綴方法論配號（實際配號用 `/error-pattern add`，由 allocator 產生）。不要使用 500 以上的流水號表示專案專屬。

---

## 與既有規範的邊界

| 文件 | 聚焦 |
|------|------|
| `.claude/pm-rules/pm-quality-baseline.md` 規則 7 | 內容進不進框架知識庫 |
| `.claude/methodologies/error-pattern-numbering-methodology.md` | 進了知識庫之後的編號形式、凍結 flat base、legacy 重號 |
| `.claude/error-patterns/README.md` | 檔案格式、分類前綴、索引 |
| `.claude/scripts/README-subtree-sync.md` | `.claude/` 同步機制與排除分類 |

---

**Last Updated**: 2026-11-20
**Version**: 2.0.0 — 退場 500+ 專案專屬區段：本 policy 不再定義編號區段，改指向捕獲時分流判準與來源前綴方法論。理由：專案專屬內容在捕獲時就導向 `docs/`、來源由前綴標示、500+ 區段現存 0 檔、sync 不依區段過濾。原 1–499／500+ 區段表、區段判定三問、升級 trigger 一併移除。
**Version**: 1.0.0 — 初版：定義 PC/IMP/ARCH 等 error-pattern 編號區段約定（framework 1–499 / project 500+），明示為文件約定非強制機制（多視角 L3）
