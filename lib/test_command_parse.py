#!/usr/bin/env python3
"""
測試命令解析共用工具

提供 Bash hook 共用的「什麼算一次測試執行」定義。pre-test-hook、
test-timeout-pre、post-test-hook 原各自判定（子字串、對原始字串做 regex），
引號內的 `\\|flutter test` 會被當成管線後的新敘述，包裝腳本的 `--` 不被
認得，pytest 也不被涵蓋。本模組把判定收斂為單一定義：沿用
git_command_parse.parse_command_statements 的切分（heredoc 剝離、換行轉
分隔符、引號語意），只檢查每個敘述去除啟動前綴後的開頭。

主要功能:
- find_test_invocations: 解析命令字串，回傳各測試呼叫（含 runner 種類）
- TestInvocation: 單次測試呼叫的結構化記錄

失敗語意（與 git_command_parse 一致，呼叫端須用 `is None` 區分）：
- `None`：命令字串無法安全解析（未閉合引號）
- `[]`：可解析但沒有測試呼叫

支援的啟動前綴：env／KEY=VAL／sudo／nohup／time／xargs、timeout、fvm、
`uv [選項] run`、`[python] run-with-timeout.py N -- <命令>`（可巢狀）。
另處理：sudo／env 的帶值選項（`sudo -u x`、`env -u X`）、python 帶值旗標
（`-X dev`、`-W ignore`）、flutter／dart 在 test 前的全域選項、npm 帶值選項
（`--prefix x`、`-w pkg`）與別名 `npm t`。解析成本低的形態一律修正，因為本機
閘門以本模組辨識 heavy 工作，漏判等於繞過閘門。
不支援（需二次解析或超出 runner 集合，閘門須另行處理）：`bash -c '...'`／
`sh -c`／`python -c`（命令位於引號字串內）、`yarn`／`pnpm`／`npx` 的測試、
`env A=1 -u X cmd`（賦值後才出現選項）、`--opt=val` 以外未列入帶值集合的
自訂選項（帶值集合採列舉，未列入的帶值選項其值會被當成子命令而漏判）。
"""

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .git_command_parse import parse_command_statements, skip_prefix_wrapper_count

RUNNER_FLUTTER = "flutter"
RUNNER_DART = "dart"
RUNNER_NPM = "npm"
RUNNER_PYTEST = "pytest"
ALL_RUNNERS = frozenset({RUNNER_FLUTTER, RUNNER_DART, RUNNER_NPM, RUNNER_PYTEST})

TIMEOUT_WRAPPER_NAME = "run-with-timeout.py"
PYTEST_EXECUTABLES = frozenset({"pytest", "py.test"})
_PYTHON_EXECUTABLE_RE = re.compile(r"^python(\d+(\.\d+)?)?$")
_TIMEOUT_OPTIONS_WITH_VALUE = frozenset({"-s", "--signal", "-k", "--kill-after"})
_UV_OPTIONS_WITH_VALUE = frozenset({
    "--directory", "--project", "--python", "-p", "--with", "-w",
    "--with-editable", "--with-requirements", "--env-file", "--group",
    "--extra", "--package", "--index", "--index-url", "--extra-index-url",
    "--cache-dir", "--config-file",
})
_SUDO_OPTIONS_WITH_VALUE = frozenset({
    "-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
    "-C", "--close-from", "-r", "--role", "-t", "--type", "-D", "--chdir",
    "-T", "--command-timeout", "-U", "--other-user",
})
_ENV_OPTIONS_WITH_VALUE = frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string", "-P"})
_PYTHON_OPTIONS_WITH_VALUE = frozenset({"-X", "-W", "--check-hash-based-pycs"})
_FLUTTER_DART_OPTIONS_WITH_VALUE = frozenset({
    "-d", "--device-id", "--packages", "--suppress-analytics-value",
    "--local-engine", "--local-engine-src-path", "--local-engine-host",
    "--local-web-sdk",
})
_NPM_OPTIONS_WITH_VALUE = frozenset({
    "--prefix", "-C", "-w", "--workspace", "--cache", "--userconfig",
    "--registry", "--loglevel", "--tag", "--otp",
})
NPM_TEST_ALIASES = frozenset({"test", "t", "tst"})

WEIGHT_HEAVY = "heavy"
WEIGHT_LIGHT = "light"
HEAVY_BUILD_EXECUTABLES = frozenset({"xcodebuild"})
INTEGRATION_TEST_MARKER = "integration_test"
_SPECIFIC_TEST_FILE_RE = re.compile(r"(_test\.dart|(^|/)test_[^/]*\.py|_test\.py)$")


@dataclass(frozen=True)
class TestInvocation:
    """單次測試呼叫：runner 為執行器種類，statement 保留含啟動前綴的完整敘述。"""

    __test__ = False  # 避免 pytest 把 Test 開頭的類別當測試收集
    runner: str
    statement: Tuple[str, ...]


def _skip_options(tokens: List[str], with_value) -> List[str]:
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        token = tokens[index]
        merged_short = len(token) > 2 and token[1] != "-" and "-" + token[-1] in with_value
        index += 2 if token in with_value or merged_short else 1
    return tokens[index:]


def _strip_timeout(tokens: List[str]) -> List[str]:
    """timeout [選項] <時長> <命令>"""
    return _skip_options(tokens[1:], _TIMEOUT_OPTIONS_WITH_VALUE)[1:]


def _strip_uv_run(tokens: List[str]) -> List[str]:
    """uv [全域選項] run [run 選項] <命令>；非 uv run 回 []。"""
    rest = _skip_options(tokens[1:], _UV_OPTIONS_WITH_VALUE)
    if not rest or rest[0] != "run":
        return []
    return _skip_options(rest[1:], _UV_OPTIONS_WITH_VALUE)


def _strip_timeout_wrapper(tokens: List[str]) -> Optional[List[str]]:
    """[直譯器 [旗標]] run-with-timeout.py N -- <命令>；不是包裝呼叫回 None。"""
    index = 0
    if _PYTHON_EXECUTABLE_RE.match(Path(tokens[0]).name):
        index = len(tokens) - len(_skip_options(tokens[1:], _PYTHON_OPTIONS_WITH_VALUE))
    if index >= len(tokens) or Path(tokens[index]).name != TIMEOUT_WRAPPER_NAME:
        return None
    rest = tokens[index + 1:]
    return rest[rest.index("--") + 1:] if "--" in rest else []


def _strip_one_launcher(tokens: List[str]) -> List[str]:
    head = tokens[0]
    if head == "sudo":  # 先於通用前綴處理：sudo／env 的選項須在此消耗
        return _skip_options(tokens[1:], _SUDO_OPTIONS_WITH_VALUE)
    if head == "env":
        return _skip_options(tokens[1:], _ENV_OPTIONS_WITH_VALUE)
    # 每輪只剝一個 token，使 nohup／time／xargs 後的 sudo／env 回到上方專屬分支
    skipped = skip_prefix_wrapper_count(tokens[:1])  # KEY=VAL／nohup／time／xargs
    if skipped:
        return tokens[skipped:]
    if head == "timeout":
        return _strip_timeout(tokens)
    if head == "fvm":
        return tokens[1:]
    if head == "uv":
        return _strip_uv_run(tokens)
    unwrapped = _strip_timeout_wrapper(tokens)
    return tokens if unwrapped is None else unwrapped


def _strip_launch_prefixes_tracking(tokens: List[str]) -> Tuple[List[str], bool]:
    """前綴可巢狀（包裝腳本內再接 uv run），反覆去除至穩定；另回報是否經過 run-with-timeout 包裝。"""
    wrapped = False
    while tokens:
        if _strip_timeout_wrapper(tokens) is not None:
            wrapped = True
        stripped = _strip_one_launcher(tokens)
        if stripped == tokens:
            break
        tokens = stripped
    return tokens, wrapped


def _strip_launch_prefixes(tokens: List[str]) -> List[str]:
    return _strip_launch_prefixes_tracking(tokens)[0]


def _is_python_module_pytest(tokens: List[str]) -> bool:
    """python [旗標] -m pytest"""
    if not _PYTHON_EXECUTABLE_RE.match(Path(tokens[0]).name):
        return False
    rest = tokens[1:]
    while rest and rest[0].startswith("-") and rest[0] != "-m":
        rest = rest[2:] if rest[0] in _PYTHON_OPTIONS_WITH_VALUE else rest[1:]
    return len(rest) >= 2 and rest[0] == "-m" and rest[1] == "pytest"


def _is_npm_test(tokens: List[str]) -> bool:
    """npm test[:x] / npm run test[:x]"""
    rest = _skip_options(tokens[1:], _NPM_OPTIONS_WITH_VALUE)
    if len(rest) > 1 and rest[0] == "run":
        rest = _skip_options(rest[1:], _NPM_OPTIONS_WITH_VALUE)
        script = rest[0] if rest else ""
        return script == "test" or script.startswith("test:")
    script = rest[0] if rest else ""
    return script in NPM_TEST_ALIASES or script.startswith("test:")


def _classify_runner(tokens: List[str]) -> Optional[str]:
    if not tokens:
        return None
    head = Path(tokens[0]).name
    if head in (RUNNER_FLUTTER, RUNNER_DART):
        rest = _skip_options(tokens[1:], _FLUTTER_DART_OPTIONS_WITH_VALUE)
        return head if rest and rest[0] == "test" else None
    if head == RUNNER_NPM:
        return RUNNER_NPM if _is_npm_test(tokens) else None
    if head in PYTEST_EXECUTABLES or _is_python_module_pytest(tokens):
        return RUNNER_PYTEST
    return None


def find_test_invocations(command: str) -> Optional[List[TestInvocation]]:
    """解析命令字串，回傳其中的測試呼叫；無法解析回 None，無命中回 []。"""
    statements = parse_command_statements(command)
    if statements is None:
        return None
    invocations = []
    for statement in statements:
        runner = _classify_runner(_strip_launch_prefixes(statement))
        if runner is not None:
            invocations.append(TestInvocation(runner=runner, statement=tuple(statement)))
    return invocations


_PYTEST_OPTIONS_WITH_VALUE = frozenset({
    "-k", "-m", "-c", "-p", "-o", "-W", "-n", "-r", "--rootdir", "--tb", "--maxfail", "--junitxml",
    "--basetemp", "--ignore", "--ignore-glob", "--deselect", "--durations", "--confcutdir",
    "--import-mode", "--log-level", "--timeout", "--color", "--capture", "--override-ini",
    "--durations-min", "--cache-dir",
})
_FLUTTER_TEST_OPTIONS_WITH_VALUE = _FLUTTER_DART_OPTIONS_WITH_VALUE | frozenset({
    "-n", "--name", "-N", "--plain-name", "-t", "--tags", "-x", "--exclude-tags", "-r", "--reporter",
    "-j", "--concurrency", "--timeout", "--platform", "--file-reporter",
    "--shard-index", "--total-shards", "--test-randomize-ordering-seed", "--flavor", "--dart-define",
    "--target", "-a", "--arch",
})
HEAVY_FLUTTER_SUBCOMMANDS = frozenset({"build", "drive"})


def _looks_like_path(value: str) -> bool:
    return "/" in value or os.path.isdir(value)


_EXPLICIT_FILE_EXTENSIONS = frozenset({".py", ".dart"})


def _command_base_dir(tokens: List[str]) -> str:
    """命令子程序的工作目錄：`uv --directory X` 會讓 pytest 在 X 下執行，相對路徑對 X 解析。

    其餘情形沿用本行程 cwd（hook 與閘門皆與 Bash 工具同 cwd）。`--directory` 可連續出現，
    後者相對前者解析；解析不出（含空值）時保留已得基準。
    """
    base = os.getcwd()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        value = None
        if token == "--directory" and index + 1 < len(tokens):
            value = tokens[index + 1]
            index += 1
        elif token.startswith("--directory="):
            value = token.split("=", 1)[1]
        if value:
            base = os.path.normpath(os.path.join(base, os.path.expanduser(value)))
        index += 1
    return base


def _is_explicit_existing_file(arg: str, base_dir: str) -> bool:
    """pytest 對命令列明確指定的檔案不套 python_files 樣式：既存一般檔案且副檔名為 .py／.dart 即具體檔案。

    路徑不存在、含 glob 字元、目錄、integration_test 皆不成立；檢查本身例外時保守回 False（判 heavy）。
    """
    if any(ch in arg for ch in "*?["):
        return False
    try:
        if os.path.splitext(arg)[1] not in _EXPLICIT_FILE_EXTENSIONS:
            return False
        return os.path.isfile(os.path.join(base_dir, os.path.expanduser(arg)))
    except Exception:  # 判準失效時保守判 heavy（只多排隊、不漏擋），不另記錄：呼叫端為閘門熱路徑
        return False


def _all_specific_test_files(args: List[str], with_value, base_dir: Optional[str] = None) -> bool:
    """位置參數非空且全部指到具體測試檔（*_test.dart、test_*.py、*_test.py、path::node id，
    或 base_dir 下既存的 .py／.dart 一般檔案）。

    混入任何目錄或非測試檔的位置參數即不成立：目錄會讓整個目錄的測試都跑。
    根本防線：被當成選項值吞掉的 token 若像路徑（含 `/` 或為既有目錄），整體不成立——
    帶值選項集合採列舉，日後分錯類時只會多排隊，不會被「選項值」吞掉的目錄繞過。
    """
    positional: List[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            positional.extend(args[index + 1:])
            break
        if arg.startswith("-"):
            if arg in with_value and index + 1 < len(args):
                if _looks_like_path(args[index + 1]):
                    return False
                index += 2
            else:
                index += 1
            continue
        positional.append(arg)
        index += 1
    if base_dir is None:
        base_dir = os.getcwd()
    return bool(positional) and all(
        _SPECIFIC_TEST_FILE_RE.search(arg.split("::", 1)[0])
        or _is_explicit_existing_file(arg.split("::", 1)[0], base_dir)
        for arg in positional)


# 查詢類旗標：只印說明、版本或列舉測試，不執行測試也不編譯，負載輕
QUERY_FLAGS = frozenset({"--help", "-h", "-help", "--version", "-version", "--collect-only"})


def _weight_of_stripped(tokens: List[str], launcher_led: bool, base_dir: Optional[str] = None) -> str:
    if any(token in QUERY_FLAGS for token in tokens[1:]):
        return WEIGHT_LIGHT
    head = Path(tokens[0]).name
    if head in HEAVY_BUILD_EXECUTABLES or (
            head == "xcrun" and any(Path(t).name in HEAVY_BUILD_EXECUTABLES for t in tokens[1:])):
        return WEIGHT_HEAVY
    if head in (RUNNER_FLUTTER, RUNNER_DART):
        rest = _skip_options(tokens[1:], _FLUTTER_DART_OPTIONS_WITH_VALUE)
        if rest and rest[0] in HEAVY_FLUTTER_SUBCOMMANDS:
            return WEIGHT_HEAVY
        if rest and rest[0] == "test":
            args = rest[1:]
            if any(INTEGRATION_TEST_MARKER in arg for arg in args):
                return WEIGHT_HEAVY
            return WEIGHT_LIGHT if _all_specific_test_files(
                args, _FLUTTER_TEST_OPTIONS_WITH_VALUE, base_dir) else WEIGHT_HEAVY
    elif _classify_runner(tokens) == RUNNER_PYTEST:
        return WEIGHT_LIGHT if _all_specific_test_files(
            tokens[1:], _PYTEST_OPTIONS_WITH_VALUE, base_dir) else WEIGHT_HEAVY
    elif _classify_runner(tokens) == RUNNER_NPM:
        return WEIGHT_HEAVY
    # 判不出 runner：launcher 開頭者依慣例是測試或編譯的包裝，保守視為 heavy（誤判只多排隊）
    return WEIGHT_HEAVY if launcher_led else WEIGHT_LIGHT


def classify_argv_weight(tokens: List[str]) -> str:
    """argv 清單（非 shell 字串）的負載分級：未指定具體測試檔的全套件測試與編譯為 heavy。

    供本機名額閘門使用；沿用 find_test_invocations 的前綴剝除，不重新拼接字串。
    """
    if not tokens:
        return WEIGHT_LIGHT
    stripped = _strip_launch_prefixes(list(tokens))
    if not stripped:
        return WEIGHT_HEAVY  # 全是 launcher 而無命令，屬 launcher 開頭判不出 runner
    return _weight_of_stripped(stripped, launcher_led=stripped != list(tokens),
                               base_dir=_command_base_dir(list(tokens)))


def _is_known_heavy_candidate(tokens: List[str]) -> bool:
    """剝除前綴後的命令是否屬已辨識的 runner／編譯器（排除「launcher 開頭判不出而保守視為 heavy」）。"""
    head = Path(tokens[0]).name
    if head in HEAVY_BUILD_EXECUTABLES or head in (RUNNER_FLUTTER, RUNNER_DART):
        return True
    if head == "xcrun" and any(Path(t).name in HEAVY_BUILD_EXECUTABLES for t in tokens[1:]):
        return True
    return _classify_runner(tokens) is not None


_TRAILING_CONTROL_OPERATORS = frozenset({"&", ";", "&&", "||", "|"})


def _without_trailing_operators(statement) -> Tuple[str, ...]:
    """去除敘述結尾的控制運算子（&、; 等），供產生可直接複製的包裝寫法。"""
    tokens = list(statement)
    while tokens and tokens[-1] in _TRAILING_CONTROL_OPERATORS:
        tokens.pop()
    if tokens and tokens[-1].endswith(";") and len(tokens[-1]) > 1:
        tokens[-1] = tokens[-1].rstrip(";")
    return tuple(tokens)


_REDIRECT_OPERATORS = frozenset({">", ">>", "<", "&>", "&>>", ">|", "<<", "<<<", ">&", "<&"})
_REDIRECT_SELF_CONTAINED_RE = re.compile(r"^\d?[<>]&\d+-?$")


def split_redirections(tokens: List[str]) -> Tuple[List[str], List[str]]:
    """把敘述 token 拆為（命令 token，重導向片段）。

    切分器把重導向留在 token 內：`2>&1`；`2`、`>`、`/tmp/e`；`&>`、`>>`、`<` 與其目標。
    重導向片段已渲染為可接在命令之後的 shell 文字（運算子與 fd 不加引號，目標以 shlex 引號保護）。
    已知限制：選項值恰為單一數字且緊接重導向運算子（`-n 2 > x`）時，該數字被當成 fd 而剝除，
    只影響建議寫法的文字，不影響 light 判定（位置參數不變）。
    """
    command: List[str] = []
    redirects: List[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _REDIRECT_SELF_CONTAINED_RE.match(token):
            redirects.append(token)
            index += 1
        elif token in _REDIRECT_OPERATORS:
            target = tokens[index + 1] if index + 1 < len(tokens) else None
            redirects.append(token if target is None else "{} {}".format(token, shlex.quote(target)))
            index += 1 if target is None else 2
        elif (len(token) == 1 and token.isdigit() and index + 2 < len(tokens)
              and tokens[index + 1] in _REDIRECT_OPERATORS):
            redirects.append("{}{} {}".format(token, tokens[index + 1], shlex.quote(tokens[index + 2])))
            index += 3
        else:
            command.append(token)
            index += 1
    return command, redirects


def _has_variable_positional(args: List[str], with_value) -> bool:
    """位置參數（非選項、非帶值選項的值）中是否含未展開的 shell 變數（`$t`、`${t}`、`$(...)`）。"""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return any("$" in a for a in args[index + 1:])
        if arg.startswith("-"):
            index += 2 if arg in with_value else 1
            continue
        if "$" in arg:
            return True
        index += 1
    return False


def has_variable_test_target(tokens: List[str]) -> bool:
    """剝除前綴後的測試命令，其測試目標是否含未展開的 shell 變數。

    此時目標無法由字面判定（變數可能指向單一測試檔，也可能指向目錄），
    封堵端據此視為無法判定而放行（fail-open）。僅看 flutter／dart test 與 pytest。
    """
    if not tokens:
        return False
    head = Path(tokens[0]).name
    if head in (RUNNER_FLUTTER, RUNNER_DART):
        rest = _skip_options(tokens[1:], _FLUTTER_DART_OPTIONS_WITH_VALUE)
        return bool(rest) and rest[0] == "test" and _has_variable_positional(
            rest[1:], _FLUTTER_TEST_OPTIONS_WITH_VALUE)
    if _classify_runner(tokens) == RUNNER_PYTEST:
        return _has_variable_positional(tokens[1:], _PYTEST_OPTIONS_WITH_VALUE)
    return False


def find_variable_target_statements(command: str) -> List[Tuple[str, ...]]:
    """回傳命令中測試目標含未展開變數的敘述（供封堵端記錄 fail-open 放行）；無法解析回 []。"""
    statements = parse_command_statements(command)
    if statements is None:
        return []
    found = []
    for statement in statements:
        cmd_tokens, _ = split_redirections(list(_without_trailing_operators(statement)))
        stripped, _wrapped = _strip_launch_prefixes_tracking(cmd_tokens)
        if has_variable_test_target(stripped):
            found.append(tuple(cmd_tokens))
    return found


def find_unwrapped_heavy_with_redirects(command: str) -> Optional[List[Tuple[Tuple[str, ...], str]]]:
    """同 find_unwrapped_heavy，每筆另附渲染後的重導向文字（無則空字串）；供產生建議寫法。

    重導向在判定前先剝除（否則 `2>&1` 等被當成非測試檔的位置參數而把單檔誤判 heavy）。
    測試目標含未展開 shell 變數者視為無法判定，不列入（fail-open）。
    """
    statements = parse_command_statements(command)
    if statements is None:
        return None
    found = []
    for statement in statements:
        cmd_tokens, redirects = split_redirections(list(_without_trailing_operators(statement)))
        stripped, wrapped = _strip_launch_prefixes_tracking(cmd_tokens)
        if wrapped or not stripped or not _is_known_heavy_candidate(stripped):
            continue
        # 判定順序：先排除含未展開 shell 變數的目標（字面無法判定，fail-open 放行），
        # 再以字面目標分級（命名樣式或基準目錄下既存 .py／.dart 檔判 light，其餘 heavy）。
        # 變數目標在字面階段不可能解析成既存檔，故必須先於檔案檢查處理。
        if has_variable_test_target(stripped):
            continue
        if _weight_of_stripped(stripped, launcher_led=False,
                               base_dir=_command_base_dir(cmd_tokens)) == WEIGHT_HEAVY:
            found.append((tuple(cmd_tokens), " ".join(redirects)))
    return found


def find_unwrapped_heavy(command: str) -> Optional[List[Tuple[str, ...]]]:
    """回傳命令中「已辨識為 heavy 且未經 run-with-timeout 包裝」的敘述（不含重導向）；無法解析回 None。

    供封堵端（pre-test-hook）使用：只認已辨識的 runner／編譯器，launcher 開頭判不出者
    不算（閘門端保守視為 heavy 只多排隊，封堵端誤判則擋掉正當命令，代價較高）。
    """
    found = find_unwrapped_heavy_with_redirects(command)
    return None if found is None else [cmd for cmd, _ in found]
