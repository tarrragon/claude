---
name: security-review
description: "Performs security review for Flutter/Dart code. Use when implementing authentication, handling user input, working with API keys or secrets, managing permissions, storing sensitive data locally, or integrating third-party APIs. Provides Flutter-specific security checklists and patterns."
---

# Security Review（Flutter/Dart）

Flutter/Dart 專案的安全審查快速指引。本 Skill 提供安全檢查清單和核心原則，詳細程式碼範例請參考 `references/flutter-security-patterns.md`。

---

## 適用場景

- 實作認證或授權功能
- 處理使用者輸入（表單、掃描結果）
- 使用 API Key 或其他機密
- 整合第三方 API（Google Books、Dio 等）
- 儲存或傳輸敏感資料
- 管理裝置權限（相機、儲存）
- 準備 Release 建置或上架

---

## 1. 機密管理

**原則**：機密不可出現在原始碼或版本控制中。

### 檢查清單

- [ ] 無硬編碼 API Key、Token、密碼
- [ ] 機密透過 `--dart-define` 或 `.env` 注入
- [ ] `.env`、`*.keystore`、`key.properties` 已加入 `.gitignore`
- [ ] `google-services.json` / `GoogleService-Info.plist` 已加入 `.gitignore`
- [ ] Git 歷史中無機密洩漏

### 核心模式

```dart
// 正確：建置時注入
const apiKey = String.fromEnvironment('API_KEY', defaultValue: '');

// 錯誤：硬編碼
const apiKey = 'sk-proj-xxxxx'; // 禁止
```

> 詳細範例：`references/flutter-security-patterns.md` 第 1 節

---

## 2. 輸入驗證

**原則**：所有使用者輸入在處理前必須驗證和清理。

### 檢查清單

- [ ] 所有表單欄位有 `validator`
- [ ] 設定 `maxLength` 限制輸入長度
- [ ] 使用白名單驗證（非黑名單）
- [ ] 掃描結果（ISBN barcode）已清理非預期字元
- [ ] 錯誤訊息不洩漏技術細節

### 核心模式

```dart
// 表單驗證
TextFormField(
  validator: (value) {
    if (value == null || value.trim().isEmpty) return '必填';
    if (value.length > maxLength) return '超過長度限制';
    return null;
  },
  inputFormatters: [
    FilteringTextInputFormatter.deny(RegExp(r'[<>{}]')),
  ],
)
```

> 詳細範例：`references/flutter-security-patterns.md` 第 2 節

---

## 3. 本地資料安全

**原則**：敏感資料使用加密儲存，一般偏好設定可用明文。

### 檢查清單

- [ ] 機密資料使用 `flutter_secure_storage`（非 `SharedPreferences`）
- [ ] SQLite 查詢使用參數化（`?` 佔位符）
- [ ] 無 SQL 字串拼接
- [ ] `SharedPreferences` 中無 Token、密碼、個資

### 核心模式

```dart
// 正確：參數化查詢
await db.rawQuery('SELECT * FROM books WHERE title LIKE ?', ['%$query%']);

// 錯誤：字串拼接（SQL 注入）
await db.rawQuery("SELECT * FROM books WHERE title LIKE '%$query%'");
```

### 儲存選擇指引

| 資料類型 | 儲存方式 |
|---------|---------|
| Token、密碼、API Key | `flutter_secure_storage` |
| 使用者偏好（主題、語言） | `SharedPreferences` |
| 結構化業務資料 | `sqflite`（參數化查詢） |
| 暫存檔案 | `path_provider` 暫存目錄 |

> 詳細範例：`references/flutter-security-patterns.md` 第 3 節

---

## 4. 網路安全

**原則**：所有網路通訊使用 HTTPS，驗證回應結構。

### 檢查清單

- [ ] 所有 API 端點使用 HTTPS
- [ ] 設定合理的連線逾時（`connectTimeout`、`receiveTimeout`）
- [ ] API 回應結構已驗證（型別檢查）
- [ ] Token 透過攔截器注入（非手動拼接）
- [ ] 401 回應時清除本地 Token

### 核心模式

```dart
// Dio 安全配置
final dio = Dio(BaseOptions(
  baseUrl: 'https://api.example.com', // HTTPS only
  connectTimeout: const Duration(seconds: 10),
  receiveTimeout: const Duration(seconds: 15),
));

// 攔截器注入 Token
dio.interceptors.add(InterceptorsWrapper(
  onRequest: (options, handler) async {
    final token = await storage.readToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  },
));
```

> 詳細範例：`references/flutter-security-patterns.md` 第 4 節

---

## 5. 權限管理

**原則**：僅請求必要權限，在需要時才請求，並說明用途。

### 檢查清單

- [ ] 僅宣告實際需要的權限（AndroidManifest / Info.plist）
- [ ] 權限在使用前才請求（非啟動時全部請求）
- [ ] iOS `Info.plist` 每個權限有用途說明字串
- [ ] 處理「永久拒絕」狀態（引導到系統設定）
- [ ] 權限被拒時提供替代方案或提示

### 核心模式

```dart
// 按需請求，處理各種狀態
Future<bool> requestCameraPermission() async {
  final status = await Permission.camera.status;
  if (status.isGranted) return true;
  if (status.isDenied) {
    final result = await Permission.camera.request();
    return result.isGranted;
  }
  if (status.isPermanentlyDenied) {
    await openAppSettings();
    return false;
  }
  return false;
}
```

> 詳細範例：`references/flutter-security-patterns.md` 第 5 節

---

## 6. 認證與授權

**原則**：Token 安全儲存，過期自動處理，敏感操作前驗證狀態。

### 檢查清單

- [ ] Token 使用 `flutter_secure_storage` 儲存
- [ ] Token 過期有自動更新機制
- [ ] 登出時清除所有本地 Token
- [ ] 敏感操作前驗證使用者認證狀態
- [ ] Refresh Token 失敗時跳轉登入頁面

> 詳細範例：`references/flutter-security-patterns.md` 第 6 節

---

## 7. 依賴安全

**原則**：定期檢查依賴漏洞，鎖定版本確保可重現建置。

### 檢查清單

- [ ] `flutter pub audit` 無已知漏洞
- [ ] `flutter pub outdated` 定期執行
- [ ] `pubspec.lock` 已提交到版本控制
- [ ] 依賴版本有合理約束（使用 `^` 語法）
- [ ] CI/CD 使用 `--enforce-lockfile` 確保一致性

### 核心指令

```bash
flutter pub audit        # 檢查已知漏洞
flutter pub outdated     # 檢查過時套件
flutter pub upgrade      # 更新依賴
```

> 詳細範例：`references/flutter-security-patterns.md` 第 7 節

---

## 8. 敏感資料外洩防護

**原則**：日誌不含敏感資料，錯誤訊息不洩漏技術細節。

### 檢查清單

- [ ] 日誌中無 Token、密碼、個人資料
- [ ] 使用者看到的錯誤訊息為通用文字（透過 i18n / ErrorHandler）
- [ ] 技術細節僅記錄到開發日誌（`kDebugMode` 判斷）
- [ ] Release 建置不輸出除錯日誌
- [ ] Stack Trace 不暴露給使用者

### 核心模式

```dart
// 正確：Release 模式下不輸出日誌
if (kDebugMode) {
  debugPrint('API Error: ${error.runtimeType}');
}

// 正確：使用 ErrorHandler 轉換錯誤訊息
final userMessage = ErrorHandler.getUserMessage(exception);

// 錯誤：直接暴露技術細節
// showError('Database error: $sqlException at line 42');
```

> 詳細範例：`references/flutter-security-patterns.md` 第 8 節

---

## 上架前安全檢查清單

Release 建置或上架前，逐項確認：

- [ ] **機密**：無硬編碼機密，全部透過環境變數注入
- [ ] **輸入驗證**：所有使用者輸入已驗證
- [ ] **SQL 注入**：所有查詢參數化
- [ ] **本地儲存**：敏感資料使用加密儲存
- [ ] **HTTPS**：所有網路通訊使用 HTTPS
- [ ] **權限**：僅宣告必要權限，有用途說明
- [ ] **認證**：Token 安全儲存和自動更新
- [ ] **日誌**：Release 建置無敏感資料輸出
- [ ] **依賴**：`flutter pub audit` 無漏洞
- [ ] **錯誤處理**：使用者看不到技術細節
- [ ] **ProGuard/R8**：Android Release 啟用程式碼混淆
- [ ] **App Transport Security**：iOS 已正確設定

---

## 參考資源

- [Flutter Security Best Practices](https://docs.flutter.dev/security)
- [OWASP Mobile Top 10](https://owasp.org/www-project-mobile-top-10/)
- [OWASP Mobile Application Security](https://mas.owasp.org/)
- 詳細程式碼範例：`references/flutter-security-patterns.md`

---

*Last Updated: 2026-03-02*
