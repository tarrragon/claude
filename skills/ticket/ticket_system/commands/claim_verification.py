"""claim 命令的 AC 驗證子系統（Ticket 0.18.0-W11-001.1.x）。

本模組承載 claim 命令在派發前自動執行 AC 驗證所需的核心函式。

Sub-ticket 1.1（已完成）落地純函式：
- ``summarize_results``
- ``render_results``

Sub-ticket 1.2（本 ticket）補齊執行層 5 函式：
- ``apply_parse_strategy``：依 parse_strategy 判定 status（exit_code/
  tail_lines/coverage_number/manual）。
- ``execute_verification``：對單一可驗證 AC 執行 subprocess.Popen，處理
  timeout/OSError 並轉成 ``VerificationResult``。
- ``run_all_verifications``：循序迭代 (AC, VC) 配對，跳過 no_template /
  is_verifiable=False，其餘派給 ``execute_verification``。
- ``collect_ac_verifications``：串接 ``parse_ac`` + ``match_template``，
  產生 (AC, ValidationCommand | None) 配對清單。

後續 sub-ticket（1.3）會補齊 ``prompt_user_decision`` / ``claim_with_verification``
等 orchestrator 函式。
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from typing import Literal

from ticket_system.lib.ac_parser import AC, parse_ac
from ticket_system.lib.validation_templates import ValidationCommand, match_template
from ticket_system.lib.verification_result import (
    VerificationResult,
    VerificationSummary,
)


# 渲染使用的狀態標籤對照表
_STATUS_TAG_MAP: dict[str, str] = {
    "passed": "PASS",
    "failed": "FAIL",
    "timeout": "SKIP",
    "env_error": "SKIP",
    "unverifiable": "N/A",
    "no_template": "----",
}

# 渲染輸出硬上限（行數與展開列數）
_MAX_DISPLAY_ROWS = 10

# unverifiable 合併集合（含 no_template / unverifiable / timeout / env_error）
_UNVERIFIABLE_STATUSES = frozenset(
    {"unverifiable", "no_template", "timeout", "env_error"}
)


def summarize_results(
    results: list[VerificationResult],
) -> VerificationSummary:
    """將驗證結果 list 聚合為 ``VerificationSummary``。

    狀態判斷規則：

    - 空 list → ``no_ac``。
    - 有任一 failed → ``has_failures``。
    - 無 failed 且有 passed → ``all_passed``。
    - 無 failed 無 passed → ``none_verifiable``。

    ``unverifiable`` 計數合併 ``unverifiable`` / ``no_template`` /
    ``timeout`` / ``env_error`` 四類（見 §4 資料結構定義）。

    Args:
        results: 單次 claim 驗證產生的結果清單。

    Returns:
        聚合後的 ``VerificationSummary``（frozen）。
    """
    if not results:
        return VerificationSummary(
            total=0, passed=0, failed=0, unverifiable=0, status="no_ac"
        )

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    unverifiable = sum(
        1 for r in results if r.status in _UNVERIFIABLE_STATUSES
    )

    status: Literal["all_passed", "has_failures", "none_verifiable"]
    if failed > 0:
        status = "has_failures"
    elif passed > 0:
        status = "all_passed"
    else:
        status = "none_verifiable"

    return VerificationSummary(
        total=len(results),
        passed=passed,
        failed=failed,
        unverifiable=unverifiable,
        status=status,
    )


def render_results(
    summary: VerificationSummary,
    results: list[VerificationResult],
    ticket_id: str,
) -> str:
    """將 summary + results 渲染為使用者可讀的文字摘要。

    輸出格式規格（<= 15 行硬上限）：

    - 第 1 行：標題（含 ticket_id 與 AC 總數）。
    - 接續：每 AC 一行（最多 10 行），超過顯示 ``... (N more)``。
    - 空行 + 末行：``Result: X passed / Y failed / Z unverifiable``。

    Args:
        summary: 聚合結果。
        results: 原始結果 list。
        ticket_id: Ticket ID（顯示於標題）。

    Returns:
        多行文字（以 ``\\n`` 串接）；``no_ac`` 時回傳空字串。
    """
    if summary.status == "no_ac":
        return ""

    lines: list[str] = [
        f"[AC verification] Ticket {ticket_id} ({summary.total} items)"
    ]

    display_count = min(len(results), _MAX_DISPLAY_ROWS)
    for i in range(display_count):
        r = results[i]
        tag = _STATUS_TAG_MAP.get(r.status, "????")
        # AC.index 是 0-based，顯示時轉 1-based
        lines.append(f"  [{tag}] #{r.ac.index + 1} {r.message}")

    if len(results) > _MAX_DISPLAY_ROWS:
        remaining = len(results) - _MAX_DISPLAY_ROWS
        lines.append(f"  ... ({remaining} more)")

    lines.append("")
    lines.append(
        f"Result: {summary.passed} passed / "
        f"{summary.failed} failed / "
        f"{summary.unverifiable} unverifiable"
    )

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Parse strategy 相關常數
# ----------------------------------------------------------------------

# tail_lines 策略：掃描 stdout 最後幾行尋找 failed count
_TAIL_SCAN_LINES = 5

# tail_lines 策略：匹配「N failed」格式
_TAIL_FAILED_PATTERN = re.compile(r"(\d+)\s+failed", re.IGNORECASE)

# coverage 策略：從 AC 文字抽取「N%」閾值
_AC_PERCENT_PATTERN = re.compile(r"(\d+)\s*%")

# coverage 策略：從 stdout 抽取所有「N%」或「N.N%」
_STDOUT_COVERAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")

# coverage 策略：無指定閾值時的 fallback 值
_COVERAGE_FALLBACK_THRESHOLD = 80

# SIGTERM → SIGKILL 之間的等待秒數（防止殘留 process group）
_SIGTERM_SIGKILL_DELAY_SEC = 1


def _extract_threshold_from_ac(ac_text: str) -> int:
    """從 AC 文字抽取覆蓋率閾值百分比（0-100）。

    搜尋第一個 ``N%`` 格式的整數；未命中時回傳 fallback 80（M3）。
    """
    m = _AC_PERCENT_PATTERN.search(ac_text)
    if m is None:
        return _COVERAGE_FALLBACK_THRESHOLD
    return int(m.group(1))


def _extract_coverage_from_stdout(stdout: str) -> float | None:
    """從 subprocess stdout 抽取覆蓋率數字。

    取最後一個 ``N%`` 或 ``N.N%``（coverage 工具通常把總覆蓋率輸出於最後）。
    未命中時回傳 ``None``。
    """
    matches = _STDOUT_COVERAGE_PATTERN.findall(stdout)
    if not matches:
        return None
    return float(matches[-1])


def apply_parse_strategy(
    strategy: str,
    stdout: str,
    stderr: bytes | str,
    exit_code: int,
    ac_text: str,
) -> Literal["passed", "failed", "unverifiable"]:
    """依 parse_strategy 判定 AC 驗證結果。

    支援 4 種 strategy：

    - ``exit_code``：exit_code == 0 → passed，否則 failed。
    - ``tail_lines``：掃描 stdout 最後 5 行，若匹配 ``N failed`` 且 N>0 → failed；
      否則以 exit_code 決定。
    - ``coverage_number``：從 AC 文字抽取閾值（fallback 80），從 stdout 抽取實測值，
      實測 >= 閾值 → passed。無法抽取實測 → failed。
    - ``manual``：固定回傳 unverifiable。

    Args:
        strategy: 4 種策略之一。
        stdout: subprocess 已 decode 的 stdout。
        stderr: subprocess 的 stderr（保留參數未來擴充用）。
        exit_code: subprocess 的 returncode。
        ac_text: AC 原始文字（供 coverage_number 抽取閾值用）。

    Returns:
        ``"passed"`` / ``"failed"`` / ``"unverifiable"``。
    """
    if strategy == "exit_code":
        return "passed" if exit_code == 0 else "failed"

    if strategy == "tail_lines":
        lines = stdout.splitlines()
        tail = lines[-_TAIL_SCAN_LINES:] if lines else []
        for line in tail:
            m = _TAIL_FAILED_PATTERN.search(line)
            if m is not None:
                failed_count = int(m.group(1))
                if failed_count == 0 and exit_code == 0:
                    return "passed"
                return "failed"
        return "passed" if exit_code == 0 else "failed"

    if strategy == "coverage_number":
        threshold = _extract_threshold_from_ac(ac_text)
        coverage = _extract_coverage_from_stdout(stdout)
        if coverage is None:
            return "failed"
        return "passed" if coverage >= threshold else "failed"

    if strategy == "manual":
        return "unverifiable"

    # 未知策略保守當作 failed（不應發生，防禦性程式碼）
    return "failed"


def _decode_safe(raw: bytes) -> str:
    """以 UTF-8 解碼；非法序列以 ``errors='replace'`` 降級（M4）。"""
    return raw.decode("utf-8", errors="replace")


def _kill_process_group(pid: int) -> None:
    """送 SIGTERM → 等 1 秒 → 送 SIGKILL 清除 process group。

    ``ProcessLookupError`` 表示 group 已退出（1 秒內自行結束），靜默忽略。
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(_SIGTERM_SIGKILL_DELAY_SEC)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute_verification(
    ac: AC,
    vc: ValidationCommand,
    cwd: str,
) -> VerificationResult:
    """對單一可驗證 AC 執行 subprocess，回傳 VerificationResult。

    呼叫契約：``vc.is_verifiable`` 必須為 True 且 ``vc.command`` 不為 None。
    不可驗證的情況應由上層 ``run_all_verifications`` 直接包裝，不進此函式。

    subprocess 細節：

    - ``shell=True``：允許 pipe（如 ``npm test 2>&1 | tail -5``）。
    - ``start_new_session=True``：獨立 process group，timeout 時可 killpg
      一次清掉整條管線，避免殘留 subprocess。
    - ``env=None``：繼承父 process 環境變數（PATH、NODE_OPTIONS 等）。
    - ``cwd``：由上層 ``resolve_project_cwd()`` 解析的專案根。

    例外處理：

    - ``subprocess.TimeoutExpired``：killpg 整組後回傳 status='timeout'。
    - ``OSError``（含 FileNotFoundError）：回傳 status='env_error'。
    - ``KeyboardInterrupt``：killpg 後重新拋出，由 ``run_all_verifications`` 或
      ``claim_with_verification`` 捕捉。

    Args:
        ac: 被驗證的 AC 物件。
        vc: 已匹配的 ``ValidationCommand``（必須 ``is_verifiable=True``）。
        cwd: subprocess 工作目錄（專案根）。

    Returns:
        ``VerificationResult``（status 為 passed/failed/timeout/env_error）。
    """
    assert vc.is_verifiable and vc.command is not None, (
        "execute_verification 僅處理可驗證模板；呼叫端須先過濾"
    )

    process: subprocess.Popen | None = None
    try:
        process = subprocess.Popen(
            vc.command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout_bytes, stderr_bytes = process.communicate(
                timeout=vc.timeout_sec
            )
        except subprocess.TimeoutExpired:
            _kill_process_group(process.pid)
            return VerificationResult(
                ac=ac,
                status="timeout",
                template_name=vc.template_name,
                message=f"exceeded {vc.timeout_sec}s",
                exit_code=None,
            )
        except KeyboardInterrupt:
            _kill_process_group(process.pid)
            raise

        stdout_text = _decode_safe(stdout_bytes)
        exit_code = process.returncode if process.returncode is not None else -1

        status = apply_parse_strategy(
            vc.parse_strategy, stdout_text, stderr_bytes, exit_code, ac.text
        )
        message = _build_message(
            vc.parse_strategy, status, exit_code, stdout_text, ac.text
        )
        return VerificationResult(
            ac=ac,
            status=status if status != "unverifiable" else "unverifiable",
            template_name=vc.template_name,
            message=message,
            exit_code=exit_code,
        )

    except OSError as err:
        # FileNotFoundError（npm 等不存在）或其他 OS 層錯誤
        return VerificationResult(
            ac=ac,
            status="env_error",
            template_name=vc.template_name,
            message=f"environment missing: {err}",
            exit_code=None,
        )


def _build_message(
    strategy: str,
    status: str,
    exit_code: int,
    stdout_text: str,
    ac_text: str,
) -> str:
    """為 VerificationResult 產生單行 message（render 用）。"""
    if strategy == "exit_code":
        return f"exit_code={exit_code}"
    if strategy == "tail_lines":
        # 取最後一行非空字串作為摘要
        lines = [l.strip() for l in stdout_text.splitlines() if l.strip()]
        tail = lines[-1] if lines else f"exit_code={exit_code}"
        return tail[:80]
    if strategy == "coverage_number":
        coverage = _extract_coverage_from_stdout(stdout_text)
        threshold = _extract_threshold_from_ac(ac_text)
        if coverage is None:
            return f"coverage not found (threshold {threshold}%)"
        return f"coverage {coverage}% (threshold {threshold}%)"
    if strategy == "manual":
        return "manual review required"
    return f"status={status}"


def run_all_verifications(
    pairs: list[tuple[AC, ValidationCommand | None]],
    cwd: str,
) -> list[VerificationResult]:
    """循序執行多個 AC 的驗證，回傳完整結果清單。

    處理三類 pair：

    - ``vc is None`` → 產生 ``status='no_template'`` 結果，不執行 subprocess。
    - ``vc.is_verifiable is False`` → 產生 ``status='unverifiable'`` 結果，
      message 取自 ``vc.unverifiable_reason``。
    - 其餘 → 委派給 ``execute_verification``。

    KeyboardInterrupt 由底層自然傳播至呼叫端（``claim_with_verification``）。

    Args:
        pairs: ``collect_ac_verifications`` 回傳的配對清單。
        cwd: subprocess 工作目錄。

    Returns:
        與 ``pairs`` 等長的 ``VerificationResult`` 清單。
    """
    results: list[VerificationResult] = []
    for ac, vc in pairs:
        if vc is None:
            results.append(
                VerificationResult(
                    ac=ac,
                    status="no_template",
                    template_name=None,
                    message="no template match",
                    exit_code=None,
                )
            )
            continue
        if not vc.is_verifiable:
            results.append(
                VerificationResult(
                    ac=ac,
                    status="unverifiable",
                    template_name=vc.template_name,
                    message=vc.unverifiable_reason or "unverifiable",
                    exit_code=None,
                )
            )
            continue
        # 顯示執行進度（stderr，避免污染 stdout 摘要）
        print(
            f"executing: {vc.template_name}... "
            f"(timeout {vc.timeout_sec}s, Ctrl-C to cancel)",
            file=sys.stderr,
        )
        results.append(execute_verification(ac, vc, cwd))
    return results


def collect_ac_verifications(
    ticket_id: str,
) -> list[tuple[AC, ValidationCommand | None]]:
    """解析 Ticket 的 AC 並逐項匹配驗證模板。

    委派給 ``parse_ac`` 取得 AC list，對每項呼叫 ``match_template`` 得到
    ``ValidationCommand | None``。本函式不做執行，僅做資料層配對。

    Args:
        ticket_id: Ticket ID（如 "0.18.0-W5-002"）。

    Returns:
        ``(AC, ValidationCommand | None)`` 配對清單；Ticket 無 AC 時回 []。

    Raises:
        ValueError: ticket_id 無效或 YAML 損毀（由 parse_ac 傳遞）。
        FileNotFoundError: 找不到 Ticket 檔案（由 parse_ac 傳遞）。
    """
    ac_list = parse_ac(ticket_id)
    return [(ac, match_template(ac.text)) for ac in ac_list]


# ----------------------------------------------------------------------
# Group F：prompt_user_decision（互動層）
# ----------------------------------------------------------------------

# 互動式 prompt 文字
_PROMPT_TEXT = "continue claim? [y] continue / [n] cancel (default: y): "

# 非 tty 環境警告訊息
_NON_TTY_WARNING = (
    "[AC verification] non-interactive environment, cancelled; "
    "use --yes or --skip-verify to override"
)

# 無效輸入最大重試次數
_MAX_INVALID_ATTEMPTS = 3

# 接受為 y 的輸入（空字串採預設 y）
_ACCEPT_YES = frozenset({"y", "yes", ""})
# 接受為 n 的輸入
_ACCEPT_NO = frozenset({"n", "no"})


def prompt_user_decision(
    summary: VerificationSummary,
    auto_yes: bool,
) -> Literal["y", "n"]:
    """互動式決定 claim 是否繼續。

    決策規則：

    - ``auto_yes=True`` → 直接回 ``'y'``，不讀 stdin。
    - ``sys.stdin.isatty() is False`` 且 ``auto_yes=False`` → 回 ``'n'``，
      stderr 提示非互動環境。
    - 否則讀 stdin 最多 3 次；空字串或 y/yes → ``'y'``；n/no → ``'n'``；
      3 次無效 → 預設 ``'n'``（fail-closed 安全預設）。

    Args:
        summary: ``VerificationSummary``（保留參數供未來擴充；目前未用於
            條件分支，拔 c 後 prompt 僅在 has_failures 場景觸發）。
        auto_yes: ``--yes`` flag 值。

    Returns:
        ``'y'`` 或 ``'n'``。
    """
    # auto_yes 短路，不受 tty 影響
    if auto_yes:
        return "y"

    # 非 tty 環境：fail-closed 預設取消
    if not sys.stdin.isatty():
        print(_NON_TTY_WARNING, file=sys.stderr)
        return "n"

    for _ in range(_MAX_INVALID_ATTEMPTS):
        try:
            raw = input(_PROMPT_TEXT)
        except EOFError:
            # stdin 已關閉（非互動情境 edge case）
            return "n"
        answer = raw.strip().lower()
        if answer in _ACCEPT_YES:
            return "y"
        if answer in _ACCEPT_NO:
            return "n"
    # 3 次無效 → 預設 n（取消）
    return "n"
