#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Hook Auto-Register - Hook 自動註冊機制

根據 Hook 檔案中的 metadata（Docstring 或 JSON Sidecar）自動掃描並註冊未登記的 Hook 到 settings.json。

特點：
- 支持 Docstring 和 JSON Sidecar 兩種 metadata 格式
- 自動檢測衝突並決策處理
- 備份-寫入-驗證三步驟確保資料安全
- 提供 --dry-run 模式預覽變更
"""

import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import argparse
import shutil


# ============================================================================
# MetadataExtractor - Metadata 提取模組
# ============================================================================

class MetadataExtractor:
    """從 Hook 檔案提取 metadata 資訊"""

    # 有效的 Hook 事件類型
    VALID_EVENT_TYPES = {
        "PreToolUse",
        "PostToolUse",
        "SessionStart",
        "UserPromptSubmit",
        "OutputResponse",
    }

    # 有效的 matcher 名稱（備選）
    VALID_MATCHERS = {
        "Write", "Edit", "Read", "Bash", "WebFetch", "WebSearch",
        "Python", "Grep", "Glob"
    }

    @staticmethod
    def extract_from_docstring(file_path: str) -> Optional[Dict[str, Any]]:
        """
        從 Hook 的 docstring 中提取 HOOK_METADATA (JSON) 區塊

        Args:
            file_path: Hook 檔案路徑

        Returns:
            metadata 字典，或 None（如果無 metadata）

        Raises:
            json.JSONDecodeError: JSON 解析失敗
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            raise IOError(f"無法讀取檔案 {file_path}: {e}")

        # 提取 docstring
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if not docstring_match:
            return None

        docstring = docstring_match.group(1)

        # 搜尋 HOOK_METADATA (JSON): 區塊
        metadata_match = re.search(
            r'HOOK_METADATA\s*\(JSON\)\s*:\s*(\{.*?\})',
            docstring,
            re.DOTALL
        )

        if not metadata_match:
            return None

        json_str = metadata_match.group(1)

        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"無效的 JSON 格式在 docstring: {e.msg}",
                e.doc,
                e.pos
            )

        return metadata

    @staticmethod
    def extract_from_sidecar(file_path: str) -> Optional[Dict[str, Any]]:
        """
        從 JSON Sidecar 檔案讀取 metadata

        Args:
            file_path: Hook 檔案路徑

        Returns:
            metadata 字典，或 None（如果 Sidecar 不存在）

        Raises:
            json.JSONDecodeError: JSON 解析失敗
        """
        # 構造 Sidecar 路徑
        hook_name = Path(file_path).name
        sidecar_dir = Path(file_path).parent / "metadata"
        sidecar_path = sidecar_dir / hook_name.replace(".py", ".json")

        if not sidecar_path.exists():
            return None

        try:
            with open(sidecar_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Sidecar JSON 無效: {e.msg}",
                e.doc,
                e.pos
            )

        return metadata

    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        驗證 metadata 的有效性

        Args:
            metadata: metadata 字典

        Returns:
            (is_valid, errors, warnings) - 是否有效、錯誤清單、警告清單
        """
        errors = []
        warnings = []

        # 驗證必填欄位
        if "event_type" not in metadata:
            errors.append("缺少必填欄位: event_type")
            return (False, errors, warnings)

        # 驗證 event_type 有效性
        event_type = metadata["event_type"]
        if event_type not in MetadataExtractor.VALID_EVENT_TYPES:
            errors.append(f"無效的 event_type: {event_type}")

        # 驗證可選欄位 - matcher
        if "matcher" in metadata:
            matcher = metadata["matcher"]
            if matcher:  # 不為空時驗證
                matchers = matcher.split("|")
                for m in matchers:
                    m = m.strip()
                    if m and m not in MetadataExtractor.VALID_MATCHERS:
                        warnings.append(f"未知的 matcher: {m}")

        # 驗證可選欄位 - timeout
        if "timeout" in metadata:
            timeout = metadata["timeout"]
            if not isinstance(timeout, int) or timeout <= 0:
                warnings.append(f"timeout 應為正整數，目前: {timeout}")

        # 驗證可選欄位 - dependencies
        if "dependencies" in metadata:
            deps = metadata["dependencies"]
            if not isinstance(deps, list):
                errors.append("dependencies 應為陣列")

        if errors:
            return (False, errors, warnings)
        else:
            return (True, [], warnings)


# ============================================================================
# SettingsManager - 配置管理模組
# ============================================================================

class SettingsManager:
    """管理 settings.json 檔案的讀寫、備份和合併"""

    @staticmethod
    def load_settings(file_path: str) -> Dict[str, Any]:
        """
        讀取並解析 settings.json

        Args:
            file_path: settings.json 檔案路徑

        Returns:
            解析後的 settings 字典

        Raises:
            FileNotFoundError: 檔案不存在
            json.JSONDecodeError: JSON 無效
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"settings.json 不存在: {file_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"settings.json JSON 無效: {e.msg}",
                e.doc,
                e.pos
            )

        return settings

    @staticmethod
    def save_settings(file_path: str, settings: Dict[str, Any]) -> None:
        """
        將配置寫入 settings.json

        Args:
            file_path: 目標檔案路徑
            settings: 要寫入的配置

        Raises:
            PermissionError: 無寫入權限
            IOError: 寫入失敗
        """
        path = Path(file_path)

        # 檢查寫入權限
        parent = path.parent
        if not os.access(parent, os.W_OK):
            raise PermissionError(f"無寫入權限: {file_path}")

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"寫入失敗: {e}")

    @staticmethod
    def create_backup(file_path: str) -> str:
        """
        建立設定檔備份

        Args:
            file_path: 原始檔案路徑

        Returns:
            備份檔案路徑

        Raises:
            Exception: 備份建立失敗
        """
        path = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = path.parent / f"{path.name}.backup-{timestamp}"

        # 處理時間戳重複
        counter = 1
        original_backup = backup_path
        while backup_path.exists():
            backup_path = original_backup.parent / f"{original_backup.name}-{counter:03d}"
            counter += 1

        try:
            shutil.copy2(str(path), str(backup_path))

            # 驗證備份有效
            with open(backup_path, 'r', encoding='utf-8') as f:
                json.load(f)

            return str(backup_path)
        except Exception as e:
            raise Exception(f"備份建立失敗: {e}")

    @staticmethod
    def merge_hooks(
        existing: Dict[str, Any],
        new_hooks_metadata: List[Tuple[str, Dict[str, Any]]]
    ) -> Tuple[Dict[str, Any], int, List[Dict[str, str]]]:
        """
        合併新 Hook 到現有配置

        Args:
            existing: 現有 settings 配置
            new_hooks_metadata: [(hook_name, metadata), ...] 清單

        Returns:
            (merged_settings, added_count, conflicts)
        """
        merged = json.loads(json.dumps(existing))  # 深拷貝
        conflicts = []
        added_count = 0

        for hook_name, metadata in new_hooks_metadata:
            event_type = metadata.get("event_type")
            matcher = metadata.get("matcher", "")

            # 定位目標位置
            if event_type not in merged.get("hooks", {}):
                merged.setdefault("hooks", {})[event_type] = []

            event_hooks = merged["hooks"][event_type]

            # 檢查衝突 - 同 Hook + 同 matcher 下是否已存在
            if SettingsManager._is_hook_registered(merged, hook_name, event_type, matcher):
                conflicts.append({
                    "hook": hook_name,
                    "reason": "已登記"
                })
                continue

            # 建立 Hook 配置
            hook_config = SettingsManager._create_hook_config(hook_name, metadata)

            # 根據 matcher 定位添加位置
            if matcher:
                # 搜尋或建立 matcher 條目
                matcher_entry = None
                for entry in event_hooks:
                    if entry.get("matcher") == matcher:
                        matcher_entry = entry
                        break

                if not matcher_entry:
                    matcher_entry = {"matcher": matcher, "hooks": []}
                    event_hooks.append(matcher_entry)

                matcher_entry["hooks"].append(hook_config)
            else:
                # 無 matcher，直接添加
                if not event_hooks:
                    event_hooks.append({"hooks": []})
                event_hooks[0].get("hooks", []).append(hook_config)

            added_count += 1

        return merged, added_count, conflicts

    @staticmethod
    def _is_hook_registered(
        settings: Dict[str, Any],
        hook_name: str,
        event_type: str,
        matcher: str
    ) -> bool:
        """檢查 Hook 是否已在指定位置登記"""
        if event_type not in settings.get("hooks", {}):
            return False

        event_hooks = settings["hooks"][event_type]

        for entry in event_hooks:
            entry_matcher = entry.get("matcher", "")
            if matcher and entry_matcher != matcher:
                continue

            for hook_config in entry.get("hooks", []):
                command = hook_config.get("command", "")
                if hook_name in command:
                    return True

        return False

    @staticmethod
    def _create_hook_config(hook_name: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """建立 Hook 配置條目"""
        config = {
            "type": "command",
            "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{hook_name}"
        }

        if metadata.get("timeout"):
            config["timeout"] = metadata["timeout"]

        return config


# ============================================================================
# HookRegistrar - Hook 協調與掃描模組
# ============================================================================

class HookRegistrar:
    """掃描 Hook 目錄並協調註冊流程"""

    @staticmethod
    def scan_hooks_directory(hooks_dir: str) -> List[str]:
        """
        掃描 Hook 目錄，返回所有 Hook 檔案名稱

        Args:
            hooks_dir: Hook 目錄路徑

        Returns:
            Hook 檔案名稱清單

        Raises:
            DirectoryError: 目錄不存在
        """
        path = Path(hooks_dir)

        if not path.is_dir():
            raise DirectoryError(f"Hook 目錄不存在: {hooks_dir}")

        # 載入排除清單
        exclude_list = set()
        exclude_file = path / "hook-exclude-list.json"
        if exclude_file.exists():
            try:
                with open(exclude_file, 'r', encoding='utf-8') as f:
                    exclude_data = json.load(f)
                    exclude_list = set(exclude_data.get("exclude_files", []))
            except Exception:
                pass  # 忽略排除清單讀取失敗

        # 掃描 .py 檔案
        all_hooks = []
        for py_file in sorted(path.glob("*.py")):
            hook_name = py_file.name
            if hook_name not in exclude_list:
                all_hooks.append(hook_name)

        return all_hooks

    @staticmethod
    def identify_registered_hooks(
        all_hooks: List[str],
        settings: Dict[str, Any]
    ) -> Tuple[List[str], List[str]]:
        """
        識別已登記和未登記的 Hook

        Args:
            all_hooks: 所有 Hook 檔案名稱
            settings: settings.json 配置

        Returns:
            (registered_hooks, unregistered_hooks)
        """
        registered = set()

        # 遍歷 settings 中的所有 Hook 配置
        for event_type, event_hooks in settings.get("hooks", {}).items():
            for entry in event_hooks:
                for hook_config in entry.get("hooks", []):
                    command = hook_config.get("command", "")
                    for hook_name in all_hooks:
                        if hook_name in command:
                            registered.add(hook_name)

        unregistered = [h for h in all_hooks if h not in registered]

        return sorted(list(registered)), sorted(unregistered)

    @staticmethod
    def extract_all_metadata(
        all_hooks: List[str],
        hooks_dir: str
    ) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]]]:
        """
        提取所有 Hook 的 metadata

        Args:
            all_hooks: Hook 檔案名稱清單
            hooks_dir: Hook 目錄路徑

        Returns:
            (metadata_map, failed_hooks) - metadata 字典和失敗清單
        """
        metadata_map = {}
        failed_hooks = []
        extractor = MetadataExtractor()

        for hook_name in all_hooks:
            file_path = os.path.join(hooks_dir, hook_name)
            metadata = None

            # 嘗試 Docstring
            try:
                metadata = extractor.extract_from_docstring(file_path)
            except Exception as e:
                pass  # 失敗時繼續嘗試 Sidecar

            # 失敗時降級到 JSON Sidecar
            if not metadata:
                try:
                    metadata = extractor.extract_from_sidecar(file_path)
                except Exception as e:
                    pass

            # 驗證 metadata
            if metadata:
                is_valid, errors, warnings = extractor.validate_metadata(metadata)
                if is_valid:
                    metadata_map[hook_name] = metadata
                else:
                    failed_hooks.append((hook_name, f"驗證失敗: {', '.join(errors)}"))
            else:
                failed_hooks.append((hook_name, "無 metadata"))

        return metadata_map, failed_hooks

    @staticmethod
    def generate_report(
        registered_count: int,
        newly_registered: int,
        failed_count: int,
        failed_details: List[Tuple[str, str]]
    ) -> str:
        """
        生成執行報告

        Args:
            registered_count: 已登記數
            newly_registered: 新增數
            failed_count: 失敗數
            failed_details: 失敗詳情清單

        Returns:
            報告字符串
        """
        report = "=" * 60 + "\n"
        report += "[Hook 自動註冊 - 執行報告]\n"
        report += "=" * 60 + "\n\n"

        report += "摘要:\n"
        report += f"  已登記: {registered_count}\n"
        report += f"  新增: {newly_registered}\n"
        report += f"  失敗: {failed_count}\n\n"

        if failed_details:
            report += "失敗詳情:\n"
            for hook_name, reason in failed_details:
                report += f"  - {hook_name}: {reason}\n"
            report += "\n"

        report += "=" * 60 + "\n"

        return report


# ============================================================================
# 命令行介面和主程式
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """解析命令行參數"""
    parser = argparse.ArgumentParser(
        description="Hook 自動註冊機制 - 掃描並自動註冊 Hook"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="預覽模式，不實際修改檔案"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細日誌模式"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="強制更新（即使 Hook 已登記也更新配置）"
    )

    parser.add_argument(
        "--output",
        default=None,
        help="指定輸出的 settings.json 路徑"
    )

    return parser.parse_args()


def validate_environment(
    hooks_dir: str = ".claude/hooks",
    settings_file: str = ".claude/settings.json"
) -> List[str]:
    """
    驗證執行環境

    Args:
        hooks_dir: Hook 目錄路徑
        settings_file: settings.json 檔案路徑

    Returns:
        錯誤訊息清單（空表示無錯誤）
    """
    errors = []

    if not Path(hooks_dir).is_dir():
        errors.append(f"Hook 目錄不存在: {hooks_dir}")

    if not Path(settings_file).is_file():
        errors.append(f"settings.json 檔案不存在: {settings_file}")

    return errors


def generate_preview_report(
    all_hooks: List[str],
    registered_hooks: List[str],
    unregistered_hooks: List[str],
    metadata_map: Dict[str, Dict[str, Any]],
    failed_hooks: List[Tuple[str, str]]
) -> str:
    """生成預覽報告"""
    report = "=" * 60 + "\n"
    report += "[Hook 自動註冊 - 預覽模式]\n"
    report += "=" * 60 + "\n\n"

    report += "掃描結果:\n"
    report += f"  總 Hook 數: {len(all_hooks)}\n"
    report += f"  已登記: {len(registered_hooks)}\n"
    report += f"  未登記: {len(unregistered_hooks)}\n"
    report += f"  無效: {len(failed_hooks)}\n\n"

    if unregistered_hooks or failed_hooks:
        report += "待處理的 Hook:\n"

        # 已驗證的未登記 Hook
        verified_unregistered = [
            h for h in unregistered_hooks
            if h in metadata_map
        ]
        for hook_name in verified_unregistered:
            metadata = metadata_map[hook_name]
            report += f"  - {hook_name}\n"
            report += f"    Event: {metadata.get('event_type')}\n"
            if metadata.get('matcher'):
                report += f"    Matcher: {metadata['matcher']}\n"
            report += "\n"

        # 失敗的 Hook
        if failed_hooks:
            report += "失敗的 Hook:\n"
            for hook_name, reason in failed_hooks:
                report += f"  - {hook_name}: {reason}\n"

    report += "\n預覽模式：無實際修改\n"
    report += "=" * 60 + "\n"

    return report


def main() -> int:
    """主程式"""
    args = parse_arguments()

    # Step 1: 環境驗證
    env_errors = validate_environment()
    if env_errors:
        print("環境驗證失敗:")
        for error in env_errors:
            print(f"  [ERROR] {error}")
        return 2

    hooks_dir = ".claude/hooks"
    settings_file = args.output or ".claude/settings.json"

    # Step 2: 掃描和提取
    try:
        registrar = HookRegistrar()
        all_hooks = registrar.scan_hooks_directory(hooks_dir)
        metadata_map, failed_hooks = registrar.extract_all_metadata(all_hooks, hooks_dir)
        settings = SettingsManager.load_settings(settings_file)
        registered, unregistered = registrar.identify_registered_hooks(all_hooks, settings)

        if args.verbose:
            print(f"掃描完成: {len(all_hooks)} 個 Hook")
            print(f"  已登記: {len(registered)}")
            print(f"  未登記: {len(unregistered)}")
            print(f"  無效: {len(failed_hooks)}")
            print()

    except Exception as e:
        print(f"[ERROR] 掃描失敗: {e}")
        return 1

    # Step 3: 預覽模式
    if args.dry_run:
        report = generate_preview_report(
            all_hooks, registered, unregistered, metadata_map, failed_hooks
        )
        print(report)
        return 0

    # Step 4: 實際執行
    try:
        # 備份
        backup_path = SettingsManager.create_backup(settings_file)
        if args.verbose:
            print(f"備份建立: {backup_path}")

        # 合併配置
        manager = SettingsManager()
        new_hooks = [
            (h, metadata_map[h])
            for h in unregistered
            if h in metadata_map
        ]

        merged_settings, added_count, conflicts = manager.merge_hooks(settings, new_hooks)

        if conflicts and args.verbose:
            print(f"檢測到 {len(conflicts)} 個衝突:")
            for c in conflicts:
                print(f"  - {c['hook']}: {c['reason']}")

        # 寫入配置
        manager.save_settings(settings_file, merged_settings)

        # 驗證
        SettingsManager.load_settings(settings_file)

        # 報告
        report = registrar.generate_report(
            len(registered),
            added_count,
            len(failed_hooks),
            failed_hooks
        )
        print(report)

        if failed_hooks:
            return 1
        else:
            return 0

    except Exception as e:
        print(f"[ERROR] 執行失敗: {e}")
        print("[INFO] 嘗試恢復備份...")
        try:
            shutil.copy2(backup_path, settings_file)
            print("[INFO] 備份恢復成功")
        except Exception as restore_error:
            print(f"[ERROR] 備份恢復失敗: {restore_error}")
            print(f"[INFO] 請手動執行: cp {backup_path} {settings_file}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
