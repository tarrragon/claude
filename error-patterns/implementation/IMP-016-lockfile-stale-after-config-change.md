# IMP-016: Lock 檔案未隨配置檔同步更新

## 分類
- **類型**: implementation
- **嚴重度**: 中
- **發現版本**: v0.31.1
- **相關 Ticket**: 0.31.1-W1-015

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

**Last Updated**: 2026-03-05
