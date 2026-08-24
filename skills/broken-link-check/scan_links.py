#!/usr/bin/env python3
"""確定性 broken-link CLI scanner（取代 LLM 手動 SKILL 作為跨框架完成 gate）。

掃描 `<root>/.claude/**/*.md` 中的路徑引用，resolve 後判定 broken/placeholder/
excluded_*，輸出確定性計數 + 分類清單。純標準庫實作（pathlib/re/argparse/json/sys），
唯一例外是動態載入的 `extract_merge_declarations`（見下方說明，容錯降級不引入
硬依賴，載入失敗不中斷主掃描）。

掃描根預設僅 `.claude/`（向後相容，不帶參數時逐字不變）；CLI `--scan-root`
可疊加額外子樹（如 `docs`），使規劃文件（ticket body、spec、usecases、
proposals）一併納入偵測。

引用抽取射程涵蓋 `.md` / `.py` / `.sh` 三種副檔名。`.py` 與 `.sh` 引用曾完全
不在 REF_REGEX 射程內，是 hook 刪除或合併後殘留引用能長期累積而無人察覺的
機制性原因——射程擴充後，這類殘留在下次掃描即會被計入 broken。

確定性三保證點（GWT #3）：
1. md_files 掃描前先 sort
2. broken_entries 依 (source_file, line) sort
3. categories 為固定 key dict（插入序固定）
"""

import argparse
import functools
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

# 預設掃描根：僅 `.claude/`。CLI `--scan-root` 可額外追加子樹（如 docs），
# 追加為疊加（既有預設不變），不取代。
DEFAULT_SCAN_ROOTS = (".claude",)

# 預設旋鈕：五排除全開啟（皆排除），可由 CLI flag 顯式覆寫納入
DEFAULT_KNOBS = {
    "include_code_block": False,
    "include_migration_backups": False,
    "include_placeholder": False,
    "include_documented": False,
    "include_archive": False,
    "include_shell_dest": False,
}

# 4 種引用前綴 x 3 種副檔名（md/py/sh）；http(s):// 與 #anchor 不在清單中故天然排除
#
# 非貪婪 `*?` 在第一個已知副檔名處即停止，遇多重副檔名檔名（如
# `worklog.md.template`）會截斷為 `worklog.md`（不存在），把有效引用誤判
# broken。尾綴 `(?:\.[A-Za-z0-9_-]+)*` 允許已知副檔名後再延伸比對真實存在
# 的後綴段；句尾標點（`.md.` 接空白/行尾）因後段無 word 字元不成立而不被
# 吞入，既有 `:*` glob 尾綴防護不受影響（冒號非 `.`，不觸發延伸）。
REF_REGEX = re.compile(
    r"(?:@\.claude/|\.claude/|\.\./|\./)[^\s)\]\"'`]*?\.(?:md|py|sh)(?:\.[A-Za-z0-9_-]+)*"
)

# W8-049：per-line 豁免 marker。error-pattern 案例表刻意記錄的不存在路徑
# （confabulation 錯誤參照 / 歷史遷移檔案軌跡）以行內 marker 顯式 opt-in 豁免，
# 歸 excluded_documented 不計 broken。marker 僅影響所在行（PC-146 放置精確性）。
# 兩個標記語彙同屬「已判定豁免」家族，差別在判定理由：broken-link-exempt 說
# 「這個路徑不存在是預期的」（示範路徑、歷史引文），portability-allow 說「這個
# 消費端專屬引用是刻意保留的」（架構性橋接、約定安裝位置）。後者蘊含前者——
# 消費端專屬引用在沒有該資產的專案就是不存在，所以同一條豁免通道處理兩者，
# 標記寫在哪一行就只豁免那一行。portability-allow 亦出現在非 HTML 註解形式
# （程式碼區塊內的 shell 註解），故不限定 <!-- --> 包裹。
#
# 2026-08-22 補充防重演書寫規則：豁免作用單位是「行」，違規單位是「引用」。
# 加 marker 前，若該行同時含現存有效 ref（含只出現在 marker 註解文字內部的
# 有效路徑），禁止直接在同一行加 marker；應先將待豁免的死引用移到獨立行/位置
# （表格列因無法插入換行，改為移除列內死引用字面、表格外新增附註段落），使
# marker 只覆蓋死引用所在行。若死引用本身不帶 `.claude/` / `./` / `../` /
# `@.claude/` 前綴（不會命中 REF_REGEX），不需要加 marker。
EXEMPT_MARKER = re.compile(r"<!--\s*broken-link-exempt\b.*?-->|portability-allow")

# fence 內 cp/mv 指令目的地參數的相對路徑：resolve_path() 對 `./X`（非
# `./.claude/X`）一律以來源檔目錄為基準，但這類指令的相對路徑基準是執行時
# cwd（通常為 repo root），靜態文字無法確定 cwd（不同於 `.claude/X`／
# `@.claude/X`／`../X` 三種前綴皆有明確、不依賴 cwd 的解析規則）。與其猜測
# cwd（會產生另一種誤判來源）或放行所有 fence 內相對路徑（會遮蔽真實
# drift——同一 fence 慣例內混有大量非 cp/mv 的 markdown 相對連結），窄化為
# 僅 cp/mv 指令行的單點相對路徑目的地才視為信心不足，見 classify_ref 的
# excluded_shell_dest 分類。
_SHELL_DEST_COMMAND = re.compile(r"^\s*(?:cp|mv)\s")

# 固定 placeholder 樣式集（SKILL 表格自身範例路徑，非真實引用）
PLACEHOLDER_SAMPLES = {
    "path/file.md",
    ".claude/path/file.md",
    "./path/file.md",
    "../path/file.md",
    "@.claude/path/file.md",
}

# W2-011 triage A 類：範例 skill 名 token（skill-marketplace-standard.md 等文件
# 用具體詞彙示範「skill 引用另一 skill」的慣例寫法，非真實存在的 skill）。
# 以路徑段精確比對（非子字串），避免誤排真實同名 skill。
_EXAMPLE_SKILL_NAME_TOKENS = {"skill-name", "case-first", "sibling-skill"}
_EXAMPLE_SKILL_NAME_SEGMENT = re.compile(
    r"(?:^|/)(?:" + "|".join(re.escape(t) for t in _EXAMPLE_SKILL_NAME_TOKENS) + r")(?:/|$)"
)

# 樣式型 placeholder 偵測（W8-047 缺陷 2）：文件中的示意路徑非真實引用。
# - glob 萬用字元 * 或 ?（如 .claude/agents/*.md、.claude/rules/**/*.md）
# - 角括號佔位 <name> / <檔名>（如 .claude/agents/<agent>.md）
# - 大括號模板 {language} / {name}（如 quality-{language}.md）
_GLOB_PLACEHOLDER = re.compile(r"[*?]")
_ANGLE_PLACEHOLDER = re.compile(r"<[^>]*>")
_BRACE_PLACEHOLDER = re.compile(r"\{[^}]*\}")
# token sentinel：路徑段為 xxx（不分大小寫，含 test_xxx.py 這種以底線接續的
# 樣式，如除錯指南中「test_xxx.py」示範測試檔名）或 UPPERCASE TEST 系列哨兵
# （TEST / TEST_AGENT / TEST_EXEMPT...）。小寫 test 嵌在真實描述名中
# （如 test-helper-design-methodology.md）不視為 placeholder，避免誤排真實斷鏈。
# 副檔名比對含 .py/.sh：射程擴充後同一類示意樣式同樣出現在這兩種副檔名
# （如 .claude/hooks/xxx-hook.py、./.claude/scripts/xxx.py）。
_XXX_TOKEN = re.compile(r"(?:^|/|_)xxx(?:\.md|\.py|\.sh|/|$)", re.IGNORECASE)
_TEST_TOKEN = re.compile(r"(?:^|/)TEST(?:_[A-Z0-9]+)*(?:\.md|/|$)")
# W2-011 triage A 類：版本佔位 vX（如 vX-main.md），區別於真實版本目錄
# （v0.13.0-... 等以數字開頭），故要求 vX 後緊接非數字字元或行尾。
_VX_PLACEHOLDER = re.compile(r"(?:^|/)vX(?:[^0-9][^/]*)?\.md$")
# W2-011 triage A 類：省略號縮寫（如 PC-050-...md、`.claude/hooks/...py`），
# 檔名以字面三個點直接接副檔名（無點分隔），與 ../ 相對路徑前綴（點+點+斜線）
# 不同構。副檔名比對含 .py/.sh：射程擴充後同一縮寫慣例同樣出現在這兩種副檔名
# （如 error-pattern 案例中示範 backtick 路徑被截斷顯示為 `.claude/hooks/...py`）。
_ELLIPSIS_PLACEHOLDER = re.compile(r"\.\.\.(?:md|py|sh)$")

# .py/.sh 射程擴充後的已知佔位符 hook 檔名 exact-match 集：文件示例中用來示範
# 「hook 檔名長什麼樣子」的虛構名稱（如「假設有個 foo.py」），非真實引用。
# 逐一列名而非以檔名長度代理判定——長度代理曾同時誤殺短真名與誤放長佔位符
# （如 my-hook.py 被排除而 my-new-hook.py 被納入，兩者屬同一佔位符家族）。
# 限定 hook(s)/ 路徑段之後，避免與其他目錄下同名真實檔案（若未來出現）誤判。
#
# 2026-08：hook(s)/ 與檔名間允許任意層子目錄（如 archived/），涵蓋
# 「hooks/archived/script-name.py」這類歸檔範例引用（git mv 範本佔位符）。放寬
# 前僅原地匹配（hooks/ 後緊接檔名），此類巢狀路徑仍判 broken。放寬安全性已
# 實測驗證：`.claude/hooks/` 全樹（含 archived/ 等所有子目錄）遞迴列出的真實
# 檔名與本清單無交集，故任意子目錄層級皆不會誤判真實檔案為佔位符。
_PLACEHOLDER_HOOK_BASENAMES = frozenset({
    "foo.py", "a.py", "x.py", "qux.py", "guard.py", "hook-name.py",
    "example-guard-hook.py", "sample-guard-hook.py", "some-new-guard-hook.py",
    "specific-hook.py", "other-hook.py", "keep.py", "foo-hook.py", "xxx-hook.py",
    "my-hook.py", "my-new-hook.py", "file.py", "file1.py", "file2.py",
    "script-name.py", "my-hook.sh", "__health_check__.py",
})
_PLACEHOLDER_HOOK_SEGMENT = re.compile(
    r"/hooks?/(?:[^/]+/)*(?:"
    + "|".join(re.escape(n) for n in sorted(_PLACEHOLDER_HOOK_BASENAMES))
    + r")$"
)


def is_placeholder_pattern(raw):
    """判定引用字串是否為樣式型 placeholder（文件示意路徑，非真實引用）。

    涵蓋 glob 萬用字元、角括號佔位、大括號模板、xxx/TEST 哨兵 token、
    範例 skill 名 token、版本佔位 vX、省略號縮寫檔名、已知佔位符 hook 檔名。
    與固定 PLACEHOLDER_SAMPLES exact-match 互補。
    """
    if _GLOB_PLACEHOLDER.search(raw):
        return True
    if _ANGLE_PLACEHOLDER.search(raw):
        return True
    if _BRACE_PLACEHOLDER.search(raw):
        return True
    if _XXX_TOKEN.search(raw):
        return True
    if _TEST_TOKEN.search(raw):
        return True
    if _EXAMPLE_SKILL_NAME_SEGMENT.search(raw):
        return True
    if _VX_PLACEHOLDER.search(raw):
        return True
    if _ELLIPSIS_PLACEHOLDER.search(raw):
        return True
    if _PLACEHOLDER_HOOK_SEGMENT.search(raw):
        return True
    return False


# W2-011 triage D 類：歷史封存文件排除策略。以「來源檔案」整檔判定，
# 與既有 migration-backups/ source_in_backup 排除機制對稱（W8-047 缺陷 1）。
# 涵蓋：hook-specs 驗收報告、其在 skills/pre-fix-eval/references/ 的複本、
# *_SUMMARY.md / *_CHECKLIST.md 命名慣例、CHANGELOG.md（含 .sync-conflicts/
# 內複本）、skills/pre-fix-eval/INDEX.md（已封存 skill 的索引頁）。
_ARCHIVE_BASENAME_SUFFIX = re.compile(r"_(?:SUMMARY|CHECKLIST)\.md$")
_ARCHIVE_REPORT_BASENAMES = {
    "pre-fix-evaluation-acceptance-report.md",
    "pre-fix-evaluation-implementation.md",
}


def is_archive_source(source_posix):
    """判定來源檔案（POSIX 相對路徑字串）是否為歷史封存文件。

    歷史封存文件的引用即使目標不存在，逐筆修復也無讀者價值（已刪除的
    歷史產物只被驗收報告/整合摘要/CHANGELOG 等歷史記錄引用）。
    """
    basename = source_posix.rsplit("/", 1)[-1]
    if basename == "CHANGELOG.md":
        return True
    if "/.sync-conflicts/" in source_posix:
        return True
    if basename in _ARCHIVE_REPORT_BASENAMES:
        return True
    if _ARCHIVE_BASENAME_SUFFIX.search(basename):
        return True
    if source_posix.endswith("skills/pre-fix-eval/INDEX.md"):
        return True
    return False


def extract_refs(text):
    """從單檔內容抽 4 種前綴 x 3 種副檔名（md/py/sh）的引用，標記 code-block 狀態 + 行號。

    fence 開合以逐行翻轉狀態機追蹤；奇數 fence（未閉合）自然延伸到 EOF。
    """
    refs = []
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        line_exempt = bool(EXEMPT_MARKER.search(line))
        line_is_shell_dest_cmd = in_fence and bool(_SHELL_DEST_COMMAND.match(line))
        for match in REF_REGEX.finditer(line):
            raw = match.group()
            shell_ambiguous_cwd = (
                line_is_shell_dest_cmd
                and raw.startswith("./")
                and not raw.startswith("./.claude/")
            )
            refs.append(
                {
                    "raw_ref": raw,
                    "line": line_no,
                    "in_code_block": in_fence,
                    "exempt": line_exempt,
                    "shell_ambiguous_cwd": shell_ambiguous_cwd,
                }
            )
    return refs


def _hook_completeness_check_path():
    """定位 hook-completeness-check.py 原始檔（scan_links.py 自身所在 repo 的
    .claude/hooks/，與被掃描的 root 參數無關）。

    scan_links.py 固定位於 `<repo>/.claude/skills/broken-link-check/`；往上
    兩層即 `<repo>/.claude/`，其下 `hooks/` 是 extract_merge_declarations 的
    權威來源。掃描目標（可能是合成測試樹）由呼叫端另外傳入 hooks_dir 決定，
    與此函式定位的「載入哪個原始檔」無關。
    """
    return Path(__file__).resolve().parents[2] / "hooks" / "hook-completeness-check.py"


@functools.lru_cache(maxsize=1)
def load_extract_merge_declarations():
    """動態載入 hook-completeness-check.py 的 extract_merge_declarations。

    連字號檔名無法用一般 import 陳述式，改以 importlib.util 動態載入。合併型
    遷移的接手者解析必須接此既有索引，不另寫重複實作。

    容錯（fail-open）：載入失敗（檔案不存在 / 缺依賴）時 stderr 記錄警告並
    回傳 None，呼叫端須將所有 broken 項的 merge_successor 視為未知（None），
    不因此中斷主掃描——合併接手者標註是輔助資訊，不是 broken 判定的前提；
    掃描器仍須把無法判定接手者的引用計入 broken，而非因輔助資訊缺失而放行。
    """
    hook_path = _hook_completeness_check_path()
    if not hook_path.is_file():
        sys.stderr.write(f"[WARN] hook-completeness-check.py not found at {hook_path}\n")
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            "hook_completeness_check_for_scan_links", hook_path
        )
        module = importlib.util.module_from_spec(spec)
        hooks_dir_str = str(hook_path.parent)
        if hooks_dir_str not in sys.path:
            sys.path.insert(0, hooks_dir_str)
        spec.loader.exec_module(module)
        return module.extract_merge_declarations
    except Exception as e:
        # 動態載入來源（pyyaml、lib/ 共用模組）多樣，容錯優先於精確例外類型
        sys.stderr.write(f"[WARN] cannot load extract_merge_declarations: {e}\n")
        return None


def _build_merge_successor_index(hooks_dir):
    """建立 {被合併檔名: 合併版檔名} 反查索引，供 broken 項標註接手者用。

    hooks_dir 不存在或載入失敗時回傳空字典（fail-open，見
    load_extract_merge_declarations 容錯說明）。hooks_dir 不存在時提前回傳，
    避免對每個沒有 .claude/hooks/ 的掃描根都嘗試動態載入（多數合成測試樹與
    docs-only 掃描根皆屬此類）。
    """
    if not hooks_dir.is_dir():
        return {}
    extract_fn = load_extract_merge_declarations()
    if extract_fn is None:
        return {}
    declarations = extract_fn(hooks_dir)
    return {
        merged_name: successor
        for successor, merged_names in declarations.items()
        for merged_name in merged_names
    }


def resolve_path(raw, source_file, root):
    """引用字串轉實際路徑字串。

    - @.claude/X 與 .claude/X：相對 repo root
    - ./.claude/X：相對 repo root（殼層呼叫慣例的特例，見下方說明）
    - 其餘 ./X 與 ../X：相對 source_file 所在目錄（os.path.normpath 純字串消解 ..）

    `./.claude/X` 獨立於一般 `./X` 規則：射程擴至 `.py`/`.sh` 後，大量引用是
    「以 repo root 為 cwd 示範指令」的殼層呼叫慣例（如
    `python3 ./.claude/scripts/x.py`），其中 `./` 語意是「執行當下目錄」，
    與純文件互相引用時 `./` 相對本文件目錄的慣例不同構。若不特判，非 repo
    root 目錄下的文件寫這種形態會被誤解析成 `<本文件目錄>/.claude/...`
    的雙層 `.claude/` 巢狀路徑，恆不存在，成為固定假陽性來源。
    """
    root = Path(root)
    source_file = Path(source_file)
    if raw.startswith("@"):
        return os.path.normpath(str(root / raw[1:]))
    if raw.startswith(".claude/"):
        return os.path.normpath(str(root / raw))
    if raw.startswith("./.claude/"):
        return os.path.normpath(str(root / raw[2:]))
    return os.path.normpath(str(source_file.parent / raw))


def classify_ref(raw, resolved, knobs, exists, exempt=False, shell_ambiguous_cwd=False):
    """判定引用分類：placeholder / excluded_backup / excluded_shell_dest /
    excluded_documented / broken / ok。

    判定順序即優先級（短路）：
    placeholder → backup → exists → shell_dest → documented → broken。
    documented 豁免僅作用於「不存在」的引用（exempt marker 行）；存在者仍歸 ok，
    不誤計 excluded_documented（marker 只取消「真實 broken」的計列，不遮蔽存在事實）。
    shell_dest 同理僅作用於「不存在」的引用（resolved 是以來源檔目錄為基準算出，
    對 cp/mv 目的地參數而言基準本身即不確定，故存在與否都不具判定力，僅在
    「以此基準判為不存在」時才降級，避免掩蓋恰好雙重成立的真實引用）。
    """
    if not knobs["include_placeholder"]:
        if raw in PLACEHOLDER_SAMPLES or is_placeholder_pattern(raw):
            return "placeholder"
    if "migration-backups/" in resolved or "hook-logs/" in resolved:
        if not knobs["include_migration_backups"]:
            return "excluded_backup"
        # 旋鈕開啟 → 落到下方 exists/broken 判定
    if exists:
        return "ok"
    if shell_ambiguous_cwd and not knobs.get("include_shell_dest"):
        return "excluded_shell_dest"
    if exempt and not knobs.get("include_documented"):
        return "excluded_documented"
    return "broken"


def _rel_to_root(path, root):
    """轉相對 root 的字串路徑（確定性，不依賴 cwd）。"""
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def scan(root, knobs=None, scan_roots=None):
    """編排 I/O：掃描指定子樹的 md → 抽引用 → resolve → 分類 → 彙總。

    scan_roots：相對 root 的子樹清單，預設 `DEFAULT_SCAN_ROOTS`（僅
    `.claude`，向後相容）。呼叫端可傳入額外子樹（如 `[".claude", "docs"]`）
    擴大掃描範圍；各子樹的檔案聯集後統一排序，確定性不受傳入順序影響。
    """
    knobs = knobs or DEFAULT_KNOBS
    scan_roots = scan_roots if scan_roots is not None else DEFAULT_SCAN_ROOTS
    root = Path(root)
    merge_successor_by_name = _build_merge_successor_index(root / ".claude" / "hooks")
    md_files = set()
    for subtree in scan_roots:
        md_files.update(root.glob(f"{subtree}/**/*.md"))
    md_files = sorted(f for f in md_files if "hook-logs/" not in str(f))
    categories = {
        "broken": 0,
        "placeholder": 0,
        "excluded_code_block": 0,
        "excluded_backup": 0,
        "excluded_documented": 0,
        "excluded_archive": 0,
        "excluded_shell_dest": 0,
    }
    broken_entries = []
    total_refs = 0
    scanned = 0
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            # Q5 雙通道：stderr 可見 + continue，禁靜默吞回傳假計數
            sys.stderr.write(f"[WARN] cannot read {f}: {e}\n")
            continue
        scanned += 1
        # W8-047 缺陷 1：來源端排除——source 檔本身在 migration-backups/ 時，
        # 其內部引用屬備份內容（非當前活躍框架債），預設整檔歸 excluded_backup。
        # 與 classify_ref 的 target 端 backup 排除對稱（旋鈕開啟才計入）。
        source_in_backup = (
            "migration-backups/" in str(f).replace(os.sep, "/")
            and not knobs["include_migration_backups"]
        )
        # W2-011 triage D 類：來源端排除——source 檔本身為歷史封存文件時，
        # 整檔引用歸 excluded_archive（旋鈕開啟才計入，與 backup 排除同構）。
        source_in_archive = is_archive_source(
            _rel_to_root(f, root).replace(os.sep, "/")
        ) and not knobs["include_archive"]
        for ref in extract_refs(text):
            total_refs += 1
            if ref["in_code_block"] and not knobs["include_code_block"]:
                categories["excluded_code_block"] += 1
                continue
            if source_in_backup:
                categories["excluded_backup"] += 1
                continue
            if source_in_archive:
                categories["excluded_archive"] += 1
                continue
            resolved = resolve_path(ref["raw_ref"], f, root)
            exists = Path(resolved).exists()
            cat = classify_ref(
                ref["raw_ref"], resolved, knobs,
                exists=exists, exempt=ref.get("exempt", False),
                shell_ambiguous_cwd=ref.get("shell_ambiguous_cwd", False),
            )
            if cat in categories:
                categories[cat] += 1
            if cat == "broken":
                basename = ref["raw_ref"].rsplit("/", 1)[-1]
                broken_entries.append(
                    {
                        "source_file": _rel_to_root(f, root),
                        "line": ref["line"],
                        "raw_ref": ref["raw_ref"],
                        "resolved_path": _rel_to_root(resolved, root),
                        "category": "broken",
                        "subcategory": None,
                        # 合併型遷移的接手者檔名（來自 extract_merge_declarations
                        # 反查索引）；無法判定（含載入失敗）一律 None，不影響
                        # broken 判定本身（fail-open，見 _build_merge_successor_index）
                        "merge_successor": merge_successor_by_name.get(basename),
                    }
                )
    broken_entries.sort(key=lambda e: (e["source_file"], e["line"]))
    return {
        "baseline": categories["broken"],
        "scanned_files": scanned,
        "total_refs": total_refs,
        "broken_count": len(broken_entries),
        "categories": categories,
        "broken": broken_entries,
    }


def _print_text_view(result):
    """人類可讀視圖（確定性：固定欄位序，禁無序 set/dict 迭代）。"""
    cats = result["categories"]
    print(
        f"broken: {result['broken_count']}  "
        f"refs: {result['total_refs']}  files: {result['scanned_files']}"
    )
    print(
        "categories: "
        f"broken={cats['broken']} placeholder={cats['placeholder']} "
        f"excluded_code_block={cats['excluded_code_block']} "
        f"excluded_backup={cats['excluded_backup']} "
        f"excluded_documented={cats['excluded_documented']} "
        f"excluded_shell_dest={cats['excluded_shell_dest']} "
        f"excluded_archive={cats['excluded_archive']}"
    )
    print("--- broken list (sorted source:line) ---")
    for e in result["broken"]:
        successor = e.get("merge_successor")
        suffix = f"  [merge_successor={successor}]" if successor else ""
        print(
            f"{e['source_file']}:{e['line']}  "
            f"{e['raw_ref']} -> {e['resolved_path']}{suffix}"
        )


# ---------------------------------------------------------------------------
# opt-in fence 稽核模式
#
# include_code_block 預設維持 False 是刻意判定：fence 內 broken 中大量為
# 歷史實作報告與教學/語法示範，翻預設會使多數變成誤報，淹沒真實 drift。
# 但維持預設不代表放棄偵測——本節開一條稽核通道讓 fence 內失效引用能被人
# 定期複查，防止 drift 在無人偵測的射程外累積。
#
# 設計約束（quality-baseline 規則 5）：不嘗試自動判定「語法示範」vs「操作
# 指引」——兩者差別是語氣（「例如」「格式如下」vs「執行以下步驟」），機器判
# 不了。全量逐筆分類的實測結果與抽樣外推值有數倍落差（詳見
# docs/work-logs/v0/v0.2/v0.2.1/fence-ref-triage.md），印證語意分類不可靠。
# 本模式只輸出機器可靠取得的原始資料與分組訊號（來源檔載體性質、行內豁免
# marker 有無、merge_successor 有無），語意分類判斷留給人。
# ---------------------------------------------------------------------------

# 載體性質訊號：依 source_file 路徑段判定，逐一列出已知路徑段而非規則推導。
# 只收錄性質單一、可機器確認的目錄慣例（commands/ 恆為可執行指令、
# error-patterns/ 恆為案例敘事、hook-specs/ 恆為歷史報告）；其餘目錄
# （skills/、pm-rules/、references/ 等）同時混有語法示範與操作指引，不構成
# 可靠訊號，強行分類反而誤導判讀者，一律回傳「未分類」。
_CARRIER_NATURE_BY_PATH_SEGMENT = (
    (".claude/commands/", "可執行指令載體"),
    (".claude/error-patterns/", "案例敘事載體"),
    (".claude/hook-specs/", "歷史報告載體"),
)
_CARRIER_NATURE_UNCLASSIFIED = "未分類"
_CARRIER_NATURE_LABELS = tuple(
    label for _, label in _CARRIER_NATURE_BY_PATH_SEGMENT
) + (_CARRIER_NATURE_UNCLASSIFIED,)


def carrier_nature(source_posix):
    """依路徑段判定 source_file 的載體性質（機器可靠訊號，非語意分類）。

    命中已知路徑段回傳對應標籤；未命中回傳「未分類」，不強行歸類——理由見
    模組上方 `_CARRIER_NATURE_BY_PATH_SEGMENT` 說明。
    """
    for segment, label in _CARRIER_NATURE_BY_PATH_SEGMENT:
        if segment in source_posix:
            return label
    return _CARRIER_NATURE_UNCLASSIFIED


def fence_audit(root, scan_roots=None):
    """opt-in fence 稽核：輸出 fence 內失效引用的可判讀分組清單，非 gate。

    掃描與判定沿用既有 extract_refs / resolve_path / classify_ref，僅將
    include_code_block 固定為 True 以取得 fence 內判定，其餘四旋鈕維持
    DEFAULT_KNOBS；不呼叫 scan()、不共用其 broken_entries schema，故不影響
    既有 --format json 輸出欄位（scan() 本身逐字不變）。

    輸出範圍涵蓋兩類 fence 內失效引用：
    - category == "broken"：無豁免 marker，主要待判讀對象
    - category == "excluded_documented"：已有豁免 marker，納入稽核供人
      複核 marker 是否仍合法（來源內容可能在標記後又變動）

    每筆額外標注三項機器可靠訊號（語意分類仍留給人，見模組上方設計約束）：
    carrier_nature（來源檔載體性質）、has_marker（該行是否已有豁免 marker）、
    merge_successor（合併型遷移的接手者，沿用既有反查索引）。彙總層另提供
    by_carrier_nature 與 marker_counts 兩組機器可靠的分組統計，取代語意
    三分類統計（歷史報告 / 語法示範 / 真實 drift 機器判不了，見上方約束）。
    """
    scan_roots = scan_roots if scan_roots is not None else DEFAULT_SCAN_ROOTS
    root = Path(root)
    audit_knobs = dict(DEFAULT_KNOBS)
    audit_knobs["include_code_block"] = True
    merge_successor_by_name = _build_merge_successor_index(root / ".claude" / "hooks")
    md_files = set()
    for subtree in scan_roots:
        md_files.update(root.glob(f"{subtree}/**/*.md"))
    md_files = sorted(f for f in md_files if "hook-logs/" not in str(f))
    entries = []
    scanned = 0
    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"[WARN] cannot read {f}: {e}\n")
            continue
        scanned += 1
        source_posix = _rel_to_root(f, root).replace(os.sep, "/")
        # 與 scan() 對稱：來源在 backup/archive 的整檔不列入稽核（沿用既有
        # 排除慣例，backup/archive 內容非當前活躍框架債）。
        if "migration-backups/" in str(f).replace(os.sep, "/"):
            continue
        if is_archive_source(source_posix):
            continue
        for ref in extract_refs(text):
            if not ref["in_code_block"]:
                continue
            resolved = resolve_path(ref["raw_ref"], f, root)
            exists = Path(resolved).exists()
            cat = classify_ref(
                ref["raw_ref"], resolved, audit_knobs,
                exists=exists, exempt=ref.get("exempt", False),
                shell_ambiguous_cwd=ref.get("shell_ambiguous_cwd", False),
            )
            if cat not in ("broken", "excluded_documented"):
                continue
            basename = ref["raw_ref"].rsplit("/", 1)[-1]
            entries.append(
                {
                    "source_file": source_posix,
                    "line": ref["line"],
                    "raw_ref": ref["raw_ref"],
                    "resolved_path": _rel_to_root(resolved, root),
                    "category": cat,
                    "carrier_nature": carrier_nature(source_posix),
                    "has_marker": bool(ref.get("exempt", False)),
                    "merge_successor": merge_successor_by_name.get(basename),
                }
            )
    entries.sort(key=lambda e: (e["source_file"], e["line"]))
    by_carrier_nature = {label: 0 for label in _CARRIER_NATURE_LABELS}
    marker_counts = {"marked": 0, "unmarked": 0}
    for e in entries:
        by_carrier_nature[e["carrier_nature"]] += 1
        marker_counts["marked" if e["has_marker"] else "unmarked"] += 1
    return {
        "scanned_files": scanned,
        "fence_entries_count": len(entries),
        "by_carrier_nature": by_carrier_nature,
        "marker_counts": marker_counts,
        "entries": entries,
    }


def _print_fence_audit_text_view(result):
    """稽核模式人類可讀視圖：依 source_file 分組，逐筆列出判讀訊號。"""
    print(
        f"fence audit（非 gate，僅供判讀）: {result['fence_entries_count']} entries  "
        f"files: {result['scanned_files']}"
    )
    print(
        "by_carrier_nature: "
        + " ".join(
            f"{label}={count}" for label, count in result["by_carrier_nature"].items()
        )
    )
    mc = result["marker_counts"]
    print(f"marker_counts: marked={mc['marked']} unmarked={mc['unmarked']}")
    print("--- entries (grouped by source_file) ---")
    last_source = None
    for e in result["entries"]:
        if e["source_file"] != last_source:
            print(f"[{e['carrier_nature']}] {e['source_file']}")
            last_source = e["source_file"]
        successor = e.get("merge_successor")
        successor_tag = f"  [merge_successor={successor}]" if successor else ""
        marker_tag = "marked" if e["has_marker"] else "unmarked"
        print(
            f"  :{e['line']}  {e['raw_ref']} -> {e['resolved_path']}  "
            f"[{e['category']}/{marker_tag}]{successor_tag}"
        )


def main(argv=None):
    """CLI 入口：解析參數 → scan → 格式化輸出 → exit code。

    exit code：0=零 broken（gate pass）/ 1=broken>0（gate fail）/ 2=執行錯誤。
    --fence-audit 為獨立稽核模式，不參與此 exit code 語意（恆 0，見該分支）。
    """
    parser = argparse.ArgumentParser(
        description="確定性 broken-link scanner for .claude/ markdown"
    )
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument(
        "--scan-root",
        action="append",
        dest="extra_scan_roots",
        default=None,
        metavar="SUBTREE",
        help=(
            "額外掃描子樹（相對 repo_root，可重複指定），疊加於預設 "
            "'.claude'（不取代）。例：--scan-root docs"
        ),
    )
    parser.add_argument("--include-code-block", action="store_true")
    parser.add_argument("--include-migration-backups", action="store_true")
    parser.add_argument("--include-placeholder", action="store_true")
    parser.add_argument("--include-documented", action="store_true")
    parser.add_argument("--include-archive", action="store_true")
    parser.add_argument("--include-shell-dest", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--fence-audit",
        action="store_true",
        help=(
            "opt-in 稽核模式：輸出 fence（程式碼區塊）內失效引用的可判讀分組"
            "清單（載體性質 / 是否已有豁免 marker / merge_successor），不做"
            "語法示範與操作指引的自動分類，不納入 gate（恆 exit 0）。"
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.repo_root)
    if not root.is_dir() or not (root / ".claude").is_dir():
        # GWT #7：致命錯誤 stderr 可見 + exit 2，不輸出假計數
        sys.stderr.write(f"[ERROR] repo root or .claude/ not found: {root}\n")
        return 2

    scan_roots = list(DEFAULT_SCAN_ROOTS)
    if args.extra_scan_roots:
        scan_roots.extend(args.extra_scan_roots)

    if args.fence_audit:
        # 稽核模式獨立分支：不建立 knobs、不呼叫 scan()，與既有 gate 路徑
        # 完全不共用執行路徑（票 acceptance：不納入任何阻擋 gate）。
        try:
            audit_result = fence_audit(root, scan_roots=scan_roots)
        except OSError as e:
            sys.stderr.write(f"[ERROR] fence audit failed: {e}\n")
            return 2
        if args.format == "json":
            print(json.dumps(audit_result, ensure_ascii=False, indent=2, sort_keys=False))
        else:
            _print_fence_audit_text_view(audit_result)
        # 稽核模式非 gate：恆 exit 0，不改變既有命令的 exit code 語意
        return 0

    knobs = {
        "include_code_block": args.include_code_block,
        "include_migration_backups": args.include_migration_backups,
        "include_placeholder": args.include_placeholder,
        "include_documented": args.include_documented,
        "include_archive": args.include_archive,
        "include_shell_dest": args.include_shell_dest,
    }

    try:
        result = scan(root, knobs, scan_roots=scan_roots)
    except OSError as e:
        sys.stderr.write(f"[ERROR] scan failed: {e}\n")
        return 2

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
    else:
        _print_text_view(result)
    return 1 if result["broken_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
