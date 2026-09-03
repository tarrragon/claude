#!/usr/bin/env python3
"""framework-issue section：comment-as-section 協作協定的寫入路徑。

背景：`tarrragon/claude#81` 當前結論區段（comment 5523472948）裁定的協作模型
——協作內容的載體是 comment 不是 body；body 只保留問題陳述與「區段索引」表。
每個區段是一則具 owner 的 comment，以 comment id 精準編輯；觀測 comment 任何
session 可隨時附加，不需 owner、不需協商。

三個命令對應三種寫入時機：

- `init`：**只執行一次**。先逐一 POST 全部區段 comment 取得 id 與永久連結，
  再 GET 現有 body、插入區段索引表、PATCH 一次。之後 body 不再由本工具改寫
  （id 在 comment 建立後才存在，索引無法在建立時就寫入——見 #82 驗證）。
- `update`：以 comment id PATCH 指定區段，只讀寫該則 comment，不觸碰 body
  或同 issue 其他 comment。更新前讀回既有內容確認首行為區段標記，非區段
  comment（如觀測、一般留言）一律拒絕，避免誤改。
- `observe`：附加一則觀測 comment，不需 owner、不改 body、不影響既有 comment。

區段與觀測以 comment 首行 HTML 註解標記區分（GitHub 渲染時不可見）：

    <!-- section: <名稱> owner: <session> -->
    <!-- observation: <摘要> by <session> -->

兩種標記字首不同（`section:` / `observation:`），區段抽取正則只比對
`section:` 開頭，觀測 comment 不會被誤判為區段（#81 acceptance 條款）。

讀取路徑 `show`／`check` 已併入本檔；查重已併入 `init`（`--dedup-keywords`
必填），並額外提供獨立唯讀子命令 `dedup` 供不建立 issue 的核對用途。gh
呼叫皆走 `subprocess.run` 直呼叫（非 `gh_common.run_gh`，因需解析 JSON
回應），供測試以替身攔截，不真打 GitHub API。

查重採「逐 token 查詢後聯集」而非單一多詞 AND 查詢：實測 `gh search issues`
對多詞查詢的 AND 語意要求詞彙落在同一欄位實例內（同一則 comment 或同一
body），詞彙分屬同一 issue 的不同 comment 時會漏判（見 tests 內
`test_search_duplicates_unions_tokens_to_cover_cross_comment_terms` 重現與
`.claude/skills/framework-issue/tests/test_section_comment.py` 同名測試的
docstring）。拆為單詞查詢後在本工具端聯集，可涵蓋此缺口。

`show` 以 body 的區段索引表為入口（`parse_index_table`），依索引列出的
comment id 分「區段」與「觀測流」兩類；索引缺失時退回全 comment 掃描首行
標記（`classify_comments`），並在輸出標示「索引缺失」。`check` 輸出三項
早期警訊（規格見 tarrragon/claude#81「增長語意與早期警訊」）：主警訊為
「當前結論」區段 `updated_at` 落後最新觀測 comment 超過設定期間；輔助為
單張 issue comment 數超過閾值；第三項為 body 索引與實際區段 comment 集合
的一致性比對。三項皆唯讀、不阻擋（exit 0），閾值與期間可由 CLI 參數覆蓋。
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from gh_common import (
    FRAMEWORK_REPO,
    emit_degraded,
    normalize_issue_ref,
    preflight,
    run_gh,
)
from section_table import upsert_section

# 區段 comment 首行標記：抓 "section:" 與 "owner:" 之間、"owner:" 之後至
# " -->" 為止的內容。非貪婪比對，不限制字元集合（owner 常含連字號，如
# "flutter-balance-99"，字元類排除法會在第一個連字號處誤斷）。
SECTION_MARKER_RE = re.compile(r"^<!-- section: (?P<name>.+?) owner: (?P<owner>.+?) -->")

# 觀測 comment 首行標記：字首為 "observation:"，與區段標記的 "section:" 不同，
# 故 SECTION_MARKER_RE 對觀測 comment 必然不命中（不需額外排除邏輯）。
OBSERVATION_MARKER_RE = re.compile(
    r"^<!-- observation: (?P<summary>.+?) by (?P<session>.+?) -->"
)

# body 區段索引表的標記區段（init 回填、之後不再改寫）。
INDEX_BEGIN = "<!-- section-index -->"
INDEX_END = "<!-- /section-index -->"
INDEX_SECTION_RE = re.compile(
    re.escape(INDEX_BEGIN) + r".*?" + re.escape(INDEX_END), re.DOTALL
)
INDEX_TABLE_HEADER = "## 區段索引\n\n| 區段 | 永久連結 |\n|------|---------|"

# 區段索引表列的解析：只要求該行以 "|" 起始且含 "issuecomment-<id>" 字樣，
# 不綁定固定欄數——已觀測到 2 欄（純連結）與 3 欄（markdown 連結 + 說明）
# 兩種真實形態，表頭與分隔列因無 issuecomment- 字樣自然被排除，不需另行
# 判斷欄數。
INDEX_ROW_ID_RE = re.compile(r"issuecomment-(?P<id>\d+)")
INDEX_ROW_URL_RE = re.compile(r"https://\S*?issuecomment-\d+")

# 「當前結論」區段名稱字串集中於此常數，check／show 皆引用，不散落。
CURRENT_CONCLUSION_SECTION_NAME = "當前結論"

# check 的兩項閾值：規格（tarrragon/claude#81「增長語意與早期警訊」）定性
# 描述「輔助訊號」與「某期間」，未給出精確數字。以下為可運作的初始預設
# 值，兩者皆可由 CLI 參數覆蓋，非規格權威值。
DEFAULT_COMMENT_THRESHOLD = 30
DEFAULT_STALE_DAYS = 7


def render_section_comment(name: str, owner: str, content: str) -> str:
    """把區段內容包上首行標記，供 POST/PATCH 使用。"""
    return f"<!-- section: {name} owner: {owner} -->\n{content}"


def render_observation_comment(summary: str, session: str, content: str) -> str:
    """把觀測內容包上首行標記，供 POST 使用。"""
    return f"<!-- observation: {summary} by {session} -->\n{content}"


def extract_section_marker(comment_body: str):
    """從 comment 首行取出區段標記；非區段 comment（含觀測）回傳 None。"""
    match = SECTION_MARKER_RE.match(comment_body or "")
    if not match:
        return None
    return {"name": match.group("name"), "owner": match.group("owner")}


def parse_index_table(body: str) -> list:
    """從 body 掃描區段索引表列，取出 [{"name":, "id":, "url":}, ...]（依原文順序）。

    不要求 `INDEX_BEGIN`／`INDEX_END` 標記存在——已觀測到手寫索引表無此標記
    仍可讀（見 `INDEX_ROW_ID_RE` 註解），故以「表格列含 issuecomment-<id>」
    作為判準，較貼近實際資料形態。
    """
    rows = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        id_match = INDEX_ROW_ID_RE.search(stripped)
        if id_match is None:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        url_match = INDEX_ROW_URL_RE.search(stripped)
        rows.append(
            {
                "name": cells[0],
                "id": int(id_match.group("id")),
                "url": url_match.group(0) if url_match else "",
            }
        )
    return rows


def classify_comments(comments: list) -> tuple:
    """依首行標記把 comments 分為（區段 dict、觀測流 list）。

    區段 dict 以 comment id 為 key，值含 name 與原始 comment；未命中區段
    標記者（含帶 observation 標記與完全無標記者）一律歸入觀測流。
    """
    sections = {}
    stream = []
    for comment in comments:
        marker = extract_section_marker(comment.get("body", ""))
        if marker is None:
            stream.append(comment)
        else:
            sections[comment.get("id")] = {"name": marker["name"], "comment": comment}
    return sections, stream


def render_index(posted_sections: list) -> str:
    """把已建立區段的 {name, html_url} 清單渲染為可 upsert 的索引區段。"""
    lines = [INDEX_BEGIN, INDEX_TABLE_HEADER]
    for section in posted_sections:
        lines.append(f"| {section['name']} | {section['html_url']} |")
    lines.append(INDEX_END)
    return "\n".join(lines)


def load_sections_spec(path: str) -> list:
    """讀取 `init --sections-file` 的 JSON 規格：[{"name":.., "content":..}]。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("sections-file 須為非空 JSON 陣列")
    for item in data:
        if "name" not in item or "content" not in item:
            raise ValueError("每個區段須含 name 與 content 欄位")
    return data


def post_comment(issue_ref: str, body: str) -> dict:
    """POST 一則 comment（mock 攔截點），回傳 gh api JSON（含 id、html_url）。"""
    result = subprocess.run(
        [
            "gh", "api",
            f"repos/{FRAMEWORK_REPO}/issues/{issue_ref}/comments",
            "-f", f"body={body}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh api 建立 comment 失敗")
    return json.loads(result.stdout or "{}")


def patch_comment(comment_id: str, body: str) -> dict:
    """PATCH 指定 comment id（mock 攔截點），只影響該則 comment。"""
    result = subprocess.run(
        [
            "gh", "api",
            f"repos/{FRAMEWORK_REPO}/issues/comments/{comment_id}",
            "--method", "PATCH",
            "-f", f"body={body}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh api 更新 comment 失敗")
    return json.loads(result.stdout or "{}")


def fetch_comment(comment_id: str) -> dict:
    """GET 指定 comment id（mock 攔截點），供 update 前確認首行標記。"""
    result = subprocess.run(
        ["gh", "api", f"repos/{FRAMEWORK_REPO}/issues/comments/{comment_id}"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh api 讀取 comment 失敗")
    return json.loads(result.stdout or "{}")


def fetch_comments(issue_ref: str) -> list:
    """GET issue 全部 comments（mock 攔截點），`show`／`check` 共用。"""
    result = subprocess.run(
        ["gh", "api", f"repos/{FRAMEWORK_REPO}/issues/{issue_ref}/comments", "--paginate"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh api 讀取 comments 失敗")
    return json.loads(result.stdout or "[]")


def fetch_body(issue_ref: str) -> str:
    """GET issue body（mock 攔截點），init 回填索引前的讀取步驟。"""
    result = subprocess.run(
        ["gh", "issue", "view", issue_ref, "--repo", FRAMEWORK_REPO, "--json", "body"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh issue view 失敗")
    payload = json.loads(result.stdout or "{}")
    return payload.get("body", "") or ""


def write_body(issue_ref: str, body: str) -> int:
    """以暫存檔透過 --body-file 回寫 body（避免長文字跳脫問題），僅 init 呼叫一次。"""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(body)
        body_file = handle.name
    try:
        return run_gh(
            ["issue", "edit", issue_ref, "--repo", FRAMEWORK_REPO, "--body-file", body_file],
            success_msg=f"body 區段索引已回填 @ {issue_ref}",
        )
    finally:
        Path(body_file).unlink(missing_ok=True)


def search_issues_by_keyword(keyword: str) -> list:
    """對 FRAMEWORK_REPO 以單一詞彙查標題／body／comment 內文（mock 攔截點）。"""
    result = subprocess.run(
        [
            "gh", "search", "issues", keyword,
            "--repo", FRAMEWORK_REPO,
            "--match", "title,body,comments",
            "--json", "number,title,url,state",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh search issues 失敗")
    return json.loads(result.stdout or "[]")


def _split_keyword_tokens(keyword_group: str) -> list:
    """把一組查重關鍵字拆為查詢 token；含空白者逐詞查再聯集（見檔頭說明），
    無空白（含單一 CJK 複合詞，如「元件契約」）視為單一 token 原樣查詢。"""
    tokens = keyword_group.split()
    return tokens if tokens else [keyword_group]


def search_duplicates(keyword_groups: list) -> dict:
    """對每組關鍵字回傳命中 issue 清單（依 issue number 去重、排序）。

    單一 token 查詢失敗只警告略過，不中止其餘 token 或其他關鍵字組——查重
    本身的降級不應阻擋 init 的既有兩階段流程（查重「不阻擋」原則延伸至此）。
    """
    results = {}
    for group in keyword_groups:
        hits_by_number = {}
        for token in _split_keyword_tokens(group):
            try:
                for issue in search_issues_by_keyword(token):
                    hits_by_number.setdefault(issue["number"], issue)
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                sys.stderr.write(
                    f"[framework-issue] 查重關鍵字「{token}」查詢失敗，略過：{exc}\n"
                )
        results[group] = [hits_by_number[n] for n in sorted(hits_by_number)]
    return results


def render_dedup_report(keyword_groups: list, results: dict) -> str:
    """組合查重報告：回顯關鍵字集合、逐組列命中清單，提醒標註關係不自動判定。"""
    lines = [
        f"[framework-issue] 查重關鍵字集合（{len(keyword_groups)} 組）：{keyword_groups}",
        "",
    ]
    for group in keyword_groups:
        hits = results.get(group, [])
        lines.append(f"## 關鍵字「{group}」（{len(hits)} 則命中）")
        if not hits:
            lines.append("  無命中")
        for issue in hits:
            lines.append(
                f"  - #{issue.get('number')} [{issue.get('state', '?')}] {issue.get('title', '')}"
            )
            lines.append(f"    {issue.get('url', '')}")
        lines.append("")
    lines.append(
        "命中不等於重複：請對每張命中 issue 標註關係（重複／切分／引用），"
        "工具不自動判定，亦不阻擋後續建立。"
    )
    return "\n".join(lines) + "\n"


def cmd_dedup(keywords: list) -> int:
    """唯讀查重：不建立 issue，供 init 前人工核對或獨立驗證查詢涵蓋範圍。"""
    results = search_duplicates(keywords)
    sys.stdout.write(render_dedup_report(keywords, results))
    return 0


def cmd_init(issue_ref: str, owner: str, sections_file: str, dedup_keywords: list) -> int:
    """查重後建立全部區段 comment，取得 id 後回填一次 body 區段索引表。"""
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        sections = load_sections_spec(sections_file)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return emit_degraded(
            f"init 前置檢查失敗：{exc}",
            "確認 issue ref 與 sections-file 格式正確後重試",
        )

    dedup_results = search_duplicates(dedup_keywords)
    sys.stdout.write(render_dedup_report(dedup_keywords, dedup_results))

    posted = []
    try:
        for section in sections:
            rendered = render_section_comment(section["name"], owner, section["content"])
            result = post_comment(issue_ref, rendered)
            posted.append({"name": section["name"], "html_url": result.get("html_url", "")})
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"init 建立區段 comment 失敗（已成功 {len(posted)}/{len(sections)} 則，"
            "body 尚未回填，需人工檢查已建立的 comment 避免重複）："
            f"{exc}",
            "檢查已建立的區段 comment，清理後修正 sections-file 重試",
        )

    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"init 已建立 {len(posted)} 則區段 comment，但讀取 body 失敗，索引未回填：{exc}",
            "手動確認區段 comment 後重跑索引回填（不重複執行 init 避免重複建立區段）",
        )

    new_body = upsert_section(body, INDEX_SECTION_RE, render_index(posted))
    return write_body(issue_ref, new_body)


def cmd_update(comment_id: str, content_file: str) -> int:
    """以 comment id PATCH 指定區段，保留首行 name/owner 標記不變。"""
    try:
        content = Path(content_file).read_text(encoding="utf-8")
    except OSError as exc:
        return emit_degraded(f"讀取 content-file 失敗：{exc}", "確認檔案路徑存在後重試")

    try:
        existing = fetch_comment(comment_id)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"讀取既有 comment {comment_id} 失敗：{exc}",
            "確認 comment id 正確且 gh 可存取後重試",
        )

    marker = extract_section_marker(existing.get("body", ""))
    if marker is None:
        return emit_degraded(
            f"comment {comment_id} 首行非區段標記，拒絕更新（避免誤改觀測或一般 comment）",
            "確認 comment id 指向一個具 <!-- section: ... owner: ... --> 標記的區段 comment",
        )

    rendered = render_section_comment(marker["name"], marker["owner"], content)
    try:
        patch_comment(comment_id, rendered)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"更新 comment {comment_id} 失敗：{exc}", "檢查權限與網路後重試")

    sys.stderr.write(f"[framework-issue] 區段「{marker['name']}」已更新 @ comment {comment_id}\n")
    return 0


def cmd_observe(issue_ref: str, summary: str, session: str, content_file: str) -> int:
    """附加一則觀測 comment，不需 owner、不改 body、不影響既有 comment。"""
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        content = Path(content_file).read_text(encoding="utf-8")
    except (ValueError, OSError) as exc:
        return emit_degraded(
            f"observe 前置檢查失敗：{exc}",
            "確認 issue ref 與 content-file 正確後重試",
        )

    rendered = render_observation_comment(summary, session, content)
    try:
        result = post_comment(issue_ref, rendered)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"附加觀測 comment 失敗：{exc}", "檢查網路與權限後重試")

    sys.stdout.write(f"觀測 comment 已附加：{result.get('html_url', '')}\n")
    return 0


def _render_show_sections(rows: list, comments_by_id: dict) -> list:
    """把區段列（來自索引或標記掃描）渲染為輸出行，含 comment 找不到時的標示。"""
    lines = [f"## 區段（{len(rows)} 則）"]
    for row in rows:
        comment = comments_by_id.get(row["id"])
        updated_at = comment.get("updated_at", "") if comment else "(comment 未找到)"
        url = row["url"] or (comment.get("html_url", "") if comment else "")
        lines.append(f"- {row['name']} updated_at={updated_at}")
        lines.append(f"  {url}")
    return lines


def _render_show_stream(stream: list) -> list:
    """把觀測流依 created_at 排序後渲染為輸出行；有 observation 標記者用摘要，否則截首行。"""
    ordered = sorted(stream, key=lambda c: c.get("created_at", ""))
    lines = [f"## 觀測流（{len(ordered)} 則，依時間序）"]
    for comment in ordered:
        marker = OBSERVATION_MARKER_RE.match(comment.get("body", "") or "")
        if marker:
            label = f"{marker.group('summary')} by {marker.group('session')}"
        else:
            body_text = comment.get("body", "") or ""
            label = body_text.splitlines()[0][:40] if body_text else "(無內容)"
        lines.append(f"- {comment.get('created_at', '')} {label}")
        lines.append(f"  {comment.get('html_url', '')}")
    return lines


def build_show_output(body: str, comments: list) -> str:
    """依 body 區段索引表為入口組合輸出；索引缺失時退回全 comment 標記掃描。"""
    index_rows = parse_index_table(body)
    comments_by_id = {comment.get("id"): comment for comment in comments}

    if index_rows:
        header = f"[framework-issue] 區段索引來源：body 表格（{len(index_rows)} 筆）"
        section_rows = index_rows
        section_ids = {row["id"] for row in index_rows}
    else:
        header = "[framework-issue] 索引缺失：body 無區段索引表，改掃描全部 comment 首行標記"
        sections, _ = classify_comments(comments)
        section_rows = [
            {"name": entry["name"], "id": cid, "url": entry["comment"].get("html_url", "")}
            for cid, entry in sections.items()
        ]
        section_ids = set(sections.keys())

    stream = [c for c in comments if c.get("id") not in section_ids]

    lines = [header, ""]
    lines.extend(_render_show_sections(section_rows, comments_by_id))
    lines.append("")
    lines.extend(_render_show_stream(stream))
    return "\n".join(lines) + "\n"


def cmd_show(issue_ref: str) -> int:
    """唯讀：以 body 區段索引為入口，輸出區分「區段」與「觀測流」。"""
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        body = fetch_body(issue_ref)
        comments = fetch_comments(issue_ref)
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"show 讀取失敗：{exc}", "確認 issue ref 正確且 gh 可存取後重試")

    sys.stdout.write(build_show_output(body, comments))
    return 0


def _parse_timestamp(value: str) -> datetime:
    """解析 GitHub API 的 ISO8601 timestamp（含 Z 後綴）。"""
    return datetime.fromisoformat((value or "").replace("Z", "+00:00"))


def _check_comment_count(total: int, threshold: int) -> str:
    """警訊 A（輔助）：單張 issue comment 數超過閾值。"""
    if total > threshold:
        return f"[警訊 A][輔助] comment 數 {total} 超過閾值 {threshold}"
    return f"[警訊 A][輔助] comment 數 {total} 未超過閾值 {threshold}（略過）"


def _check_index_consistency(index_rows: list, sections: dict) -> str:
    """警訊 C：body 索引列出的 comment id 與實際區段 comment 集合比對。"""
    if not index_rows:
        return "[警訊 C] 索引缺失，無法比對（body 無區段索引表）"

    index_ids = {row["id"] for row in index_rows}
    actual_ids = set(sections.keys())
    if index_ids == actual_ids:
        return f"[警訊 C] 索引一致：{len(index_ids)} 筆"

    lines = [f"[警訊 C] 索引不一致：索引 {len(index_ids)} 筆、實際區段 {len(actual_ids)} 筆"]
    missing_in_index = sorted(actual_ids - index_ids)
    missing_in_actual = sorted(index_ids - actual_ids)
    if missing_in_index:
        lines.append(f"  索引缺漏的區段 comment id：{missing_in_index}")
    if missing_in_actual:
        lines.append(f"  索引列出但實際非區段/不存在的 comment id：{missing_in_actual}")
    return "\n".join(lines)


def _find_conclusion_comment(sections: dict):
    """從區段 dict 找出名稱為「當前結論」的 comment；找不到回傳 None。"""
    return next(
        (
            entry["comment"]
            for entry in sections.values()
            if entry["name"] == CURRENT_CONCLUSION_SECTION_NAME
        ),
        None,
    )


def _format_staleness_hit(conclusion: dict, newer: list, stale_days: int) -> str:
    """組合警訊 B 觸發時的訊息：落後期間 + 全部新增觀測 comment 的 html_url。"""
    lines = [
        f"[警訊 B][主警訊] 觸發：「{CURRENT_CONCLUSION_SECTION_NAME}」"
        f"updated_at={conclusion.get('updated_at')} 落後最新觀測 "
        f"{newer[-1].get('created_at')}，超過設定期間 {stale_days} 天",
        "  當前結論之後新增的觀測 comment：",
    ]
    lines.extend(f"  - {c.get('html_url', '')}" for c in newer)
    return "\n".join(lines)


def _check_conclusion_staleness(sections: dict, stream: list, stale_days: int) -> str:
    """警訊 B（主警訊）：「當前結論」區段 updated_at 落後最新觀測超過設定期間。

    命中時列出 updated_at 之後新增的全部觀測 comment 之 html_url（不只超過
    期間的那些），供 owner 直接整合。
    """
    conclusion = _find_conclusion_comment(sections)
    if conclusion is None:
        return f"[警訊 B][主警訊] 找不到「{CURRENT_CONCLUSION_SECTION_NAME}」區段 comment，無法比對"
    if not stream:
        return "[警訊 B][主警訊] 無觀測 comment，無需比對"

    conclusion_updated = _parse_timestamp(conclusion.get("updated_at", ""))
    newer = sorted(
        (c for c in stream if _parse_timestamp(c.get("created_at", "")) > conclusion_updated),
        key=lambda c: c.get("created_at", ""),
    )
    if not newer:
        return f"[警訊 B][主警訊] 未觸發：無晚於 updated_at={conclusion.get('updated_at')} 的觀測"

    gap = _parse_timestamp(newer[-1].get("created_at", "")) - conclusion_updated
    if gap <= timedelta(days=stale_days):
        return f"[警訊 B][主警訊] 未觸發：距最新觀測 {gap} <= 設定期間 {stale_days} 天"

    return _format_staleness_hit(conclusion, newer, stale_days)


def build_check_output(body: str, comments: list, comment_threshold: int, stale_days: int) -> str:
    """組合三項早期警訊：主警訊（時效）、輔助（comment 數）、索引一致性。"""
    sections, stream = classify_comments(comments)
    index_rows = parse_index_table(body)

    lines = [f"[framework-issue] check（comment 數：{len(comments)}）", ""]
    lines.append(_check_conclusion_staleness(sections, stream, stale_days))
    lines.append(_check_comment_count(len(comments), comment_threshold))
    lines.append(_check_index_consistency(index_rows, sections))
    return "\n".join(lines) + "\n"


def cmd_check(issue_ref: str, comment_threshold: int, stale_days: int) -> int:
    """唯讀：輸出三項早期警訊，不阻擋（exit 0）。"""
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        body = fetch_body(issue_ref)
        comments = fetch_comments(issue_ref)
    except (ValueError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"check 讀取失敗：{exc}", "確認 issue ref 正確且 gh 可存取後重試")

    sys.stdout.write(build_check_output(body, comments, comment_threshold, stale_days))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framework-issue section",
        description="comment-as-section 協作協定的寫入路徑（init/update/observe）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="查重後建立全部區段 comment 並回填 body 區段索引（僅執行一次）")
    p_init.add_argument("issue_ref", help="framework issue ref（如 tarrragon/claude#81 或純號 81）")
    p_init.add_argument("--owner", required=True, help="區段建立者/維護者 session 識別")
    p_init.add_argument(
        "--sections-file", required=True,
        help='JSON 檔，格式 [{"name": "當前結論", "content": "..."}]',
    )
    p_init.add_argument(
        "--dedup-keywords", nargs="+", required=True,
        help="init 前查重的關鍵字集合（每組可含空白，逐一加引號；命中清單印於"
             "輸出，不自動判定、不阻擋建立）",
    )

    p_dedup = sub.add_parser(
        "dedup", help="唯讀：以標題與 comment 內文查既有 issue，列命中清單不建立 issue"
    )
    p_dedup.add_argument(
        "--keywords", nargs="+", required=True,
        help="查重關鍵字集合（每組可含空白，逐一加引號）",
    )

    p_update = sub.add_parser("update", help="以 comment id PATCH 更新既有區段內容")
    p_update.add_argument("comment_id", help="區段 comment 的 GitHub comment id")
    p_update.add_argument("--content-file", required=True, help="新內容檔（不含首行標記）")

    p_observe = sub.add_parser("observe", help="附加觀測 comment，任何 session 可用不需 owner")
    p_observe.add_argument("issue_ref", help="framework issue ref（如 tarrragon/claude#81 或純號 81）")
    p_observe.add_argument("--summary", required=True, help="觀測摘要（進入首行標記）")
    p_observe.add_argument("--session", required=True, help="本次觀測的 session 識別")
    p_observe.add_argument("--content-file", required=True, help="觀測內容檔")

    p_show = sub.add_parser(
        "show", help="唯讀：以 body 區段索引為入口，輸出區分「區段」與「觀測流」"
    )
    p_show.add_argument("issue_ref", help="framework issue ref（如 tarrragon/claude#81 或純號 81）")

    p_check = sub.add_parser("check", help="唯讀：輸出三項早期警訊，不阻擋（exit 0）")
    p_check.add_argument("issue_ref", help="framework issue ref（如 tarrragon/claude#81 或純號 81）")
    p_check.add_argument(
        "--comment-threshold", type=int, default=DEFAULT_COMMENT_THRESHOLD,
        help=f"警訊 A 的 comment 數閾值（預設 {DEFAULT_COMMENT_THRESHOLD}）",
    )
    p_check.add_argument(
        "--stale-days", type=int, default=DEFAULT_STALE_DAYS,
        help=f"警訊 B 的落後期間天數（預設 {DEFAULT_STALE_DAYS}）",
    )

    return parser


def main(argv=None) -> int:
    parsed = build_parser().parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    if parsed.command == "init":
        return cmd_init(
            parsed.issue_ref, parsed.owner, parsed.sections_file, parsed.dedup_keywords
        )
    if parsed.command == "dedup":
        return cmd_dedup(parsed.keywords)
    if parsed.command == "update":
        return cmd_update(parsed.comment_id, parsed.content_file)
    if parsed.command == "observe":
        return cmd_observe(parsed.issue_ref, parsed.summary, parsed.session, parsed.content_file)
    if parsed.command == "show":
        return cmd_show(parsed.issue_ref)
    return cmd_check(parsed.issue_ref, parsed.comment_threshold, parsed.stale_days)


if __name__ == "__main__":
    sys.exit(main())
