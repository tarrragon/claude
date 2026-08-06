#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Bash Edit Guard Hook - PreToolUse Hook

功能: 偵測 Bash 中的高風險操作。兩模式處置不同——原地編輯出警告後放行，
      裸 cd / pushd 直接擋下並指引 git -C

觸發時機: 執行 Bash 工具時

檢測模式 A（原地編輯，建議改用 Edit 工具）:
  - sed -i 或 sed --in-place (原地編輯，不可逆)
  - perl -pi 或 perl -i.bak (原地編輯，不可逆)

檢測模式 B（裸 cd / pushd，建議改用 git -C 或子 shell）:
  - 行首裸 cd / pushd（含多行命令第二行行首，connector 集涵蓋 \\n）
  - 串接後裸 cd / pushd（&& cd、; cd、|| cd）
  - pushd 與 cd 同樣改變持久 cwd 並觸發 chpwd（IMP-056），一併偵測
  - 排除子 shell 形式：以括號深度追蹤，未閉合子 shell 內的所有 cd/pushd
    （不論 connector 為 (、&& 或 ;）皆不改變持久 cwd，一致排除
  - 排除 git -C / uv -d（不含 cd 指令，天然不命中）
  - 排除還原至專案根 cd /<repo-root>（污染後補救的合法用途）

行為:
  - 模式 A（sed/perl 原地編輯）: 輸出警告訊息（permission_decision=allow），允許繼續執行。
  - 模式 B（裸 cd / pushd）: permission_decision=deny（IMP-008 三度復發後根治）。
    命中即在命令送出前擋下，cwd 不因該次命令改變；reason 附 git -C / 子 shell /
    uv -d 替代指引。兩個已知放行面（皆非缺陷，但「永不改變 cwd」不成立）：
    還原至專案根的 cd 屬刻意排除（見上）；偵測為正則掃描字面命令，
    `bash -c 'cd x'`、`eval`、變數展開、`builtin cd` 等非字面形式不在範圍。
    cd + edit 同時命中以 deny 為準。
    FP 抑制：heredoc body 與單/雙引號字串內的字面 cd 不算裸 cd，避免擋掉合法 script 撰寫。
"""

import json
import os
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output
from lib.hook_messages import ValidationMessages, format_message


def _detect_bash_edit_patterns(command: str, literal_ranges=None) -> bool:
    """
    檢測是否為高風險原地編輯操作（白名單降級版本）

    降級策略：
    原始 6 個 pattern 中保留 2 個高風險原地編輯模式（sed -i / perl -pi），
    移除 4 個噪音模式（輸出重定向 / awk 重定向 / 通用 > 檔案）。
    實測分析：3 天內 1662 次 Action 中不可逆風險佔比 ~0%；
    保留的兩個 pattern 才是真正的原地編輯不可逆風險。

    保留模式:
    1. sed -i 或 sed --in-place（原地編輯，不可逆）
    2. perl -pi 或 perl -i.bak（原地編輯，不可逆）

    移除模式（觀察期 W10-047.3 起）:
    - sed/awk + > file 重定向（多為合法產出）
    - 通用命令 > 程式碼檔（多為合法產出，誤報率高）

    FP 抑制（0.2.1-W3-193，單趟狀態機修復見 0.2.1-W3-204）：與模式 B 共用
    _literal_offset_ranges()，落在 heredoc body / 引號字串內的字面命中不
    視為真正執行的原地編輯；引號外的真實命中不受影響仍會觸發。

    Args:
        command: Bash 命令
        literal_ranges: 字面區段範圍清單（未提供時內部計算）

    Returns:
        bool - 是否偵測到高風險原地編輯模式
    """
    if literal_ranges is None:
        literal_ranges = _literal_offset_ranges(command)

    # 模式 1: sed -i 或 sed --in-place（原地編輯）
    for match in re.finditer(r'sed\s+(-i|--in-place)', command):
        if not _offset_in_literal(match.start(), literal_ranges):
            return True

    # 模式 2: perl -pi 或 perl -i.bak（原地編輯）
    for match in re.finditer(r'perl\s+(-pi|-i\.bak)', command):
        if not _offset_in_literal(match.start(), literal_ranges):
            return True

    return False


# 裸 cd / pushd 出現點掃描樣式
# connector 涵蓋：行首(^)、換行(\n)、&&、;、||、左括號(()
# \bcd\b / \bpushd\b 後須接空白 + 引數，避免命中 cdrom / pushder 等字面
_BARE_CD_PATTERN = re.compile(
    r'(^|\n|&&|;|\|\||\()\s*\b(cd|pushd)\s+(\S+)'
)


# heredoc 標頭樣式：<< 或 <<- 後可選空白，delimiter 可被單/雙引號包住
_HEREDOC_HEADER_PATTERN = re.compile(r'<<-?\s*([\'"]?)([A-Za-z_][A-Za-z0-9_]*)\1')


def _find_closing_quote(command: str, start: int, quote_char: str) -> int:
    """
    從 start（開引號位置）之後尋找配對的收尾引號 offset，依 shell 語意
    區分單雙引號的跳脫行為（0.2.1-W3-205）：

    - 雙引號（quote_char == '"'）：反斜線具跳脫作用，`\\"` 不會提前收尾。
    - 單引號：反斜線不具跳脫作用，是字面字元，遇到第一個單引號即收尾。

    Returns:
        int - 收尾引號的 offset，找不到時回傳 -1（未閉合）
    """
    i = start + 1
    length = len(command)
    while i < length:
        ch = command[i]
        if quote_char == '"' and ch == '\\' and i + 1 < length:
            i += 2
            continue
        if ch == quote_char:
            return i
        i += 1
    return -1


def _literal_offset_ranges(command: str):
    """
    回傳命令中「字面文字區段」的 offset 範圍清單 [(start, end), ...]，
    供 DENY 升級後抑制誤擋——落在這些區段內的 cd/pushd 是腳本內容而非
    真正執行的裸 cd（避免擋掉合法 script 撰寫）。

    單趟 left-to-right 狀態機掃描，帶引號與 heredoc 狀態（0.2.1-W3-204）：
    1. 引號優先消耗：掃描到 ' 或 " 時，整段引號字串（含引號本身）直接記
       為一段字面區段並跳過，區段內容不再被個別檢視——因此引號內出現的
       `<<DELIM` 字面不會被誤判為真 heredoc 標頭（修復 0.2.1-W3-193 遺留
       的兩趟獨立掃描互不知情問題）。
    2. heredoc 標頭僅在引號外承認：只有在非引號消耗狀態下掃描到 `<<` 時
       才嘗試比對 heredoc 標頭。
    3. 未閉合 heredoc 不產生 range：標頭比對成功但找不到結束 delimiter
       時，直接跳過標頭本身繼續掃描，不再抑制任何區段（移除舊版「延伸至
       命令結尾」的行為，那是抑制最激進、也是漏放缺陷的根因）。

    務實邊界（PreToolUse 只見 raw 字串、無完整 shell parse）：

    - heredoc 結束 delimiter 比照常見用法（行首可選空白 + delimiter 單
      獨成行）。
    - **未閉合引號 → 不足額抑制**。掃描到未配對引號即中止，其後不再產生
      任何字面區段。呼叫端仍對整條原始命令做 regex 掃描，故未被抑制的
      字面內容（例如 heredoc body 內的 `cd`）會被當成真實命中。後果是
      假 DENY——擋掉合法工作。此方向刻意選擇，理由不是「比較安全」而是
      **可觀測性不對稱**：漏放無聲無息，假 DENY 會立刻被使用者回報並修正。
      代價須誠實計入：擋錯一次，使用者學到的是繞過本 hook。

    跳脫引號處理（0.2.1-W3-205）：反斜線跳脫依 shell 語意分流處理，不採
    「不分單雙引號一律處理」的簡化版——單雙引號跳脫語意不同（雙引號內
    `\\"` 是跳脫、單引號內反斜線是字面字元），簡化版會在單引號含反斜線
    的合法命令上再造成新的配對錯位，等同把一個已知漏放換成另一個。實作
    上：引號外的反斜線一律跳脫下一字元（含引號字元本身，故 `\\"` 不會
    被誤判為開啟一段引號）；雙引號內的反斜線依樣跳脫下一字元（`\\"` 不
    提前收尾）；單引號內的反斜線不具跳脫作用，遇到即以一般字元處理，第
    一個引號字元就收尾。

    **仍存在的漏放（0.2.1-W3-207 追蹤）：命令替換巢狀。**本實作看不到
    `$(...)` 內部重新開啟的引號脈絡，實測反例：

        echo "$(echo "x") && cd /tmp"   → 真實裸 cd 被劃進字面區而放行

    首個引號與 `$(echo "` 的引號配對，錯位後把後續真實命令吞掉。
    `${var#"x"}`、`$((...))` 同類。方向與 0.2.1-W3-204 修掉的缺陷相同
    （漏放、無聲）。另有兩個方向無害的失準：backtick 完全不視為引號
    （零抑制，誤報方向）、ANSI-C quoting `$'...'` 內的反斜線按普通單引號
    處理（收尾早一位，實測方向無害但屬測資巧合非結構保證）。

    **這三者不是三個獨立 case，是同一個缺失概念——沒有引號脈絡堆疊。**
    下次再出現引號類漏放時，禁止加第四條分支；正解是把 quote、heredoc、
    command substitution 統一為 push/pop 的 context stack，三者會一起
    消失（0.2.1-W3-207 記錄該解法與觸發條件）。

    Returns:
        list[tuple[int, int]] - 字面區段的 [start, end) offset 範圍
    """
    ranges = []
    length = len(command)
    i = 0
    while i < length:
        ch = command[i]

        if ch == '\\' and i + 1 < length:
            # 引號外的跳脫：反斜線與下一字元一併跳過，避免 \" 之類的
            # 跳脫引號被誤判為開啟一段引號（0.2.1-W3-205）
            i += 2
            continue

        if ch in ("'", '"'):
            close = _find_closing_quote(command, i, ch)
            if close == -1:
                # 未閉合引號：中止掃描，不再產生後續字面區段
                break
            ranges.append((i, close + 1))
            i = close + 1
            continue

        if ch == '<':
            header = _HEREDOC_HEADER_PATTERN.match(command, i)
            if header:
                delim = header.group(2)
                header_end = header.end()
                nl = command.find('\n', header_end)
                if nl == -1:
                    # 標頭後無換行 → 無 body 內容，跳過標頭本身
                    i = header_end
                    continue
                body_start = nl + 1
                end_delim_re = re.compile(
                    r'(?m)^[ \t]*' + re.escape(delim) + r'[ \t]*$'
                )
                end_match = end_delim_re.search(command, body_start)
                if end_match:
                    ranges.append((body_start, end_match.start()))
                    i = end_match.end()
                else:
                    # 未閉合 heredoc：不產生 range，僅跳過標頭本身
                    i = header_end
                continue

        i += 1

    return ranges


def _offset_in_literal(offset: int, literal_ranges) -> bool:
    """offset 是否落在任一字面區段內（用於抑制 DENY）。"""
    for start, end in literal_ranges:
        if start <= offset < end:
            return True
    return False


def _find_bare_cd_target(command: str, literal_ranges=None) -> str | None:
    """
    掃描命令，回傳第一個構成「裸 cd / pushd」的命中 target，無命中回傳 None。

    本環境 zsh 有 chpwd hook，裸 cd / pushd 會觸發 ls 淹沒工具結果（IMP-056），
    是 confabulation 觸發鏈第 1 環。規則建議改用 git -C 或子 shell。

    命中模式:
    - 行首 cd / pushd（含換行後的行首，connector 集涵蓋 \\n —— 修復多行漏報）
    - 串接後 cd / pushd（&& cd、; cd、|| cd）
    - pushd 與 cd 同樣改變持久 cwd 並觸發 chpwd，一併偵測

    排除（不視為裸 cd）:
    - 子 shell 內的 cd / pushd：以括號深度追蹤命中位置，凡命中點落在未閉合
      子 shell 內（depth > 0）一律排除，不論該命中 connector 為 (、&& 或 ;。
      修復前 (cd a && cd b) 第二個 cd 因 connector 為 && 誤報，現一致排除。
    - git -C <path> / uv -d <path>：不含 cd 指令，天然不命中
    - 還原至專案根 cd /<repo-root>：污染後補救的合法用途（CLAUDE_PROJECT_DIR）

    收窄修正（W1-026）:
    舊版排除所有絕對路徑 cd，導致 cd /<repo-root>/subdir（絕對子目錄）被靜默放行。
    現收窄為「target 正規化後恰等於專案根」才排除，絕對子目錄恢復 warn。
    CLAUDE_PROJECT_DIR 未設時保守不排除（warn 不 deny）。

    False-positive 務實邊界（限制）:
    PreToolUse 只見 raw command 字串，無完整 shell parse。
    heredoc／quoted 字串內的字面 cd 可能誤判。warn 不 deny，誤判成本低。

    Args:
        command: Bash 命令

    Returns:
        str | None - 命中的 cd/pushd target；無命中回傳 None
    """
    # 專案根（用於排除「污染後還原至專案根」的合法 cd）
    # CLAUDE_PROJECT_DIR 未設時為 None，保守不排除任何絕對路徑
    project_root = os.environ.get('CLAUDE_PROJECT_DIR')
    if project_root:
        project_root = project_root.rstrip('/')

    # FP 抑制（DENY 升級配套）：heredoc body 與單/雙引號字串內的字面 cd 是
    # 腳本內容而非真正執行的裸 cd，命中點落在這些區段一律 skip。
    if literal_ranges is None:
        literal_ranges = _literal_offset_ranges(command)

    for match in _BARE_CD_PATTERN.finditer(command):
        target = match.group(3)

        # 排除 0: 命中的 cd/pushd 關鍵字落在字面區段（heredoc/quoted）內 → 非裸 cd
        if _offset_in_literal(match.start(2), literal_ranges):
            continue

        # 排除 1: 子 shell 內的 cd / pushd — 關鍵字落在未閉合括號內則排除。
        # 以「cd/pushd 關鍵字起點」之前的括號淨深度判定（含 connector 的左括號）：
        # 對 (cd a && cd b)，兩個關鍵字起點前的 depth 皆為 1 → 一致排除。
        # 對 cd outer && (cd inner)，外層前 depth=0（命中），內層前 depth=1（排除）。
        prefix = command[: match.start(2)]
        depth = prefix.count('(') - prefix.count(')')
        if depth > 0:
            continue

        # 排除 2: 還原至專案根 cd /<repo-root> — 污染後補救的合法用途
        # 收窄：僅 target 正規化後恰等於專案根才排除；絕對子目錄恢復 warn
        if project_root and target.rstrip('/') == project_root:
            continue

        # 命中：裸 cd / pushd（行首或串接後，且非專案根還原、非子 shell）
        return target

    # 排除 3 & 4: git -C / uv -d 不含 cd 指令，天然不命中上方掃描
    return None


def _detect_bare_cd(command: str) -> bool:
    """偵測裸 cd / pushd，回傳是否命中（細節見 _find_bare_cd_target）。

    test-only：main() 流程直接呼叫 _find_bare_cd_target() 取得 target 供
    DENY reason 使用，本函式僅供測試以布林斷言簡化呼叫（0.2.1-W3-204）。
    """
    return _find_bare_cd_target(command) is not None


def _print_warning_message(command: str) -> None:
    """
    輸出警告訊息到 stderr

    Args:
        command: 檢測到的 Bash 命令
    """
    # 截短命令顯示（最多 100 字元）
    display_command = command[:100] + ('...' if len(command) > 100 else '')

    warning = format_message(
        ValidationMessages.BASH_EDIT_DETAILED_WARNING,
        command=display_command
    )
    return warning


def _bare_cd_warning_message(command: str) -> str:
    """
    產生裸 cd 警告訊息（走 ValidationMessages 常數）。

    Args:
        command: 偵測到裸 cd 的 Bash 命令

    Returns:
        str - 格式化後的提示訊息
    """
    display_command = command[:100] + ('...' if len(command) > 100 else '')
    return format_message(
        ValidationMessages.BARE_CD_WARNING,
        command=display_command
    )


def _bare_cd_deny_reason(target: str) -> str:
    """
    產生裸 cd DENY 的 permission_decision_reason（含命中 target + 替代指引）。

    DENY 在命令送出前擋下，cwd 不因該次命令改變（IMP-008 三度復發後由 warn
    升級為 DENY）。已知放行面見檔頭「行為」段——本函式不宣稱涵蓋所有改變
    cwd 的形式。reason 提供 git -C / 子 shell / uv -d 三種合法替代。

    Args:
        target: 命中的裸 cd/pushd target 路徑

    Returns:
        str - DENY reason 文字
    """
    return (
        "偵測到裸 cd/pushd（target={}），會改變持久 cwd 並觸發 chpwd ls 淹沒"
        "（IMP-008）。請改用以下合法替代：\n"
        "  - git 操作：git -C <abs> <cmd>（首選，完全不換 cwd）\n"
        "  - 一般命令：子 shell (cd <dir> && <cmd>)\n"
        "  - uv 專案：uv -d <dir> run <cmd>\n"
        "詳見 .claude/rules/core/bash-tool-usage-rules.md 規則一"
    ).format(target)


def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("bash-edit-guard")

    try:
        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if input_data is None:
            return 0
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 檢查是否為 Bash 工具
        if tool_name != "Bash":
            # 非 Bash 工具：直接允許
            logger.info("跳過: 工具類型 %s 不是 Bash", tool_name)
            return 0

        # 取得命令內容
        command = tool_input.get("command", "")

        # 兩偵測獨立：原地編輯偵測 + 裸 cd 偵測，各自蒐集警告
        # 兩者共用同一套字面區段抑制（0.2.1-W3-193），避免重複計算
        warnings = []
        literal_ranges = _literal_offset_ranges(command)

        if _detect_bash_edit_patterns(command, literal_ranges):
            # 診斷日誌記錄完整命令（不截斷）以利 FP 診斷；UI 訊息仍截短顯示
            logger.info("警告: 偵測到編輯操作 - %s", command)
            warnings.append(_print_warning_message(command))

        bare_cd_target = _find_bare_cd_target(command, literal_ranges)
        if bare_cd_target is not None:
            # 診斷日誌記錄完整命令 + 命中 target（不截斷）以利 FP 診斷
            logger.info(
                "提示: 偵測到裸 cd/pushd（target=%s）- %s",
                bare_cd_target,
                command,
            )
            warnings.append(_bare_cd_warning_message(command))

        if not warnings:
            # 不符合任何偵測模式：直接允許
            logger.info("允許: 正常 Bash 命令")
            return 0

        # bare cd 命中 → DENY（命令送出前擋下，cwd 不因該次命令改變；IMP-008
        # 三度復發後由 warn 升級為 DENY。已知放行面見檔頭「行為」段）。
        # sed/perl 原地編輯維持 warn（allow）。cd + edit 同時命中以 deny 為準。
        if bare_cd_target is not None:
            emit_hook_output(
                "PreToolUse",
                additional_context="\n\n".join(warnings),
                permission_decision="deny",
                permission_decision_reason=_bare_cd_deny_reason(bare_cd_target),
            )
            return 0

        # 僅 sed/perl 原地編輯 → warn（allow，誤判成本低）
        emit_hook_output(
            "PreToolUse",
            additional_context="\n\n".join(warnings),
            permission_decision="allow",
            permission_decision_reason="Bash 提示已發送，允許執行",
        )

        return 0

    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        # JSON 解析失敗：直接允許執行，不阻塊
        return 0
    except Exception as e:
        logger.error("執行錯誤: %s", e)
        # 任何錯誤都不阻塊（非阻塞原則）
        return 0


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "bash-edit-guard")
    sys.exit(exit_code)
