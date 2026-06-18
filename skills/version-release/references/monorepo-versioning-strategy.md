# Monorepo 版本策略決策指南：單一版本號 vs 子專案獨立版本

monorepo 設定 `project_type` 前，先決定版本模型。兩種模型對應不同的 `.version-release.yaml` 配置，選錯會引入無謂的維護負擔或遺失必要的相容性管理。

## 核心判準

依下列四問判斷，多數偏「是」→ 單一版本號；多數偏「否」→ 子專案獨立版本。

| 判準 | 問題 | 單一版本（是） | 獨立版本（否） |
|------|------|----------------|----------------|
| 耦合方式 | 子專案是否靠共用契約綁死、改一邊另一邊必須同動？ | 是（同一產品的多個部位） | 否（介面穩定、各自演進） |
| 獨立消費者 | 是否有人單獨依賴某子專案、且可能用不同版本？ | 否（永遠成對部署） | 是（如共用 library 被多下游消費） |
| 相容性 | 「A 版配 B 版」是否需要被當問題管理？ | 否（同 tag 即相容） | 是（需相容矩陣 A↔B） |
| 發布節奏 | 子專案是否各自獨立發布、節奏差異大？ | 否（一起出貨） | 是（各自 cadence + 向後相容保證） |

**核心主張**：獨立版本號的價值在「子專案被獨立發佈、被不同下游以不同版本消費」。若子專案是緊耦合、成對部署、無獨立消費者的「同一產品多部位」，獨立版本只引入相容矩陣維護負擔卻換不到好處（YAGNI）；此時單一版本號把相容性壓成一個軸（同 tag 即相容），低成本高一致。

## 兩種模型的配置對應

### 單一版本號（統一版本 monorepo）

整個 repo 一個版本、一個 tag 標整個產品快照。指定一個子專案的版本檔為產品版本 SoT（其餘子專案若為 tag-driven 語言如 Go 則隨之）。

```yaml
# 例：app/（Flutter）+ server/（Go），以 app/pubspec.yaml 為產品版本 SoT
project_type: flutter
version_source:
  primary: app/pubspec.yaml
  parser: yaml
tag_format: "v{version}"
```

> 註：目前 `project_type: monorepo` 預設「子專案各自獨立版本」（見下），尚無「統一版本 monorepo」一級模式。統一版本 monorepo 的慣用做法是 `project_type` 取主版本源子專案的語言類型 + `version_source.primary` 明指該子目錄版本檔。

### 子專案獨立版本

各子專案各自版本號、各自 tag。

```yaml
project_type: monorepo
subprojects:
  - path: packages/frontend
    version_source: { primary: package.json, parser: json }
  - path: packages/backend
    version_source: { primary: pyproject.toml, parser: toml }
```

## worked example：app_tunnel（採單一版本號）

| 判準 | 實況 | 結論 |
|------|------|------|
| 耦合 | app↔server 靠 `docs/contract.md`、WS tty subprotocol、enrollment v2 payload 綁死 | 同一產品兩半 |
| 獨立消費者 | 無；單人自用、單一部署 | 獨立版本價值不存在 |
| 相容性 | 「app 配哪個 server」＝同一個 tag | 單軸即可 |
| 發布節奏 | 一次 tag 整個 repo | 成對出貨 |

四問全偏「是」→ 採單一版本號，配置用上方「統一版本 monorepo」recipe（`project_type: flutter` + `version_source: app/pubspec.yaml`）。

## 反向觸發：何時該改成獨立版本

若日後出現下列任一，重新評估改獨立版本：某子專案被別的 repo 重用為依賴、子專案開始分開散佈給不同對象、或兩端發布節奏分化且需向後相容保證。
