# 程式碼品質範例彙編（語意化命名 / 檔案路徑語意 / 五事件評估）

> 本文件集中展示專案規範中關鍵原則的「可執行範例」，作為每日開發快速參考。
>
> 搭配閱讀：`CLAUDE.md` 的「程式碼品質規範」。

---

## 語意化命名與單一句意原則

```javascript
// 不佳：無法從名稱理解目的或輸入/輸出
function handle(data) { /* ... */ }
const d = user.roles.includes('admin');

// 建議：單一句意 + 語意清楚的命名
/**
 * 驗證並保存使用者設定
 * 負責功能：1) 驗證輸入 2) 持久化到 storage
 * 使用情境：使用者在設定頁點擊儲存
 */
async function validateAndSaveUserSettings(userSettings) { /* ... */ }

const hasAdminPermission = user.roles.includes('admin');
```

---

## 檔案路徑語意規範（強制）

```text
src/
  core/errors/StandardError.js
  extractors/readmoo/services/ReadmooCatalogService.js
  overview/controller/OverviewPageController.js
```

```javascript
// 不佳：相對深度難以理解來源責任
import { StandardError } from '../../../core/errors/StandardError.js';

// 建議：路徑即描述來源 domain 與責任
import { StandardError } from 'src/core/errors/StandardError.js';
import { ReadmooCatalogService } from 'src/extractors/readmoo/services/ReadmooCatalogService.js';
```

---

## 五事件評估準則（非硬性上限）

```javascript
// 警示案例：直接協調 >5 個事件/步驟，需檢討職責
function buildOverviewPage() {
  eventBus.emit('EXTRACTOR.FETCH.START');
  const books = fetchBooks();
  eventBus.emit('TRANSFORM.NORMALIZE.START');
  const normalized = normalizeBooks(books);
  eventBus.emit('ENRICH.METADATA.START');
  const enriched = enrichMetadata(normalized);
  eventBus.emit('STORAGE.SAVE.START');
  storage.save(enriched);
  eventBus.emit('UI.RENDER.START');
  renderOverview(enriched);
}

// 建議：以協調器維持單一句意，子步驟下放至專職函式
function buildOverviewPage() {
  return orchestrateOverviewBuild();
}

function orchestrateOverviewBuild() {
  const data = gatherOverviewData();      // EXTRACTOR.*
  const processed = processOverviewData(data); // TRANSFORM.*, ENRICH.*
  return persistAndRenderOverview(processed);  // STORAGE.*, UI.*
}
```

---

## 類別命名（Class）與檔案/資料夾命名（File/Domain）

```text
路徑與名稱一致（domain-oriented path）
src/extractors/readmoo/services/readmoo-catalog.service.js  ->  class ReadmooCatalogService
src/overview/controller/overview-page.controller.js         ->  class OverviewPageController
src/core/errors/standard-error.js                           ->  class StandardError
```

```javascript
// 不佳：名稱與責任不清楚
class Utils { /* does many things */ }

// 建議：PascalCase + 角色後綴，單一句意
class ReadmooCatalogService { /* responsible for reading Readmoo catalog */ }
class OverviewPageController { /* responsible for coordinating Overview page lifecycle */ }
class StandardError extends Error { /* responsible for standardized error model */ }
```

```text
檔案命名（擇一定稿並全專案一致）
1) feature.type.js（沿用 docs/README.md）
   e.g. readmoo-catalog.service.js, overview-page.controller.js
2) kebab-case.role.js（一檔一類）
   e.g. standard-error.model.js
```

---

## 類別/單檔複雜度拆分範例

```javascript
// 警示：單一類別協調過多事件/依賴 (>5)
class OverviewPageController {
  constructor(eventBus, extractor, transformer, enricher, storage, renderer) {
    this.eventBus = eventBus;
    this.extractor = extractor;
    this.transformer = transformer;
    this.enricher = enricher;
    this.storage = storage;
    this.renderer = renderer;
  }
  async build() { /* 直接協調 6 個協作者 */ }
}

// 建議：引入協調器分層，控制公開方法數量
class OverviewBuildCoordinator {
  constructor(extractor, processor, persister) {
    this.extractor = extractor;   // 聚合 EXTRACTOR.*
    this.processor = processor;   // 聚合 TRANSFORM.*, ENRICH.*
    this.persister = persister;   // 聚合 STORAGE.*, UI.*
  }
  async buildOverview() { /* 維持單一句意 */ }
}

class OverviewPageController {
  constructor(coordinator) { this.coordinator = coordinator; }
  async init() { return this.coordinator.buildOverview(); }
}
```

---

## 使用建議

- 進入開發 session 前，先快速掃過本頁範例，對照手邊任務的命名、路徑與函式複雜度。
- 當發現函式名稱與行為不對齊、路徑語意不清、或步驟數量膨脹時，立即重構。
- 若遇到拿捏不準的情境，在工作日誌標註案例並提 issue 討論，將新案例補充到本文件。
