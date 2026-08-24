#!/usr/bin/env bash
# Phase 1 自動化形式掃描（dry-run-guide.md 前置條件）。
#
# 檢查標的：本 skill（compositional-writing）自身檔案內，是否存在指向
# 「本 skill 目錄以外」且未標記 portability-allow / broken-link-exempt 的
# 路徑引用（@.claude/X、.claude/X、./X、../X，副檔名 .md/.py/.sh）。
#
# 範圍刻意限定於本 skill 自身目錄（不掃其他 skill）：本檔是 compositional-
# writing 的 Phase 2 dry-run 前置條件，只需驗證「這個 skill 自己是否自
# 包含」，非通用的全庫可攜性稽核。若改成「掃全部 .claude/skills/ 下未標記
# 的絕對路徑引用」這種全庫定義，量測顯示會回報數百筆同量級誤報——那種數量
# 級的檢查在第一次執行就會被關閉，不具驗收價值；縮小到單一 skill 自身邊界
# 後，誤報趨近於零且仍能抓到真實的跨 skill 硬連結。
#
# 刻意不 import broken-link-check/scan_links.py：本檔的職責正是驗證
# compositional-writing 能否脫離框架其餘部分獨立運作，若反過來依賴另一個
# skill 的實作檔，會自我推翻要驗證的前提，故下方以獨立 inline Python 重
# 現所需的最小子集（REF_REGEX / EXEMPT_MARKER / 路徑正規化邏輯），
# 非重複造輪子而是刻意的邊界選擇。
#
# 用法：
#   portability-check.sh                     # 掃描並印分類統計
#   portability-check.sh --report <path>     # 額外輸出可重跑的分類清單檔（TSV）
#   portability-check.sh --self-test         # 以內嵌 ground truth 驗證分類邏輯
#
# exit 0 = 無違規；exit 1 = 發現違規；exit 2 = 執行環境錯誤。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

REPORT_PATH=""
SELF_TEST="0"

while [ $# -gt 0 ]; do
    case "$1" in
        --report)
            if [ $# -lt 2 ]; then
                echo "[ERROR] --report 需要一個輸出路徑參數" >&2
                exit 2
            fi
            REPORT_PATH="$2"
            shift 2
            ;;
        --report=*)
            REPORT_PATH="${1#--report=}"
            shift
            ;;
        --self-test)
            SELF_TEST="1"
            shift
            ;;
        -h|--help)
            # 用法文字寫死於此而非從檔頭註解切行：以行號取用法會在檔頭增減行時
            # 靜默取到錯誤區段，而該漂移不會使任何檢查變紅。
            cat <<'USAGE'
用法：
  portability-check.sh                     掃描並印分類統計
  portability-check.sh --report <path>     額外輸出可重跑的分類清單檔（TSV）
  portability-check.sh --self-test         以內嵌 ground truth 驗證分類邏輯

exit 0 = 無違規；exit 1 = 發現違規；exit 2 = 執行環境錯誤。
分類判準：.claude/references/skill-marketplace-standard.md §2.4
USAGE
            exit 0
            ;;
        *)
            echo "[ERROR] 未知參數: $1（可用：--report <path> / --self-test / --help）" >&2
            exit 2
            ;;
    esac
done

if [ ! -d "${SKILL_DIR}" ]; then
    echo "[ERROR] skill 目錄不存在: ${SKILL_DIR}" >&2
    exit 2
fi

python3 - "${SKILL_DIR}" "${REPORT_PATH}" "${SELF_TEST}" <<'PYEOF'
import os
import re
import sys

skill_dir = os.path.realpath(sys.argv[1])
report_path = sys.argv[2]
self_test = sys.argv[3] == "1"

# repo root：.claude/skills/<skill> 往上三層
repo_root = os.path.realpath(os.path.join(skill_dir, "..", "..", ".."))
skill_rel = os.path.relpath(skill_dir, repo_root).replace(os.sep, "/")

REF_REGEX = re.compile(
    r"(?:@\.claude/|\.claude/|\.\./|\./)[^\s)\]\"'`]*?\.(?:md|py|sh)(?:\.[A-Za-z0-9_-]+)*"
)
EXEMPT_MARKER = re.compile(r"<!--\s*broken-link-exempt\b.*?-->|portability-allow")

# --- 誤報排除規則 -----------------------------------------------------------
# 共同判準：字面本身不指向單一具體檔案，故不構成「引用」。計入這類字面會使
# 掃描器輸出含永遠無法消除的項目（全庫量測顯示約佔未標記引用的 3.7%）。
# 三個語法家族：
#   glob        通配字元（.claude/**/*.md、.claude/hooks/*.py）
#   placeholder 佔位符（.claude/error-patterns/{category}/*.md、<skill>、$VAR）
#   example     格式示範用的通用路徑（@.claude/path/file.md，見
#               broken-link-check/SKILL.md 的「偵測的路徑格式」對照表）
# 救濟手段：若某筆真實引用被誤排除，於該行加 portability-allow 標記說明。
GLOB_METACHARS = ("*", "?")
PLACEHOLDER_CHARS = re.compile(r"[{}<>$]")
EXAMPLE_SEGMENTS = frozenset(
    {"path", "to", "dir", "subdir", "example", "foo", "bar", "baz", "xxx"}
)
EXAMPLE_BASENAMES = frozenset({"file.md", "file.py", "file.sh"})

# --- 分類判準 ---------------------------------------------------------------
# 來源條文：.claude/references/skill-marketplace-standard.md §2.4「框架共用層
# 引用」的四類判定表，不留無處可歸的第四類：
#   framework-layer   .claude/{rules,pm-rules,methodologies,references,hooks,
#                     agents,error-patterns}/ —— 框架共用層，日常開發不違規
#   cross-skill       .claude/skills/<other-skill>/ —— §2.1/§4.2 禁令對象，需處置
#   project-specific  其餘（docs/work-logs/、.claude/worktrees/ 等）——
#                     §1.2/§4.1，需通用化或搬 references/project-integration/
#   landing-layer     來源檔位於 references/project-integration/ ——
#                     §2.4「與 §3 的邊界」，已依 §3 排除於上架範圍，不受分類拘束
# 判定順序：landing-layer 先於目標路徑判定（該段以來源檔位置為準，非目標）。
FRAMEWORK_LAYER_DIRS = frozenset(
    {
        "rules",
        "pm-rules",
        "methodologies",
        "references",
        "hooks",
        "agents",
        "error-patterns",
    }
)
LANDING_LAYER_MARKER = "references/project-integration/"

CLASS_LABELS = {
    "cross-skill": "跨 skill 硬連結（§2.1/§4.2，需處置）",
    "project-specific": "專案特定產物（§1.2/§4.1，需處置）",
    "framework-layer": "框架共用層引用（§2.4，日常開發不違規）",
    "landing-layer": "落地層（§2.4 與 §3 的邊界，不受分類拘束）",
}
ACTIONABLE_CLASSES = ("cross-skill", "project-specific")


def false_positive_reason(raw):
    """回傳誤報家族名稱；非誤報回傳 None。判準見上方「誤報排除規則」。"""
    if any(ch in raw for ch in GLOB_METACHARS):
        return "glob"
    if PLACEHOLDER_CHARS.search(raw):
        return "placeholder"
    segments = raw.lstrip("@").split("/")
    if segments[-1] in EXAMPLE_BASENAMES:
        return "example"
    if any(seg in EXAMPLE_SEGMENTS for seg in segments[1:-1]):
        return "example"
    return None


def to_repo_relative(raw, source_rel):
    """把引用字面正規化為 repo 相對路徑（純字串運算，不觸碰檔案系統）。"""
    if raw.startswith("@"):
        target = raw[1:]
    elif raw.startswith("./.claude/"):
        target = raw[2:]
    elif raw.startswith(".claude/"):
        target = raw
    else:
        target = os.path.join(os.path.dirname(source_rel), raw)
    return os.path.normpath(target).replace(os.sep, "/")


def classify(raw, source_rel):
    """依 §2.4 判定表歸類。source_rel 為 repo 相對的來源檔路徑。"""
    if LANDING_LAYER_MARKER in source_rel:
        return "landing-layer"
    target = to_repo_relative(raw, source_rel)
    segments = target.split("/")
    if segments[:2] == [".claude", "skills"] and len(segments) > 2:
        return "framework-layer" if target.startswith(skill_rel + "/") else "cross-skill"
    if segments[0] == ".claude" and len(segments) > 1 and segments[1] in FRAMEWORK_LAYER_DIRS:
        return "framework-layer"
    return "project-specific"


# --- self-test 用 ground truth ----------------------------------------------
# 來源：上游可攜性引用分類 ANA 落地於其 Test Results 章節的 15 筆人工分類表
# （commit 0c9bd1e5a），是目前唯一已落地、可逐筆比對的人工分類樣本。
# 該表 target 欄有四筆為敘述性簡寫（兩筆記為目錄、一筆以萬用字元縮寫檔名、
# 一筆為 .yaml），本 fixture 改記各該 source:line 上經核對的實際字面，使
# 比對對象與掃描器實際處理的字面一致。
GROUND_TRUTH = [
    (".claude/skills/decision-tree-helper/SKILL.md", 166,
     ".claude/pm-rules/task-splitting.md", "framework-layer"),
    (".claude/skills/bulk-evaluate/SKILL.md", 155,
     ".claude/skills/parallel-evaluation/SKILL.md", "cross-skill"),
    (".claude/skills/pre-fix-eval/references/pre-fix-evaluation-implementation.md", 3,
     ".claude/hooks/post-test-hook.py", "framework-layer"),
    (".claude/skills/pre-fix-eval/INDEX.md", 246,
     ".claude/methodologies/ticket-lifecycle-management-methodology.md", "framework-layer"),
    (".claude/skills/parallel-evaluation/references/integration-guide.md", 190,
     ".claude/rules/core/decision-trigger-binding.md", "framework-layer"),
    (".claude/skills/doc-flow/SKILL.md", 201,
     ".claude/references/document-system.md", "framework-layer"),
    (".claude/skills/dart-test-async-guardian/SKILL.md", 198,
     ".claude/rules/core/bash-tool-usage-rules.md", "framework-layer"),
    (".claude/skills/worktree/SKILL.md", 47,
     ".claude/worktrees/", "project-specific"),
    (".claude/skills/continuous-learning/references/upgrade-decision-tree.md", 165,
     ".claude/error-patterns/process-compliance/PC-061-memory-upgrade-blindness.md",
     "framework-layer"),
    (".claude/skills/wrap-decision/references/project-integration/pm-rules-map.md", 24,
     ".claude/config/wrap-triggers.yaml", "landing-layer"),
    (".claude/skills/ticket/SKILL.md", 371,
     ".claude/rules/core/bash-tool-usage-rules.md", "framework-layer"),
    (".claude/skills/bulk-evaluate/references/context-budget-formula.md", 159,
     ".claude/rules/core/cognitive-load.md", "framework-layer"),
    (".claude/skills/bulk-evaluate/references/context-budget-formula.md", 158,
     ".claude/pm-rules/parallel-dispatch.md", "framework-layer"),
    (".claude/skills/dart-style-guardian/SKILL.md", 8,
     ".claude/methodologies/component-library-bidirectional-constraint-methodology.md",
     "framework-layer"),
    (".claude/skills/parallel-evaluation/references/integration-guide.md", 183,
     ".claude/pm-rules/parallel-dispatch.md", "framework-layer"),
]


def run_self_test():
    mismatches = []
    for source_rel, line_no, raw, expected in GROUND_TRUTH:
        actual = classify(raw, source_rel)
        if actual != expected:
            mismatches.append((source_rel, line_no, raw, expected, actual))
    agreed = len(GROUND_TRUTH) - len(mismatches)
    rate = agreed / len(GROUND_TRUTH) * 100
    print(
        f"self-test（ground truth：上游 ANA 的 15 筆人工分類表）："
        f"{agreed}/{len(GROUND_TRUTH)} 一致（{rate:.1f}%）"
    )
    for source_rel, line_no, raw, expected, actual in mismatches:
        print(f"  MISMATCH {source_rel}:{line_no}  {raw}")
        print(f"           人工判定={expected}  機器分類={actual}")
    return 0 if not mismatches else 1


if self_test:
    sys.exit(run_self_test())


# --- 掃描本 skill -----------------------------------------------------------
classified = []  # (source_rel, line_no, raw, class)
excluded = []  # (source_rel, line_no, raw, reason)

md_files = []
for dirpath, _dirnames, filenames in os.walk(skill_dir):
    for name in filenames:
        if name.endswith(".md"):
            md_files.append(os.path.join(dirpath, name))
md_files.sort()

if not md_files:
    sys.stderr.write(f"[ERROR] 未在 {skill_dir} 找到任何 .md 檔案\n")
    sys.exit(2)

for path in md_files:
    source_rel = os.path.relpath(path, repo_root).replace(os.sep, "/")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write(f"[WARN] 無法讀取 {source_rel}: {e}\n")
        continue
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if EXEMPT_MARKER.search(line):
            continue
        for m in REF_REGEX.finditer(line):
            raw = m.group()
            target = to_repo_relative(raw, source_rel)
            if target == skill_rel or target.startswith(skill_rel + "/"):
                continue  # 落在本 skill 目錄內，非跨界引用
            reason = false_positive_reason(raw)
            if reason:
                excluded.append((source_rel, line_no, raw, reason))
                continue
            classified.append((source_rel, line_no, raw, classify(raw, source_rel)))

counts = {key: 0 for key in CLASS_LABELS}
for _source, _line, _raw, cls in classified:
    counts[cls] += 1

if report_path:
    try:
        parent = os.path.dirname(os.path.abspath(report_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write("# portability-check 分類清單\n")
            fh.write(f"# scope\t{skill_rel}\n")
            fh.write("# 分類判準\t.claude/references/skill-marketplace-standard.md §2.4\n")
            fh.write("# 欄位\tsource_file:line\ttarget_ref\tclass\n")
            for source_rel, line_no, raw, cls in sorted(classified):
                fh.write(f"{source_rel}:{line_no}\t{raw}\t{cls}\n")
            for source_rel, line_no, raw, reason in sorted(excluded):
                fh.write(f"{source_rel}:{line_no}\t{raw}\texcluded:{reason}\n")
    except OSError as e:
        sys.stderr.write(f"[ERROR] 無法寫入報告檔 {report_path}: {e}\n")
        sys.exit(2)

print(f"portability-check: 掃描 {len(md_files)} 個檔案，跨界引用（未標記）{len(classified)} 筆")
for key in ("cross-skill", "project-specific", "framework-layer", "landing-layer"):
    print(f"  {counts[key]:>4}  {CLASS_LABELS[key]}")
print(f"  {len(excluded):>4}  誤報排除（glob / placeholder / 範例路徑，非真實引用）")
if report_path:
    print(f"分類清單已寫入: {report_path}")

violations = [item for item in classified if item[3] in ACTIONABLE_CLASSES]
if violations:
    print(f"\nportability violations: {len(violations)}")
    for source_rel, line_no, raw, cls in sorted(violations):
        print(f"  {source_rel}:{line_no}  {raw}  [{cls}]")
    print(
        "\n修復方式：跨 skill 硬連結依 §2.1 轉條件語；專案特定產物依 §1.2 通用化"
        "或搬入 references/project-integration/；確屬刻意的跨界橋接則於該行加"
        " portability-allow 標記。"
    )
    sys.exit(1)

sys.exit(0)
