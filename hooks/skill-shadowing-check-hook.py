#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill Shadowing Check Hook

Hook Event: SessionStart

Purpose:
    Claude Code 對同名 skill 的實際載入優先序為 managed → personal
    （`~/.claude/skills/`）→ project（`.claude/skills/`）——見 0.2.1-W3-104
    Problem Analysis 的雙重獨立事證（PM 前台實測 Base directory + 官方執行
    檔靜態分析：skill 合併陣列順序如上，去重採 uniqBy 語意，先出現者保留，
    後出現者被靜默捨棄）。

    這代表：任何人在 project 版 skill 目錄下新增或修改內容，只要更高優先序
    的同名 skill 存在且內容分歧，新內容永遠不會被載入——宣告層（規則寫了）
    與執行層（規則送不到執行點）脫節，且失效對規則作者不可見（ARCH-BAL-003
    實例）。

    本 hook 掃描 project／personal 兩層全部同名 skill（不限定特定名單），對
    每組 skill 遞迴比對**整個目錄**。分歧時輸出 WARNING，列出 skill 名稱、
    雙方版本號、差異檔案清單，使此類遮蔽在下次發生時當場可見。

Coverage gap (0.2.1-W3-113 N2, 明文揭露而非隱含於讀者推論):
    本 hook 只掃描 project 與 personal 兩層，**不掃描 managed（policy-scope）
    與 plugin marketplace 層**——後兩者優先序等於或高於 personal，一旦與
    project 同名碰撞會造成完全遮蔽而非僅內容分歧，且本 hook 完全看不見。
    本機實測 plugin marketplace 層現有 49 個 skill，與本專案 55 個 project
    skill 目前零碰撞（潛伏風險，非現行缺陷）。managed 層路徑解析與 plugin
    marketplace 目錄結構因 marketplace 而異，非本票（W3-113）範圍，追蹤於
    0.2.1-W3-115。

Why soft check (never blocks):
    分歧不代表當下有 bug（可能是刻意的 personal 專屬客製，見 get_exclude_list），
    僅代表「有遮蔽風險，需人工確認是否為預期」。依 quality-baseline 規則 4，
    異常需可見，但不等於必須阻擋 session 啟動。

Scope (W3-104 實作約束，禁止硬編碼特定 skill 名稱):
    掃描 project 與 personal 兩側 `.claude/skills/` 下所有子目錄，任一存在
    `SKILL.md` 或 `skill.md`（大小寫皆接受）即視為一個 skill。僅需目錄名稱
    在兩側同時出現即納入比對，不限定為 wrap-decision / zellij。

Noise exclusion (0.2.1-W3-107 H1, 0.2.1-W3-113 H2):
    遞迴比對排除 `__pycache__`／`.venv`／`venv`／`.git`／`node_modules` 目錄
    與 `*.pyc`、`.DS_Store` 檔案——這些是編譯期/系統/虛擬環境產生的內容，
    project 端常有而 personal 端沒有（如 wrap-decision/hooks/__pycache__、
    多個 skill 各帶的 .venv 達 500+ 檔），若不排除會在完全同步的兩側之間
    造成 false positive，且 .venv 檔案量會把差異清單的截斷額度吃光。

Directory-level read errors (0.2.1-W3-113 H1/N5):
    遞迴列檔改用 `os.walk(..., onerror=raise)`（非 `Path.rglob`）：rglob
    底層 scandir 遇 PermissionError 時內部吞掉並跳過該子樹、不向外拋，使
    呼叫端的 except OSError 永遠不會觸發——兩側同一子樹皆不可讀時會 silently
    產生「內容一致」的假結論，正是本 hook 存在的目的要消滅的失效模式。改用
    onerror callback 強制轉為例外後，此類情形會正確計入 skipped。

Context delivery (0.2.1-W3-113 N1, 取代 0.2.1-W3-107 M3 的不完整版本):
    exit 0 時 Claude Code 只從 **stdout** 注入 SessionStart context，stderr
    僅 transcript/debug 可見。OK 狀態輸出 `{"suppressOutput": true}`；有內容
    （WARNING 或 skipped 通知）時輸出 `hookSpecificOutput.additionalContext`
    + `suppressOutput: false`，比照 session-start-gitignore-check-hook.py。
    stderr + logger 仍保留為次要通道（quality-baseline 規則 4「建議」層級，
    本情境屬業務邏輯發現非 hook 例外），不作為主要送達路徑。

Exit codes:
    0 - Always (soft check, never blocks session)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely


HOOK_NAME = "skill-shadowing-check"

# Hook 位於 .claude/hooks/<file>，故 parent.parent = .claude/，parent.parent.parent = project root
_HOOK_FILE = Path(__file__).resolve()
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or _HOOK_FILE.parent.parent.parent)

_ENTRY_FILENAMES = ("SKILL.md", "skill.md")  # 專案內兩種寫法並存，皆需接受

# 0.2.1-W3-112 L3：錨定行首（re.MULTILINE + ^），只吃非空白 token。
# 舊版 [^\s—\-]+ 誤把 hyphen 當分隔符，"2.7.0-rc1" 會被截成 "2.7.0"；真正的
# 分隔符是「空白 + em-dash」（"2.7.0 — 說明文字"），\S+ 遇空白即停，天然正確。
# 錨定行首避免 search() 抓到表格/範例內非首次出現的 "**Version**" 字樣。
#
# 0.2.1-W3-113 N7（決定：不修）：本模式假設版本行位於行首，本專案 rules/
# 廣泛使用「**Last Updated**: … | **Version**: …」合併式寫法，若 skill 入口
# 檔日後改採該寫法會靜默退化為 'unknown'。實測本專案 52 個 project skill
# 入口檔 100% 為行首式、0 個合併式，現況無影響；且純屬顯示層（比對邏輯是
# 內容位元組比對，不依賴版本號），維持現狀，待入口檔實際出現合併式寫法
# 時再處理。
_VERSION_PATTERN = re.compile(r"^\*\*Version\*\*:\s*(\S+)", re.MULTILINE)

# 0.2.1-W3-113 H2：.venv/venv/.git/node_modules 為虛擬環境/VCS 產生內容，
# 跨機必然不同（bin/activate、pyvenv.cfg 內嵌絕對路徑），比照
# hook-completeness-check.py 的既有排除慣例補齊。
_NOISE_DIR_NAMES = {"__pycache__", ".venv", "venv", ".git", "node_modules"}
_NOISE_FILE_NAMES = {".DS_Store"}
_NOISE_FILE_SUFFIXES = (".pyc",)

_MAX_DIFF_LINES_PER_SKILL = 10  # 差異檔案清單過長時截斷，避免 WARNING 洗版
# 0.2.1-W3-113 H2：截斷前優先排序——入口檔與 references/ 是本專案
# stub-and-satellite 慣例下 substance 的主要載體，噪音檔案已由
# _NOISE_DIR_NAMES 排除，此為第二層防護：其餘子目錄（如 hooks/）差異數量
# 較多時，仍優先讓最關鍵的分歧留在截斷後的可見範圍內。
_PRIORITY_PATH_PREFIXES = ("SKILL.md", "skill.md", "references/")

# 0.2.1-W3-113 N6：get_exclude_list() 所在位置，供 WARNING advice 明確指路
# （審查者 grep 全 .claude/ 確認先前版本無任何文件提及此機制存在）。
EXCLUDE_LIST_LOCATION = f".claude/hooks/{_HOOK_FILE.name}"


class FileDiff(NamedTuple):
    symbol: str  # '+' 僅 project / '-' 僅 personal / '~' 內容不同
    rel_path: str  # 相對於 skill 目錄的 POSIX 路徑
    note: str


class Divergence(NamedTuple):
    name: str
    project_version: str
    personal_version: str
    diffs: List[FileDiff]


class ScanResult(NamedTuple):
    checked_count: int  # 實際完成比對且確認一致的 skill 數
    excluded_diff_count: int  # 依 get_exclude_list 過濾掉的「檔案差異」數（N6：非 skill 層級）
    skipped: List[str]  # 因讀取錯誤無法下結論的 skill 名稱（M1：不可計入一致）
    divergences: List[Divergence]


def get_exclude_list() -> Set[str]:
    """回傳跳過分歧檢查的 `skill名稱/相對路徑` 清單（刻意的 personal 專屬客製）。

    格式：`'skill-name/relative/path/to/file'`（相對於 skill 目錄，POSIX 分
    隔符）。粒度為單一檔案而非整個 skill（0.2.1-W3-113 N6）：若排除整個
    skill，會連帶讓該 skill 其餘內容的真實分歧永遠不再被偵測，與排除清單
    「標記已知例外」的本意相悖。過濾發生於 `_diff_skill_dirs` 之後（見
    `find_divergent_skills`）。新增項目時請附註排除理由。目前無已知刻意
    分歧，回傳空集合。

    設定位置：本檔（`.claude/hooks/skill-shadowing-check-hook.py`）。
    """
    return set()


def _is_noise_file(name: str) -> bool:
    """判斷檔名是否屬編譯期/系統雜訊檔案（目錄層雜訊由 _collect_files 剪枝）。"""
    return name in _NOISE_FILE_NAMES or name.endswith(_NOISE_FILE_SUFFIXES)


def _raise(exc: OSError) -> None:
    """os.walk 的 onerror callback：強制把目錄層級掃描錯誤轉為例外向上傳遞。

    os.walk 預設吞掉 scandir/listdir 的 OSError 並靜默跳過該子樹（Path.rglob
    亦是如此，底層共用機制）。兩側同一子樹皆不可讀時，會使 _collect_files
    回傳看似一致的部分結果，讓 _diff_skill_dirs 誤判為「內容一致」——正是
    本 hook 存在的目的要消滅的失效模式（0.2.1-W3-113 H1/N5）。
    """
    raise exc


def _collect_files(skill_dir: Path) -> Dict[str, Path]:
    """遞迴列出 skill_dir 下所有非雜訊檔案，回傳 {相對路徑(posix): 絕對路徑}。

    目錄層級的 OSError（權限不足等）經 onerror=_raise 向上傳遞，由呼叫端
    `_diff_skill_dirs` 的 except OSError 接住並計入 skipped，不再被靜默吞掉。
    """
    result: Dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(skill_dir, onerror=_raise):
        dirnames[:] = [d for d in dirnames if d not in _NOISE_DIR_NAMES]
        base = Path(dirpath)
        for filename in filenames:
            if _is_noise_file(filename):
                continue
            abs_path = base / filename
            result[abs_path.relative_to(skill_dir).as_posix()] = abs_path
    return result


def _find_entry_file(skill_dir: Path) -> Optional[Path]:
    """回傳 skill 目錄下的入口檔案（優先 SKILL.md，其次 skill.md）。

    以 iterdir() 取得實際檔名再比對，而非組路徑後 is_file()（0.2.1-W3-112
    L1）：macOS APFS 預設 case-insensitive，(dir/'SKILL.md').is_file() 對
    實際檔名為 skill.md 的檔案也會回 True，導致本函式永遠回傳大寫路徑，
    WARNING 印出的路徑與 `ls` 顯示的實際大小寫不符。專案內 error-pattern／
    continuous-learning／strategic-compact 三個 skill 實際檔名皆為 skill.md。

    skill_dir 本身不可讀時，iterdir() 的 OSError 向上傳遞（不在此吞掉），
    由呼叫端 `_list_skills` 記錄並計入 skipped（0.2.1-W3-113 N5，clove H4：
    舊版在此 except OSError 回傳 None，導致該 skill 從統計中整個消失，不進
    skipped 也不算 checked，讀者無從得知它存在過）。
    """
    actual_names = {p.name: p for p in skill_dir.iterdir() if p.is_file()}
    for filename in _ENTRY_FILENAMES:
        if filename in actual_names:
            return actual_names[filename]
    return None


def _list_skills(skills_root: Path, logger) -> Tuple[Dict[str, Path], List[str]]:
    """列出 skills_root 下每個含入口檔案的子目錄。

    直接回傳入口檔路徑（而非目錄路徑）：呼叫端需要目錄時用 `.parent`
    取得，需要入口檔時直接使用，消除重複 `_find_entry_file` 呼叫與
    Optional 特例（0.2.1-W3-107 L2）。skills_root 不存在時回傳空結果
    （personal 目錄在全新安裝可能不存在），不視為錯誤。

    Returns:
        (可比對的 {目錄名稱: 入口檔絕對路徑}, 因讀取錯誤無法列出入口檔的
        目錄名稱清單)。後者供呼叫端計入 skipped（0.2.1-W3-113 N5）。
    """
    result: Dict[str, Path] = {}
    failed: List[str] = []
    if not skills_root.is_dir():
        return result, failed
    for entry in sorted(skills_root.iterdir()):
        if not entry.is_dir():
            continue
        try:
            entry_file = _find_entry_file(entry)
        except OSError as exc:
            msg = f"[SkillShadowCheck] 讀取 skill 目錄失敗（{entry}）: {exc}"
            logger.warning(msg)
            sys.stderr.write(msg + "\n")
            failed.append(entry.name)
            continue
        if entry_file is not None:
            result[entry.name] = entry_file
    return result, failed


def _extract_version(text: str) -> str:
    """從入口檔內容抽取 `**Version**: X.Y.Z` 標記，找不到回傳 'unknown'。"""
    match = _VERSION_PATTERN.search(text)
    return match.group(1) if match else "unknown"


def _extract_version_safe(entry_file: Path, logger) -> str:
    """讀入口檔並抽取版本號；讀取失敗雙通道記錄（M1），解碼失敗不拋例外（M2）。"""
    try:
        raw = entry_file.read_bytes()
    except OSError as exc:
        msg = f"[SkillShadowCheck] 讀取版本號失敗（{entry_file}）: {exc}"
        logger.warning(msg)
        sys.stderr.write(msg + "\n")
        return "unknown"
    return _extract_version(raw.decode("utf-8", errors="replace"))


def _files_differ(project_path: Path, personal_path: Path) -> bool:
    """比對兩個檔案內容是否不同。

    0.2.1-W3-113 H3（決定：部分採用）：先比 `stat().st_size`，大小不同即
    短路回傳 True，避免讀完整個大檔案才發現大小已經不同。未採用審查建議的
    `filecmp.cmp(shallow=False)` 分塊比對與單檔大小上限（超過即記 skipped）
    ——理由：(1) 本專案 skill 目錄現況檔案皆為 KB 級文字檔（見 Solution
    du 量測），效能非現行問題；(2) 加大小上限會讓超限的大檔案退化為
    skipped、內容分歧無法偵測，等於為了尚未發生的效能問題主動引入新的
    偵測盲區，與本票（W3-107→W3-113）持續在消滅的失效模式方向相反。
    """
    if project_path.stat().st_size != personal_path.stat().st_size:
        return True
    return project_path.read_bytes() != personal_path.read_bytes()


def _diff_skill_dirs(
    project_dir: Path, personal_dir: Path, logger
) -> Optional[List[FileDiff]]:
    """遞迴比對兩個 skill 目錄（已排除雜訊檔），回傳差異清單。

    Returns:
        [] 表示完全一致；非空列表為差異清單；None 表示比對過程遇讀取錯誤，
        無法下結論（呼叫端須計入 skipped，不可視為一致，對應 M1 修正）。
    """
    try:
        project_files = _collect_files(project_dir)
        personal_files = _collect_files(personal_dir)
    except OSError as exc:
        msg = f"[SkillShadowCheck] 掃描目錄失敗（{project_dir} / {personal_dir}）: {exc}"
        logger.warning(msg)
        sys.stderr.write(msg + "\n")
        return None

    diffs: List[FileDiff] = []
    diffs.extend(
        FileDiff("+", rel, "僅 project 有")
        for rel in sorted(set(project_files) - set(personal_files))
    )
    diffs.extend(
        FileDiff("-", rel, "僅 personal 有")
        for rel in sorted(set(personal_files) - set(project_files))
    )

    for rel in sorted(set(project_files) & set(personal_files)):
        try:
            differs = _files_differ(project_files[rel], personal_files[rel])
        except OSError as exc:
            msg = f"[SkillShadowCheck] 讀取檔案失敗（{rel}）: {exc}"
            logger.warning(msg)
            sys.stderr.write(msg + "\n")
            return None
        if differs:
            diffs.append(FileDiff("~", rel, "內容不同"))

    return diffs


def _filter_excluded(
    name: str, diffs: List[FileDiff], exclude_list: Set[str]
) -> Tuple[List[FileDiff], int]:
    """依 `skill名稱/相對路徑` 粒度過濾已知刻意分歧（0.2.1-W3-113 N6）。

    Returns:
        (排除後剩餘的差異清單, 被排除的差異數)。
    """
    kept = [d for d in diffs if f"{name}/{d.rel_path}" not in exclude_list]
    return kept, len(diffs) - len(kept)


def find_divergent_skills(
    project_skills_root: Path, personal_skills_root: Path, logger
) -> ScanResult:
    """比對 project 與 personal 兩側同名 skill 的完整目錄內容。"""
    project_skills, project_failed = _list_skills(project_skills_root, logger)
    personal_skills, personal_failed = _list_skills(personal_skills_root, logger)
    shared_names = sorted(set(project_skills) & set(personal_skills))
    exclude_list = get_exclude_list()

    divergences: List[Divergence] = []
    skipped: List[str] = list(set(project_failed) | set(personal_failed))
    excluded_diff_count = 0
    diff_failed_count = 0

    for name in shared_names:
        project_entry = project_skills[name]
        personal_entry = personal_skills[name]
        diffs = _diff_skill_dirs(project_entry.parent, personal_entry.parent, logger)
        if diffs is None:
            diff_failed_count += 1
            skipped.append(name)
            continue

        diffs, excluded_here = _filter_excluded(name, diffs, exclude_list)
        excluded_diff_count += excluded_here
        if not diffs:
            continue

        divergences.append(
            Divergence(
                name,
                _extract_version_safe(project_entry, logger),
                _extract_version_safe(personal_entry, logger),
                diffs,
            )
        )

    checked_count = len(shared_names) - diff_failed_count - len(divergences)
    return ScanResult(checked_count, excluded_diff_count, sorted(set(skipped)), divergences)


def _priority_key(diff: FileDiff) -> Tuple[int, str]:
    is_priority = diff.rel_path.startswith(_PRIORITY_PATH_PREFIXES)
    return (0 if is_priority else 1, diff.rel_path)


def _format_diff_lines(diffs: List[FileDiff]) -> List[str]:
    """差異清單依優先序排序後截斷至 _MAX_DIFF_LINES_PER_SKILL 行（H2）。"""
    ordered = sorted(diffs, key=_priority_key)
    lines = [f"      {d.symbol} {d.rel_path}（{d.note}）" for d in ordered[:_MAX_DIFF_LINES_PER_SKILL]]
    remaining = len(ordered) - _MAX_DIFF_LINES_PER_SKILL
    if remaining > 0:
        lines.append(f"      ... 還有 {remaining} 個差異")
    return lines


def _divergence_text_lines(divergences: List[Divergence]) -> List[str]:
    lines = [
        f"[WARNING][SkillShadowCheck] {len(divergences)} 個同名 skill 內容分歧"
        "（personal 目錄實際載入優先於 project，project 端修改可能未生效，"
        "見 0.2.1-W3-104）:"
    ]
    for divergence in divergences:
        lines.append(
            f"  - {divergence.name}: project={divergence.project_version} / "
            f"personal={divergence.personal_version}（{len(divergence.diffs)} 個檔案差異）"
        )
        lines.extend(_format_diff_lines(divergence.diffs))
    lines.append(
        "建議: 確認分歧是否為刻意的 personal 專屬客製"
        f"（可於 {EXCLUDE_LIST_LOCATION} 的 get_exclude_list() 標記，"
        "格式為 'skill-name/相對路徑'）；若非刻意，以 project 版（權威內容）"
        "整個目錄覆寫 personal 版——存在新增/缺少檔案時，"
        "單獨複製入口檔不足以消除分歧"
    )
    return lines


def _skipped_text_lines(skipped: List[str]) -> List[str]:
    return [
        f"[WARNING][SkillShadowCheck] {len(skipped)} 個 skill 因讀取錯誤無法比對，"
        f"未計入內容一致: {', '.join(skipped)}"
    ]


def _report_divergences(divergences: List[Divergence], logger) -> str:
    """輸出 WARNING 至 stderr/logger（次要通道），回傳文字供 additionalContext 使用。"""
    lines = _divergence_text_lines(divergences)
    for line in lines:
        print(line, file=sys.stderr)
        logger.warning(line)
    return "\n".join(lines)


def _report_skipped(skipped: List[str], logger) -> str:
    """讀取錯誤導致無法下結論的 skill，獨立於 OK/WARNING 之外可見輸出（M1）。"""
    lines = _skipped_text_lines(skipped)
    for line in lines:
        print(line, file=sys.stderr)
        logger.warning(line)
    return "\n".join(lines)


def _report_ok(result: ScanResult, logger) -> None:
    """OK 狀態：僅寫日誌，不佔用 SessionStart context 預算。"""
    msg = (
        f"[SkillShadowCheck] OK: {result.checked_count} 個 project/personal 同名 skill "
        f"內容一致（無遮蔽風險），排除 {result.excluded_diff_count} 個已知分歧檔案"
    )
    logger.info(msg)


def build_hook_output(result: ScanResult, logger) -> Dict[str, Any]:
    """組裝 SessionStart hook JSON 輸出（0.2.1-W3-113 N1）。

    exit 0 時 Claude Code 只從 stdout 注入 SessionStart context，stderr 僅
    transcript/debug 可見。W3-107/W3-112 版本的 WARNING 全部走 stderr，
    main() 恆 return 0，實際上送不到 session 啟動訊息——與本 hook docstring
    自己宣告的「異常必須可見」矛盾。比照 session-start-gitignore-check-hook.py：
    OK 用 suppressOutput，有內容時用 hookSpecificOutput.additionalContext。
    """
    sections: List[str] = []
    if result.skipped:
        sections.append(_report_skipped(result.skipped, logger))
    if result.divergences:
        sections.append(_report_divergences(result.divergences, logger))

    if not sections:
        _report_ok(result, logger)
        return {"suppressOutput": True}

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(sections) + "\n",
        },
        "suppressOutput": False,
    }


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)

    project_skills_root = PROJECT_ROOT / ".claude" / "skills"
    personal_skills_root = Path.home() / ".claude" / "skills"

    if not project_skills_root.is_dir():
        # 0.2.1-W3-113 H5（決定：修正）：project 側 .claude/skills/ 不存在時
        # _list_skills 會靜默回傳空結果，最終輸出與「兩側皆無分歧」無法區分。
        # 補一行 stderr 說明，協助判斷是環境設定問題還是真的沒有 skill。
        msg = f"[SkillShadowCheck] project skills 目錄不存在: {project_skills_root}"
        logger.warning(msg)
        sys.stderr.write(msg + "\n")

    result = find_divergent_skills(project_skills_root, personal_skills_root, logger)
    output = build_hook_output(result, logger)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
