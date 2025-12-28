#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Async Resource Scanner - 掃描 Dart/Flutter 測試中的異步資源問題

用於檢測可能導致測試卡住的異步資源問題：
1. 長延遲（>= 5 秒）沒有對應的清理
2. Timer.periodic 沒有 cancel()
3. StreamController 沒有 close()
4. 缺少 tearDown

使用方式：
    # 掃描單個檔案（嚴格模式，預設）
    uv run async_resource_scanner.py test/unit/test_file.dart

    # 掃描目錄（遞迴）
    uv run async_resource_scanner.py test/unit/ --recursive

    # 警告模式（不阻止執行）
    uv run async_resource_scanner.py test/unit/ --warn-only

    # Hook 模式（從 stdin 讀取測試路徑）
    uv run async_resource_scanner.py --hook-mode
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Issue:
    """問題報告"""
    file_path: str
    line_number: int
    issue_type: str
    description: str
    suggestion: str


@dataclass
class ScanResult:
    """掃描結果"""
    file_path: str
    issues: list[Issue] = field(default_factory=list)
    has_tear_down: bool = False
    long_delays: list[tuple[int, int]] = field(default_factory=list)  # (line, seconds)
    timer_periodics: list[int] = field(default_factory=list)  # line numbers
    stream_controllers: list[int] = field(default_factory=list)  # line numbers
    has_cancel: bool = False
    has_close: bool = False


def scan_file(file_path: Path) -> ScanResult:
    """掃描單個 Dart 測試檔案"""
    result = ScanResult(file_path=str(file_path))

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        result.issues.append(Issue(
            file_path=str(file_path),
            line_number=0,
            issue_type="read_error",
            description=f"無法讀取檔案: {e}",
            suggestion="確認檔案存在且可讀取"
        ))
        return result

    lines = content.split('\n')

    # 檢查是否有 tearDown
    result.has_tear_down = bool(re.search(r'tearDown\s*\(', content))

    # 檢查是否有 cancel() 和 close()
    result.has_cancel = '.cancel()' in content or '.cancel(' in content
    result.has_close = '.close()' in content or '.close(' in content

    # 掃描每一行
    for line_num, line in enumerate(lines, start=1):
        # 檢測長延遲
        delay_match = re.search(r'Duration\s*\(\s*seconds\s*:\s*(\d+)', line)
        if delay_match:
            seconds = int(delay_match.group(1))
            if seconds >= 5:
                result.long_delays.append((line_num, seconds))

        # 檢測 Timer.periodic
        if 'Timer.periodic' in line:
            result.timer_periodics.append(line_num)

        # 檢測 StreamController
        if 'StreamController' in line and 'broadcast()' in line:
            result.stream_controllers.append(line_num)

    # 生成問題報告
    _generate_issues(result)

    return result


def _generate_issues(result: ScanResult) -> None:
    """根據掃描結果生成問題報告"""
    file_path = result.file_path

    # 長延遲問題
    for line_num, seconds in result.long_delays:
        if not result.has_tear_down:
            result.issues.append(Issue(
                file_path=file_path,
                line_number=line_num,
                issue_type="long_delay_no_cleanup",
                description=f"發現 {seconds} 秒延遲，但沒有 tearDown 清理",
                suggestion="添加 tearDown(() {{ service.clearAllQueries(); }}) 或縮短延遲時間"
            ))

    # Timer.periodic 問題
    for line_num in result.timer_periodics:
        if not result.has_cancel:
            result.issues.append(Issue(
                file_path=file_path,
                line_number=line_num,
                issue_type="timer_no_cancel",
                description="使用 Timer.periodic 但沒有對應的 cancel()",
                suggestion="保存 Timer 引用並在 tearDown/dispose 中調用 timer.cancel()"
            ))

    # StreamController 問題
    for line_num in result.stream_controllers:
        if not result.has_close:
            result.issues.append(Issue(
                file_path=file_path,
                line_number=line_num,
                issue_type="stream_no_close",
                description="使用 StreamController.broadcast() 但沒有對應的 close()",
                suggestion="在 dispose 方法中調用 controller.close()"
            ))


def scan_directory(dir_path: Path, recursive: bool = False) -> list[ScanResult]:
    """掃描目錄中的所有測試檔案"""
    results = []

    if recursive:
        dart_files = list(dir_path.rglob('*_test.dart'))
    else:
        dart_files = list(dir_path.glob('*_test.dart'))

    for file_path in dart_files:
        result = scan_file(file_path)
        if result.issues:
            results.append(result)

    return results


def print_report(results: list[ScanResult], strict: bool = True) -> bool:
    """輸出掃描報告，返回是否有問題"""
    total_issues = sum(len(r.issues) for r in results)

    if total_issues == 0:
        print("✅ 掃描完成，未發現異步資源問題")
        return False

    # 輸出問題
    if strict:
        print(f"❌ 發現 {total_issues} 個異步資源問題，必須修復後才能執行測試\n")
    else:
        print(f"⚠️  發現 {total_issues} 個潛在的異步資源問題\n")

    for result in results:
        if not result.issues:
            continue

        print(f"📁 {result.file_path}")
        print("-" * 60)

        for issue in result.issues:
            icon = "❌" if strict else "⚠️"
            print(f"  {icon} Line {issue.line_number}: {issue.description}")
            print(f"     💡 {issue.suggestion}")
            print()

    # 輸出修復建議摘要
    print("\n📋 修復建議摘要：")
    print("1. 為每個測試 group 添加 tearDown 清理未完成的異步操作")
    print("2. 將長延遲（>= 5秒）縮短為 100-500ms（足夠測試邏輯但不阻塞）")
    print("3. 確保 Timer.periodic 有對應的 cancel()")
    print("4. 確保 StreamController 有對應的 close()")

    return True


def parse_hook_input() -> Optional[str]:
    """從 stdin 解析 Hook 輸入，獲取測試路徑"""
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return None

        # 嘗試解析 JSON（Claude Code Hook 格式）
        try:
            data = json.loads(input_data)
            command = data.get('tool_input', {}).get('command', '')
        except json.JSONDecodeError:
            command = input_data

        # 檢查是否為測試命令
        if 'flutter test' not in command and 'dart test' not in command:
            return None

        # 提取測試路徑
        parts = command.split()
        for i, part in enumerate(parts):
            if part in ('test', 'flutter', 'dart'):
                continue
            if part.endswith('.dart') or part.startswith('test/'):
                return part

        # 預設掃描整個 test 目錄
        return 'test/'

    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Async Resource Scanner - 掃描 Dart/Flutter 測試中的異步資源問題"
    )
    parser.add_argument(
        'path',
        nargs='?',
        help="要掃描的檔案或目錄路徑"
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help="遞迴掃描目錄"
    )
    parser.add_argument(
        '--warn-only',
        action='store_true',
        help="警告模式，不阻止執行"
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        default=True,
        help="嚴格模式，發現問題時返回非零退出碼（預設）"
    )
    parser.add_argument(
        '--hook-mode',
        action='store_true',
        help="Hook 模式，從 stdin 讀取測試命令"
    )

    args = parser.parse_args()

    # Hook 模式
    if args.hook_mode:
        test_path = parse_hook_input()
        if test_path is None:
            # 不是測試命令，直接通過
            sys.exit(0)
        args.path = test_path
        args.recursive = True

    # 確保有路徑
    if not args.path:
        parser.print_help()
        return 1

    path = Path(args.path)

    if not path.exists():
        print(f"❌ 路徑不存在: {path}")
        return 1

    # 執行掃描
    if path.is_file():
        results = [scan_file(path)]
        results = [r for r in results if r.issues]
    else:
        results = scan_directory(path, recursive=args.recursive)

    # 輸出報告
    strict = not args.warn_only
    has_issues = print_report(results, strict=strict)

    # 返回退出碼
    if has_issues and strict:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
