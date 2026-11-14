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
`sh -c`／`python -c`（命令位於引號字串內）、shell 函式參數（`run() { "$@"; };
run uv run pytest`，runner 只出現在參數位置）、變數展開為命令（`$CMD`、
`"${arr[@]}"`）、`yarn`／`pnpm`／`npx` 的測試、`env A=1 -u X cmd`（賦值後才出現
選項）、`--opt=val` 以外未列入帶值集合的自訂選項（帶值集合採列舉，未列入的帶值
選項其值會被當成子命令而漏判）。其中 bash -c、函式參數、變數展開三種形態，若命令
文字中看得到 runner 字樣，find_unrecognized_runner_mention 會回報，pre-test-hook
以 additionalContext 提醒（不阻擋）；runner 字樣不在命令文字中者（腳本檔內呼叫、
變數在別處定義）仍無法察覺。
"""

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .git_command_parse import (
    parse_command_statements,
    skip_prefix_wrapper_count,
    strip_heredoc_bodies,
    strip_line_comments,
)

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

# 自行取得名額的命令（命令名, 子命令）：判不出 runner 一律 heavy 的唯一例外，判 light。
# worktree merge 由 merge_gate.hold 無條件自行取得名額；run-with-timeout 啟動被包裝命令時以
# slot_gate.child_env 去除持有標記，被包裝的 merge 認不出祖先已持有；SLOT_COUNT 為 1。
# 外層若也判 heavy 先取得名額，內層 merge 會排在外層之後，兩者互等至外層逾時。
SELF_SLOTTED_COMMANDS = frozenset({("worktree", "merge")})


def _is_self_slotted(tokens: List[str]) -> bool:
    return len(tokens) >= 2 and (Path(tokens[0]).name, tokens[1]) in SELF_SLOTTED_COMMANDS


def _weight_of_stripped(tokens: List[str], base_dir: Optional[str] = None) -> str:
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
        # 已辨識的 runner、子命令不編譯也不跑測試（pub get、analyze 等）：light，不屬判不出 runner
        return WEIGHT_LIGHT
    elif _classify_runner(tokens) == RUNNER_PYTEST:
        return WEIGHT_LIGHT if _all_specific_test_files(
            tokens[1:], _PYTEST_OPTIONS_WITH_VALUE, base_dir) else WEIGHT_HEAVY
    elif _classify_runner(tokens) == RUNNER_NPM:
        return WEIGHT_HEAVY
    if _is_self_slotted(tokens):
        return WEIGHT_LIGHT
    # 判不出 runner 一律 heavy（誤判只多排隊）：裸 python3、bash -c、env 前綴同判，
    # 命令形態不改變結果，間接執行的全套件測試無法以改寫形態繞過名額
    return WEIGHT_HEAVY


def classify_argv_weight(tokens: List[str]) -> str:
    """argv 清單（非 shell 字串）的負載分級。

    light：指定具體測試檔的測試、查詢類旗標、SELF_SLOTTED_COMMANDS、空命令；
    其餘（全套件測試、編譯、判不出 runner 的命令）皆 heavy。
    供本機名額閘門使用；沿用 find_test_invocations 的前綴剝除，不重新拼接字串。
    """
    if not tokens:
        return WEIGHT_LIGHT
    stripped = _strip_launch_prefixes(list(tokens))
    if not stripped:
        return WEIGHT_HEAVY  # 全是 launcher 而無命令，判不出 runner
    return _weight_of_stripped(stripped, base_dir=_command_base_dir(list(tokens)))


def _is_known_heavy_candidate(tokens: List[str]) -> bool:
    """剝除前綴後的命令是否屬已辨識的 runner／編譯器（排除「判不出 runner 而保守視為 heavy」）。"""
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


def find_wrapped_self_slotted(command: str) -> Optional[List[Tuple[Tuple[str, ...], str]]]:
    """經 run-with-timeout 包裝的 SELF_SLOTTED_COMMANDS 敘述；每筆為（去除包裝後的命令, 重導向文字）。

    自行取得名額的命令內部有自己的排隊與逾時；外層包裝的計時器從啟動即開始，
    會把內部排隊算進逾時，排得久就被外層中止。無法解析回 None。
    """
    statements = parse_command_statements(command)
    if statements is None:
        return None
    found = []
    for statement in statements:
        cmd_tokens, redirects = split_redirections(list(_without_trailing_operators(statement)))
        stripped, wrapped = _strip_launch_prefixes_tracking(cmd_tokens)
        if wrapped and stripped and _is_self_slotted(stripped):
            found.append((tuple(stripped), " ".join(redirects)))
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
        if _weight_of_stripped(stripped, base_dir=_command_base_dir(cmd_tokens)) == WEIGHT_HEAVY:
            found.append((tuple(cmd_tokens), " ".join(redirects)))
    return found


# 命令文字中的 runner 字樣（不經敘述切分，直接比對原始字串）。用來發現「看得到 runner、
# 卻辨識不出測試呼叫」的間接形態：shell 函式參數（f uv run pytest）、變數展開（$CMD）、
# bash -c 字串內。唯讀命令（grep pytest 檔案）也會命中，所以只用於提醒，不用於阻擋。
_RUNNER_MENTION_RE = re.compile(
    r"(?<![\w.-])(?:py\.test|pytest)(?![\w-])"
    r"|\b(?:flutter|dart)\s+test\b"
    r"|\bnpm\s+(?:test|t|tst)\b"
)


# 引號內容仍屬可執行文字的兩種前綴：`bash|sh|zsh -c`／`eval` 的引數（間接執行），
# 以及變數賦值的值（`CMD="uv run pytest"; $CMD` 之後以變數展開執行）。
_EXEC_STRING_PREFIX_RE = re.compile(
    r"(?:(?:^|[\s;&|(])(?:ba|z)?sh\s+(?:-\w+\s+)*-\w*c\w*\s*|(?:^|[\s;&|(])eval\s+)$"
)
_ASSIGNMENT_PREFIX_RE = re.compile(r"(?:^|[\s;&|(])[A-Za-z_][A-Za-z0-9_]*=$")


def _read_substitution(text: str, start: int) -> Tuple[str, int]:
    """從 `$(` 之後的位置讀到對應的 `)`，回傳 (內文, 結束後位置)；不平衡時讀到結尾。"""
    depth, i = 1, start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], len(text)


def _scan_executable(text: str) -> str:
    """回傳 shell 實際會當成命令解讀的文字：引號外內容、命令替換，以及
    `bash -c`／`eval`／變數賦值後的引號字串（遞迴處理）；其餘引號內文（訊息、
    --why 文字等引數）以空白取代。不嘗試完整 shell 語法，引號未閉合時其後一律保留。
    """
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 2
            continue
        if ch not in ("'", '"'):
            out.append(ch)
            i += 1
            continue
        end = text.find(ch, i + 1) if ch == "'" else _find_double_quote_end(text, i + 1)
        if end < 0:  # 未閉合：保守保留其後全文
            out.append(text[i:])
            break
        body = text[i + 1:end]
        before = "".join(out)
        if _EXEC_STRING_PREFIX_RE.search(before) or _ASSIGNMENT_PREFIX_RE.search(before):
            out.append(" " + _scan_executable(body) + " ")
        elif ch == '"':
            out.append(" " + _double_quote_substitutions(body) + " ")
        else:
            out.append(" ")
        i = end + 1
    return "".join(out)


def _find_double_quote_end(text: str, start: int) -> int:
    """雙引號字串的結束位置（略過反斜線跳脫）；找不到回 -1。"""
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i
        i += 1
    return -1


def _double_quote_substitutions(body: str) -> str:
    """雙引號內只有 `$(...)` 與反引號會執行，取出其內文（遞迴處理），其餘丟棄。"""
    parts: List[str] = []
    i = 0
    while i < len(body):
        if body.startswith("$(", i):
            inner, i = _read_substitution(body, i + 2)
            parts.append(_scan_executable(inner))
            continue
        if body[i] == "`":
            end = body.find("`", i + 1)
            end = len(body) if end < 0 else end
            parts.append(_scan_executable(body[i + 1:end]))
            i = end + 1
            continue
        i += 1
    return " ".join(parts)


def _executable_text(command: str) -> str:
    """剝除 heredoc 內文與行註解後，只留下 shell 會當成命令解讀的文字。"""
    return _scan_executable(strip_line_comments(strip_heredoc_bodies(command)))


def find_unrecognized_runner_mention(command: str) -> Optional[str]:
    """命令文字含 runner 字樣、但 find_test_invocations 辨識不出任何測試呼叫時，回傳該字樣。

    辨識結果為 []（可解析但無測試呼叫）或 None（無法解析）都算辨識不出；已辨識出至少
    一個測試呼叫時回 None（直接形態已由封堵端與環境檢查處理）。命令不含 runner 字樣回 None。
    """
    match = _RUNNER_MENTION_RE.search(_executable_text(command or ""))
    if match is None:
        return None
    invocations = find_test_invocations(command)
    if invocations:
        return None
    return match.group(0)


def find_unwrapped_heavy(command: str) -> Optional[List[Tuple[str, ...]]]:
    """回傳命令中「已辨識為 heavy 且未經 run-with-timeout 包裝」的敘述（不含重導向）；無法解析回 None。

    供封堵端（pre-test-hook）使用：只認已辨識的 runner／編譯器，判不出 runner 者
    不算（閘門端保守視為 heavy 只多排隊，封堵端誤判則擋掉正當命令，代價較高）。
    """
    found = find_unwrapped_heavy_with_redirects(command)
    return None if found is None else [cmd for cmd, _ in found]


# FVM 管理的執行檔，以及代表「已是釘選版」的執行檔路徑片段（專案內 .fvm/flutter_sdk、
# fvm 快取的 versions/<版本>）：直接以這些路徑呼叫即為釘選版，不需再加 fvm 前綴。
FVM_MANAGED_EXECUTABLES = frozenset({RUNNER_FLUTTER, RUNNER_DART})
_PINNED_SDK_PATH_MARKERS = ("/.fvm/", ".fvm/flutter_sdk", "/fvm/versions/")


def strip_prefixes_noting_fvm(tokens: List[str]) -> Tuple[List[str], bool]:
    """與 _strip_launch_prefixes 相同的剝除，另回報過程中是否經過 fvm。"""
    via_fvm = False
    while tokens:
        if tokens[0] == "fvm":
            via_fvm = True
        stripped = _strip_one_launcher(tokens)
        if stripped == tokens:
            break
        tokens = stripped
    return tokens, via_fvm


def _cd_target(statement: List[str], base: Optional[str]) -> Tuple[bool, Optional[str]]:
    """敘述為 `cd <目錄>` 時回 (True, 新基準)；目標含變數或無法判定時新基準為 None。"""
    if not statement or statement[0] != "cd":
        return False, base
    args = [t for t in statement[1:] if not t.startswith("-")]
    if base is None or len(args) != 1 or "$" in args[0] or args[0] == "-":
        return True, None
    return True, os.path.normpath(os.path.join(base, os.path.expanduser(args[0])))


def find_unmanaged_flutter_statements(
    command: str, start_dir: str, uses_fvm
) -> Optional[List[Tuple[str, ...]]]:
    """命令位置為 flutter／dart、所在專案使用 FVM、而未經 fvm 呼叫的敘述。

    逐敘述追蹤 `cd <字面目錄>` 更新基準目錄；cd 目標無法判定後的敘述不判定（放行）。
    uses_fvm 為判定函式（lib.flutter_launcher.uses_fvm），由呼叫端傳入。
    無法解析回 None；無命中回 []。
    """
    statements = parse_command_statements(command)
    if statements is None:
        return None
    found = []
    base: Optional[str] = start_dir
    for statement in statements:
        cmd_tokens, _ = split_redirections(list(_without_trailing_operators(statement)))
        is_cd, base = _cd_target(cmd_tokens, base)
        if is_cd or base is None or not cmd_tokens:
            continue
        stripped, via_fvm = strip_prefixes_noting_fvm(cmd_tokens)
        if via_fvm or not stripped:
            continue
        executable = stripped[0]
        if Path(executable).name not in FVM_MANAGED_EXECUTABLES:
            continue
        if any(marker in executable for marker in _PINNED_SDK_PATH_MARKERS):
            continue
        if uses_fvm(base):
            found.append(tuple(cmd_tokens))
    return found
