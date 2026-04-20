#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Python Environment Guard Hook

SessionStart hook 負責偵測並修復 Python 執行環境，尤其針對 Windows 上
Microsoft Store 的 App Execution Alias stub
(C:\\Users\\<user>\\AppData\\Local\\Microsoft\\WindowsApps\\python*.exe)
會使 `python3` 指令以 exit 49 失敗的狀況。

流程：
  1. 偵測當前 `python3` 是否為 Store stub 或完全失效
  2. 若異常，透過 `uv python find` 找真實 Python 解譯器
  3. 在 $HOME/bin 動態生成本機 shim，指向偵測到的真實 Python 絕對路徑
  4. shim 是本機產物（不進 git），每台機器依自身環境生成

設計原則：
  - 路徑不寫死於框架：shim 內容由 hook 動態偵測後生成
  - 僅 Windows 觸發：其他平台的 `python3` 通常直接可用
  - 冪等：已有正確 shim 則不覆寫
  - 非侵入：偵測失敗或無法建立時僅警告，不阻塞 session

Exit code: 0 always (never block session)
"""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging


STORE_STUB_MARKERS = ("WindowsApps", "AppInstallerPythonRedirector")
# 兩種 shim 並存：
#   .cmd 版（CRLF、Windows 路徑）讓 Windows CMD / PowerShell / Python subprocess
#         shutil.which 走 PATHEXT 能找到並執行。
#   無副檔名 shell script 版（LF、POSIX 路徑）讓 Git Bash / MSYS2 能執行
#         （Git Bash 只對 `.exe` 做 PATHEXT 匹配，不認 .cmd）。
# 兩種 shim 都在 exec Python 前設 PYTHONUTF8=1，避免 Windows Python 預設
# 走 cp950 (Big5) 導致中文輸出被 UTF-8 終端解讀為亂碼。
BATCH_SHIM_TEMPLATE = '@set PYTHONUTF8=1\r\n@"{python_path}" %*\r\n'
SHELL_SHIM_TEMPLATE = '#!/bin/sh\nexport PYTHONUTF8=1\nexec "{python_path}" "$@"\n'
PROBE_TIMEOUT_SECONDS = 5
UV_VERSION_CANDIDATES = ("3.12", "3.11", "3.13", "3")


def _is_store_stub(python_path: Path) -> bool:
    """判斷 path 是否指向 Microsoft Store 的 App Execution Alias stub。"""
    try:
        resolved = str(python_path.resolve())
    except OSError:
        resolved = str(python_path)
    return any(marker in resolved for marker in STORE_STUB_MARKERS)


def _probe_python(path: Path) -> bool:
    """實際執行 path 指向的 python，確認能回傳版本資訊。

    `.cmd`/`.bat` shim 在 Windows 需要透過 cmd.exe 才能執行；對這類副檔名
    使用 shell=True 讓 subprocess 自動走 cmd，其他情況直接執行 executable。
    """
    is_batch = path.suffix.lower() in (".cmd", ".bat")
    probe_code = "import sys; print(sys.version_info[0])"
    try:
        if is_batch:
            cmd = f'"{path}" -c "{probe_code}"'
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
                shell=True,
            )
        else:
            result = subprocess.run(
                [str(path), "-c", probe_code],
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        return result.returncode == 0 and result.stdout.strip().isdigit()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False


def _detect_current_python3_status() -> tuple[Path | None, str]:
    """偵測當前 `python3` 狀態。

    Returns:
        (path_if_usable, status) 其中 status in {"ok", "stub", "missing"}.
    """
    found = shutil.which("python3")
    if not found:
        return None, "missing"
    path = Path(found)
    if _is_store_stub(path):
        return None, "stub"
    if _probe_python(path):
        return path, "ok"
    return None, "stub"


def _find_real_python_via_uv() -> Path | None:
    """用 `uv python find` 找真實可用的 Python 解譯器，優先 3.12。"""
    if not shutil.which("uv"):
        return None
    for version in UV_VERSION_CANDIDATES:
        try:
            result = subprocess.run(
                ["uv", "python", "find", version],
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, OSError):
            continue
        if result.returncode != 0:
            continue
        candidate = result.stdout.strip()
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists() and not _is_store_stub(path) and _probe_python(path):
            return path
    return None


def _to_posix_path(win_path: Path) -> str:
    """將 Windows 格式路徑（C:\\Users\\...）轉為 Git Bash 可用的 POSIX 形式。"""
    s = str(win_path)
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/")
        return f"/{drive}{rest}"
    return s.replace("\\", "/")


def _write_shim(shim_path: Path, content: str, logger) -> str:
    """建立或更新 shim 檔案（內容由呼叫端決定，保留字面行尾）。

    Returns:
        "created" / "updated" / "unchanged" / "failed"
    """
    try:
        shim_path.parent.mkdir(parents=True, exist_ok=True)
        existed = shim_path.exists()
        if existed:
            current = shim_path.read_text(encoding="utf-8")
            if current == content:
                return "unchanged"
        # newline="" 避免 Python 自動轉換行尾，保留 template 裡的 CRLF / LF
        shim_path.write_text(content, encoding="utf-8", newline="")
        mode = shim_path.stat().st_mode
        shim_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return "updated" if existed else "created"
    except OSError as exc:
        logger.error("Failed to write shim %s: %s", shim_path, exc)
        return "failed"


def _build_shim_specs(real_python: Path) -> list[tuple[str, str]]:
    """產生所有 shim 檔案規格：(filename, content)。"""
    python_windows = str(real_python)
    python_posix = _to_posix_path(real_python)
    batch_content = BATCH_SHIM_TEMPLATE.format(python_path=python_windows)
    shell_content = SHELL_SHIM_TEMPLATE.format(python_path=python_posix)
    return [
        ("python3.cmd", batch_content),
        ("python.cmd", batch_content),
        ("python3", shell_content),
        ("python", shell_content),
    ]


def _check_path_contains(target_dir: Path) -> bool:
    """檢查 target_dir 是否在當前 PATH 中（容忍 Windows / POSIX 格式差異）。"""
    path_env = os.environ.get("PATH", "")
    target_posix = _to_posix_path(target_dir)
    target_win = str(target_dir)
    try:
        target_resolved = target_dir.resolve()
    except OSError:
        target_resolved = None
    for entry in path_env.split(os.pathsep):
        if not entry:
            continue
        if entry == target_posix or entry == target_win:
            return True
        if target_resolved is not None:
            try:
                if Path(entry).resolve() == target_resolved:
                    return True
            except OSError:
                continue
    return False


def _emit(message: str) -> None:
    """對用戶可見的輸出（SessionStart 會匯總顯示 stderr）。"""
    print(f"[python-env-guard] {message}", file=sys.stderr)


def _ensure_pythonutf8_in_settings_local(project_root: Path, logger) -> str:
    """確保 .claude/settings.local.json 的 env.PYTHONUTF8 設為 "1"。

    Claude Code 啟動時讀取 settings.local.json 的 env，注入所有 Bash tool
    subprocess 的環境變數。這是最廣覆蓋的解法：uv tool 建立的 Windows exe
    wrapper（如 ticket CLI）不走 $HOME/bin shim，必須從父 process 繼承
    PYTHONUTF8 才能正確走 UTF-8 模式。

    Returns:
        "ok" / "written" / "failed"
    """
    settings_path = project_root / ".claude" / "settings.local.json"
    try:
        data: dict = {}
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        env_section = data.setdefault("env", {})
        if env_section.get("PYTHONUTF8") == "1":
            return "ok"
        env_section["PYTHONUTF8"] = "1"
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Wrote env.PYTHONUTF8=1 to %s", settings_path)
        return "written"
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to update %s: %s", settings_path, exc)
        return "failed"


def _current_python_uses_utf8() -> bool:
    """探測當前 python3 subprocess 輸出是否為 UTF-8。"""
    try:
        result = subprocess.run(
            [
                "python3",
                "-c",
                "import sys; print(sys.stdout.encoding.lower())",
            ],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            shell=True,
        )
        if result.returncode != 0:
            return False
        encoding = result.stdout.strip().lower()
        return encoding.startswith("utf")
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return False


def main() -> int:
    logger = setup_hook_logging("python-environment-guard")

    if platform.system() != "Windows":
        logger.info("Skipped: platform %s unaffected by Store stub", platform.system())
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())

    current, status = _detect_current_python3_status()
    if status != "ok":
        logger.warning("python3 status=%s; evaluating shim generation", status)
        real_python = _find_real_python_via_uv()
        if real_python is None:
            logger.error("No real Python found via uv; manual install required")
            _emit(
                "python3 is Microsoft Store stub and no real Python was found. "
                "Install via `uv python install 3.12` then restart session."
            )
            return 0

        shim_dir = Path.home() / "bin"
        shim_specs = _build_shim_specs(real_python)
        results = {}
        for name, content in shim_specs:
            results[name] = _write_shim(shim_dir / name, content, logger)

        changed = [n for n, r in results.items() if r in ("created", "updated")]
        if changed:
            logger.info(
                "shim %s in %s -> %s",
                ",".join(changed),
                shim_dir,
                real_python,
            )
            _emit(
                f"Created/updated python shim ({len(changed)} files) in "
                f"{_to_posix_path(shim_dir)} -> {real_python}"
            )

        if not _check_path_contains(shim_dir):
            logger.warning("shim dir %s not in PATH", shim_dir)
            _emit(
                f"NOTICE: {_to_posix_path(shim_dir)} not in PATH. "
                "Add to shell profile: export PATH=\"$HOME/bin:$PATH\""
            )
    else:
        logger.info("python3 healthy: %s", current)

    # PYTHONUTF8 注入：修復 Windows Python 預設走 cp950 導致的中文亂碼。
    # 寫入 settings.local.json 讓下次 session Bash tool subprocess 自動繼承。
    env_current = os.environ.get("PYTHONUTF8")
    settings_status = _ensure_pythonutf8_in_settings_local(project_root, logger)
    if settings_status == "written":
        _emit(
            "Wrote PYTHONUTF8=1 to .claude/settings.local.json. "
            "Restart Claude Code session to eliminate Python CJK output garbling."
        )
    elif env_current != "1" and not _current_python_uses_utf8():
        logger.warning(
            "PYTHONUTF8 not active in current session (env=%s); "
            "restart required after settings.local.json update",
            env_current,
        )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[python-env-guard] unexpected error: {exc}", file=sys.stderr)
        sys.exit(0)
