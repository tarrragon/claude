# Flutter/Dart 安全模式詳細指引

本文件提供 SKILL.md 各安全類別的詳細程式碼範例和說明。

---

## 目錄

1. [機密管理詳細範例](#1-機密管理詳細範例)
2. [輸入驗證詳細範例](#2-輸入驗證詳細範例)
3. [本地資料安全詳細範例](#3-本地資料安全詳細範例)
4. [網路安全詳細範例](#4-網路安全詳細範例)
5. [權限管理詳細範例](#5-權限管理詳細範例)
6. [認證與授權詳細範例](#6-認證與授權詳細範例)
7. [依賴安全詳細範例](#7-依賴安全詳細範例)
8. [敏感資料外洩防護詳細範例](#8-敏感資料外洩防護詳細範例)

---

## 1. 機密管理詳細範例

### 環境變數方案

使用 `--dart-define` 在建置時注入機密：

```dart
// 建置指令
// flutter build apk --dart-define=API_KEY=your-key-here

// 程式碼中讀取
class AppConfig {
  static const String apiKey = String.fromEnvironment(
    'API_KEY',
    defaultValue: '',
  );

  static void validateConfig() {
    if (apiKey.isEmpty) {
      throw StateError('API_KEY 未設定，請使用 --dart-define=API_KEY=xxx');
    }
  }
}
```

### .env 檔案方案（使用 flutter_dotenv）

```dart
// pubspec.yaml
// dependencies:
//   flutter_dotenv: ^5.1.0

// .env（加入 .gitignore）
// API_KEY=sk-xxxxx
// BASE_URL=https://api.example.com

import 'package:flutter_dotenv/flutter_dotenv.dart';

Future<void> main() async {
  await dotenv.load(fileName: '.env');
  final apiKey = dotenv.env['API_KEY'] ?? '';
  if (apiKey.isEmpty) {
    throw StateError('API_KEY not configured in .env');
  }
  runApp(const MyApp());
}
```

### .gitignore 設定

```gitignore
# 機密檔案
.env
.env.local
*.keystore
*.jks
key.properties
google-services.json
GoogleService-Info.plist
```

### CI/CD 安全建置

```yaml
# GitHub Actions 範例
env:
  API_KEY: ${{ secrets.API_KEY }}
steps:
  - run: flutter build apk --dart-define=API_KEY=$API_KEY
```

---

## 2. 輸入驗證詳細範例

### Form 驗證模式

```dart
/// 需求：所有使用者輸入必須驗證後才能提交
class BookFormValidators {
  static const int maxTitleLength = 200;
  static const int maxIsbnLength = 13;

  static String? validateTitle(String? value) {
    if (value == null || value.trim().isEmpty) {
      return null; // 使用 i18n：context.l10n!.titleRequired
    }
    if (value.length > maxTitleLength) {
      return null; // 使用 i18n：context.l10n!.titleTooLong
    }
    return null;
  }

  static String? validateIsbn(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    final cleaned = value.replaceAll(RegExp(r'[-\s]'), '');
    if (cleaned.length != 10 && cleaned.length != 13) {
      return null; // 使用 i18n
    }
    if (!RegExp(r'^[0-9X]+$').hasMatch(cleaned)) {
      return null; // 使用 i18n
    }
    return null;
  }
}
```

### Widget 中使用驗證

```dart
Form(
  key: _formKey,
  child: Column(
    children: [
      TextFormField(
        controller: _titleController,
        validator: BookFormValidators.validateTitle,
        maxLength: BookFormValidators.maxTitleLength,
        inputFormatters: [
          // 限制特殊字元
          FilteringTextInputFormatter.deny(RegExp(r'[<>{}]')),
        ],
      ),
    ],
  ),
)
```

### 自訂 InputFormatter

```dart
/// 需求：防止 SQL 注入和 XSS 字元
class SafeTextInputFormatter extends TextInputFormatter {
  static final _dangerousPattern = RegExp(r'''[<>"';&|`$]''');

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    if (_dangerousPattern.hasMatch(newValue.text)) {
      return oldValue;
    }
    return newValue;
  }
}
```

### 掃描輸入驗證

```dart
/// 需求：ISBN 掃描結果驗證
/// 約束：mobile_scanner 回傳的原始字串可能包含非預期字元
String? sanitizeScanResult(String rawBarcode) {
  final cleaned = rawBarcode.trim().replaceAll(RegExp(r'[^0-9X-]'), '');
  if (cleaned.isEmpty) return null;
  if (cleaned.length < 10 || cleaned.length > 17) return null;
  return cleaned;
}
```

---

## 3. 本地資料安全詳細範例

### flutter_secure_storage 用法

```dart
// pubspec.yaml
// dependencies:
//   flutter_secure_storage: ^9.0.0

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  final FlutterSecureStorage _storage;

  SecureStorageService()
      : _storage = const FlutterSecureStorage(
          aOptions: AndroidOptions(encryptedSharedPreferences: true),
          iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
        );

  Future<void> saveToken(String token) async {
    await _storage.write(key: 'auth_token', value: token);
  }

  Future<String?> readToken() async {
    return await _storage.read(key: 'auth_token');
  }

  Future<void> deleteAll() async {
    await _storage.deleteAll();
  }
}
```

### SQLite 安全

```dart
/// 需求：使用參數化查詢防止 SQL 注入
class BookRepository {
  // 正確：參數化查詢
  Future<List<Map<String, dynamic>>> searchBooks(String query) async {
    return await db.rawQuery(
      'SELECT * FROM books WHERE title LIKE ?',
      ['%$query%'],
    );
  }

  // 錯誤：字串拼接（SQL 注入風險）
  // Future<List<Map<String, dynamic>>> searchBooks(String query) async {
  //   return await db.rawQuery(
  //     "SELECT * FROM books WHERE title LIKE '%$query%'",
  //   );
  // }
}
```

### SharedPreferences 安全

```dart
/// 約束：SharedPreferences 為明文儲存，禁止存放機密資料
class PreferencesService {
  // 允許：使用者偏好設定
  Future<void> saveTheme(String theme) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme', theme);
  }

  // 禁止：機密資料
  // Future<void> saveToken(String token) async {
  //   final prefs = await SharedPreferences.getInstance();
  //   await prefs.setString('auth_token', token); // 明文！
  // }
}
```

---

## 4. 網路安全詳細範例

### Dio 安全配置

```dart
import 'package:dio/dio.dart';

Dio createSecureDio() {
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 15),
    // HTTPS only
    baseUrl: 'https://api.example.com',
  ));

  // 請求攔截器：注入 Token
  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) async {
      final token = await secureStorage.readToken();
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (error, handler) {
      // 401 時清除 Token 並跳轉登入
      if (error.response?.statusCode == 401) {
        secureStorage.deleteAll();
      }
      handler.next(error);
    },
  ));

  return dio;
}
```

### Certificate Pinning（高安全需求）

```dart
// 適用於處理金融或高度敏感資料的場景
import 'dart:io';

SecurityContext createSecurityContext() {
  final context = SecurityContext();
  // 載入預置的 CA 憑證
  context.setTrustedCertificatesBytes(certBytes);
  return context;
}
```

### API 回應驗證

```dart
/// 需求：驗證 API 回應結構，防止惡意回應
T parseApiResponse<T>(
  Response response,
  T Function(Map<String, dynamic>) fromJson,
) {
  if (response.statusCode != 200) {
    throw ApiException(code: response.statusCode ?? 0);
  }
  final data = response.data;
  if (data is! Map<String, dynamic>) {
    throw const FormatException('Invalid response format');
  }
  return fromJson(data);
}
```

---

## 5. 權限管理詳細範例

### permission_handler 最佳實踐

```dart
import 'package:permission_handler/permission_handler.dart';

class PermissionService {
  /// 需求：相機權限用於 ISBN 掃描
  /// 約束：必須先解釋用途再請求
  Future<bool> requestCameraPermission() async {
    final status = await Permission.camera.status;

    if (status.isGranted) return true;

    if (status.isDenied) {
      final result = await Permission.camera.request();
      return result.isGranted;
    }

    if (status.isPermanentlyDenied) {
      // 引導使用者到系統設定
      await openAppSettings();
      return false;
    }

    return false;
  }

  /// 需求：僅在需要時請求，不要啟動時全部請求
  Future<Map<Permission, PermissionStatus>> requestRequired(
    List<Permission> permissions,
  ) async {
    return await permissions.request();
  }
}
```

### 平台設定

```xml
<!-- Android: android/app/src/main/AndroidManifest.xml -->
<!-- 只宣告實際需要的權限 -->
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.INTERNET" />
<!-- 移除不需要的權限 -->
```

```xml
<!-- iOS: ios/Runner/Info.plist -->
<key>NSCameraUsageDescription</key>
<string>需要相機權限來掃描書籍 ISBN 條碼</string>
<!-- 每個權限都需要有明確的用途說明 -->
```

---

## 6. 認證與授權詳細範例

### Token 安全管理

```dart
class AuthService {
  final SecureStorageService _storage;
  final Dio _dio;

  /// 需求：Token 過期自動更新
  Future<String?> getValidToken() async {
    final token = await _storage.readToken();
    if (token == null) return null;

    if (_isTokenExpired(token)) {
      return await _refreshToken();
    }
    return token;
  }

  /// 約束：Refresh Token 必須安全儲存
  Future<String?> _refreshToken() async {
    final refreshToken = await _storage.read(key: 'refresh_token');
    if (refreshToken == null) return null;

    try {
      final response = await _dio.post('/auth/refresh', data: {
        'refresh_token': refreshToken,
      });
      final newToken = response.data['access_token'] as String;
      await _storage.saveToken(newToken);
      return newToken;
    } catch (e) {
      await _storage.deleteAll();
      return null;
    }
  }

  bool _isTokenExpired(String token) {
    // JWT 解析和過期檢查
    // ...
    return false;
  }
}
```

### 使用者狀態保護

```dart
/// 需求：敏感操作前驗證使用者狀態
class AuthGuard {
  static Future<bool> canPerformSensitiveAction(AuthState state) async {
    if (!state.isAuthenticated) return false;
    if (state.isTokenExpired) return false;
    return true;
  }
}
```

---

## 7. 依賴安全詳細範例

### flutter pub audit

```bash
# 檢查已知漏洞
flutter pub audit

# 檢查過時套件
flutter pub outdated

# 更新依賴
flutter pub upgrade

# 檢查 pubspec.lock 一致性
flutter pub get --enforce-lockfile
```

### 依賴版本控管

```yaml
# pubspec.yaml - 版本約束最佳實踐

dependencies:
  # 允許 patch 更新（推薦）
  dio: ^5.9.0

  # 精確版本（高安全需求時）
  # dio: 5.9.0

  # 禁止：不設限
  # dio: any
```

### 建置完整性

```bash
# 確保 pubspec.lock 已提交
git add pubspec.lock

# CI/CD 中使用鎖定版本
flutter pub get --enforce-lockfile
```

---

## 8. 敏感資料外洩防護詳細範例

### 日誌安全

```dart
/// 約束：禁止在日誌中輸出敏感資料
class AppLogger {
  // 正確：遮蔽敏感資訊
  static void logApiCall(String endpoint, int statusCode) {
    debugPrint('API: $endpoint -> $statusCode');
  }

  // 錯誤：洩漏 Token
  // static void logApiCall(String endpoint, String token) {
  //   debugPrint('API: $endpoint with token: $token');
  // }
}
```

### 錯誤訊息安全

```dart
/// 需求：錯誤訊息不可包含技術細節
/// 約束：使用 ErrorHandler 轉換為使用者友善訊息
class SecureErrorHandler {
  // 正確：通用錯誤訊息
  static String getUserMessage(Exception error) {
    if (error is DioException) {
      return _mapNetworkError(error);
    }
    // 使用 i18n 系統回傳通用訊息
    return 'An error occurred. Please try again.';
  }

  // 正確：技術細節僅記錄到日誌
  static void logError(Exception error, StackTrace stack) {
    debugPrint('Error: ${error.runtimeType}: $error');
    debugPrint('Stack: $stack');
  }
}
```

### 螢幕擷取防護（高安全需求）

```dart
// Android：防止螢幕擷取
// 在 MainActivity.kt 中：
// window.setFlags(
//   WindowManager.LayoutParams.FLAG_SECURE,
//   WindowManager.LayoutParams.FLAG_SECURE
// )
```

### Release Build 安全

```dart
// 確保 Release 建置不包含除錯資訊
// 使用 kReleaseMode 判斷
import 'package:flutter/foundation.dart';

void logDebugInfo(String message) {
  if (kDebugMode) {
    debugPrint(message);
  }
  // Release 模式下不輸出任何日誌
}
```

---

## 參考資源

- [Flutter Security Best Practices](https://docs.flutter.dev/security)
- [Dart Secure Coding Guidelines](https://dart.dev/guides/language/effective-dart)
- [OWASP Mobile Top 10](https://owasp.org/www-project-mobile-top-10/)
- [OWASP Mobile Application Security](https://mas.owasp.org/)
- [flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage)
- [permission_handler](https://pub.dev/packages/permission_handler)

---

*Last Updated: 2026-03-02*
