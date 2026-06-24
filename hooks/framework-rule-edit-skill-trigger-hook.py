#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""framework-rule-edit-skill-trigger-hook — Layer A 事前 SKILL 觸發提示

來源：Ticket 0.18.0-W17-127.2（W17-122 ANA Solution Layer A 落地）

觸發點：PreToolUse Edit / Write
條件：tool_input.file_path 經 lib.framework_paths.is_framework_path 判定為
      framework 規則層編輯，且本 session transcript 尚未呼叫
      `Skill compositional-writing`，且該路徑在本 session 內尚未警告過。

行為：
- 預設 exit 0 警告（避免大規模誤擋；ginger ROI 警示）
- strict 模式（.claude/config/skill-trigger-strict.yaml: strict=true）
  下對未呼叫 SKILL 場景 exit 2 阻擋，附豁免說明

訊息設計（acceptance #4）：
- 機會成本語氣（「建議」「成本較高的捷徑」「豁免條件」）
- 不使用「禁止 / 必須 / 不可」絕對主義詞

cache 設計（acceptance #2）：
- file-based per-session cache：.claude/hook-logs/skill-trigger-cache-{session_id}.json
- key = file_path（已警告路徑同 session 不再警告）
- session 邊界嚴格隔離：不同 session_id 不共用 cache

失敗策略：
- 任何 I/O / YAML / transcript 解析失敗皆走放行路徑（exit 0、不訊息）
- hook 不可阻擋主流程因自身內部錯誤
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
    from lib import framework_paths
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# 常數：路徑與檔名
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
STRICT_CONFIG_REL = ".claude/config/skill-trigger-strict.yaml"
CACHE_DIR_REL = ".claude/hook-logs"
CACHE_FILE_PREFIX = "skill-trigger-cache-"

# SKILL 名稱（Skill 工具呼叫的 input.skill 欄位值）
SKILL_NAME = "compositional-writing"


# ---- 訊息（機會成本語氣，acceptance #4） ----

WARN_MESSAGE = """\
[skill-trigger] 偵測到 framework 規則層編輯：{path}

建議：本次 Edit 涉及規則文字（rules/methodology/skill/agent 等），
compositional-writing SKILL 的原則 3（機會成本語氣）與抽象層級貼合
較難在無 SKILL 引導時自動覆蓋。建議在繼續編輯前讀一次 SKILL：

  Skill: compositional-writing

成本較高的捷徑：直接 Edit 而未讀 SKILL，後續可能需要 Layer 2 委員
（如 basil-writing-critic）審查時補修文字風格。

豁免條件（任一成立可忽略本提示）：
- 純格式調整（縮排、表格對齊、連結修正）未涉內容
- 已在近期 session 讀過 SKILL 且本次 Edit 範圍未涉原則 3 維度
- 修正既有錯字 / 簡體字 / 禁用詞（document-format-rules 範疇）

本次提示僅顯示一次，同 session 內同一路徑後續 Edit 不再警告。
"""

STRICT_MESSAGE = """\
[skill-trigger][strict] 偵測到 framework 規則層編輯：{path}

當前 strict 模式啟用（.claude/config/skill-trigger-strict.yaml）。
建議在繼續編輯前讀一次 compositional-writing SKILL，再重試本次操作；
讀後重試可獲得原則 3 自動覆蓋，若範圍未涉原則 3 維度可走豁免條件標記：

  Skill: compositional-writing

豁免條件（成立時可在 commit msg 標記豁免理由後重試）：
- 純格式調整（縮排、表格對齊、連結修正）未涉內容
- 已在近期 session 讀過 SKILL 且本次 Edit 範圍未涉原則 3 維度
- 修正既有錯字 / 簡體字 / 禁用詞

切回警告模式：將 skill-trigger-strict.yaml 的 strict 改回 false
（適用於 strict 在當前情境成本過高時的撤回路徑）。
"""


# ---- 工具函式 ----


def _get_project_dir() -> Path:
    """取得專案根目錄（CLAUDE_PROJECT_DIR 為主，fallback cwd）。"""
    env = os.environ.get(PROJECT_DIR_ENV)
    if env:
        return Path(env)
    return Path.cwd()


def _is_strict_mode(logger) -> bool:
    """讀取 strict 配置；任何錯誤皆視為 false（保守降級）。"""
    config_path = _get_project_dir() / STRICT_CONFIG_REL
    if not config_path.exists():
        logger.debug("strict 配置不存在，預設 false: %s", config_path)
        return False
    try:
        import yaml  # 延後 import 降低 hook 啟動成本

        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            return False
        return bool(data.get("strict", False))
    except Exception as e:  # noqa: BLE001 — 廣捕保守降級
        logger.info("strict 配置解析失敗（保守降級為 false）: %s", e)
        return False


def _cache_path(session_id: str) -> Path:
    """組出 session-scoped cache 檔路徑（嚴格隔離跨 session）。"""
    safe_id = session_id.replace("/", "_").replace("\\", "_") if session_id else "unknown"
    return _get_project_dir() / CACHE_DIR_REL / f"{CACHE_FILE_PREFIX}{safe_id}.json"


def _load_cache(session_id: str, logger) -> Set[str]:
    """讀取 session 內已警告路徑集合。失敗回傳空集合。"""
    if not session_id:
        return set()
    path = _cache_path(session_id)
    if not path.exists():
        return set()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            warned = data.get("warned_paths", [])
            if isinstance(warned, list):
                return {str(p) for p in warned}
        return set()
    except Exception as e:  # noqa: BLE001
        logger.info("cache 讀取失敗（視為空 cache）: %s", e)
        return set()


def _save_cache(session_id: str, warned: Set[str], logger) -> None:
    """寫入 session cache。失敗僅記錄不丟例外。"""
    if not session_id:
        return
    path = _cache_path(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {"session_id": session_id, "warned_paths": sorted(warned)},
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as e:  # noqa: BLE001
        logger.info("cache 寫入失敗（不影響主流程）: %s", e)


def _scan_transcript_for_skill(transcript_path: Optional[str], logger) -> bool:
    """掃描 JSONL transcript，判斷是否已呼叫過 Skill compositional-writing。

    純字串 / JSON 解析，禁用 LLM（W17-122 ginger 警示「hook 用純字串 match」）。

    Returns:
        True 若 transcript 中曾出現 tool_use(name=Skill, input.skill=compositional-writing)
    """
    if not transcript_path:
        logger.debug("transcript_path 為空，視為未呼叫")
        return False
    path = Path(transcript_path)
    if not path.exists():
        logger.debug("transcript 不存在: %s", transcript_path)
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # 快速字串預過濾（避免 JSON parse 每行）
                if SKILL_NAME not in line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    if block.get("name") != "Skill":
                        continue
                    inp = block.get("input") or {}
                    if isinstance(inp, dict) and inp.get("skill") == SKILL_NAME:
                        return True
    except OSError as e:
        logger.info("transcript 讀取失敗（視為未呼叫）: %s", e)
        return False
    return False


def _extract_file_path(input_data: dict) -> Optional[str]:
    """從 PreToolUse input 抽出 tool_input.file_path。"""
    tool_input = input_data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    fp = tool_input.get("file_path")
    if not isinstance(fp, str) or not fp:
        return None
    return fp


def _compute_edit_metrics(
    tool_name: str, tool_input: dict, file_path: str
) -> tuple:
    """計算編輯體量指標：(file_size_before, file_size_after, diff_line_count)。

    用途：協助 W17-198 dry-run 期間誤報分類（typo / 格式 / 語意修訂）。
    任何 IO/解析錯誤一律回傳 (0, 0, 0)，不破壞主流程。

    - Edit：依 old_string / new_string 估算 size after，diff_line_count 為
      新舊字串換行數差異絕對值（單行修改至少算 1 行）
    - Write：新檔 size before=0；覆寫時讀取既有檔計算 size_before / old_lines
    """
    try:
        if not isinstance(tool_input, dict):
            return (0, 0, 0)

        if tool_name == "Edit":
            old = tool_input.get("old_string") or ""
            new = tool_input.get("new_string") or ""
            if not isinstance(old, str) or not isinstance(new, str):
                return (0, 0, 0)
            try:
                file_size_before = os.path.getsize(file_path)
            except OSError:
                file_size_before = 0
            file_size_after = (
                file_size_before
                - len(old.encode("utf-8"))
                + len(new.encode("utf-8"))
            )
            line_diff = abs(new.count("\n") - old.count("\n"))
            # 單行修改（行數相同但內容變更）至少算 1 行
            if line_diff == 0 and old != new:
                line_diff = 1
            return (file_size_before, file_size_after, line_diff)

        if tool_name == "Write":
            content = tool_input.get("content") or ""
            if not isinstance(content, str):
                return (0, 0, 0)
            file_size_before = 0
            old_lines = 0
            try:
                if os.path.exists(file_path):
                    file_size_before = os.path.getsize(file_path)
                    with open(file_path, "r", encoding="utf-8") as f:
                        old_content = f.read()
                    old_lines = old_content.count("\n") + (1 if old_content else 0)
            except OSError:
                file_size_before = 0
                old_lines = 0
            file_size_after = len(content.encode("utf-8"))
            new_lines = content.count("\n") + (1 if content else 0)
            line_diff = abs(new_lines - old_lines)
            return (file_size_before, file_size_after, line_diff)

        return (0, 0, 0)
    except Exception:  # noqa: BLE001 — 廣捕保守降級，metrics 不可破壞主流程
        return (0, 0, 0)


def _normalize_to_relative(file_path: str) -> str:
    """將絕對路徑轉為相對於專案根目錄的形式（供 framework_paths 比對）。"""
    project_dir = _get_project_dir()
    try:
        p = Path(file_path).resolve()
        return str(p.relative_to(project_dir.resolve()))
    except (ValueError, OSError):
        return file_path


# ---- 主邏輯 ----


def main() -> int:
    logger = setup_hook_logging("framework-rule-edit-skill-trigger")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        logger.debug("跳過：工具 %s 非 Edit/Write", tool_name)
        return 0

    file_path = _extract_file_path(input_data)
    if not file_path:
        logger.debug("跳過：tool_input 無 file_path")
        return 0

    rel_path = _normalize_to_relative(file_path)

    if not framework_paths.is_framework_path(rel_path):
        logger.debug("跳過：非 framework 路徑 %s", rel_path)
        return 0

    session_id = input_data.get("session_id") or ""
    warned_paths = _load_cache(session_id, logger)

    if rel_path in warned_paths:
        logger.debug("跳過：本 session 已警告過 %s", rel_path)
        return 0

    # 掃描 transcript：若已呼叫 SKILL，記入 cache 並放行
    transcript_path = input_data.get("transcript_path")
    if _scan_transcript_for_skill(transcript_path, logger):
        logger.info("transcript 已含 SKILL 呼叫，放行：%s", rel_path)
        # 不寫入 warned_paths（已讀 SKILL 屬於合規路徑，無需 cache 警告）
        return 0

    # 未呼叫 SKILL：依 strict 模式決定 exit code
    strict = _is_strict_mode(logger)

    # 寫入 cache：同 session 內同路徑只警告 / 阻擋一次
    warned_paths.add(rel_path)
    _save_cache(session_id, warned_paths, logger)

    tool_input = input_data.get("tool_input") or {}
    metrics = _compute_edit_metrics(tool_name, tool_input, file_path)

    if strict:
        sys.stderr.write(STRICT_MESSAGE.format(path=rel_path))
        logger.info("strict 模式阻擋 framework 編輯：%s", rel_path)
        logger.info(
            "edit metrics: path=%s tool=%s file_size_before=%d file_size_after=%d diff_line_count=%d",
            rel_path, tool_name, metrics[0], metrics[1], metrics[2],
        )
        return 2

    sys.stderr.write(WARN_MESSAGE.format(path=rel_path))
    logger.info("警告 framework 編輯未先讀 SKILL：%s", rel_path)
    logger.info(
        "edit metrics: path=%s tool=%s file_size_before=%d file_size_after=%d diff_line_count=%d",
        rel_path, tool_name, metrics[0], metrics[1], metrics[2],
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "framework-rule-edit-skill-trigger"))
