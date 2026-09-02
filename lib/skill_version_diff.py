"""Skill 版本摘要與漂移報告 — sync-claude-push.py / sync-claude-pull.py 共用（0.2.1-W3-356）。

沿革：extract_skill_versions 與 format_skill_version_diff 原在 push、pull 兩腳本
各自定義一份逐字重複的實作（W2-001 建立時各自複製）。report_skill_repo_drift 原
只存在於 push（0.2.1-W3-351 建立、0.2.1-W3-353 改為呼叫 skill-sync 的 public
`sync_status_report`），pull 端從未對稱呼叫——但 pull 才是本地 skills 被遠端覆寫
的時刻，漂移在 pull 之後產生的機率高於 push 之後。本模組將三者提升至 .claude/lib/
供兩端 import，消除重複並讓 pull 收尾也能輸出同格式的漂移報告（ARCH-BAL-016：
避免恢復對稱呼叫時又各自重寫一份）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from lib.skill_case_guard import warn_skill_md_case_mismatch
from lib.sync_exclude_manifest import load_sync_skills_config

# 分歧清單的顯示上限。超出者以「另有 N 個」帶過，完整清單由 skill-sync 取得。
SKILL_DRIFT_PREVIEW_LIMIT = 10

# 全格式一致的 **Version**: X 行（CHANGELOG.md 頂端條目與舊格式 SKILL.md
# body 皆用此字面）。
_VERSION_LINE_RE = re.compile(r"\*\*Version\*\*:\s*(\S+)")
# SKILL.md frontmatter 內巢狀於 `metadata:` 區塊的 `version:` 欄位（新格式）。
_METADATA_BLOCK_RE = re.compile(r"^metadata:[ \t]*\n((?:[ \t]+\S.*\n?)*)", re.MULTILINE)
_METADATA_VERSION_RE = re.compile(r"^[ \t]+version:\s*(\S+)", re.MULTILINE)
# SKILL.md frontmatter 頂層（非巢狀於 metadata: 之下）的 `version:` 欄位——
# 部分第三方 skill 的 frontmatter schema 與本專案慣例不同，仍以此欄位表示
# 版本（如 `impeccable` skill）。
_TOPLEVEL_VERSION_RE = re.compile(r"^version:\s*(\S+)", re.MULTILINE)


def _extract_changelog_version(skill_dir: Path) -> str | None:
    """讀取同目錄 CHANGELOG.md 最上方（新到舊排序，見各檔頂部說明）的
    **Version** 條目——本輪版本紀錄外移後，此為多數 skill 的權威版本來源。
    """
    changelog = skill_dir / "CHANGELOG.md"
    if not changelog.is_file():
        return None
    try:
        text = changelog.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = _VERSION_LINE_RE.search(text)
    return m.group(1) if m else None


def _extract_frontmatter_metadata_version(text: str) -> str | None:
    """從 SKILL.md YAML frontmatter 巢狀的 `metadata.version` 欄位擷取版本號。

    不引入 YAML 解析依賴（本模組其餘部分皆為輕量 regex 掃描，維持一致），
    改以區塊邊界定位——先框出 `metadata:` 區塊（延續其後每一行縮排內容），
    再於區塊內尋找 `version:` 欄位，避免誤認 frontmatter 中其他非 metadata
    區塊裡巧合出現的 `version:` 字樣。
    """
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    front = text[3:end]
    block_match = _METADATA_BLOCK_RE.search(front)
    if not block_match:
        return None
    ver_match = _METADATA_VERSION_RE.search(block_match.group(1))
    return ver_match.group(1) if ver_match else None


def extract_skill_versions(skills_dir: Path) -> dict[str, str]:
    """掃描 skills/*/ 提取各 skill 的版本號。

    `glob("*/SKILL.md")` 判準對大小寫是否敏感依 Python 版本而異（3.13 起
    在省略 `case_sensitive` 時改為探測實際檔案系統），故本函式在掃描前先以
    版本無關的 `os.scandir` 判準告警大小寫不符項——即使該版本的 glob 折疊
    命中，仍讓維護者知道檔名不精確、日後換掃描實作可能再度漏收。

    四層優先序（版本紀錄外移後，單一來源已無法涵蓋全部 skill；優先序依
    「權威性 + 涵蓋率」排列，見遷移紀錄的實測數據）：
      1. 同目錄 CHANGELOG.md 最上方 **Version** 條目（新格式，多數已遷移
         的 skill 的權威來源；部分 skill 未在 frontmatter 重複記錄版本，
         此為唯一來源）
      2. SKILL.md frontmatter 巢狀的 `metadata.version`（新格式，兩個住址
         之一，未必所有已遷移 skill 皆有此欄位）
      3. SKILL.md body 內的 **Version**: 行（舊格式，向後相容尚未遷移者）
      4. SKILL.md frontmatter 頂層 `version:` 欄位（既有 fallback，涵蓋
         frontmatter schema 與本專案慣例不同的第三方 skill）

    參數:
        skills_dir: skills 目錄路徑（如 .claude/skills/ 或 temp_dir/skills/）

    傳回:
        dict[str, str]: {skill 名稱: 版本號}，無版本號者不列入
    """
    versions: dict[str, str] = {}
    if not skills_dir.is_dir():
        return versions
    for warning in warn_skill_md_case_mismatch(skills_dir):
        print(f"[skill-version-diff] {warning}", file=sys.stderr)  # i18n-exempt
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_name = skill_md.parent.name
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        version = _extract_changelog_version(skill_md.parent)
        if not version:
            version = _extract_frontmatter_metadata_version(text)
        if not version:
            m = _VERSION_LINE_RE.search(text)
            version = m.group(1) if m else None
        if not version:
            m = _TOPLEVEL_VERSION_RE.search(text)
            version = m.group(1) if m else None

        if version:
            versions[skill_name] = version
    return versions


def format_skill_version_diff(
    before: dict[str, str], after: dict[str, str]
) -> str | None:
    """比對前後 skill 版本，產生摘要文字。無變更時回傳 None。

    參數:
        before: 同步前的 {skill: version}
        after: 同步後的 {skill: version}

    傳回:
        str | None: 摘要文字（含換行），無變更時 None
    """
    all_names = sorted(set(before) | set(after))
    new_skills: list[str] = []
    updated_skills: list[str] = []
    removed_skills: list[str] = []
    for name in all_names:
        old_ver = before.get(name)
        new_ver = after.get(name)
        if old_ver is None and new_ver is not None:
            new_skills.append(f"{name} ({new_ver})")
        elif old_ver is not None and new_ver is None:
            removed_skills.append(f"{name} (was {old_ver})")
        elif old_ver != new_ver:
            updated_skills.append(f"{name} {old_ver} -> {new_ver}")
    if not new_skills and not updated_skills and not removed_skills:
        return None
    lines = ["[Skill 變更摘要]"]  # i18n-exempt
    if new_skills:
        lines.append(f"  新增: {', '.join(new_skills)}")  # i18n-exempt
    if updated_skills:
        lines.append(f"  更新: {', '.join(updated_skills)}")  # i18n-exempt
    if removed_skills:
        lines.append(f"  移除: {', '.join(removed_skills)}")  # i18n-exempt
    return "\n".join(lines)


def report_skill_repo_drift(claude_dir: Path) -> str:
    """比對本地 skill 與 skill 庫的內容雜湊，回傳給使用者閱讀的報告。

    整段流程（repo 解析、取遠端 manifest、分類）交給 skill-sync 的
    `sync_status_report`，本函式只負責呈現。0.2.1-W3-134 移除的舊實作與
    0.2.1-W3-351 的第一版恢復都只重用了中段分類器、自行重寫取檔與來源設定，
    後者因此硬編了 repo URL 而繞過 `SKILL_SYNC_REPO` 覆寫，與 skill-sync 本體
    比對不同的遠端（ARCH-BAL-016）。

    排除政策（`excluded_skills`）由本函式從 `sync-skills.yaml` 的 `private` 清單
    讀取並注入：skill-sync 是零框架依賴套件，對「private」這個概念零知識，只接收
    呼叫端提供的一份現成清單。此清單原本只在推送過濾生效（overlay 複製與
    `--clean` 傳播），本檢查段從未套用，導致 private skill 每次都被誤列為「遠端
    無記錄，需人工確認後 push」——排除政策只在寫入路徑生效，報告路徑對其無知。

    永不拋出：本函式在 push/pull 成功之後執行，檢查失敗只代表少了一份資訊，
    不該讓已完成的同步看起來像失敗。故 try 涵蓋到最後一次消費外部資料為止，
    而非只包住取檔——僅包取檔會讓分類與解包的例外從保護外逃逸（IMP-BAL-008）。

    參數:
        claude_dir: .claude 目錄路徑（push 側為本地 project_root/.claude，
        pull 側同為本地 project_root/.claude；兩端讀的都是同步後的本地狀態）

    傳回:
        str: 給使用者閱讀的報告文字（永不含例外堆疊，降級為單行說明）
    """
    try:
        from skill_sync.cli import sync_status_report

        private_skills = load_sync_skills_config(claude_dir)["private"]
        status = sync_status_report(
            claude_dir / "skills", excluded_skills=private_skills
        )
        remote_line = f"[skill 庫檢查] 比對遠端：{status.repo_url}"  # i18n-exempt

        if not status.local_count:
            return f"{remote_line}\n本地無已安裝 skill，略過"  # i18n-exempt
        if not status.remote_count:
            # 遠端可達但 manifest 為空時，全部項目會落入「無遠端雜湊」，讀起來
            # 像檢查通過；明說沒有比對對象，避免空結果被當成一致。
            return f"{remote_line}\n遠端 versions.json 無任何項目，未進行比對"  # i18n-exempt

        counts = (  # i18n-exempt
            f"一致 {len(status.up_to_date)}、分歧 {len(status.diverged)}、"  # i18n-exempt
            f"本地客製 {len(status.overridden)}、"  # i18n-exempt
            f"排除（private）{len(status.excluded_by_policy)}、"  # i18n-exempt
            f"遠端有記錄無雜湊 {len(status.skipped_no_hash)}、"  # i18n-exempt
            f"遠端無記錄 {len(status.skipped_remote_missing)}"  # i18n-exempt
        )
        lines = [remote_line, f"[skill 庫檢查] {counts}"]  # i18n-exempt
        # 專案特化 skill 設計上就不該有遠端記錄，不是待處理的缺口，故不附
        # push 指引——與下方 skipped_remote_missing 的「需確認後 push」語氣相反。
        if status.excluded_by_policy:
            lines.append(  # i18n-exempt
                "   專案特化，設計上不推送（sync-skills.yaml private）："  # i18n-exempt
                f"{', '.join(status.excluded_by_policy)}"
            )
        # 兩種盲區成因不同（前者等下次 push 自動補；後者需人工確認遠端該不該
        # 有這個 skill），單一計數無法分辨該做什麼，故列出成因與名單。
        if status.skipped_no_hash:
            lines.append(  # i18n-exempt
                "   遠端有記錄無雜湊（舊格式 manifest，下次 push 會自動補）："  # i18n-exempt
                f"{', '.join(status.skipped_no_hash)}"
            )
        if status.skipped_remote_missing:
            lines.append(  # i18n-exempt
                "   遠端無記錄（從未被 push 記錄過，需確認遠端是否該有此 skill 後 push 或標註不推送理由）："  # i18n-exempt
                f"{', '.join(status.skipped_remote_missing)}"
            )
        # 逐項列出但設上限，與 sync 腳本 uncleaned_deletions 的呈現慣例一致：
        # 分歧數可達數十筆，全列會把收尾訊息淹沒，反而讓人學會略過整段。
        for entry in status.diverged[:SKILL_DRIFT_PREVIEW_LIMIT]:
            # 版本號相同而內容不同是最常見的分歧形態；不註明成因，讀者會把它
            # 當誤報而略過整段。
            suffix = "（版本相同，內容不同）" if entry.local == entry.remote else ""  # i18n-exempt
            lines.append(  # i18n-exempt
                f"   - {entry.name}: 本地 {entry.local} / 遠端 {entry.remote}{suffix}"  # i18n-exempt
            )
        hidden = len(status.diverged) - SKILL_DRIFT_PREVIEW_LIMIT
        if hidden > 0:
            lines.append(f"   ...（另有 {hidden} 個）")  # i18n-exempt
        if status.diverged:
            first = status.diverged[0]
            lines.append(  # i18n-exempt
                "   方向需人工判斷（內容雜湊只證明不同，不證明誰較新），逐一處理："  # i18n-exempt
                f"{first.pull_command} 或 {first.push_command}"  # i18n-exempt
            )
            lines.append(  # i18n-exempt
                "   此為 skill 發佈庫，與 sync-push 目標 repo 不同；"  # i18n-exempt
                "上方[Skill 變更摘要]是 push 前後本地快照差異，本段是本地與此發佈庫的雜湊比對，兩者指涉對象不同"  # i18n-exempt
            )
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001 - 降級為警告，見 docstring
        # 帶上例外型別：契約破損（ImportError / AttributeError）與網路不可達
        # 若呈現為同一行文字，讀者無從判斷該重試還是該修安裝。
        return f"[skill 庫檢查] 略過：{type(e).__name__}: {e}"  # i18n-exempt
