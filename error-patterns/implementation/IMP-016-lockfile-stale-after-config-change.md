# IMP-016: Lock 檔案未隨配置檔同步更新

## 分類
- **類型**: implementation
- **嚴重度**: 中
- **發現版本**: v0.31.1

---

## 症狀

修改 `pyproject.toml` 的 `requires-python` 從 `>=3.11` 改為 `>=3.14` 後，`uv.lock` 仍包含舊版本的 marker：

```
requires-python = ">=3.11"
{ name = "tomli", marker = "python_full_version <= '3.11'" }
```

程式碼和文件看似更新完畢，但 lock 檔案中殘留過時的依賴解析結果。

---

## 根因

`uv.lock` 是根據 `pyproject.toml` 的 `requires-python` 解析產生的快照。修改 `pyproject.toml` 後若未執行 `uv lock`，lock 檔案不會自動更新。

**行為模式**：開發者聚焦在程式碼和文件中的硬編碼值（grep + replace），但忽略了自動生成的衍生檔案也需要重新生成。

---

## 解決方案

修改 `pyproject.toml` 的版本相關欄位後，立即執行：

```bash
(cd <project-dir> && uv lock)
```

確認 lock 檔案已更新後，將 `uv.lock` 加入 commit。

---

## 預防措施

1. **修改 pyproject.toml 後的檢查清單**：
   - [ ] `uv lock` 已重新執行
   - [ ] `uv.lock` 中無殘留舊版本引用（`grep` 驗證）
   - [ ] `uv.lock` 已加入 git staging

2. **通用原則**：修改「源頭配置檔」時，必須同步更新所有「衍生檔案」（lock files、generated code、build artifacts）

3. **類似場景**：
   - `pubspec.yaml` 修改後需 `flutter pub get` 更新 `pubspec.lock`
   - `go.mod` 修改後需 `go mod tidy` 更新 `go.sum`
   - `package.json` 修改後需 `npm install` 更新 `package-lock.json`

---

## 偵測方式

```bash
# 驗證 uv.lock 與 pyproject.toml 一致
(cd <project-dir> && uv lock --check)
# 若不一致會回傳非零 exit code
```

---

## 變體：依賴變更合併進共用 checkout 後，本機解析結果沒有更新

**現象**：一條線在 worktree 裡新增依賴，`pubspec.yaml` 與 `pubspec.lock` 都已同步提交，合併進 main 也沒問題。但共用的主 checkout 沒有重跑 `pub get`，本機的套件解析結果（`.dart_tool/package_config.json`）仍是舊的。之後另一條線在主 checkout 跑 analyze，新依賴的 import 解析不到，回 rc=3，看起來像程式缺陷。

**與主條目的差別**：主條目是 lock 檔沒有重新產生，提交內容本身有缺口。這個變體的提交內容完整，缺的是「合併之後」本機狀態的更新；lock 檔比對檢查（`--check` 類）會通過，偵測不到。

**做法**：

- 合併的變更動到 `pubspec.yaml`、`pyproject.toml`、`package.json` 等依賴宣告檔時，合併後在主 checkout 重跑對應的安裝命令（`fvm flutter pub get`、`uv sync`、`npm install`）。
- 在主 checkout 遇到「import 解析不到」時，先查最近合併的 commit 有沒有動到依賴宣告檔，再判斷是不是程式缺陷。

**實例**：2026-11-03，某 Flutter 專案的一條線新增 watcher 依賴並合併。另一條線在主 checkout 跑 `dart analyze` 回 rc=3，跑完 `pub get` 後就沒問題了，`pubspec.lock` 沒有變動。同一天另一條線也在新建的 worktree 遇到同樣情況：worktree 從含新依賴的 main 切出，但沒有先跑 `pub get`，analyze 就誤報。新建 worktree 時也要先跑一次安裝命令。2026-11-04 又出現反方向的情況：analyze 通過，但 `flutter test` 編譯失敗。清掉 `.dart_tool` 重跑之後就正常了，判定是本機的分析結果過期。兩個方向的成因相同，都是本機解析狀態沒有跟著依賴或程式碼更新。

---

**Last Updated**: 2026-11-03
