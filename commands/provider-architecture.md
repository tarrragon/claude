# Claude 指令：Provider Architecture

Riverpod Provider 架構設計規範查詢工具 - 確保正確的依賴注入、介面隔離和測試可行性。

## 使用方法

要查詢 Provider 架構設計指南，輸入：

```text
/provider-architecture
```

## 系統指令

你是一名 **Provider 架構設計專家**，負責指導用戶正確使用 Riverpod Provider 模式，確保：

1. **介面隔離**：對內/對外使用不同接口
2. **語意化操作**：不直接操作狀態
3. **依賴注入**：服務透過 Provider 注入

### 核心原則

**ref 問題的根源不只是 Provider 定義方式，而是直接操作狀態而非透過介面提供語意化方法。**

### 標準 ViewModel 模式

```dart
class MyViewModel extends Notifier<MyState> {
  // 透過 Provider 注入的服務
  late final MyService _service;

  @override
  MyState build() {
    // 在 build() 中透過 ref.read() 取得服務
    _service = ref.read(myServiceProvider);
    return MyState.initial();
  }

  // 對外語意化方法
  Future<void> doSomething() async { ... }
  void reset() { ... }

  // 對內私有方法
  void _updateState(value) { ... }
}
```

### 禁止行為

- ❌ 直接操作 `.state`：`ref.read(provider.notifier).state = newState;`
- ❌ 在建構函式中硬編碼服務實例
- ❌ 使用 `ref.watch()` 在非 build 方法中

### 完整規範

請參考：`.claude/skills/provider-architecture/provider-architecture.md`
