# PC-159: development-setup IMP 文件安裝指令未在 fresh shell 實機驗證

> **錯誤類別**：流程合規（IMP 完成標準不含 fresh shell 驗證）
> **嚴重度**：高（換電腦/clone/CI 全部失敗，阻塞用戶工作流）
> **發現案例**：0.19.0-W3-050（換新電腦後依 W6-001.1 development-setup.md 安裝 codegraph 失敗，發現 `npm install -g codegraph` 安裝的是 469B placeholder 而非實際 CLI）

---

## 症狀

IMP 類 ticket（含環境配置 / 安裝指南 / dependency 設定範疇）通過 acceptance 並 commit，但實際安裝指令在 fresh shell 環境執行時失敗。常見訊號：

| 場景 | 訊號 |
|------|------|
| 換新電腦執行 setup | 文件指令跑完但 binary 不在 PATH / version 衝突 / package 錯名 |
| fresh clone 後初始化 | acceptance「已驗證安裝可用」實際只在 PM 既有環境驗證 |
| CI 容器執行 setup | 與本地差異暴露（PATH / shell init / package alias） |
| 半年後重新加入專案 | npm/PyPI 上的 package 名稱已被 squat 或 deprecate |

## 根因

IMP ticket 寫安裝指令時的驗證點與「fresh shell」之間有兩道落差：

1. **PM/agent 環境污染**：撰寫 ticket 時，作者環境已存在所需 binary（從先前手動安裝、apt/brew、其他專案安裝等），執行 `which <binary>` 看似 OK，但 *為什麼 OK* 未被檢驗。文件據此推測「應該是 `npm install -g X`」，實際對 fresh shell 無效。

2. **acceptance 條件粒度太粗**：W6-001.1 acceptance #3「本專案執行 mcp__codegraph__codegraph_status 回報正常」依賴 binary 已在 PATH 的既有環境，未觸及「fresh shell 從零安裝是否能達到該狀態」。

3. **package name squat / namespace 混淆**：npm/PyPI 等 registry 上熱門短名常被 placeholder package 佔據（如 `codegraph@1.0.0` 469B 無 bin 入口），實際工具發布在 scoped name（`@astudioplus/codegraph-mcp`）。文件指令未驗證即假設短名 = 真實 package。

4. **文件指令含「依官方文件」模糊指引**：development-setup.md「依官方文件安裝」「從 release 下載」等模糊段落迴避了驗證責任，誰來填具體指令未明示。

## 案例：W6-001.1 → W3-050

| 階段 | 觀察 |
|------|------|
| W6-001.1 完成 | development-setup.md 寫「`npm install -g codegraph`」+ acceptance 通過（PM mac-eric 環境已有 codegraph binary `~/.nvm/.../bin/codegraph`） |
| 換新電腦 tarragon | `npm install -g codegraph` → 安裝 npm registry 上的 codegraph@1.0.0（469B placeholder package，無 bin 入口）→ `which codegraph` not found |
| 真實安裝路徑 | 實際 codegraph MCP server 為 `@astudioplus/codegraph-mcp@0.16.6`（bin: `codegraph-mcp`，CLI 格式：`-w .` 而非 `serve --mcp --path .`） |
| 修正路徑 | W3-050 修 `.mcp.json` 配置對齊新 CLI + 文件待更新 |

> 完整時間軸與根因鏈見 W3-050 ticket md 與 commit `c9fc6bcd`。

## 防護要點

### Acceptance 層（IMP ticket schema）

IMP 類 ticket 含安裝指令時，acceptance 必須包含以下至少一項：

| 驗證方式 | 適用情境 |
|---------|---------|
| `which <binary> -a`（在 fresh shell 確認） | 安裝工具到 PATH |
| 在 clean docker container 跑指令驗證 | 完整 reproducibility |
| 列出 package 完整 scoped name 與 version 範圍 | 防 npm squat（如 `@astudioplus/codegraph-mcp@^0.16.0`） |
| 列出官方 repo URL（GitHub / GitLab） | 防 namespace 混淆 |

### 規則層（自律）

| 動作時機 | 強制查詢 |
|---------|---------|
| 撰寫 IMP 安裝指令 ticket 時 | 詢問「我的環境是否 fresh？若否，先用 docker / 新 shell 驗證」 |
| 寫「依官方文件」「從 release 下載」前 | 改寫為具體命令 + 官方 URL，禁止模糊指引 |
| 文件 commit 含安裝指令前 | grep `npm install -g <短名>` 模式，逐項驗證 npm registry 內容 |

### Hook 層（建議實作）

PostToolUse:Edit / PostToolUse:Write 偵測對 `docs/development-setup.md` / `docs/environment-recovery-guide.md` 或類似安裝指南檔案的變更時，輸出 reminder：「請確認新增/修改的安裝指令已在 fresh shell 驗證；若未驗證，建議在 ticket acceptance 加入 fresh shell 驗證條件」。

### 文件層

- `docs/development-setup.md` 增加開頭聲明：所有指令必須含 scoped package name + version range，禁止短名假設
- `docs/environment-recovery-guide.md` 在「新電腦/長期暫停後恢復」段落加 fresh shell 驗證 checklist

## 相關 Ticket

| Ticket | 關係 |
|--------|------|
| 0.19.0-W6-001.1 | source：development-setup.md 寫入未驗證指令 |
| 0.19.0-W3-050 | 揭露案例：換電腦觸發失敗 + 修正 .mcp.json |
| 待建 IMP | 更新 W6-001.1 development-setup.md 用 scoped package name |
| 0.19.0-W3-049（ANA） | 共振分析：mint commit 後未 complete + 本案 W6-001.1 安裝指令未驗證，皆屬「文件 vs 實機驗證不一致」根因家族 |

## 相關規則 / Memory

- `.claude/rules/core/quality-baseline.md` 規則 5：所有發現必須追蹤
- `.claude/rules/core/document-writing-style.md`：禁止模糊指引（「依官方文件」需具體化）
- memory `feedback_failure_learning_principle`：疏失發生時提煉教訓 + 固化規則

---

**Last Updated**: 2026-05-25
**Source**: 0.19.0-W3-050 commit c9fc6bcd
