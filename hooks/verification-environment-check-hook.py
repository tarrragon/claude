#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///

"""
Verification Environment Check Hook

SessionStart 事件觸發時，確認「實機驗證環境」是否就緒——換機器或接手舊
專案時，session 一開始就能發現配方缺失或釘住裝置不存在，而非到首次實機
驗證才卡住。

檢查邏輯（四步）：
1. 偵測專案有無 runtime surface（pubspec.yaml 含 `sdk: flutter` 依賴，或
   integration_test/ 目錄存在）。無 → 靜默跳過（非 Flutter 專案不適用）。
2. 有 runtime surface 時，查 `.claude/skills/verify/SKILL.md` 是否存在。
   缺 → WARNING，建議 `/verify bootstrap` 或於 saas 選型訪談補
   verification-surface 維度；integration_test/ 已存在但配方缺時語氣加重
   （已有測試層卻無法實機驗證）。
3. 配方存在時，從內容抽取模擬器 UDID 樣式（8-4-4-4-12 hex），與
   `xcrun simctl list devices available` 比對（僅 macOS；其他平台跳過此
   步並於訊息中說明）。釘住裝置不存在 → WARNING，附換環境重新釘裝置的
   步驟。
4. 配方存在且裝置可用（或非 macOS 略過裝置檢查）→ 輸出一行 INFO
   「驗證環境就緒」（有 runtime surface 時就緒與否都顯性；只有「無
   runtime surface」的專案才靜默，避免非 Flutter 專案洗版）。

失敗模式（規則 4：異常可觀測性，雙通道）：
- 任何 I/O / subprocess 例外 → logger.warning/error（寫入日誌檔）+ 降級
  為不阻塞 session 啟動；simctl 逾時視為「無法判定裝置可用性」，不視為
  裝置不存在（避免 false positive WARNING）。
- 非預期例外由 run_hook_safely 頂層捕獲，寫入 critical 日誌。

設計要點：
- UV 單檔 PEP 723，dependencies=[]（不引入外部套件）。
- simctl 呼叫設 timeout，避免拖慢 session 啟動。
- 僅 INFO/WARNING 語氣，不阻擋（不使用 permissionDecision=deny）。

來源：用戶裁示 — session init 應包含實機測試設定確認（PC-BAL-029 場景：
配方含機器特定值，換機必失效，此失效應在 session 啟動即顯性化）
"""

import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)

EXIT_SUCCESS = 0

# simctl 逾時秒數（SessionStart 不可長等）
SIMCTL_TIMEOUT_SECONDS = 5

# 驗證配方（verify skill）路徑，相對於專案根目錄
VERIFY_SKILL_RELPATH = ".claude/skills/verify/SKILL.md"

# on-device 整合測試目錄，相對於專案根目錄
INTEGRATION_TEST_RELPATH = "integration_test"

# pubspec.yaml 相對路徑
PUBSPEC_RELPATH = "pubspec.yaml"

# pubspec.yaml 內偵測 Flutter runtime 的樣式（dependencies 下 `sdk: flutter`）
_FLUTTER_SDK_DEP_RE = re.compile(r"^\s*sdk:\s*flutter\s*$", re.MULTILINE)

# 模擬器 UDID 樣式（8-4-4-4-12 hex，大小寫皆可）。
# 要求鄰近標籤詞（UDID / -d / --device）：配方檔可能含其他 UUID 樣式字串
# （換機歷史記錄、多裝置範例），無上下文的 first-match 會靜默抓錯目標。
_UDID_PATTERN = r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
_UDID_RE = re.compile(
    rf"(?:UDID\s*[=:]?\s*|-d\s+|--device\s+)({_UDID_PATTERN})\b"
)
# 無標籤詞 fallback（配方只寫裸 UDID 時仍可抓取）
_UDID_BARE_RE = re.compile(rf"\b({_UDID_PATTERN})\b")

# simctl stderr 記入日誌的截斷長度（避免超長錯誤淹沒日誌）
STDERR_LOG_TRUNCATE_CHARS = 300


def has_runtime_surface(project_root: Path, logger) -> bool:
    """偵測專案是否有 Flutter runtime surface。

    判準（任一成立即視為有 runtime surface）：
    - pubspec.yaml 存在且含 `sdk: flutter` 依賴
    - integration_test/ 目錄存在

    Args:
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        bool: 是否偵測到 runtime surface
    """
    pubspec = project_root / PUBSPEC_RELPATH
    if pubspec.exists():
        try:
            content = pubspec.read_text(encoding="utf-8")
            if _FLUTTER_SDK_DEP_RE.search(content):
                logger.debug("偵測到 pubspec.yaml 含 sdk: flutter 依賴")
                return True
        except OSError as e:
            logger.warning("讀取 pubspec.yaml 失敗: %s", e)

    integration_test_dir = project_root / INTEGRATION_TEST_RELPATH
    if integration_test_dir.is_dir():
        logger.debug("偵測到 integration_test/ 目錄存在")
        return True

    logger.info("未偵測到 Flutter runtime surface，跳過驗證環境檢查")
    return False


def find_verify_skill(project_root: Path) -> Optional[Path]:
    """回傳驗證配方檔案路徑（存在時）。"""
    skill_path = project_root / VERIFY_SKILL_RELPATH
    return skill_path if skill_path.exists() else None


def has_integration_test_dir(project_root: Path) -> bool:
    """integration_test/ 目錄是否存在（用於加重配方缺失警語）。"""
    return (project_root / INTEGRATION_TEST_RELPATH).is_dir()


def extract_pinned_udid(skill_content: str, logger) -> Optional[str]:
    """從配方內容抽取第一個模擬器 UDID 樣式。

    Args:
        skill_content: SKILL.md 內容
        logger: 日誌物件

    Returns:
        UDID 字串或 None（未找到）
    """
    # 優先取有標籤詞（UDID / -d / --device）鄰近的樣式；多筆時取最後一筆
    # （配方慣例：現行值寫在最新內容，歷史值在前）並記 warning 供查核。
    labeled = _UDID_RE.findall(skill_content)
    if labeled:
        unique = list(dict.fromkeys(labeled))
        if len(unique) > 1:
            logger.warning(
                "配方含 %d 個帶標籤 UDID（%s），取最後一筆比對", len(unique), ", ".join(unique)
            )
        return unique[-1]
    bare = _UDID_BARE_RE.findall(skill_content)
    if bare:
        unique = list(dict.fromkeys(bare))
        if len(unique) > 1:
            logger.warning(
                "配方含 %d 個無標籤 UDID 樣式（%s），取最後一筆比對", len(unique), ", ".join(unique)
            )
        return unique[-1]
    logger.debug("配方內容未找到 UDID 樣式，跳過裝置可用性比對")
    return None


def check_udid_available(udid: str, logger) -> Optional[bool]:
    """檢查釘住的模擬器 UDID 是否在本機可用（僅 macOS）。

    Args:
        udid: 待檢查的模擬器 UDID
        logger: 日誌物件

    Returns:
        True: 裝置可用
        False: 裝置不存在（已成功查詢，但清單中無此 UDID）
        None: 無法判定（非 macOS、simctl 缺失、逾時或其他例外）——
              視為「無法判定」而非「不存在」，避免 false positive WARNING
    """
    try:
        proc = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available"],
            capture_output=True,
            text=True,
            timeout=SIMCTL_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        logger.warning("xcrun/simctl 不存在，無法判定裝置可用性: %s", e)
        return None
    except subprocess.TimeoutExpired as e:
        logger.warning("simctl 查詢逾時（%ss），無法判定裝置可用性: %s", SIMCTL_TIMEOUT_SECONDS, e)
        return None
    except Exception as e:  # noqa: BLE001 — SessionStart 不可因任何例外阻塞
        logger.warning("simctl 查詢異常，無法判定裝置可用性: %s", e, exc_info=True)
        return None

    if proc.returncode != 0:
        logger.warning(
            "simctl 非零退出 (rc=%s): stderr=%s",
            proc.returncode,
            proc.stderr.strip()[:STDERR_LOG_TRUNCATE_CHARS],
        )
        return None

    # UUID hex 大小寫不敏感（RFC 4122）：配方以小寫記錄時不可 false negative
    available = udid.upper() in proc.stdout.upper()
    logger.info("釘住裝置 UDID=%s 可用性=%s", udid, available)
    return available


def build_missing_skill_message(integration_test_exists: bool) -> str:
    """組裝配方缺失時的 WARNING 訊息。"""
    lines = [
        "[WARNING] 驗證環境未就緒：找不到驗證配方",
        "",
        f"預期路徑：`{VERIFY_SKILL_RELPATH}`（不存在）",
    ]
    if integration_test_exists:
        lines.append(
            f"注意：`{INTEGRATION_TEST_RELPATH}/` 已存在整合測試，"
            "但無驗證配方將無法完成實機驗證流程。"
        )
    lines.extend(
        [
            "",
            "建議動作：",
            "- 執行 `/verify bootstrap` 建立首次驗證配方，或",
            "- 於 saas 選型訪談補 verification-surface 維度",
        ]
    )
    return "\n".join(lines)


def build_device_unavailable_message(udid: str, skill_relpath: str) -> str:
    """組裝釘住裝置不存在時的 WARNING 訊息（換環境重釘步驟）。"""
    return "\n".join(
        [
            "[WARNING] 驗證環境已換機：釘住的模擬器裝置在本機不存在",
            "",
            f"配方 `{skill_relpath}` 釘住的 UDID `{udid}` 未出現在"
            " `xcrun simctl list devices available` 清單中。",
            "",
            "建議動作：",
            "- 執行 `xcrun simctl list devices available` 找出本機可用裝置",
            f"- 更新 `{skill_relpath}` 中的 UDID 為本機裝置",
            "- 重新執行一次驗證流程確認配方可用",
        ]
    )


def check_verification_environment(project_root: Path, logger) -> Optional[str]:
    """執行四步檢查，回傳要顯示的訊息（INFO 或 WARNING）或 None（靜默跳過）。

    有 runtime surface 時必回傳訊息（INFO/WARNING 皆可能，AC 要求「配方存在
    且釘住裝置可用時輸出 OK」為可測試行為，非靜默）；無 runtime surface 時
    才靜默跳過（非 Flutter 專案不適用）。

    Args:
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        str: 需顯示的訊息（`[WARNING] ...` 或 `[INFO] ...` 開頭）
        None: 無 runtime surface（靜默跳過，僅此情境）
    """
    # Step 1：無 runtime surface → 靜默跳過
    if not has_runtime_surface(project_root, logger):
        return None

    # Step 2：查配方存在性
    skill_path = find_verify_skill(project_root)
    if skill_path is None:
        integration_test_exists = has_integration_test_dir(project_root)
        logger.warning(
            "驗證配方缺失 (%s)，integration_test 存在=%s",
            VERIFY_SKILL_RELPATH, integration_test_exists,
        )
        return build_missing_skill_message(integration_test_exists)

    # Step 3：配方存在，抽 UDID 並比對本機可用性（僅 macOS 有意義）
    if platform.system() != "Darwin":
        logger.info("非 macOS 平台，跳過裝置可用性比對")
        return "[INFO] 驗證環境就緒：配方存在（非 macOS 平台，跳過裝置可用性比對）"

    try:
        skill_content = skill_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("讀取驗證配方失敗，跳過裝置比對: %s", e)
        return "[INFO] 驗證環境就緒：配方存在（讀取內容失敗，跳過裝置可用性比對）"

    udid = extract_pinned_udid(skill_content, logger)
    if udid is None:
        return "[INFO] 驗證環境就緒：配方存在（未偵測到釘住裝置 UDID，跳過裝置可用性比對）"

    availability = check_udid_available(udid, logger)
    if availability is False:
        return build_device_unavailable_message(udid, VERIFY_SKILL_RELPATH)
    if availability is None:
        return f"[INFO] 驗證環境就緒：配方存在（釘住裝置 UDID={udid}，可用性無法判定，simctl 查詢失敗或逾時）"

    # availability is True
    return f"[INFO] 驗證環境就緒：配方存在，釘住裝置 UDID={udid} 本機可用"


def build_hook_output(message: Optional[str]) -> dict:
    """組裝 SessionStart hook 的 JSON 輸出。"""
    if not message:
        return {"suppressOutput": True}
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
        "suppressOutput": False,
    }


def main() -> int:
    """主入口：讀 stdin（可忽略內容）→ 四步檢查 → 輸出 JSON。"""
    logger = setup_hook_logging("verification-environment-check")
    logger.info("驗證環境檢查 hook 啟動")

    try:
        # SessionStart 可能無 stdin 或給簡短 JSON；不阻塞
        read_json_from_stdin(logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("讀取 stdin 失敗（忽略）: %s", e)

    try:
        project_root = get_project_root()
    except Exception as e:  # noqa: BLE001
        logger.error("取得 project_root 失敗，跳過檢查: %s", e, exc_info=True)
        print(json.dumps(build_hook_output(None), ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    message = check_verification_environment(project_root, logger)
    output = build_hook_output(message)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info("驗證環境檢查 hook 完成（has_message=%s）", message is not None)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "verification-environment-check"))
