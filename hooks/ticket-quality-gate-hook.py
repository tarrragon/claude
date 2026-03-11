#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Ticket Quality Gate Hook

自動檢測 Ticket 品質（C1/C2/C3 Code Smell）

使用方式:
    PostToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_name":"Write","tool_input":{"file_path":"test.md","content":"..."}}' | python3 ticket-quality-gate-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）

重構紀錄 (v0.28.0):
- 使用 .claude/lib/hook_io 共用模組
- 使用 .claude/config/quality_rules.yaml 配置檔案
- 優化觸發條件配置載入
"""

import sys
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging, run_hook_safely, read_json_from_stdin,
    get_project_root, validate_hook_input
)
from lib.hook_messages import QualityMessages, CoreMessages, format_message

from lib.ticket_quality.detectors import (
    check_god_ticket_automated,
    check_incomplete_ticket_automated,
    check_ambiguous_responsibility_automated
)
from lib.ticket_quality.reporters import (
    generate_markdown_report,
    generate_json_report
)

# 注意：hook_io 和 config_loader 需要別處定義或導入
try:
    from hook_io import read_hook_input, write_hook_output
except ImportError:
    def read_hook_input():
        return json.load(sys.stdin)
    def write_hook_output(data):
        print(json.dumps(data, ensure_ascii=False))

try:
    from config_loader import load_quality_rules
except ImportError:
    def load_quality_rules():
        return {}

# 全域常數
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2

# 全域快取（記憶體）
_check_cache: Dict[str, Dict[str, Any]] = {}
_quality_config: Optional[Dict[str, Any]] = None

def get_quality_config() -> Dict[str, Any]:
    """取得品質規則配置（快取）"""
    global _quality_config
    if _quality_config is None:
        _quality_config = load_quality_rules()
    return _quality_config

def get_cache_ttl() -> timedelta:
    """從配置取得快取 TTL"""
    config = get_quality_config()
    ttl_minutes = config.get("cache", {}).get("ttl_minutes", 5)
    return timedelta(minutes=ttl_minutes)

def get_default_cache_stats() -> Dict[str, Any]:
    """從配置取得預設快取統計"""
    config = get_quality_config()
    return config.get("cache", {}).get("default_stats", {
        "total_checks": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "avg_execution_time_with_cache": 0.0,
        "avg_execution_time_without_cache": 0.0,
        "last_updated": "",
        "version": "v0.28.0"
    })

def validate_input(input_data: Dict[str, Any], logger) -> bool:
    """
    驗證輸入格式 - 由 hook_utils.validate_hook_input 擔當基礎驗證，
    此函式負責額外的深層驗證（tool_input 的子欄位檢查）

    Args:
        input_data: Hook 輸入資料
        logger: 日誌記錄器

    Returns:
        bool - 輸入格式是否正確
    """
    # 基礎驗證：必要頂層欄位
    if not validate_hook_input(input_data, logger, ("tool_name", "tool_input")):
        return False

    # 額外驗證：tool_input 子欄位
    tool_input = input_data.get("tool_input") or {}
    if "file_path" not in tool_input or "content" not in tool_input:
        logger.error("tool_input 缺少 file_path 或 content")
        return False

    return True

def should_trigger_check(input_data: Dict[str, Any], logger) -> bool:
    """
    判斷是否應觸發檢測（使用配置檔案）

    條件:
    1. 工具類型為 Write/Edit/MultiEdit
    2. 檔案副檔名為 .md
    3. 檔案路徑包含 Ticket 相關關鍵字
    4. 檔案內容包含 Ticket 結構標記

    Args:
        input_data: Hook 輸入資料
        logger: 日誌記錄器

    Returns:
        bool - 是否應觸發檢測
    """
    # 從配置載入觸發條件
    config = get_quality_config()
    trigger_config = config.get("trigger_conditions", {})

    # 條件 1: 工具類型檢查
    tool_name = input_data.get("tool_name", "")
    allowed_tools = trigger_config.get("allowed_tools", ["Write", "Edit", "MultiEdit"])
    if tool_name not in allowed_tools:
        logger.info(f"工具類型不符: {tool_name}")
        return False

    # 條件 2: 檔案類型檢查
    file_path = input_data["tool_input"]["file_path"]
    file_extension = trigger_config.get("file_extension", ".md")
    if not file_path.endswith(file_extension):
        logger.info(f"檔案類型不符: {file_path}")
        return False

    # 條件 3: 檔案路徑關鍵字檢查
    ticket_path_keywords = trigger_config.get("ticket_path_keywords", [
        "docs/work-logs/",
        "docs/tickets/",
        "-ticket-",
        "-task-"
    ])
    if not any(keyword in file_path for keyword in ticket_path_keywords):
        logger.info(f"檔案路徑不符合 Ticket 格式: {file_path}")
        return False

    # 條件 4: 檔案內容結構檢查
    content = input_data["tool_input"]["content"]
    ticket_structure_markers = trigger_config.get("ticket_structure_markers", [
        "## 實作步驟",
        "## 驗收條件",
        "## 參考文件",
        "Layer 1", "Layer 2", "Layer 3", "Layer 4", "Layer 5"
    ])
    if not any(marker in content for marker in ticket_structure_markers):
        logger.info("檔案內容不符合 Ticket 結構")
        return False

    logger.info(f"觸發條件檢查通過: {file_path}")
    return True

def calculate_file_hash(content: str) -> str:
    """
    計算檔案內容 hash

    Args:
        content: 檔案內容

    Returns:
        str - MD5 hash
    """
    return hashlib.md5(content.encode()).hexdigest()

def should_skip_check_due_to_cache(file_path: str, file_hash: str, logger) -> bool:
    """
    檢查是否應跳過檢測（基於快取，使用配置的 TTL）

    快取命中條件:
    1. 快取中存在該檔案
    2. 時間未過期（從配置讀取）
    3. 檔案 hash 未變更

    Args:
        file_path: 檔案路徑
        file_hash: 檔案內容 hash
        logger: 日誌記錄器

    Returns:
        bool - True 表示應跳過（快取命中），False 表示應執行檢測
    """
    # 檢查快取是否存在
    if file_path not in _check_cache:
        logger.debug(f"快取未命中: {file_path}")
        return False

    cached_entry = _check_cache[file_path]
    cached_time = cached_entry["time"]
    cached_hash = cached_entry["hash"]

    # 從配置取得 TTL
    cache_ttl = get_cache_ttl()

    # 檢查 1: 時間是否過期
    if datetime.now() - cached_time > cache_ttl:
        logger.debug(f"快取過期: {file_path}")
        del _check_cache[file_path]
        return False

    # 檢查 2: 檔案內容是否變更
    if cached_hash != file_hash:
        logger.debug(f"檔案內容已變更: {file_path}")
        del _check_cache[file_path]
        return False

    # 快取命中
    logger.info(f"快取命中: {file_path}")
    return True

def update_check_cache(file_path: str, file_hash: str, check_results: Dict[str, Any], logger) -> None:
    """
    更新快取

    Args:
        file_path: 檔案路徑
        file_hash: 檔案內容 hash
        check_results: 檢測結果
        logger: 日誌記錄器
    """
    _check_cache[file_path] = {
        "hash": file_hash,
        "time": datetime.now(),
        "result": check_results
    }
    logger.debug(f"快取已更新: {file_path}")

def cleanup_expired_cache(logger) -> None:
    """清理過期快取（避免記憶體洩漏，使用配置的 TTL）"""
    current_time = datetime.now()
    cache_ttl = get_cache_ttl()
    expired_keys = [
        file_path for file_path, cached_entry in _check_cache.items()
        if current_time - cached_entry["time"] > cache_ttl
    ]

    for key in expired_keys:
        del _check_cache[key]
        logger.debug(f"清理過期快取: {key}")

    if expired_keys:
        logger.info(f"清理了 {len(expired_keys)} 個過期快取條目")

def get_cache_stats_dir() -> Path:
    """
    取得快取統計目錄路徑

    Returns:
        Path - 快取統計目錄
    """
    project_dir = get_project_root()
    cache_dir = project_dir / ".claude" / "hook-logs" / "ticket-quality-gate" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def load_cache_stats(logger) -> Dict[str, Any]:
    """
    載入快取統計資料（使用配置的預設值）

    Returns:
        dict - 快取統計資料
    """
    cache_dir = get_cache_stats_dir()
    stats_file = cache_dir / "cache_stats.json"

    if not stats_file.exists():
        return get_default_cache_stats()

    try:
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        logger.debug("快取統計資料載入成功")
        return stats
    except Exception as e:
        logger.warning(f"快取統計資料載入失敗，使用預設值: {e}")
        return get_default_cache_stats()

def save_cache_stats(stats: Dict[str, Any], logger) -> None:
    """
    儲存快取統計資料

    Args:
        stats: 快取統計資料
        logger: 日誌記錄器
    """
    cache_dir = get_cache_stats_dir()
    stats_file = cache_dir / "cache_stats.json"

    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.debug("快取統計資料儲存成功")
    except Exception as e:
        # 快取統計失敗不應該阻止 Hook 執行
        logger.warning(f"快取統計資料儲存失敗: {e}")

def update_cache_stats(cache_hit: bool, execution_time: float, logger) -> None:
    """
    更新快取統計資料

    使用指數移動平均（EMA）計算平均執行時間，避免舊資料過度影響

    Args:
        cache_hit: 是否命中快取
        execution_time: 執行時間（秒）
        logger: 日誌記錄器
    """
    try:
        stats = load_cache_stats(logger)

        # 更新統計資料
        stats["total_checks"] += 1

        # 指數移動平均（alpha=0.1，較重視新資料）
        alpha = 0.1

        if cache_hit:
            stats["cache_hits"] += 1
            prev_avg = stats.get("avg_execution_time_with_cache", execution_time)
            stats["avg_execution_time_with_cache"] = (
                alpha * execution_time + (1 - alpha) * prev_avg
            )
        else:
            stats["cache_misses"] += 1
            prev_avg = stats.get("avg_execution_time_without_cache", execution_time)
            stats["avg_execution_time_without_cache"] = (
                alpha * execution_time + (1 - alpha) * prev_avg
            )

        stats["last_updated"] = datetime.now().isoformat()

        # 儲存統計資料
        save_cache_stats(stats, logger)

        logger.info(
            f"快取統計更新：命中={cache_hit}, 執行時間={execution_time:.3f}s, "
            f"總檢測={stats['total_checks']}, 命中率={(stats['cache_hits'] / stats['total_checks'] * 100):.1f}%"
        )
    except Exception as e:
        logger.warning(f"更新快取統計失敗: {e}")

def generate_cache_stats_report(logger) -> str:
    """
    生成快取統計報告（Markdown 格式）

    Returns:
        str: Markdown 格式的統計報告
    """
    try:
        stats = load_cache_stats(logger)

        # 計算命中率
        total = stats.get("total_checks", 0)
        hits = stats.get("cache_hits", 0)
        hit_rate = (hits / total * 100) if total > 0 else 0

        # 計算效能提升
        with_cache = stats.get("avg_execution_time_with_cache", 0)
        without_cache = stats.get("avg_execution_time_without_cache", 0)
        speedup = (without_cache / with_cache) if with_cache > 0 else 1.0

        report = f"""## 快取統計報告

**版本**: {stats.get("version", "unknown")}
**最後更新**: {stats.get("last_updated", "N/A")}

### 總覽

- **總檢測次數**: {total:,}
- **快取命中**: {hits:,} ({hit_rate:.1f}%)
- **快取未命中**: {stats.get("cache_misses", 0):,} ({100 - hit_rate:.1f}%)

### 執行時間

- **快取命中平均時間**: {with_cache:.3f}s
- **快取未命中平均時間**: {without_cache:.3f}s
- **效能提升**: {speedup:.1f}x

### 效能評級

"""

        # 效能評級
        if hit_rate >= 70:
            report += "優秀 - 快取命中率 > 70%\n"
        elif hit_rate >= 50:
            report += "良好 - 快取命中率 50-70%\n"
        else:
            report += "需改善 - 快取命中率 < 50%\n"

        report += "\n---\n\n_此統計由 Ticket Quality Gate Hook 自動生成_\n"

        return report
    except Exception as e:
        logger.warning(f"生成快取統計報告失敗: {e}")
        return """## 快取統計報告

_無統計資料_

快取統計將在首次執行後開始記錄。
"""

def run_check_with_error_handling(check_name: str, check_function, logger) -> Dict[str, Any]:
    """
    執行檢測函式，處理異常

    策略: 捕捉所有異常，回傳錯誤狀態而非拋出

    Args:
        check_name: 檢測名稱
        check_function: 檢測函式
        logger: 日誌記錄器

    Returns:
        dict - 檢測結果或錯誤資訊
    """
    try:
        logger.info(f"執行 {check_name} 檢測...")
        result = check_function()
        logger.info(f"{check_name} 檢測完成，狀態: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"{check_name} 檢測失敗: {e}", exc_info=True)
        return {
            "status": "error",
            "confidence": 0.0,
            "error_message": str(e),
            "error_type": type(e).__name__
        }

def run_all_checks(ticket_content: str, file_path: str, logger) -> Dict[str, Any]:
    """
    執行所有 Code Smell 檢測

    策略: 即使部分檢測失敗，仍回傳其他檢測結果

    Args:
        ticket_content: Ticket 內容
        file_path: 檔案路徑
        logger: 日誌記錄器

    Returns:
        dict - 完整檢測結果
    """
    results = {
        "file_path": file_path,
        "check_time": datetime.now().isoformat(),
        "checks": {},
        "summary": {
            "total_checks": 3,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "errors": 0
        }
    }

    # C1 檢測
    results["checks"]["c1_god_ticket"] = run_check_with_error_handling(
        "C1 God Ticket",
        lambda: check_god_ticket_automated(ticket_content),
        logger
    )
    update_summary(results, "c1_god_ticket")

    # C2 檢測
    results["checks"]["c2_incomplete_ticket"] = run_check_with_error_handling(
        "C2 Incomplete Ticket",
        lambda: check_incomplete_ticket_automated(ticket_content),
        logger
    )
    update_summary(results, "c2_incomplete_ticket")

    # C3 檢測
    results["checks"]["c3_ambiguous_responsibility"] = run_check_with_error_handling(
        "C3 Ambiguous Responsibility",
        lambda: check_ambiguous_responsibility_automated(ticket_content),
        logger
    )
    update_summary(results, "c3_ambiguous_responsibility")

    # 計算整體狀態和信心度
    results["overall_status"] = calculate_overall_status(results)
    results["overall_confidence"] = calculate_overall_confidence(results)

    # 收集需人工審查項目
    results["summary"]["needs_human_review"] = collect_needs_human_review(results)

    return results

def update_summary(results: Dict[str, Any], check_key: str) -> None:
    """
    更新檢測摘要

    Args:
        results: 檢測結果
        check_key: 檢測鍵名
    """
    check_result = results["checks"][check_key]
    status = check_result.get("status", "unknown")

    if status == "passed":
        results["summary"]["passed"] += 1
    elif status == "failed":
        results["summary"]["failed"] += 1
    elif status == "warning":
        results["summary"]["warnings"] += 1
    elif status == "error":
        results["summary"]["errors"] += 1

def calculate_overall_status(results: Dict[str, Any]) -> str:
    """
    計算整體狀態

    Args:
        results: 檢測結果

    Returns:
        str - "passed" / "failed" / "warning" / "error" / "partial"
    """
    summary = results["summary"]

    if summary["errors"] == summary["total_checks"]:
        return "error"
    elif summary["errors"] > 0:
        return "partial"
    elif summary["failed"] > 0:
        return "failed"
    elif summary["warnings"] > 0:
        return "warning"
    else:
        return "passed"

def calculate_overall_confidence(results: Dict[str, Any]) -> float:
    """
    計算整體信心度

    Args:
        results: 檢測結果

    Returns:
        float - 整體信心度 (0.0-1.0)
    """
    checks = results["checks"]
    confidences = []

    for check_key, check_result in checks.items():
        if check_result.get("status") != "error":
            confidences.append(check_result.get("confidence", 0.0))

    if not confidences:
        return 0.0

    # 如果有失敗，使用平均值；如果全部通過，使用最小值（保守評估）
    if results["overall_status"] == "failed":
        return sum(confidences) / len(confidences)
    else:
        return min(confidences)

def collect_needs_human_review(results: Dict[str, Any]) -> list:
    """
    收集需人工審查的項目

    Args:
        results: 檢測結果

    Returns:
        list - 需人工審查的檢測項目名稱
    """
    needs_review = []

    for check_key, check_result in results["checks"].items():
        if check_result.get("needs_human_review", False):
            needs_review.append(check_key)

    return needs_review

def generate_hook_output(check_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成 Hook 輸出格式

    Args:
        check_results: 檢測結果

    Returns:
        dict - Hook 輸出 JSON
    """
    # 生成 Markdown 報告
    markdown_report = generate_markdown_report(
        check_results,
        check_results["file_path"]
    )

    # 決定 decision 和 reason
    decision, reason = determine_decision(check_results)

    return {
        "decision": decision,
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": markdown_report
        },
        "check_results": check_results
    }

def determine_decision(check_results: Dict[str, Any]) -> tuple:
    """
    根據檢測結果決定 decision 和 reason

    規則:
    - 任何 failed 狀態 → decision: "block"
    - 只有 warning 狀態 → decision: "allow" + 警告訊息
    - 全部 passed → decision: "allow"
    - 錯誤 → decision: "allow"（非阻塞原則）

    Args:
        check_results: 檢測結果

    Returns:
        (decision, reason)
    """
    summary = check_results["summary"]
    overall_status = check_results["overall_status"]

    if overall_status == "error":
        return "allow", format_message(CoreMessages.HOOK_ERROR, error="檢測系統錯誤，請查看日誌")

    if overall_status == "partial":
        reason = f"⚠️ 部分檢測失敗（{summary['errors']} 個錯誤），允許操作繼續"
        return "allow", reason

    if summary["failed"] > 0:
        failed_checks = [
            name for name, check in check_results["checks"].items()
            if check["status"] == "failed"
        ]
        reason = format_message(QualityMessages.TICKET_QUALITY_CHECK_FAILED, reason=f"{summary['failed']} 個 Code Smell: {', '.join(failed_checks)}")
        return "block", reason

    if summary["warnings"] > 0:
        warning_checks = [
            name for name, check in check_results["checks"].items()
            if check["status"] == "warning"
        ]
        reason = f"檢測通過，但有 {summary['warnings']} 個警告需要注意: {', '.join(warning_checks)}"
        return "allow", reason

    reason = QualityMessages.TICKET_QUALITY_CHECK_PASSED
    return "allow", reason

def save_check_report(check_results: Dict[str, Any], file_path: str, logger) -> None:
    """
    儲存檢測報告

    Args:
        check_results: 檢測結果
        file_path: Ticket 檔案路徑
        logger: 日誌記錄器
    """
    # 建立報告目錄
    project_dir = get_project_root()
    report_dir = project_dir / ".claude" / "hook-logs" / "ticket-quality-gate" / datetime.now().strftime("%Y-%m-%d")
    report_dir.mkdir(parents=True, exist_ok=True)

    # 產生報告檔名
    ticket_name = Path(file_path).stem
    timestamp = datetime.now().strftime("%H%M%S")

    # 儲存 Markdown 報告
    markdown_file = report_dir / f"check-{ticket_name}-{timestamp}.md"
    markdown_content = generate_markdown_report(check_results, file_path)
    markdown_file.write_text(markdown_content, encoding="utf-8")
    logger.info(f"Markdown 報告已儲存: {markdown_file}")

    # 儲存 JSON 報告
    json_file = report_dir / f"check-{ticket_name}-{timestamp}.json"
    json_content = generate_json_report(check_results, file_path)
    json_file.write_text(json_content, encoding="utf-8")
    logger.info(f"JSON 報告已儲存: {json_file}")

def print_error_json(error: Exception, logger) -> None:
    """
    輸出錯誤 JSON

    Args:
        error: 異常物件
        logger: 日誌記錄器
    """
    error_output = {
        "decision": "allow",
        "reason": CoreMessages.DEFAULT_ALLOW,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "Ticket 品質檢測執行失敗，請查看日誌: .claude/hook-logs/ticket-quality-gate/ticket-quality-gate.log"
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat()
        }
    }
    print(json.dumps(error_output, ensure_ascii=False, indent=2))

def main() -> int:
    """
    主入口點

    執行流程:
    1. 讀取 JSON 輸入
    2. 檢查觸發條件
    3. 快取檢查（記錄時間）
    4. 執行檢測（記錄時間）
    5. 產生 Hook 輸出
    6. 儲存報告
    7. 更新快取
    8. 更新快取統計
    9. 決定 exit code

    Returns:
        int - Exit code
    """
    import time

    logger = setup_hook_logging("ticket-quality-gate")

    try:
        # 步驟 1: 初始化日誌
        logger.info("Ticket Quality Gate Hook 啟動")

        # 步驟 2: 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)

        # 步驟 3: 驗證輸入格式
        if not validate_input(input_data, logger):
            logger.error("輸入格式錯誤")
            print(json.dumps({
                "decision": "allow",
                "reason": "Hook 輸入格式錯誤，允許操作繼續"
            }, ensure_ascii=False, indent=2))
            return EXIT_SUCCESS

        # 步驟 4: 檢查觸發條件
        if not should_trigger_check(input_data, logger):
            logger.info("不符合觸發條件，跳過檢測")
            return EXIT_SUCCESS

        # 步驟 5: 快取檢查（記錄開始時間）
        file_path = input_data["tool_input"]["file_path"]
        ticket_content = input_data["tool_input"]["content"]
        file_hash = calculate_file_hash(ticket_content)

        start_time = time.time()
        cache_hit = should_skip_check_due_to_cache(file_path, file_hash, logger)

        if cache_hit:
            # 快取命中：記錄快速執行時間
            execution_time = time.time() - start_time
            update_cache_stats(cache_hit=True, execution_time=execution_time, logger=logger)
            logger.info(f"快取命中，跳過檢測，執行時間: {execution_time:.3f}s")
            return EXIT_SUCCESS

        # 步驟 6: 執行檢測（快取未命中）
        check_results = run_all_checks(ticket_content, file_path, logger)
        execution_time = time.time() - start_time

        # 步驟 7: 產生 Hook 輸出
        hook_output = generate_hook_output(check_results)
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))

        # 步驟 8: 儲存報告
        save_check_report(check_results, file_path, logger)

        # 步驟 9: 更新快取
        update_check_cache(file_path, file_hash, check_results, logger)

        # 步驟 10: 更新快取統計（快取未命中）
        update_cache_stats(cache_hit=False, execution_time=execution_time, logger=logger)

        # 步驟 11: 清理過期快取
        cleanup_expired_cache(logger)

        # 步驟 12: 決定 exit code
        if check_results["overall_status"] == "failed":
            logger.info(f"檢測失敗，exit code = 2（通知 Claude），執行時間: {execution_time:.3f}s")
            return EXIT_BLOCK  # 2
        else:
            logger.info(f"檢測通過，exit code = 0，執行時間: {execution_time:.3f}s")
            return EXIT_SUCCESS  # 0

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        print_error_json(e, logger)
        return EXIT_ERROR  # 1

if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-quality-gate"))
