#!/usr/bin/env python3
"""framework-issue section：comment-as-section 協作協定的寫入路徑。

背景：`tarrragon/claude#81` 當前結論區段（comment 5523472948）裁定的協作模型
——協作內容的載體是 comment 不是 body；body 只保留問題陳述與「區段索引」表。
每個區段是一則具 owner 的 comment，以 comment id 精準編輯；觀測 comment 任何
session 可隨時附加，不需 owner、不需協商。

五個命令對應五種寫入時機：

- `init`：**預設每張 issue 只執行一次**。先逐一 POST 全部區段 comment 取得
  id 與永久連結，再 GET 現有 body、與既有索引列合併、PATCH 一次；之後 body
  不再由本工具改寫（id 在 comment 建立後才存在，索引無法在建立時就寫入——
  見 #82 驗證）。issue 已有任何區段 comment 時預設拒絕（exit 3，提示改用
  `add`），避免重複 `init` 誤把此次區段清單當全部內容整段覆寫既有索引
  （見 #81 事故：第二個 session 的 `init` 使第一個 session 的 4 則區段從
  `show` 消失）；`--force` 可略過此檢查，與既有索引列合併而非覆寫。
- `add`：POST 單一區段 comment，於既有索引表追加一列（不存在索引表時建立），
  供 `init` 之後對同一 issue 新增區段——一般情況仍建議用 `add`，因為它不需
  重新查重，且不會誤觸 `init` 的一次性拒絕檢查。
- `update`：以 comment id PATCH 指定區段，只讀寫該則 comment，不觸碰 body
  或同 issue 其他 comment。更新前讀回既有內容確認首行為區段標記，非區段
  comment（如觀測、一般留言）一律拒絕，避免誤改。
- `transfer-owner`：PATCH 首行標記的 owner 欄，內容不變，供 owner 移交。
- `observe`：附加一則觀測 comment，不需 owner、不改 body、不影響既有 comment。

`init`／`add`／`transfer-owner` 共用 `validate_owner` 驗證 owner 識別格式
（`<kebab-case 前綴>-<數字序號>`），不合法一律 exit 3（見 `EXIT_DEGRADED`）。

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
docstring）。拆為單詞查詢後在本工具端聯集，可涵蓋此缺口。每筆命中另標示
「命中詞」（哪些 token 命中）與「命中位置」（title／body／comments 任一
子集，本地比對，見 `_hit_field_labels`），並依命中 token 數遞減排序，供
人工從大量命中中優先排除只命中單一 token 的雜訊。

`show` 以 body 的區段索引表為入口（`parse_index_table`），依索引列出的
comment id 分「區段」與「觀測流」兩類；索引缺失時退回全 comment 掃描首行
標記（`classify_comments`），並在輸出標示「索引缺失」。`check` 輸出三項
早期警訊（規格見 tarrragon/claude#81「增長語意與早期警訊」）：主警訊逐一
比對名稱以「當前結論」開頭的全部區段（涵蓋多 owner 以 `add` 附加的後綴
區段），各自的 `updated_at` 是否落後最新觀測 comment 超過設定期間並標明
owner；輔助為單張 issue comment 數超過閾值；第三項為 body 索引與實際區段
comment 集合的一致性比對。三項皆唯讀、不阻擋（exit 0），閾值與期間可由
CLI 參數覆蓋。

`init`／`add`／`update` 對區段名以「待辦與來源」開頭的區段（`ticket-intake.md`
的「待辦與來源（<consumer>）」慣例）額外解析首張表格並驗證欄位與列舉值
（`validate_todo_table`）：唯讀掃描曾實測 69 張 open issue 有 28 個此類
區段、144 列可解析，但「狀態」欄自由文字超過 12 種、「階段」欄超過 8
種，聚合後無法篩選——寫入端不驗證，讀取端就分不出類。欄位缺漏或列舉值
不合法時 exit 3 並印合法值集合與違規列，不寫入 GitHub。

`todo` 子命令為此表格的讀取路徑：跨 open issue 聚合全部「待辦與來源*」
區段表格列。範圍預設本 consumer 擁有的 open issue（讀本地擁有登記檔
`owned_issues_registry`，缺失時退回 owner 前綴推導，與
`session-start-issue-check-hook.py` 的 heuristic 同源但獨立實作——該檔
案為 hook 腳本，不供其他模組 import），`--all` 改掃 `FRAMEWORK_REPO` 全部
open issue，`--issue N` 只掃單一 issue（明確指定即略過範圍解析）。支援
`--status`／`--stage`／`--priority`／`--consumer` 篩選與 `--json` 輸出；
依優先級排序（P0 最前）；表頭不符的區段印警告並跳過，不中止其餘 issue 或
區段的聚合。comments 抓取採 per-issue 快取，同次執行內跨區段／跨候選驗證
重複使用。
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gh_common import (
    FRAMEWORK_REPO,
    emit_degraded,
    normalize_issue_ref,
    preflight,
    run_gh,
)
from owned_issues_registry import owned_issue_numbers, record_owned_issue
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

# 協定標記：body 含此行代表該 issue 採用 comment-as-section 協定（見
# comment-as-section-protocol.md 開頭定義）。init／add 回填索引時若 body
# 缺此標記則於首行 upsert，與索引回填同一次 PATCH 完成（見 _ensure_schema_marker）。
FW_ISSUE_SCHEMA_MARKER = "<!-- fw-issue-schema: comment-as-section v1 -->"

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

# owner 識別格式：<專案目錄 kebab-case 前綴>-<session 序號>，如
# "flutter-balance-77"。init／add／transfer-owner 共用同一驗證（見
# validate_owner）——判準明確而執法只掛在單一入口，存量會從另一入口累積
# （同儕以代理人名稱 "framework-issue-curator" init 七張未被攔下即為一例）。
OWNER_FORMAT_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-[0-9]+$")

# check 的兩項閾值：規格（tarrragon/claude#81「增長語意與早期警訊」）定性
# 描述「輔助訊號」與「某期間」，未給出精確數字。以下為可運作的初始預設
# 值，兩者皆可由 CLI 參數覆蓋，非規格權威值。
DEFAULT_COMMENT_THRESHOLD = 30
DEFAULT_STALE_DAYS = 7

# gh api comment 物件的標準欄位，供 cmd_update 從既有 comment 回推 issue
# number（cmd_update 只收 comment_id，不像 cmd_init 直接持有 issue_ref）。
_ISSUE_URL_NUMBER_RE = re.compile(r"/issues/(?P<num>\d+)$")

# 「待辦與來源」表格 schema（本 ticket 權威定義，DOC 側列舉文件與此一致）。
# 區段名以此前綴開頭時，init／add／update 觸發表格驗證，todo 觸發聚合。
TODO_SECTION_NAME_PREFIX = "待辦與來源"

# 必要欄位：缺任一即 exit 3。「型別」為選填欄，存在與否構成僅有的兩種
# 合法表頭形態（見 TODO_VALID_HEADERS）——唯讀掃描曾實測表頭僅此 2 種。
# 「型別」插於「來源票」之後（非附加於表尾）：對 `todo --all` 的實跑觀測
# 顯示既有 issue 的 7 欄表格一致採此順序（curator 派發模板既有慣例），
# 插入位置若改為表尾會使這些既有合法表格被誤判表頭不符。
TODO_REQUIRED_COLUMNS = ["來源票", "做什麼", "acceptance 條數", "優先級", "階段", "狀態"]
TODO_OPTIONAL_COLUMNS = ["型別"]
TODO_HEADER_WITH_TYPE = (
    TODO_REQUIRED_COLUMNS[:1] + TODO_OPTIONAL_COLUMNS + TODO_REQUIRED_COLUMNS[1:]
)
TODO_VALID_HEADERS = [
    TODO_REQUIRED_COLUMNS,
    TODO_HEADER_WITH_TYPE,
]

# 「狀態」「階段」列舉權威值（與 DOC 側 ticket-intake.md／
# comment-as-section-protocol.md 的文字描述同步維護，票面 how.strategy
# 為權威來源）。
TODO_STATUS_VALUES = ["待裁票", "已裁票", "進行中", "完成", "不執行"]
TODO_STAGE_VALUES = ["可立即執行", "本版", "下版", "待條件"]

# todo 輸出排序：優先級由高至低；未知優先級值排在已知值之後，不拋錯
# （聚合是唯讀操作，不應因單一列的雜訊值中止整體輸出）。
TODO_PRIORITY_ORDER = ["P0", "P1", "P2", "P3"]

# markdown 表格列偵測：整行以 "|" 起訖（允許前後空白，呼叫端已 strip）。
# 分隔列（表頭與資料列之間）偵測：每個儲存格只含 "-" 與可選首尾 ":"。
_TABLE_ROW_RE = re.compile(r"^\|.*\|$")
_TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _now_iso() -> str:
    """owned-issues 登記檔的 updated_at 時間戳（UTC ISO8601）。"""
    return datetime.now(timezone.utc).isoformat()


def _issue_number_from_comment(comment: dict) -> Optional[int]:
    """從 gh api comment 物件的 issue_url 回推所屬 issue number；缺失或格式
    不符回傳 None（呼叫端略過登記檔寫入，不影響既有 GitHub 寫入結果）。"""
    match = _ISSUE_URL_NUMBER_RE.search(comment.get("issue_url", "") or "")
    return int(match.group("num")) if match else None


def render_section_comment(name: str, owner: str, content: str) -> str:
    """把區段內容包上首行標記，供 POST/PATCH 使用。"""
    return f"<!-- section: {name} owner: {owner} -->\n{content}"


def render_observation_comment(summary: str, session: str, content: str) -> str:
    """把觀測內容包上首行標記，供 POST 使用。"""
    return f"<!-- observation: {summary} by {session} -->\n{content}"


def validate_owner(owner: str) -> None:
    """驗證 owner 識別格式；不合法時拋 ValueError（呼叫端捕捉後轉為 exit 3
    降級提示），訊息含格式規則與範例。"""
    if not OWNER_FORMAT_RE.match(owner):
        raise ValueError(
            f"owner 格式不符：'{owner}'。"
            "須為 <kebab-case 前綴>-<數字序號>，如 'flutter-balance-77'"
            "（不可為代理人名稱如 'framework-issue-curator'，"
            "或含底線如 'flutter_balance-pm'）"
        )


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


def render_index_table(rows: list) -> str:
    """把 [{"name":, "url":}, ...] 渲染為可 upsert 的索引區段（表格列）。

    `init`／`add` 共用：`init` 一次性渲染全部剛建立的區段；`add` 併入既有
    索引列（來自 `parse_index_table`）與新增的一列後整段重渲染，兩者欄位
    統一為 name/url，呼叫端各自映射（`init` 的來源為 html_url）。
    """
    lines = [INDEX_BEGIN, INDEX_TABLE_HEADER]
    for row in rows:
        lines.append(f"| {row['name']} | {row['url']} |")
    lines.append(INDEX_END)
    return "\n".join(lines)


def render_index(posted_sections: list) -> str:
    """把已建立區段的 {name, html_url} 清單渲染為可 upsert 的索引區段。"""
    rows = [{"name": section["name"], "url": section["html_url"]} for section in posted_sections]
    return render_index_table(rows)


def _merge_index_rows(existing_rows: list, new_rows: list) -> list:
    """合併既有索引列與新建立的區段列，以 comment id 去重（保留既有列在前
    的原文順序）。`init`／`add` 共用：`init` 原本以本次區段清單整段覆寫
    索引，導致他方既有列從 show 消失；`add` 對無 `<!-- section-index -->`
    標記的手寫索引表每執行一次即把既有列再複製一輪（見本 ticket why 段與
    Problem Analysis 第二個同源缺陷）。以 id 去重同時處理兩者：即使
    `existing_rows` 因修法前的殘留狀態已含重複列，經任一次 `add`／`init`
    即可自我修復。
    """
    seen = set()
    merged = []
    for row in existing_rows + new_rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        merged.append(row)
    return merged


def _strip_raw_index_rows(body: str) -> str:
    """移除 body 內未被 `INDEX_BEGIN`／`INDEX_END` 標記包住的索引表區塊
    （表頭、分隔列、資料列，以及緊接其上、因而變孤立的標題行），避免與
    即將回填的合併索引重複並存於 body。

    已標記區段交由 `upsert_section` 的整段取代處理，不在本函式範圍內。
    手寫表（無標記）原本會在 `upsert_section` 的 append 分支被當作『body
    其餘內容』原樣保留，使下次執行時 `parse_index_table` 對新舊兩表重複
    計入既有列（見本 ticket Problem Analysis 第二個同源缺陷）；本函式在
    合併既有列之後、回填前，把手寫表整段自 body 移除，使結果只留一張表。
    """
    if INDEX_BEGIN in body:
        return body
    lines = body.splitlines()
    remove = set()
    for i, line in enumerate(lines):
        if not INDEX_ROW_ID_RE.search(line):
            continue
        j = i
        while j >= 0 and lines[j].strip().startswith("|"):
            remove.add(j)
            j -= 1
        j = i
        while j < len(lines) and lines[j].strip().startswith("|"):
            remove.add(j)
            j += 1
    if not remove:
        return body
    heading_line = INDEX_TABLE_HEADER.splitlines()[0]
    table_top = min(remove)
    cursor = table_top - 1
    if cursor >= 0 and lines[cursor].strip() == "":
        blank_idx = cursor
        cursor -= 1
        if cursor >= 0 and lines[cursor].strip() == heading_line:
            remove.add(cursor)
            remove.add(blank_idx)
    elif cursor >= 0 and lines[cursor].strip() == heading_line:
        remove.add(cursor)
    kept = [line for idx, line in enumerate(lines) if idx not in remove]
    return "\n".join(kept)


def _ensure_schema_marker(body: str) -> str:
    """若 body 缺 `FW_ISSUE_SCHEMA_MARKER` 則於首行補上；已存在則原樣返回。

    取代原本「先 `gh issue edit` 手動補標記、再 `init` 回填索引」的兩階段
    流程——兩次手工 PATCH 順序未定義，兩個 session 交錯操作時有並行覆蓋
    窗口。呼叫端（`cmd_init`／`cmd_add`）在同一次 `write_body` PATCH 內
    連同索引一併寫入，不增加 PATCH 次數。
    """
    body = body or ""
    if FW_ISSUE_SCHEMA_MARKER in body:
        return body
    return f"{FW_ISSUE_SCHEMA_MARKER}\n{body}"


def load_sections_spec(path: str) -> list:
    """讀取 `init --sections-file` 的 JSON 規格：[{"name":.., "content":..}]。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("sections-file 須為非空 JSON 陣列")
    for item in data:
        if "name" not in item or "content" not in item:
            raise ValueError("每個區段須含 name 與 content 欄位")
    return data


def _split_table_row(line: str) -> List[str]:
    """把一行 `| a | b |` 拆為去除前後空白的儲存格清單。"""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown_table(content: str) -> Optional[Tuple[List[str], List[List[str]]]]:
    """從一段內容抽取首張 markdown 表格，回傳 `(表頭儲存格, 資料列清單)`；
    找不到表格（少於表頭+至少一列的連續 `|` 起訖行）回傳 `None`。

    只掃描第一個連續的「以 `|` 起訖」行區塊——內容含多張表格時只取第一張，
    與 `validate_todo_table`／`todo` 聚合的「首張表格」約定一致。分隔列
    （表頭與資料列之間、儲存格僅含 `-`/`:` 者）存在則跳過，不存在也不視為
    錯誤（容忍手寫、非標準 markdown 渲染器產生的表格）。
    """
    table_lines = []
    started = False
    for line in (content or "").splitlines():
        stripped = line.strip()
        if _TABLE_ROW_RE.match(stripped):
            table_lines.append(stripped)
            started = True
        elif started:
            break
    if len(table_lines) < 2:
        return None

    header = _split_table_row(table_lines[0])
    data_lines = table_lines[1:]
    if data_lines and all(
        _TABLE_SEPARATOR_CELL_RE.match(cell) for cell in _split_table_row(data_lines[0])
    ):
        data_lines = data_lines[1:]
    rows = [_split_table_row(line) for line in data_lines]
    return header, rows


def validate_todo_table(name: str, content: str) -> None:
    """驗證「待辦與來源*」區段的表格欄位與列舉值；不合法時拋 `ValueError`
    （呼叫端捕捉後轉為 exit 3），訊息含合法值集合與違規列原文，供操作者
    不需另外查文件即可修正。名稱不以 `TODO_SECTION_NAME_PREFIX` 開頭者
    視為非待辦表區段，略過（回傳 `None`，不驗證）。
    """
    if not name.startswith(TODO_SECTION_NAME_PREFIX):
        return

    parsed = parse_markdown_table(content)
    if parsed is None:
        raise ValueError(
            f"區段「{name}」名稱以「{TODO_SECTION_NAME_PREFIX}」開頭，"
            f"但內容找不到可解析的表格；合法表頭：{TODO_VALID_HEADERS}"
        )
    header, rows = parsed
    if header not in TODO_VALID_HEADERS:
        raise ValueError(
            f"區段「{name}」表頭不符：{header}；合法表頭：{TODO_VALID_HEADERS}"
        )

    for row in rows:
        row_map = dict(zip(header, row))
        for column in TODO_REQUIRED_COLUMNS:
            if not row_map.get(column, "").strip():
                raise ValueError(
                    f"區段「{name}」表格列缺少必要欄位「{column}」：{row}"
                )
        status = row_map.get("狀態", "")
        if status not in TODO_STATUS_VALUES:
            raise ValueError(
                f"區段「{name}」表格列「狀態」值不合法：'{status}'；"
                f"合法值：{TODO_STATUS_VALUES}｜違規列：{row}"
            )
        stage = row_map.get("階段", "")
        if stage not in TODO_STAGE_VALUES:
            raise ValueError(
                f"區段「{name}」表格列「階段」值不合法：'{stage}'；"
                f"合法值：{TODO_STAGE_VALUES}｜違規列：{row}"
            )


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


def write_body(issue_ref: str, body: str, success_msg: Optional[str] = None) -> int:
    """以暫存檔透過 --body-file 回寫 body（避免長文字跳脫問題）；`init` 僅呼叫
    一次，`add` 每次呼叫皆為同一個 issue 的索引回填。`success_msg` 未提供時
    用回填索引的通用訊息；`cmd_add` 傳入含區段名／owner 的訊息，供操作者從
    輸出直接確認建立結果（同 `cmd_transfer_owner` 逐字印出結果的取向）。"""
    if success_msg is None:
        success_msg = f"body 區段索引已回填 @ {issue_ref}"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(body)
        body_file = handle.name
    try:
        return run_gh(
            ["issue", "edit", issue_ref, "--repo", FRAMEWORK_REPO, "--body-file", body_file],
            success_msg=success_msg,
        )
    finally:
        Path(body_file).unlink(missing_ok=True)


def search_issues_by_keyword(keyword: str) -> list:
    """對 FRAMEWORK_REPO 以單一詞彙查標題／body／comment 內文（mock 攔截點）。

    keyword 排在全部旗標之後、以 `--` 分隔。查重 token 可能以 `-` 開頭（如
    「commit -a」拆分出的 "-a"、或 "--force"），若排在旗標前會被 gh 的
    cobra flag parser 誤判為短／長旗標，回 unknown flag 錯誤（實測重現：
    未加 `--` 時 `gh search issues -a ...` 回 "unknown shorthand flag"）；
    `--` 之後 pflag 停止解析旗標，全部視為位置參數，可安全涵蓋此形態
    （既有測試關鍵字皆無 `-` 開頭，屬 PC-BAL-064 取樣單一格）。

    `--json` 額外取 `body`（原本只取 number/title/url/state）：供
    `_hit_field_labels` 本地判定命中位置（title／body 本地子字串比對），
    不需為此額外呼叫 gh。
    """
    result = subprocess.run(
        [
            "gh", "search", "issues",
            "--repo", FRAMEWORK_REPO,
            "--match", "title,body,comments",
            "--json", "number,title,url,state,body",
            "--", keyword,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh search issues 失敗")
    return json.loads(result.stdout or "[]")


def _has_comment_match(issue_number: int, token: str, comment_cache: dict) -> bool:
    """對候選 issue 的全部 comment 本地比對是否含 token（大小寫不敏感）。

    每個 issue 的 comment 清單只抓取一次並存入 `comment_cache`，供同一次
    `search_duplicates` 執行內跨 token／跨關鍵字組重複使用，避免對同一
    issue 因命中多個 token 而重複呼叫 `gh api`。抓取失敗（網路／權限）時
    快取空清單並回傳未命中，不中止其餘比對——查重本身的降級不應阻擋整體
    流程（同 `search_duplicates` 既有的「不阻擋」原則）。
    """
    if issue_number not in comment_cache:
        try:
            comment_cache[issue_number] = fetch_comments(str(issue_number))
        except (OSError, subprocess.SubprocessError, RuntimeError):
            comment_cache[issue_number] = []
    token_lower = token.lower()
    return any(
        token_lower in (comment.get("body", "") or "").lower()
        for comment in comment_cache[issue_number]
    )


def _hit_field_labels(token: str, issue: dict, comment_cache: dict) -> set:
    """判定 token 對 issue 的命中位置集合（title／body／comments 任一子集，
    可並存亦可能三者皆未命中）。title／body 以 search 回傳的欄位本地比對；
    comments 對該 issue 全部 comment 本地比對（見 `_has_comment_match`，
    有快取）。

    此為近似判定，非精確重現 GitHub 全文檢索的分詞／詞幹化語意——僅供
    dedup 報告標示命中位置，協助人工快速排除雜訊，不作為機械判準。
    """
    token_lower = token.lower()
    fields = set()
    if token_lower in (issue.get("title", "") or "").lower():
        fields.add("title")
    if token_lower in (issue.get("body", "") or "").lower():
        fields.add("body")
    if _has_comment_match(issue["number"], token, comment_cache):
        fields.add("comments")
    return fields


def _split_keyword_tokens(keyword_group: str) -> list:
    """把一組查重關鍵字拆為查詢 token；含空白者逐詞查再聯集（見檔頭說明），
    無空白（含單一 CJK 複合詞，如「元件契約」）視為單一 token 原樣查詢。"""
    tokens = keyword_group.split()
    return tokens if tokens else [keyword_group]


def search_duplicates(keyword_groups: list) -> tuple:
    """對每組關鍵字回傳命中 issue 清單，與略過的 token 查詢失敗總數（回傳
    `(results, skipped_count)`）。每筆命中額外帶 `matched_tokens`（該 issue
    命中的 token 清單）與 `hit_fields`（命中位置集合，見 `_hit_field_labels`），
    供 `render_dedup_report` 標示；清單依 `matched_tokens` 數量遞減排序（同
    數量再依 issue number 遞增），命中多個 token 的 issue 較可能是真實重複，
    優先排在報告前段。

    單一 token 查詢失敗只警告略過，不中止其餘 token 或其他關鍵字組——查重
    本身的降級不應阻擋 init 的既有兩階段流程（查重「不阻擋」原則延伸至此）。
    失敗數需回傳而非只印 stderr：查重涵蓋範圍縮小若無法從報告本身得知，
    呼叫端會誤把「整體成功」讀成「查詢皆完整涵蓋」（見 render_dedup_report
    的涵蓋缺口宣告）。
    """
    results = {}
    skipped = 0
    comment_cache: dict = {}
    for group in keyword_groups:
        hits_by_number = {}
        for token in _split_keyword_tokens(group):
            try:
                for issue in search_issues_by_keyword(token):
                    entry = hits_by_number.setdefault(
                        issue["number"], {"issue": issue, "tokens": set(), "fields": set()}
                    )
                    entry["tokens"].add(token)
                    entry["fields"] |= _hit_field_labels(token, issue, comment_cache)
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                skipped += 1
                sys.stderr.write(
                    f"[framework-issue][WARNING] 查重關鍵字「{token}」查詢失敗，略過：{exc}\n"
                )
        ordered = sorted(
            hits_by_number.values(),
            key=lambda entry: (-len(entry["tokens"]), entry["issue"]["number"]),
        )
        results[group] = [
            {
                **entry["issue"],
                "matched_tokens": sorted(entry["tokens"]),
                "hit_fields": sorted(entry["fields"]),
            }
            for entry in ordered
        ]
    return results, skipped


def render_dedup_report(keyword_groups: list, results: dict, skipped: int = 0) -> str:
    """組合查重報告：回顯關鍵字集合、逐組列命中清單，提醒標註關係不自動判定。

    每筆命中列出「命中詞」與「命中位置」（見 `search_duplicates` 的
    `matched_tokens`／`hit_fields`），供人工優先排除只命中單一 token 的
    雜訊；`results` 傳入時已依命中 token 數遞減排序，此函式不重排。

    末行固定重述略過的 token 查詢失敗數（`tail -1` 即可見），使涵蓋範圍
    縮小成為報告本身可見的明確宣告，不只依賴 stderr 的單行警告。
    """
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
            matched_tokens = issue.get("matched_tokens", [])
            hit_fields = issue.get("hit_fields", [])
            lines.append(
                f"    命中詞：{'、'.join(matched_tokens) or '（無）'}"
                f"｜命中位置：{'、'.join(hit_fields) or '（無）'}"
            )
        lines.append("")
    lines.append(
        "命中不等於重複：請對每張命中 issue 標註關係（重複／切分／引用），"
        "工具不自動判定，亦不阻擋後續建立。"
    )
    lines.append(f"查詢失敗略過的 token 數：{skipped}")
    return "\n".join(lines) + "\n"


def cmd_dedup(keywords: list) -> int:
    """唯讀查重：不建立 issue，供 init 前人工核對或獨立驗證查詢涵蓋範圍。"""
    results, skipped = search_duplicates(keywords)
    sys.stdout.write(render_dedup_report(keywords, results, skipped))
    return 0


def cmd_init(
    issue_ref: str, owner: str, sections_file: str, dedup_keywords: list, force: bool = False
) -> int:
    """查重後建立全部區段 comment，取得 id 後與既有索引列合併回填一次 body
    區段索引表。issue 已有任何區段 comment 時預設拒絕（`init` 僅供建立初始
    索引，重複建立應改用 `add`），`--force` 可略過此檢查（見本 ticket why：
    第二個 session 對已 `init` 過的 issue 再次 `init` 會整段覆寫索引，導致
    第一個 session 的既有區段從 `show` 消失）。
    """
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        validate_owner(owner)
        sections = load_sections_spec(sections_file)
        for section in sections:
            validate_todo_table(section["name"], section["content"])
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return emit_degraded(
            f"init 前置檢查失敗：{exc}",
            "確認 issue ref、owner 格式與 sections-file 格式正確後重試",
        )

    if not force:
        try:
            existing_sections, _ = classify_comments(fetch_comments(issue_ref))
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            return emit_degraded(
                f"init 前置檢查（既有區段掃描）失敗：{exc}",
                "確認 issue ref 正確且 gh 可存取後重試，或以 --force 略過此檢查",
            )
        if existing_sections:
            return emit_degraded(
                f"issue {issue_ref} 已有 {len(existing_sections)} 則區段 comment，"
                "init 僅供建立初始索引，拒絕重複執行",
                f"改用 `add {issue_ref} --owner {owner} --name <區段名> "
                "--content-file <path>` 對此 issue 追加新區段，"
                "或加 --force 略過此檢查（會與既有索引列合併，不覆寫既有 owner 的區段）",
            )

    dedup_results, dedup_skipped = search_duplicates(dedup_keywords)
    sys.stdout.write(render_dedup_report(dedup_keywords, dedup_results, dedup_skipped))

    posted = []
    try:
        for section in sections:
            rendered = render_section_comment(section["name"], owner, section["content"])
            result = post_comment(issue_ref, rendered)
            posted.append(
                {
                    "name": section["name"],
                    "id": result.get("id"),
                    "html_url": result.get("html_url", ""),
                }
            )
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"init 建立區段 comment 失敗（已成功 {len(posted)}/{len(sections)} 則，"
            "body 尚未回填，需人工檢查已建立的 comment 避免重複）："
            f"{exc}",
            "檢查已建立的區段 comment，清理後修正 sections-file 重試",
        )

    # 區段 comment 已全數建立成功，owner 對此 issue 的擁有關係已確立——
    # 即使後續 body 索引回填失敗，登記檔仍應反映此事實（見
    # owned_issues_registry 模組 docstring：best-effort 快取，寫入失敗不
    # 影響已完成的 GitHub 寫入結果）。
    record_owned_issue(int(issue_ref), owner, _now_iso())

    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"init 已建立 {len(posted)} 則區段 comment，但讀取 body 失敗，索引未回填：{exc}",
            "手動確認區段 comment 後重跑索引回填（不重複執行 init 避免重複建立區段）",
        )

    existing_rows = parse_index_table(body)
    new_rows = [{"name": p["name"], "id": p["id"], "url": p["html_url"]} for p in posted]
    merged_rows = _merge_index_rows(existing_rows, new_rows)
    body = _strip_raw_index_rows(body)
    body = _ensure_schema_marker(body)
    new_body = upsert_section(body, INDEX_SECTION_RE, render_index_table(merged_rows))
    return write_body(issue_ref, new_body)


def cmd_add(issue_ref: str, owner: str, name: str, content_file: str) -> int:
    """建立單一區段 comment，於既有索引表追加一列（不存在索引表時建立）；
    其他既有列的 comment id／連結不受影響（供 `init` 之後對同一 issue
    追加新區段，見本 ticket why 段：init 每張 issue 只能跑一次的缺口）。
    """
    try:
        issue_ref = normalize_issue_ref(issue_ref)
        validate_owner(owner)
        content = Path(content_file).read_text(encoding="utf-8")
        validate_todo_table(name, content)
    except (ValueError, OSError) as exc:
        return emit_degraded(
            f"add 前置檢查失敗：{exc}",
            "確認 issue ref、owner 格式與 content-file 正確後重試",
        )

    rendered = render_section_comment(name, owner, content)
    try:
        result = post_comment(issue_ref, rendered)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"add 建立區段 comment 失敗：{exc}", "檢查網路與權限後重試")

    # 區段 comment 已建立成功，owner 對此區段的擁有關係已確立——即使後續
    # body 索引回填失敗，登記檔仍應反映此事實（同 cmd_init 取向，見
    # owned_issues_registry 模組 docstring）。
    record_owned_issue(int(issue_ref), owner, _now_iso())

    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"add 已建立區段 comment（{result.get('html_url', '')}），"
            f"但讀取 body 失敗，索引未更新：{exc}",
            "手動確認區段 comment 後重跑索引回填（不重複執行 add 避免重複建立區段）",
        )

    existing_rows = parse_index_table(body)
    new_row = {"name": name, "id": result.get("id"), "url": result.get("html_url", "")}
    merged_rows = _merge_index_rows(existing_rows, [new_row])
    body = _strip_raw_index_rows(body)
    body = _ensure_schema_marker(body)
    new_body = upsert_section(body, INDEX_SECTION_RE, render_index_table(merged_rows))
    return write_body(
        issue_ref, new_body,
        success_msg=f"區段「{name}」已建立 @ {issue_ref}，owner={owner}",
    )


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

    try:
        validate_todo_table(marker["name"], content)
    except ValueError as exc:
        return emit_degraded(str(exc), "確認表格欄位與列舉值合法後重試")

    rendered = render_section_comment(marker["name"], marker["owner"], content)
    try:
        patch_comment(comment_id, rendered)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"更新 comment {comment_id} 失敗：{exc}", "檢查權限與網路後重試")

    # 更新成功後同步刷新登記檔（見 owned_issues_registry 模組 docstring）：
    # cmd_update 只收 comment_id，issue number 須從既有 comment 的
    # issue_url 回推；回推失敗（欄位缺失/格式不符）不影響本次更新結果，
    # 僅略過登記檔寫入。
    issue_number = _issue_number_from_comment(existing)
    if issue_number is not None:
        record_owned_issue(issue_number, marker["owner"], _now_iso())

    sys.stderr.write(f"[framework-issue] 區段「{marker['name']}」已更新 @ comment {comment_id}\n")
    return 0


def cmd_transfer_owner(comment_id: str, new_owner: str) -> int:
    """PATCH 首行標記的 owner 欄，內容不變；同步登記檔（供 owner 移交，見
    本 ticket why 段：update 保留首行 owner 標記不變，無命令可改 owner）。
    """
    try:
        validate_owner(new_owner)
    except ValueError as exc:
        return emit_degraded(str(exc), "確認 --to 為合法 owner 格式後重試")

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
            f"comment {comment_id} 首行非區段標記，拒絕轉移 owner（避免誤改觀測或一般 comment）",
            "確認 comment id 指向一個具 <!-- section: ... owner: ... --> 標記的區段 comment",
        )

    # 內容不變：existing body 為「首行標記 + 內容」，切除首行後重新組裝
    # 相同內容、僅替換 owner 欄。
    _, _, content = (existing.get("body", "") or "").partition("\n")
    rendered = render_section_comment(marker["name"], new_owner, content)
    try:
        patch_comment(comment_id, rendered)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(
            f"轉移 owner 失敗（comment {comment_id}）：{exc}", "檢查權限與網路後重試"
        )

    issue_number = _issue_number_from_comment(existing)
    if issue_number is not None:
        record_owned_issue(issue_number, new_owner, _now_iso())

    sys.stderr.write(
        f"[framework-issue] 區段「{marker['name']}」owner 已由 "
        f"{marker['owner']} 轉移至 {new_owner} @ comment {comment_id}\n"
    )
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
    """把區段列（來自索引或標記掃描）渲染為輸出行，含 comment 找不到時的標示。

    owner 從 comment body 首行標記回推（`_owner_of`，與 `check` 共用）——
    `transfer-owner` 是唯一會改 owner 的操作，`show` 原本不印 owner 使驗證
    手段不在同一套 CLI 內，操作者需另外開 comment 才能確認結果。
    """
    lines = [f"## 區段（{len(rows)} 則）"]
    for row in rows:
        comment = comments_by_id.get(row["id"])
        updated_at = comment.get("updated_at", "") if comment else "(comment 未找到)"
        owner = _owner_of(comment) if comment else "(comment 未找到)"
        url = row["url"] or (comment.get("html_url", "") if comment else "")
        lines.append(f"- {row['name']} owner={owner} updated_at={updated_at}")
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


def _find_conclusion_comments(sections: dict) -> list:
    """從區段 dict 找出名稱以「當前結論」開頭的全部 comment（依 comment id
    排序，供多 owner 場景逐則比對）。單一「當前結論」時回傳單一元素清單，
    既有行為不變；多 owner 以 `add` 附加的後綴區段（如「當前結論（<consumer>：
    <主題>）」）現一併涵蓋（見本 ticket why：字串相等定位使第二 owner 缺主
    警訊涵蓋）。"""
    return sorted(
        (
            entry
            for entry in sections.values()
            if entry["name"].startswith(CURRENT_CONCLUSION_SECTION_NAME)
        ),
        key=lambda entry: entry["comment"].get("id") or 0,
    )


def _owner_of(comment: dict) -> str:
    """從區段 comment body 首行標記回推 owner。sections dict（來自
    classify_comments）只保留 name，未保留 owner，故於此按需重新解析。"""
    marker = extract_section_marker(comment.get("body", "") or "")
    return marker["owner"] if marker else "?"


def _format_staleness_hit(name: str, owner: str, conclusion: dict, newer: list, stale_days: int) -> str:
    """組合警訊 B 觸發時的訊息：落後期間 + 全部新增觀測 comment 的 html_url。"""
    lines = [
        f"[警訊 B][主警訊] 觸發：「{name}」（owner: {owner}）"
        f"updated_at={conclusion.get('updated_at')} 落後最新觀測 "
        f"{newer[-1].get('created_at')}，超過設定期間 {stale_days} 天",
        "  當前結論之後新增的觀測 comment：",
    ]
    lines.extend(f"  - {c.get('html_url', '')}" for c in newer)
    return "\n".join(lines)


def _check_single_conclusion(name: str, comment: dict, stream: list, stale_days: int) -> str:
    """對單一「當前結論*」區段比對 updated_at 是否落後最新觀測，輸出標明 owner。"""
    owner = _owner_of(comment)
    label = f"「{name}」（owner: {owner}）"
    conclusion_updated = _parse_timestamp(comment.get("updated_at", ""))
    newer = sorted(
        (c for c in stream if _parse_timestamp(c.get("created_at", "")) > conclusion_updated),
        key=lambda c: c.get("created_at", ""),
    )
    if not newer:
        return (
            f"[警訊 B][主警訊] 未觸發：{label} "
            f"updated_at={comment.get('updated_at')} 無晚於此的觀測"
        )

    gap = _parse_timestamp(newer[-1].get("created_at", "")) - conclusion_updated
    if gap <= timedelta(days=stale_days):
        return f"[警訊 B][主警訊] 未觸發：{label} 距最新觀測 {gap} <= 設定期間 {stale_days} 天"

    return _format_staleness_hit(name, owner, comment, newer, stale_days)


def _check_conclusion_staleness(sections: dict, stream: list, stale_days: int) -> str:
    """警訊 B（主警訊）：名稱以「當前結論」開頭的全部區段，逐則比對 updated_at
    是否落後最新觀測超過設定期間，各自輸出並標明 owner（多 owner 場景見
    `_find_conclusion_comments`）。

    命中時列出該區段 updated_at 之後新增的全部觀測 comment 之 html_url（不只
    超過期間的那些），供 owner 直接整合。
    """
    conclusions = _find_conclusion_comments(sections)
    if not conclusions:
        return f"[警訊 B][主警訊] 找不到「{CURRENT_CONCLUSION_SECTION_NAME}」區段 comment，無法比對"
    if not stream:
        return "[警訊 B][主警訊] 無觀測 comment，無需比對"

    return "\n".join(
        _check_single_conclusion(entry["name"], entry["comment"], stream, stale_days)
        for entry in conclusions
    )


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


# --- todo：跨 open issue 聚合「待辦與來源*」區段表格列（唯讀） ---


def list_open_issue_numbers(limit: int = 500) -> List[int]:
    """列出 `FRAMEWORK_REPO` 全部 open issue number（mock 攔截點）。

    `--limit` 取遠高於唯讀掃描實測值（69 張）的預設上限，避免日後 issue
    數量成長時被靜默截斷；此為防禦性上界，非仰賴截斷排除雜訊（同
    `search_duplicates` 家族既有取向）。
    """
    result = subprocess.run(
        [
            "gh", "issue", "list", "--repo", FRAMEWORK_REPO,
            "--state", "open", "--limit", str(limit), "--json", "number",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh issue list 失敗")
    return [item["number"] for item in json.loads(result.stdout or "[]")]


def _project_owner_prefix() -> str:
    """本專案 owner 慣例前綴：git 主 repo 目錄名稱 kebab-case 化。

    與 `session-start-issue-check-hook.py` 的 `_project_owner_prefix` 同一
    heuristic（見該檔案頭「owner 識別」說明），本檔獨立實作一份精簡版本
    ——該檔案為 hook 腳本（獨立 PEP 723 shebang），不供其他模組 import；
    重複的是判斷邏輯，非可抽取的共用模組。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).parent.name.replace("_", "-")
    except (subprocess.TimeoutExpired, OSError):
        pass
    return Path.cwd().name.replace("_", "-")


def _cached_comments(issue_number: int, cache: Dict[int, list]) -> list:
    """`todo` 專用的 per-issue comments 快取：同次執行內同一 issue 只呼叫
    一次 `fetch_comments`（候選 owner 驗證與表格聚合共用同一份快取）。
    """
    if issue_number not in cache:
        cache[issue_number] = fetch_comments(str(issue_number))
    return cache[issue_number]


def _search_candidate_issue_numbers(prefix: str) -> List[int]:
    """以 gh search issues 用 owner 前綴粗篩候選 issue（見
    `session-start-issue-check-hook.py` 檔頭「候選發現」說明，同一 query
    組成方式：單一字串觸發同一 comment 實例內的 AND 匹配）。失敗一律回傳
    空清單，`owned_issue_numbers_or_fallback` 的 fail-open 語意延伸至此。
    """
    query = f"owner {prefix}"
    try:
        result = subprocess.run(
            [
                "gh", "search", "issues", "--repo", FRAMEWORK_REPO,
                "--match", "comments", "--json", "number", "--limit", "30",
                "--", query,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return []
        return [hit["number"] for hit in json.loads(result.stdout or "[]")]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        return []


def _discover_owned_issue_numbers_by_prefix(prefix: str) -> List[int]:
    """候選發現 + 本地驗證：僅回傳確認存在 owner 標記以 `<prefix>-` 開頭之
    區段的候選 issue（owned-issues 登記檔缺失/損毀時的 fallback，見
    `owned_issue_numbers_or_fallback`）。"""
    comment_cache: Dict[int, list] = {}
    owned = []
    for number in _search_candidate_issue_numbers(prefix):
        try:
            comments = _cached_comments(number, comment_cache)
        except (OSError, subprocess.SubprocessError, RuntimeError):
            continue
        for comment in comments:
            marker = extract_section_marker(comment.get("body", "") or "")
            if marker and marker["owner"].startswith(f"{prefix}-"):
                owned.append(number)
                break
    return owned


def owned_issue_numbers_or_fallback() -> Tuple[List[int], str]:
    """回傳 `(本 consumer 擁有的 issue number 清單, 判定依據標籤)`。優先讀
    本地擁有登記檔（`owned_issues_registry`，`init`／`update` 成功寫入
    GitHub 後同步落地）；缺失或無法讀取（`None`）時退回 owner 前綴推導。
    """
    numbers = owned_issue_numbers()
    if numbers is not None:
        return numbers, "owned-issues 登記檔"
    prefix = _project_owner_prefix()
    return _discover_owned_issue_numbers_by_prefix(prefix), f"owner 前綴 `{prefix}-`"


def _resolve_todo_targets(all_issues: bool, issue_number: Optional[int]) -> Tuple[List[int], str]:
    """解析 `todo` 的目標 issue 範圍：`--issue` 明確指定時直接信任、不受
    開關狀態限制；`--all` 掃 `FRAMEWORK_REPO` 全部 open issue；預設掃本
    consumer 擁有的 open issue（擁有清單與 open 清單取交集——擁有登記檔
    不記錄開關狀態，需另查）。查 open 清單失敗時只警告降級為未過濾擁有
    清單，不中止整體查詢（唯讀聚合的降級不應阻擋操作者拿到部分結果）。
    """
    if issue_number is not None:
        return [issue_number], f"issue #{issue_number}"
    if all_issues:
        return list_open_issue_numbers(), "全部 open issue"

    owned, label = owned_issue_numbers_or_fallback()
    try:
        open_numbers = set(list_open_issue_numbers())
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        sys.stderr.write(
            f"[framework-issue][警告] 列出 open issue 狀態失敗，"
            f"改列全部擁有 issue（未過濾開關狀態）：{exc}\n"
        )
        return owned, label
    return [number for number in owned if number in open_numbers], label


def _collect_todo_rows(issue_number: int, comment_cache: Dict[int, list]) -> List[dict]:
    """對單一 issue 抓取全部「待辦與來源*」區段的表格列，每列附加 `issue`
    （issue number）與 `owner`（區段首行標記的 owner）兩個聚合欄位。表頭
    不符 `TODO_VALID_HEADERS` 的區段印警告並跳過（不中止其餘區段或 issue
    的聚合，見 acceptance「todo 對表頭不符的區段印警告並繼續」）。
    """
    try:
        comments = _cached_comments(issue_number, comment_cache)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        sys.stderr.write(
            f"[framework-issue][警告] issue #{issue_number} comments 讀取失敗，略過：{exc}\n"
        )
        return []

    rows = []
    for comment in comments:
        marker = extract_section_marker(comment.get("body", "") or "")
        if marker is None or not marker["name"].startswith(TODO_SECTION_NAME_PREFIX):
            continue
        _, _, content = (comment.get("body", "") or "").partition("\n")
        parsed = parse_markdown_table(content)
        if parsed is None or parsed[0] not in TODO_VALID_HEADERS:
            found_header = parsed[0] if parsed else "(找不到表格)"
            sys.stderr.write(
                f"[framework-issue][警告] issue #{issue_number} 區段"
                f"「{marker['name']}」表頭不符，略過：{found_header}\n"
            )
            continue
        header, table_rows = parsed
        for raw_row in table_rows:
            row = dict(zip(header, raw_row))
            row["issue"] = issue_number
            row["owner"] = marker["owner"]
            rows.append(row)
    return rows


def _filter_todo_rows(
    rows: List[dict],
    status: Optional[str],
    stage: Optional[str],
    priority: Optional[str],
    consumer: Optional[str],
) -> List[dict]:
    """依 `--status`／`--stage`／`--priority`／`--consumer` 篩選列（皆選
    填，未提供者不篩）。`--consumer` 比對 owner 前綴（owner 格式為
    `<consumer>-<序號>`，見 `OWNER_FORMAT_RE`）。"""
    def _matches(row: dict) -> bool:
        if status and row.get("狀態") != status:
            return False
        if stage and row.get("階段") != stage:
            return False
        if priority and row.get("優先級") != priority:
            return False
        if consumer and not row.get("owner", "").startswith(f"{consumer}-"):
            return False
        return True

    return [row for row in rows if _matches(row)]


def _sort_todo_rows(rows: List[dict]) -> List[dict]:
    """依優先級排序（`TODO_PRIORITY_ORDER` 由高至低）；未知優先級值排在
    已知值之後，同優先級依 issue number 遞增，保持輸出穩定可重現。"""
    def _key(row: dict) -> tuple:
        priority = row.get("優先級", "")
        rank = (
            TODO_PRIORITY_ORDER.index(priority)
            if priority in TODO_PRIORITY_ORDER
            else len(TODO_PRIORITY_ORDER)
        )
        return (rank, row.get("issue", 0))

    return sorted(rows, key=_key)


def render_todo_report(target_count: int, label: str, rows: List[dict]) -> str:
    """組合 `todo` 的純文字輸出：範圍摘要一行 + 逐列摘要。"""
    lines = [
        f"[framework-issue] todo（範圍：{label}，{target_count} 張 issue，{len(rows)} 列）",
        "",
    ]
    if not rows:
        lines.append("無待辦列")
        return "\n".join(lines) + "\n"
    for row in rows:
        type_suffix = f"｜型別={row['型別']}" if row.get("型別") else ""
        lines.append(
            f"- #{row.get('issue')} [{row.get('優先級', '?')}][{row.get('階段', '?')}]"
            f"[{row.get('狀態', '?')}] owner={row.get('owner', '?')} "
            f"來源票={row.get('來源票', '?')} "
            f"acceptance={row.get('acceptance 條數', '?')} "
            f"— {row.get('做什麼', '')}{type_suffix}"
        )
    return "\n".join(lines) + "\n"


def cmd_todo(
    all_issues: bool = False,
    issue_number: Optional[int] = None,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    priority: Optional[str] = None,
    consumer: Optional[str] = None,
    as_json: bool = False,
) -> int:
    """唯讀：跨 open issue 聚合「待辦與來源*」區段表格列。"""
    try:
        target_numbers, label = _resolve_todo_targets(all_issues, issue_number)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return emit_degraded(f"todo 目標範圍解析失敗：{exc}", "確認 gh 可存取後重試")

    comment_cache: Dict[int, list] = {}
    rows: List[dict] = []
    for number in target_numbers:
        rows.extend(_collect_todo_rows(number, comment_cache))

    rows = _sort_todo_rows(_filter_todo_rows(rows, status, stage, priority, consumer))

    if as_json:
        sys.stdout.write(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_todo_report(len(target_numbers), label, rows))
    return 0


# --keywords／--dedup-keywords 收值階段中，遇到這些已知旗標字串即停止收集
# （見 _escape_dash_prefixed_keyword_values）；集合僅列本檔實際註冊的旗標。
_KEYWORD_VALUE_STOP_FLAGS = frozenset(
    {
        "-h", "--help", "--owner", "--sections-file", "--content-file",
        "--summary", "--session", "--comment-threshold", "--stale-days",
        "--name", "--to", "--force",
    }
)
_MULTI_VALUE_KEYWORD_FLAGS = frozenset({"--keywords", "--dedup-keywords"})
# 不可見前綴，逃脫 argparse 的「看似選項」啟發式後於 main() 內還原。
_DASH_VALUE_ESCAPE = "\x00literal-dash\x00"


def _escape_dash_prefixed_keyword_values(argv: list) -> list:
    """讓 `--keywords`／`--dedup-keywords` 的值可含無空白、以 `-` 開頭的
    token（如 "-a"、"--force"）。

    argparse 對 `nargs='+'` 的貪婪收值仰賴「看起來像選項」啟發式：任一無
    空白且以 `-` 開頭的 token 一律視為新選項起點（CPython bpo-9334），純值
    語意的 "--force" 因而在 argparse 層即被拒為 unrecognized arguments，
    早於 `search_issues_by_keyword` 的 gh 呼叫修正之前就先失敗，兩者是各自
    獨立的擋點。收值階段中非已知旗標字串的 `-` 開頭 token 一律加不可見
    前綴繞過此啟發式；收值結束（遇已知旗標）後不再加註記，`main()` 解析
    完成後以 `_unescape_dash_prefixed_value` 逐一還原。
    """
    escaped = []
    consuming = False
    for token in argv:
        if token in _MULTI_VALUE_KEYWORD_FLAGS:
            consuming = True
            escaped.append(token)
            continue
        if token in _KEYWORD_VALUE_STOP_FLAGS:
            consuming = False
        elif consuming and token.startswith("-"):
            escaped.append(_DASH_VALUE_ESCAPE + token)
            continue
        escaped.append(token)
    return escaped


def _unescape_dash_prefixed_value(value: str) -> str:
    """還原 `_escape_dash_prefixed_keyword_values` 加上的不可見前綴。"""
    if value.startswith(_DASH_VALUE_ESCAPE):
        return value[len(_DASH_VALUE_ESCAPE):]
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framework-issue section",
        description="comment-as-section 協作協定的寫入路徑（init/add/update/transfer-owner/observe）",
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
    p_init.add_argument(
        "--force", action="store_true",
        help="issue 已有區段 comment 時仍執行 init（與既有索引列合併，不覆寫既有 owner 的區段）",
    )

    p_add = sub.add_parser(
        "add", help="建立單一區段 comment，於既有索引表追加一列（不存在索引表時建立）"
    )
    p_add.add_argument("issue_ref", help="framework issue ref（如 tarrragon/claude#81 或純號 81）")
    p_add.add_argument("--owner", required=True, help="區段建立者/維護者 session 識別")
    p_add.add_argument("--name", required=True, help="區段名稱")
    p_add.add_argument("--content-file", required=True, help="區段內容檔（不含首行標記）")

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

    p_transfer = sub.add_parser(
        "transfer-owner", help="PATCH 既有區段 comment 首行標記的 owner 欄，內容不變"
    )
    p_transfer.add_argument("comment_id", help="區段 comment 的 GitHub comment id")
    p_transfer.add_argument("--to", required=True, help="新 owner 識別")

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

    p_todo = sub.add_parser(
        "todo",
        help="唯讀：跨 open issue 聚合「待辦與來源*」區段表格列（預設掃本 consumer 擁有的 open issue）",
    )
    todo_scope = p_todo.add_mutually_exclusive_group()
    todo_scope.add_argument(
        "--all", action="store_true",
        help=f"掃 {FRAMEWORK_REPO} 全部 open issue（非僅本 consumer 擁有）",
    )
    todo_scope.add_argument("--issue", type=int, dest="issue_number", help="只掃描單一 issue number")
    p_todo.add_argument("--status", help=f"只列此狀態值（合法值：{TODO_STATUS_VALUES}）")
    p_todo.add_argument("--stage", help=f"只列此階段值（合法值：{TODO_STAGE_VALUES}）")
    p_todo.add_argument("--priority", help="只列此優先級值（如 P0/P1/P2/P3）")
    p_todo.add_argument("--consumer", help="只列 owner 前綴符合此 consumer 的列")
    p_todo.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 陣列輸出")

    return parser


def main(argv=None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parsed = build_parser().parse_args(_escape_dash_prefixed_keyword_values(raw_argv))

    gate = preflight()
    if gate != 0:
        return gate

    if parsed.command == "init":
        return cmd_init(
            parsed.issue_ref, parsed.owner, parsed.sections_file,
            [_unescape_dash_prefixed_value(k) for k in parsed.dedup_keywords],
            force=parsed.force,
        )
    if parsed.command == "add":
        return cmd_add(parsed.issue_ref, parsed.owner, parsed.name, parsed.content_file)
    if parsed.command == "dedup":
        return cmd_dedup([_unescape_dash_prefixed_value(k) for k in parsed.keywords])
    if parsed.command == "update":
        return cmd_update(parsed.comment_id, parsed.content_file)
    if parsed.command == "transfer-owner":
        return cmd_transfer_owner(parsed.comment_id, parsed.to)
    if parsed.command == "observe":
        return cmd_observe(parsed.issue_ref, parsed.summary, parsed.session, parsed.content_file)
    if parsed.command == "show":
        return cmd_show(parsed.issue_ref)
    if parsed.command == "todo":
        return cmd_todo(
            all_issues=parsed.all,
            issue_number=parsed.issue_number,
            status=parsed.status,
            stage=parsed.stage,
            priority=parsed.priority,
            consumer=parsed.consumer,
            as_json=parsed.as_json,
        )
    return cmd_check(parsed.issue_ref, parsed.comment_threshold, parsed.stale_days)


if __name__ == "__main__":
    sys.exit(main())
