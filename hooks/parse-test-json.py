#!/usr/bin/env python3
#
# parse-test-json.py - Flutter 測試 JSON 解析器
# 功能: 將 flutter test --reporter json 輸出轉換為簡潔摘要
#
# 使用: python3 parse-test-json.py <json-file>
#

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestResult:
    """測試結果資料類別"""
    file_path: str
    test_name: str
    result: str  # 'success', 'failure', 'error'
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: int = 0


class FlutterTestParser:
    """Flutter 測試 JSON 解析器"""

    def __init__(self, json_file: str):
        self.json_file = Path(json_file)
        self.tests: Dict[int, Dict] = {}  # test_id -> test_info
        self.results: List[TestResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.total_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.skip_count = 0

    def parse(self) -> bool:
        """解析 JSON 檔案"""
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        self._process_event(event)
                    except json.JSONDecodeError as e:
                        # 跳過無效的 JSON 行，這在測試輸出中很常見
                        pass

            return True
        except Exception as e:
            print(f"❌ 錯誤: 無法解析 JSON 檔案", file=sys.stderr)
            print(f"   檔案: {self.json_file}", file=sys.stderr)
            print(f"   原因: {e}", file=sys.stderr)
            return False

    def _process_event(self, event: Dict) -> None:
        """處理單個事件"""
        event_type = event.get('type')

        if event_type == 'testStart':
            self._process_test_start(event)
        elif event_type == 'testDone':
            self._process_test_done(event)
        elif event_type == 'error':
            self._process_error_event(event)
        elif event_type == 'allTestsDone':
            self._process_all_tests_done(event)

    def _process_test_start(self, event: Dict) -> None:
        """處理測試開始事件"""
        test_id = event.get('test', {}).get('id')
        test_name = event.get('test', {}).get('name')

        if test_id and test_name:
            self.tests[test_id] = {
                'name': test_name,
                'start_time': event.get('time')
            }

    def _process_test_done(self, event: Dict) -> None:
        """處理測試完成事件"""
        test_id = event.get('testID')
        result = event.get('result')  # 'success', 'failure', 'error'
        duration = event.get('elapsed', 0)

        if test_id not in self.tests:
            return

        test_info = self.tests[test_id]
        test_name = test_info['name']

        # 提取檔案路徑和測試名稱
        file_path, display_name = self._parse_test_name(test_name)

        # 更新計數
        self.total_count += 1
        if result == 'success':
            self.success_count += 1
        elif result == 'failure':
            self.failure_count += 1
            # 記錄失敗的測試（等待 error 事件取得詳細訊息）
            self.results.append(TestResult(
                file_path=file_path,
                test_name=display_name,
                result='failure',
                duration_ms=duration
            ))
        elif result == 'error':
            self.error_count += 1
            self.results.append(TestResult(
                file_path=file_path,
                test_name=display_name,
                result='error',
                duration_ms=duration
            ))
        else:
            # skip 或其他狀態
            self.skip_count += 1

    def _process_error_event(self, event: Dict) -> None:
        """處理錯誤事件"""
        test_id = event.get('testID')
        error_msg = event.get('error', '')
        stack_trace = event.get('stackTrace', '')

        # 嘗試關聯到對應的測試
        if test_id in self.tests:
            test_info = self.tests[test_id]
            test_name = test_info['name']
            file_path, display_name = self._parse_test_name(test_name)

            # 更新最後一個對應的結果記錄
            for result in reversed(self.results):
                if result.test_name == display_name and result.file_path == file_path:
                    result.error_message = error_msg
                    result.stack_trace = stack_trace
                    break

    def _process_all_tests_done(self, event: Dict) -> None:
        """處理全部測試完成事件"""
        self.end_time = event.get('time')

    def _parse_test_name(self, full_name: str) -> Tuple[str, str]:
        """
        解析測試完整名稱
        格式通常為: "test/path/file_test.dart: 測試名稱"
        """
        if ': ' in full_name:
            parts = full_name.split(': ', 1)
            return parts[0], parts[1]
        elif ' ' in full_name:
            # 有些情況只有測試名稱
            return 'unknown', full_name
        return 'unknown', full_name

    def generate_summary(self) -> str:
        """生成測試摘要"""
        lines = []

        # 標題
        lines.append("=" * 50)
        lines.append("測試摘要")
        lines.append("=" * 50)
        lines.append("")

        # 統計資訊
        lines.append(f"總數: {self.total_count} | 通過: {self.success_count} | "
                    f"失敗: {self.failure_count} | 錯誤: {self.error_count} | 跳過: {self.skip_count}")
        lines.append("")

        # 計算通過率
        if self.total_count > 0:
            pass_rate = (self.success_count / self.total_count) * 100
            lines.append(f"通過率: {pass_rate:.1f}%")
        else:
            lines.append("通過率: 無測試")

        lines.append("")

        # 失敗和錯誤測試詳情
        failures_and_errors = [r for r in self.results if r.result in ['failure', 'error']]

        if failures_and_errors:
            lines.append("-" * 50)
            lines.append(f"失敗和錯誤測試 ({len(failures_and_errors)})")
            lines.append("-" * 50)
            lines.append("")

            for idx, result in enumerate(failures_and_errors, 1):
                lines.append(f"{idx}. {result.file_path}")
                lines.append(f"   測試: {result.test_name}")
                if result.error_message:
                    # 簡化錯誤訊息，只取前 500 字
                    error_preview = result.error_message[:500]
                    if len(result.error_message) > 500:
                        error_preview += "... [已截斷]"
                    lines.append(f"   錯誤: {error_preview}")
                if result.stack_trace:
                    # 只顯示 stack trace 的前 3 行
                    trace_lines = result.stack_trace.split('\n')[:3]
                    for trace_line in trace_lines:
                        if trace_line.strip():
                            lines.append(f"   {trace_line}")
                lines.append("")

        lines.append("=" * 50)

        return "\n".join(lines)

    def print_summary(self) -> None:
        """列印測試摘要到標準輸出"""
        summary = self.generate_summary()
        print(summary)

        # 如果有失敗，返回非零 exit code
        if self.failure_count > 0 or self.error_count > 0:
            sys.exit(1)


def main():
    """主程式入口"""
    if len(sys.argv) < 2:
        print("❌ 使用方式: python3 parse-test-json.py <json-file>", file=sys.stderr)
        print("", file=sys.stderr)
        print("引數:", file=sys.stderr)
        print("  json-file: flutter test --reporter json 的輸出檔案", file=sys.stderr)
        sys.exit(2)

    json_file = sys.argv[1]

    # 驗證檔案存在
    if not Path(json_file).exists():
        print(f"❌ 錯誤: 檔案不存在: {json_file}", file=sys.stderr)
        sys.exit(2)

    # 解析和生成摘要
    parser = FlutterTestParser(json_file)

    if not parser.parse():
        sys.exit(2)

    parser.print_summary()


if __name__ == '__main__':
    main()
