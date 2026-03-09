#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Output Style Check - SessionStart Hook 用於驗證 output-style 配置

在 Session 啟動時檢查 output-style 文件是否存在且格式正確，
確保 5W1H 回應格式的系統級強制機制正常運作。

Hook Event: SessionStart

輸出：直接輸出文字到 stdout，會顯示在 Session 開始時
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


# Output Style 配置
OUTPUT_STYLES_DIR = ".claude/output-styles"
REQUIRED_STYLES = [
    {
        "file": "5w1h-format.md",
        "name": "5W1H Structured Response",
        "required_sections": ["核心要求", "Task Type 分類", "格式範例", "強制檢查清單"],
    }
]


def check_output_style_file(style_config: dict, base_path: Path) -> tuple[bool, list[str]]:
    """檢查單個 output-style 文件"""
    errors = []
    file_path = base_path / OUTPUT_STYLES_DIR / style_config["file"]

    # 檢查文件是否存在
    if not file_path.exists():
        errors.append(f"文件不存在: {file_path}")
        return False, errors

    # 讀取文件內容
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        errors.append(f"無法讀取文件: {e}")
        return False, errors

    # 檢查 frontmatter
    if not content.startswith("---"):
        errors.append("缺少 frontmatter (文件應以 --- 開頭)")
        return False, errors

    # 檢查 name 欄位
    if f'name: {style_config["name"]}' not in content:
        errors.append(f"frontmatter 中缺少正確的 name 欄位 (應為: {style_config['name']})")

    # 檢查 keep-coding-instructions
    if "keep-coding-instructions:" not in content:
        errors.append("frontmatter 中缺少 keep-coding-instructions 欄位")

    # 檢查必要章節
    for section in style_config.get("required_sections", []):
        if section not in content:
            errors.append(f"缺少必要章節: {section}")

    return len(errors) == 0, errors


def main():
    logger = setup_hook_logging("output-style-check")
    # 獲取專案根目錄
    base_path = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    output = "\n" + "=" * 60 + "\nOutput Style Check - 系統級格式強制驗證\n" + "=" * 60 + "\n\n"
    print(output, end="")
    logger.info("Output Style Check 開始")

    all_passed = True
    total_styles = len(REQUIRED_STYLES)
    passed_styles = 0

    for style in REQUIRED_STYLES:
        passed, errors = check_output_style_file(style, base_path)

        if passed:
            passed_styles += 1
            msg = f"[PASS] {style['file']}: 驗證通過"
            print(msg)
            logger.info(msg)
        else:
            all_passed = False
            msg = f"[FAIL] {style['file']}: 驗證失敗"
            print(msg)
            logger.info(msg)
            for error in errors:
                print(f"   - {error}")
                logger.warning(error)
        print()

    # 摘要
    if all_passed:
        msg = f"[PASS] Output Style 檢查通過 ({passed_styles}/{total_styles})"
        print(msg)
        logger.info(msg)
        msg = "   5W1H 回應格式已在系統級別啟用"
        print(msg)
        logger.info(msg)
    else:
        msg = f"[WARNING] Output Style 檢查部分失敗 ({passed_styles}/{total_styles})"
        print(msg)
        logger.warning(msg)
        print()
        print("修復建議:")
        logger.warning("修復建議:")
        print("  1. 確認 .claude/output-styles/ 目錄存在")
        logger.warning("  1. 確認 .claude/output-styles/ 目錄存在")
        print("  2. 確認必要的 output-style 文件已正確配置")
        logger.warning("  2. 確認必要的 output-style 文件已正確配置")
        print("  3. 檢查 frontmatter 格式是否正確")
        logger.warning("  3. 檢查 frontmatter 格式是否正確")

    print()
    print("=" * 60)
    print()

    logger.info("Output Style Check 完成")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "output-style-check"))
