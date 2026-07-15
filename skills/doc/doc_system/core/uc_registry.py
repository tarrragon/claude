"""UC 編號 SSOT 解析與白名單驗證 — 供 uc list/verify/trace/context 共用。

SSOT 解析規則與豁免範圍定義於 docs/spec/uc-numbering-convention.md 第 3、5 節，
本模組是該規則的唯一實作（單一來源），PreToolUse 寫入驗證 hook 須複用本模組，
避免各自實作導致規則漂移。
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# SSOT 檔案相對路徑（本專案適配，見 uc-numbering-convention.md 第 6 節跨專案表）
USE_CASES_SPEC_RELATIVE_PATH = "docs/app-use-cases.md"

# 合法 UC 標題行格式：## UC-XX: 標題
UC_HEADING_RE = re.compile(r"^## (UC-\d{2}): (.+)$")

# 主要成功場景區塊標題與步驟行格式（供 get_uc_summary 解析主流程摘要）
MAIN_FLOW_HEADING = "### 主要成功場景"
MAIN_FLOW_STEP_RE = re.compile(r"^\d+\.\s+\*\*")

# 子場景標籤格式：「數字+字母」開頭接句點，涵蓋兩種真實 spec 結構
# （見 docs/app-use-cases.md）：
# - H2 子場景：UC-05/06 用 `## 5A. ...`/`## 6A. ...` 劃分獨立段落，
#   6A/6B 各自帶 `### 主要成功場景`，需合併並標記來源段落。
# - H4 子場景：UC-08/09 在單一 `### 主要成功場景` 內用 `#### 8A. ...`
#   劃分子場景，各自獨立編號，需標記來源子場景避免編號重複歧義。
SUBSECTION_H2_RE = re.compile(r"^##\s+(\d+[A-Za-z]+)\.")
SUB_SCENARIO_H4_RE = re.compile(r"^####\s+(\d+[A-Za-z]+)\.")

# 主流程摘要最多保留步數（截斷策略：Context Bundle 注入避免過度膨脹）
MAX_MAIN_FLOW_STEPS = 10

# 合法 UC 編號格式（兩位數零填充）
VALID_UC_FORMAT_RE = re.compile(r"^UC-\d{2}$")

# 掃描文字時抓取所有 UC- 開頭 token（含合法、格式違規與偽子樹）。
# 大小寫不敏感（IGNORECASE）以涵蓋小寫 uc-01 等變體；並額外納入
# 全形連字號（－/﹣/―）與全形字母數字，違規判定時一律先正規化為
# 半形大寫（見 normalize_token）再比對，故此處放寬擷取範圍不影響
# 判定準確性，只是擴大「能被掃到」的範圍。
UC_TOKEN_RE = re.compile(
    r"\b[UuＵｕ][CcＣｃ][-－﹣―][A-Za-z0-9０-９Ａ-Ｚａ-ｚ]+"
    r"(?:\.[A-Za-z0-9０-９Ａ-Ｚａ-ｚ]+)*"
)

# UC-Pattern 設計模式標註豁免：UC- 後接大寫字母開頭（非純數字），
# 對應規範第 5 節「UC-Pattern 設計模式標註」豁免類別
UC_PATTERN_EXEMPT_RE = re.compile(r"^UC-[A-Z][a-zA-Z]")

# 全形轉半形字元對照（連字號與數字/字母），供 normalize_token 使用
_FULLWIDTH_HYPHENS = "－﹣―"
_FULLWIDTH_OFFSET = 0xFF00 - 0x20  # 全形字元碼點與對應半形字元的固定偏移量


def normalize_token(token: str) -> str:
    """將 token 正規化為半形大寫形式，供違規判定使用（規則來源：本模組職責）。

    處理範圍：大小寫統一為大寫；全形連字號/字母/數字轉半形。
    正規化後的形式才是違規判定與訊息輸出的依據，避免變體各自判斷造成漂移。
    """
    chars = []
    for ch in token:
        if ch in _FULLWIDTH_HYPHENS:
            chars.append("-")
        elif 0xFF01 <= ord(ch) <= 0xFF5E:
            chars.append(chr(ord(ch) - _FULLWIDTH_OFFSET))
        else:
            chars.append(ch)
    return "".join(chars).upper()


# 豁免路徑：以此開頭的相對路徑不受「必須存在於 SSOT」約束（規範第 5 節）
EXEMPT_PATH_PREFIXES = (
    "docs/work-logs/",
    "test/fixtures/",
    "tests/fixtures/",
    "docs/spec/",
)

# 豁免路徑：精確相符（SSOT 自身）
EXEMPT_PATH_EXACT = (USE_CASES_SPEC_RELATIVE_PATH,)

# 掃描副檔名（單點定義，避免 CLI 與 hook 各自維護清單漂移，防止各自擴充副檔名時遺漏另一端）。
# 比對時一律先 .lower() 再 endswith，故此處維持小寫即可涵蓋大小寫變體。
#
# 兩份清單差異理由：
# - CLI_SCANNABLE_EXTENSIONS（doc uc verify/trace 全量掃描）涵蓋文件與設定檔
#   （.md/.yaml/.yml），因為 CLI 是離線批次稽核工具，目標是找出專案中所有
#   UC 引用（含規格文件、設定檔內的說明性引用），範圍越完整越能發現漂移。
# - HOOK_SCANNABLE_EXTENSIONS（PreToolUse 即時攔截）僅涵蓋程式碼檔，
#   因為 hook 目的是攔截「新寫入的程式碼」誤用未定義 UC 編號；文件類檔案
#   的編輯多屬規格本身或說明性文字，不適合即時 WARNING（避免編輯 spec/
#   worklog 時被誤擾），且路徑豁免已涵蓋 docs/spec、docs/work-logs 等情境。
CLI_SCANNABLE_EXTENSIONS = (".dart", ".py", ".md", ".yaml", ".yml", ".ts", ".js")
HOOK_SCANNABLE_EXTENSIONS = (".dart", ".js", ".ts", ".py")


def get_ssot_path(project_root: str) -> Path:
    """回傳本專案 SSOT 檔案的絕對路徑。"""
    return Path(project_root) / USE_CASES_SPEC_RELATIVE_PATH


def parse_ssot(project_root: str) -> dict[str, dict]:
    """解析 SSOT，回傳 {UC-XX: {"title": str, "line": int}}。

    line 為標題行在 SSOT 檔案中的 1-based 行號，供 uc context 定位使用。
    SSOT 檔案不存在時回傳空字典。
    """
    ssot_path = get_ssot_path(project_root)
    result: dict[str, dict] = {}
    if not ssot_path.is_file():
        return result

    with open(ssot_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            match = UC_HEADING_RE.match(line.rstrip("\n"))
            if match:
                result[match.group(1)] = {
                    "title": match.group(2).strip(),
                    "line": lineno,
                }
    return result


def get_valid_uc_map(project_root: str) -> dict[str, str]:
    """回傳 {UC-XX: 標題} 合法集合（parse_ssot 的簡化投影）。"""
    return {uc_id: info["title"] for uc_id, info in parse_ssot(project_root).items()}


def _extract_main_flow_steps(lines: list[str], heading_lineno: int) -> tuple[list[str], bool]:
    """從 UC 標題行後擷取「主要成功場景」步驟清單。

    只在該 UC 區塊內（下一個合法 `## UC-XX: ...` 標題前）搜尋 MAIN_FLOW_HEADING。
    支援三種真實 spec 結構（見 docs/app-use-cases.md）：

    - 標準單段（UC-01~04/07/10）：單一 `### 主要成功場景`，遇下一個
      `### ` 子標題即結束，取第一段步驟。
    - 多段主流程（UC-06）：`## 6A.`/`## 6B.` 等 H2 子場景各自帶獨立
      `### 主要成功場景`，合併所有段落步驟，每步加 `[6A]`/`[6B]` 前綴。
    - H4 子場景（UC-08/09）：單一 `### 主要成功場景` 內用 `#### 8A.`
      等劃分子場景，每步加 `[8A]` 等前綴，消除跨子場景編號重複歧義。
    - 無主流程（UC-05）：整個 UC 區塊都找不到 MAIN_FLOW_HEADING，
      fallback 收集區塊內所有 `### ` 章節標題作為摘要。

    每步僅保留 `N. **步驟名稱**` 格式的標題行本身（不含後續詳述子項），
    至多 MAX_MAIN_FLOW_STEPS 步（fallback 章節標題摘要同樣受此上限約束）。

    回傳 (steps_or_titles, is_section_summary)：is_section_summary 為 True
    時表示走 fallback（無主流程），內容是章節標題而非步驟。
    """
    in_main_flow = False
    found_main_flow = False
    steps: list[str] = []
    section_titles: list[str] = []
    active_label: str | None = None

    for line in lines[heading_lineno:]:
        # 僅在遇到下一個合法 UC 標題（`## UC-XX: ...`）時視為區塊結束；
        # 專案內部分 UC 用 `## 6A. ...` 等次級標題劃分子場景，非新 UC，不可誤判。
        if UC_HEADING_RE.match(line):
            break
        stripped = line.strip()

        h2_sub = SUBSECTION_H2_RE.match(stripped)
        if h2_sub:
            active_label = h2_sub.group(1)
            in_main_flow = False
            continue

        h4_sub = SUB_SCENARIO_H4_RE.match(stripped)
        if h4_sub:
            active_label = h4_sub.group(1)
            continue

        if stripped.startswith("### "):
            if stripped == MAIN_FLOW_HEADING:
                in_main_flow = True
                found_main_flow = True
            else:
                # 已收集過主流程步驟時，下一個非主流程 H3 標題視為區塊
                # 結束；尚未收集到步驟時（fallback 模式）繼續掃描，把
                # 標題本身記入摘要。
                if found_main_flow and steps:
                    break
                in_main_flow = False
                if not found_main_flow:
                    section_titles.append(stripped[len("### ") :])
                    if len(section_titles) >= MAX_MAIN_FLOW_STEPS:
                        break
            continue

        if in_main_flow and MAIN_FLOW_STEP_RE.match(stripped):
            steps.append(f"[{active_label}] {stripped}" if active_label else stripped)
            if len(steps) >= MAX_MAIN_FLOW_STEPS:
                break

    if steps:
        return steps, False
    return section_titles, bool(section_titles)


def get_uc_summary(uc_id: str, project_root: str) -> dict | None:
    """回傳 UC 摘要：標題、spec 位置、主流程步驟，供 Context Bundle 自動注入使用。

    uc_id 不存在於 SSOT 時回傳 None；main_flow 找不到「主要成功場景」區塊
    時 fallback 回傳章節標題摘要（非所有 UC 都採此標準結構，如 UC-05 用
    其他標題），此時 is_section_summary 為 True。真正無任何內容可摘要
    時（區塊為空）main_flow 才回傳空 list，is_section_summary 為 False。
    """
    ssot = parse_ssot(project_root)
    if uc_id not in ssot:
        return None

    info = ssot[uc_id]
    ssot_path = get_ssot_path(project_root)
    try:
        with open(ssot_path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []

    main_flow, is_section_summary = _extract_main_flow_steps(lines, info["line"])

    return {
        "uc_id": uc_id,
        "title": info["title"],
        "spec_path": USE_CASES_SPEC_RELATIVE_PATH,
        "spec_line": info["line"],
        "main_flow": main_flow,
        "is_section_summary": is_section_summary,
    }


def is_exempt_path(file_path: str, project_root: str) -> bool:
    """判定路徑是否屬規範第 5 節五類豁免中的「路徑類」豁免（不含 UC-Pattern token 類）。

    雙錨點比對：優先用相對 project_root 的路徑前綴（一般情況，錨點 1）；
    當檔案不在 project_root 之下（如 worktree 派發時 CLAUDE_PROJECT_DIR
    指向主 repo、但實際編輯的檔案位於同構的 worktree 路徑），relpath 會產生
    `../` 前綴使錨點 1 恆假，改以絕對路徑的路徑片段比對（錨點 2）——
    worktree 鏡射主 repo 目錄結構，子路徑片段相同，僅根目錄不同。
    """
    abs_path = Path(file_path).resolve()
    abs_str = str(abs_path).replace(os.sep, "/")

    try:
        rel = os.path.relpath(str(abs_path), project_root)
    except ValueError:
        rel = str(abs_path)
    rel = rel.replace(os.sep, "/")

    if not rel.startswith(".."):
        if rel in EXEMPT_PATH_EXACT:
            return True
        if any(rel.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return True
        return False

    # 錨點 2（僅當檔案不在 project_root 之下時啟用）：以路徑片段比對，
    # 避免巧合子字串誤判（要求前後皆為路徑邊界）。
    if any(abs_str.endswith("/" + exact) for exact in EXEMPT_PATH_EXACT):
        return True
    return any((f"/{prefix}") in abs_str for prefix in EXEMPT_PATH_PREFIXES)


def is_pattern_exempt_token(token: str) -> bool:
    """判定 token 是否為 UC-Pattern 設計模式標註豁免（規範第 5 節）。"""
    return bool(UC_PATTERN_EXEMPT_RE.match(token))


def find_uc_tokens_in_text(text: str) -> list[tuple[str, int]]:
    """回傳文字中所有 UC- 開頭 token（原始大小寫/全形形態）及其所在行號（1-based）。

    回傳原始擷取形態（供訊息顯示定位），違規判定與白名單比對一律經
    normalize_token() 轉換為正規形式後再進行，見 is_violation_token。
    """
    hits: list[tuple[str, int]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in UC_TOKEN_RE.finditer(line):
            hits.append((match.group(0), lineno))
    return hits


def is_violation_token(token: str, valid: dict[str, str]) -> bool:
    """判定 token 是否為違規（非法自創、格式錯誤或偽子樹），已排除豁免情況。

    判定一律以 normalize_token() 正規化後的形式為準（大小寫/全形變體
    視為同一 token），確保 `uc-99`、`ＵＣ－99`、`UC-99` 判定一致。
    """
    if is_pattern_exempt_token(token):
        return False
    normalized = normalize_token(token)
    if VALID_UC_FORMAT_RE.match(normalized):
        return normalized not in valid
    # 格式不符（三位數、偽子樹如 UC-01.4.20 等）一律視為違規
    return True


def self_test(project_root: str) -> tuple[bool, str]:
    """驗證 SSOT 解析結果非空且全數符合合法格式，供啟動時或 CI 快速校驗。

    不比對精確數量（避免每次新增/移除 UC 用例都須同步改常數，製造
    spec 同步負擔）；改驗證「至少一筆」且「每筆皆符合 UC-\\d{2} 格式」，
    格式異常（如 SSOT 標題行解析出非預期鍵值）才判定失敗。
    """
    valid = get_valid_uc_map(project_root)
    if not valid:
        return False, f"SSOT 解析結果為空（{USE_CASES_SPEC_RELATIVE_PATH} 缺失或無合法標題行）"

    malformed = sorted(uc_id for uc_id in valid if not VALID_UC_FORMAT_RE.match(uc_id))
    if malformed:
        return False, f"SSOT 解析出格式不符的 UC 鍵值：{malformed}"

    return True, f"self-test 通過：{len(valid)} 個合法 UC（{sorted(valid.keys())}）"


FINGERPRINT_SIDECAR_FILENAME = ".uc-fingerprints.json"


def parse_ssot_with_content(project_root: str) -> dict[str, dict]:
    """解析 SSOT，回傳 {UC-XX: {"title": str, "line": int, "content": str}}。

    content 為該 UC 區塊的原始文字（從標題行到下一個 UC 標題行前，或 EOF）。
    用於 fingerprint 計算——任何文字變更都會改變 hash，達成漂移偵測。
    """
    ssot_path = get_ssot_path(project_root)
    if not ssot_path.is_file():
        return {}

    with open(ssot_path, encoding="utf-8") as f:
        all_lines = f.readlines()

    headings: list[tuple[int, str, str]] = []
    for idx, line in enumerate(all_lines):
        match = UC_HEADING_RE.match(line.rstrip("\n"))
        if match:
            headings.append((idx, match.group(1), match.group(2).strip()))

    result: dict[str, dict] = {}
    for i, (line_idx, uc_id, title) in enumerate(headings):
        end_idx = headings[i + 1][0] if i + 1 < len(headings) else len(all_lines)
        content = "".join(all_lines[line_idx:end_idx])
        result[uc_id] = {
            "title": title,
            "line": line_idx + 1,
            "content": content,
        }

    return result


def compute_fingerprint(content: str) -> str:
    """計算內容的 SHA256 指紋。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_fingerprint_sidecar_path(project_root: str) -> Path:
    """回傳指紋 sidecar JSON 的絕對路徑。"""
    return Path(project_root) / FINGERPRINT_SIDECAR_FILENAME


def update_fingerprints(project_root: str) -> dict[str, dict]:
    """計算所有 UC 指紋並寫入 sidecar JSON，回傳寫入的指紋資料。"""
    uc_data = parse_ssot_with_content(project_root)
    fingerprints: dict[str, dict] = {}
    now = datetime.now(timezone.utc).isoformat()
    for uc_id, info in sorted(uc_data.items()):
        fingerprints[uc_id] = {
            "fingerprint": compute_fingerprint(info["content"]),
            "title": info["title"],
            "updated_at": now,
        }

    sidecar_path = get_fingerprint_sidecar_path(project_root)
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(fingerprints, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return fingerprints


def check_fingerprints(project_root: str) -> tuple[list[str], list[str], list[str]]:
    """比對 sidecar 指紋與當前內容，回傳 (drifted, added, removed)。

    drifted: 內容已變更的 UC ID
    added: SSOT 中有但 sidecar 中沒有的 UC ID
    removed: sidecar 中有但 SSOT 中已消失的 UC ID
    三者皆為空表示無漂移。sidecar 不存在時三者皆為空（非錯誤，尚未初始化）。
    """
    sidecar_path = get_fingerprint_sidecar_path(project_root)
    if not sidecar_path.is_file():
        return [], [], []

    with open(sidecar_path, encoding="utf-8") as f:
        saved = json.load(f)

    uc_data = parse_ssot_with_content(project_root)

    current_ids = set(uc_data.keys())
    saved_ids = set(saved.keys())

    drifted = sorted(
        uc_id
        for uc_id in current_ids & saved_ids
        if compute_fingerprint(uc_data[uc_id]["content"]) != saved[uc_id]["fingerprint"]
    )
    added = sorted(current_ids - saved_ids)
    removed = sorted(saved_ids - current_ids)

    return drifted, added, removed


if __name__ == "__main__":
    import sys

    from doc_system.core.file_locator import FileLocator

    ok, message = self_test(FileLocator.get_project_root())
    print(message)
    sys.exit(0 if ok else 1)
