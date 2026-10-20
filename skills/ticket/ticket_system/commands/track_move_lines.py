"""
ticket track move-lines 子命令

依行範圍把來源檔的一段文字搬到目標檔，於記憶體驗證行數守恆後以
暫存檔加 rename 寫入；任一步失敗即還原兩檔並以非 0 結束。

用法：
    ticket track move-lines <ticket-id> --src <path> --lines <起>-<迄> \
        --dst <path> --at <行號|end>

src 與 dst 皆須落在 ticket where.files 的寫入範圍內（與 track commit
同一判準），否則拒絕且兩檔不變。--at N 表示插入後搬移段的第一行為
目標檔第 N 行；end 為附加於目標檔尾端。
"""
if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track move-lines")
    sys.exit(1)


import argparse
import logging
import os
import stat
import sys
import tempfile
from typing import List, Optional, Tuple

from ticket_system.commands.track_commit import (
    CRITERIA_REJECTION_GUIDANCE,
)
from ticket_system.lib.file_conflict import write_files
from ticket_system.lib.messages import ErrorMessages, format_error
from ticket_system.lib.project_root import resolve_project_cwd
from ticket_system.lib.ticket_loader import load_ticket
from ticket_system.lib.write_scope import (
    out_of_scope_files,
    resolve_repo_root,
    to_repo_relative,
    unsafe_paths,
)


logger = logging.getLogger(__name__)


class MoveLinesError(Exception):
    """搬移前置驗證或寫入失敗（訊息直接輸出給使用者）。"""


def _parse_range(text: str, total: int) -> Tuple[int, int]:
    """解析 `起-迄`（1 起算、含兩端），回傳 0 起算的 [start, end) 切片界線。"""
    parts = text.split("-")
    if len(parts) != 2 or not all(p.isdecimal() and p.isascii() for p in parts):
        raise MoveLinesError(f"--lines 格式須為 <起>-<迄>，收到 {text!r}")
    first, last = int(parts[0]), int(parts[1])
    if first < 1 or last < first or last > total:
        raise MoveLinesError(f"--lines {text} 超出來源檔範圍（共 {total} 行）")
    return first - 1, last


def _parse_at(text: str, dst_total: int) -> int:
    """解析 --at，回傳 0 起算的插入索引；end 為檔尾。"""
    if text == "end":
        return dst_total
    if not (text.isdecimal() and text.isascii()) or not 1 <= int(text) <= dst_total + 1:
        raise MoveLinesError(f"--at 須為 1..{dst_total + 1} 或 end，收到 {text!r}")
    return int(text) - 1


def _split_lines(text: str) -> List[str]:
    """只以 \\n 為行界並保留換行（與 grep -n 的行號一致）。"""
    parts = text.split("\n")
    lines = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _eol_of(lines: List[str]) -> str:
    """該檔既有換行風格：首個帶換行的行為 CRLF 則 CRLF，否則 LF。"""
    for ln in lines:
        if ln.endswith("\n"):
            return "\r\n" if ln.endswith("\r\n") else "\n"
    return "\n"


def _with_newline(line: str, eol: str = "\n") -> str:
    return line if line.endswith("\n") else line + eol


def _plan_move(
    src_lines: List[str], dst_lines: List[str], start: int, stop: int, at: int
) -> Tuple[List[str], List[str], List[str]]:
    """回傳 (新來源行, 新目標行, 搬移段)。

    搬移段或其前一行缺結尾換行時補上，使行邊界不因拼接而合併。
    """
    src_eol, dst_eol = _eol_of(src_lines), _eol_of(dst_lines)
    moved = [_with_newline(ln, src_eol) for ln in src_lines[start:stop]]
    new_src = src_lines[:start] + src_lines[stop:]
    head = dst_lines[:at]
    if head:
        head[-1] = _with_newline(head[-1], dst_eol)
    return new_src, head + moved + dst_lines[at:], moved


def _verify_conservation(
    old_src: List[str], new_src: List[str], old_dst: List[str],
    new_dst: List[str], moved: List[str], at: int,
) -> None:
    """來源減少行數須等於目標增加行數，且目標內搬移段逐字等於抽出段。"""
    removed, added = len(old_src) - len(new_src), len(new_dst) - len(old_dst)
    if removed != added or removed != len(moved):
        raise MoveLinesError(
            f"行數不守恆：來源減少 {removed}、目標增加 {added}、搬移段 {len(moved)}"
        )
    if new_dst[at:at + len(moved)] != moved:
        raise MoveLinesError("目標內的搬移段與抽出段不逐字相同")


def _stage_temp(path: str, content: bytes, mode: int) -> str:
    """在 path 同目錄寫暫存檔（權限設為 mode）並回傳其路徑。"""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".move-lines-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.chmod(tmp, mode)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError as unlink_exc:
            # 清理失敗不得蓋掉原例外；殘檔路徑記錄供人工刪除
            msg = f"暫存檔清理失敗，請手動刪除：{tmp}（{unlink_exc}）"
            logger.warning(msg)
            sys.stderr.write(f"[WARNING] {msg}\n")
        raise
    return tmp


def _write_both(src: str, dst: str, new_src: bytes, new_dst: bytes,
                old_src: bytes) -> None:
    """暫存檔 rename 寫入兩檔（保留原權限）；失敗則以預先備份還原來源。

    還原本身失敗時保留備份檔並在訊息寫明兩檔狀態與備份位置。
    """
    tmps: List[str] = []
    try:
        src_mode = stat.S_IMODE(os.stat(src).st_mode)
        dst_mode = stat.S_IMODE(os.stat(dst).st_mode)
        tmp_src = _stage_temp(src, new_src, src_mode)
        tmps.append(tmp_src)
        tmp_dst = _stage_temp(dst, new_dst, dst_mode)
        tmps.append(tmp_dst)
        backup = _stage_temp(src, old_src, src_mode)
        tmps.append(backup)
    except OSError as exc:
        _cleanup(tmps)
        raise MoveLinesError(f"寫入前置失敗，兩檔未動：{exc}") from exc
    try:
        os.replace(tmp_src, src)
        os.replace(tmp_dst, dst)
    except OSError as exc:
        _recover(src, dst, backup, tmps, exc)
    _cleanup(tmps)


def _recover(src: str, dst: str, backup: str, tmps: List[str],
             cause: OSError) -> None:
    """寫入失敗後以備份還原來源；一律拋 MoveLinesError。"""
    try:
        os.replace(backup, src)
    except OSError as restore_exc:
        tmps.remove(backup)  # 保留備份供人工還原
        _cleanup(tmps)
        raise MoveLinesError(
            f"寫入失敗（{cause}）且還原失敗（{restore_exc}）。"
            f"dst 未被改動：{dst}；src 可能已是搬移後內容：{src}；"
            f"src 原始內容備份：{backup}"
        ) from restore_exc
    _cleanup(tmps)
    raise MoveLinesError(f"寫入失敗，兩檔已還原：{cause}") from cause


def _cleanup(tmps: List[str]) -> None:
    """刪除暫存檔；單檔刪除失敗只記錄並繼續（搬移結果已定，不應回報失敗）。"""
    for tmp in tmps:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError as exc:
            msg = f"暫存檔清理失敗（搬移已完成，請手動刪除）：{tmp}（{exc}）"
            logger.warning(msg)
            sys.stderr.write(f"[WARNING] {msg}\n")


def _read_lines(path: str) -> Tuple[bytes, List[str]]:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        return raw, _split_lines(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise MoveLinesError(f"無法讀取 {path}：{exc}") from exc


def _check_scope(ticket: dict, args: argparse.Namespace, repo_root: str) -> None:
    declared = {to_repo_relative(p, repo_root, repo_root) for p in write_files(ticket)}
    pair = [args.src, args.dst]
    out = out_of_scope_files(pair, declared, repo_root, repo_root)
    if out:
        raise MoveLinesError(
            "以下檔案不在 ticket where.files 宣告的寫入範圍內，拒絕搬移：\n"
            + "\n".join(f"  - {f}" for f in out) + "\n" + CRITERIA_REJECTION_GUIDANCE
        )
    unsafe = unsafe_paths(pair, repo_root, repo_root)
    if unsafe:
        raise MoveLinesError(
            "以下檔案是 symlink 或解析後落在 repo 之外，拒絕搬移：\n"
            + "\n".join(f"  - {f}" for f in unsafe) + "\n" + CRITERIA_REJECTION_GUIDANCE
        )


def _run_move(ticket: dict, args: argparse.Namespace, repo_root: str) -> str:
    _check_scope(ticket, args, repo_root)
    src = os.path.join(repo_root, to_repo_relative(args.src, repo_root, repo_root))
    dst = os.path.join(repo_root, to_repo_relative(args.dst, repo_root, repo_root))
    if os.path.realpath(src) == os.path.realpath(dst):
        raise MoveLinesError("src 與 dst 不可相同")
    old_src_raw, src_lines = _read_lines(src)
    old_dst_raw, dst_lines = _read_lines(dst)
    start, stop = _parse_range(args.lines, len(src_lines))
    at = _parse_at(args.at, len(dst_lines))
    new_src, new_dst, moved = _plan_move(src_lines, dst_lines, start, stop, at)
    _verify_conservation(src_lines, new_src, dst_lines, new_dst, moved, at)
    _write_both(src, dst, "".join(new_src).encode("utf-8"),
                "".join(new_dst).encode("utf-8"), old_src_raw)
    return f"[OK] 已搬移 {len(moved)} 行：{args.src}:{args.lines} -> {args.dst}（--at {args.at}）"


def execute_move_lines(args: argparse.Namespace, version: str) -> int:
    """`ticket track move-lines`：成功回 0，任何拒絕或失敗回 1（兩檔不變）。"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        msg = format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id)
        logger.error("move-lines 失敗：%s", msg)
        sys.stderr.write(f"[ERROR] {msg}\n")
        return 1
    repo_root: Optional[str] = resolve_repo_root(
        getattr(args, "worktree", None), resolve_project_cwd()
    )
    if repo_root is None:
        msg = (f"--worktree {args.worktree} 不是合法的 git 目錄，"
               "或不屬本 repo 的 git worktree list（查詢失敗亦拒絕）")
        logger.error("move-lines 失敗：%s", msg)
        sys.stderr.write(f"[ERROR] {msg}\n")
        return 1
    try:
        print(_run_move(ticket, args, repo_root))
    except MoveLinesError as exc:
        logger.error("move-lines 失敗：%s", exc)
        sys.stderr.write(f"[ERROR] {exc}\n")
        return 1
    return 0


def register_move_lines_command(subparsers: "argparse._SubParsersAction") -> None:
    """註冊 move-lines 子命令。"""
    p = subparsers.add_parser(
        "move-lines",
        help="依行範圍搬移文字（src/dst 須在 where.files 內，驗證行數守恆後原子寫入）",
    )
    p.add_argument("ticket_id", help="Ticket ID")
    p.add_argument("--src", required=True, help="來源檔路徑")
    p.add_argument("--lines", required=True, help="來源行範圍 <起>-<迄>（1 起算、含兩端）")
    p.add_argument("--dst", required=True, help="目標檔路徑")
    p.add_argument("--at", required=True, help="目標檔插入位置：行號或 end")
    p.add_argument("--worktree", default=None, help="檔案所在 linked worktree 絕對路徑")
