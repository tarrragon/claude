#!/usr/bin/env python3
"""spec validate 的 API surface 完整性檢核：FR 段落提及 API 行為卻缺 endpoint 路徑定義時列出提醒。

背景：0.4.1-W1-001 檢討發現 SPEC-014 FR-04 曾寫「analytics API 回 501」卻無 endpoint
路徑定義，缺口到派發實作才暴露（F5）。本檢核作為 /spec validate Layer 1 的擴充規則，
在規格撰寫階段機械性掃描此類缺口。
"""

import argparse
import re
import sys
from pathlib import Path

FR_HEADER_RE = re.compile(r"^### (FR-\d+):.*$", re.MULTILINE)
PATH_RE = re.compile(r"/v1/[A-Za-z0-9_/{}=&,:.\-]*")
SUBJECT_BEFORE_RE = re.compile(r"([A-Za-z][\w-]*)\s+(?:API|api|endpoint)")
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

# 自足訊號：本身即代表「描述 API 行為」，不需搭配其他詞
SELF_SUFFICIENT_SIGNAL_RE = re.compile(r"endpoint|API.{0,8}回", re.IGNORECASE)
# 動詞 / status code 訊號常與 SQL（DELETE FROM ...）或一般傳輸層敘述混用，
# 需搭配 API/端點 上下文才視為 HTTP 行為描述，避免誤判 SQL 語句或籠統敘述
HTTP_VERB_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\b|status code", re.IGNORECASE)
API_CONTEXT_RE = re.compile(r"API|端點", re.IGNORECASE)
# 表格欄位標題「Endpoint」或「endpoint 路徑」小節標籤本身是路徑定義的引導語，非缺口
TABLE_HEADER_ENDPOINT_RE = re.compile(r"\|\s*endpoint\s*\|", re.IGNORECASE)
ENDPOINT_INTRO_RE = re.compile(r"endpoint\s*路徑", re.IGNORECASE)


def split_fr_sections(spec_text):
    """依 `### FR-XX:` 標題切出各功能需求段落，回傳 (fr_id, 段落內容) 清單。"""
    headers = list(FR_HEADER_RE.finditer(spec_text))
    sections = []
    for idx, header in enumerate(headers):
        start = header.start()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(spec_text)
        sections.append((header.group(1), spec_text[start:end]))
    return sections


def extract_subject(line):
    """取「API」或「endpoint」前緊鄰的英文識別字，作為比對 endpoint 路徑的主題詞。"""
    match = SUBJECT_BEFORE_RE.search(line)
    return match.group(1).lower() if match else None


def is_signal_line(line):
    """判斷該行是否為「描述 API 行為」的訊號行（排除標題、表格標題與路徑定義引導語）。"""
    if line.lstrip().startswith("#"):
        return False
    if TABLE_HEADER_ENDPOINT_RE.search(line) or ENDPOINT_INTRO_RE.search(line):
        return False
    if SELF_SUFFICIENT_SIGNAL_RE.search(line):
        return True
    return bool(HTTP_VERB_RE.search(line) and API_CONTEXT_RE.search(line))


def check_api_surface(spec_text):
    """掃描每個 FR 段落，回傳提及 API 行為卻無對應 endpoint 路徑定義的行清單。

    每筆缺口為 {"fr_id": str, "line": str}。判定邏輯：
    - 程式碼區塊（```...```）與行內程式碼（`...`）不參與訊號掃描（避免 SQL/識別字誤判），
      但其中出現的路徑仍計入段落已定義路徑（比對用原始段落文字，非去除程式碼後的版本）
    - 標題行（`#` 開頭）不參與掃描
    - 訊號行本身已含 `/v1/...` 路徑 → 視為完整定義，略過
    - 訊號行有主題詞（如 analytics）且該詞出現於段落內任一路徑 → 視為段落已定義，略過
    - 其餘（含無主題詞可比對者）→ 列為缺口
    """
    findings = []
    for fr_id, section in split_fr_sections(spec_text):
        section_paths = " ".join(PATH_RE.findall(section)).lower()
        prose = CODE_BLOCK_RE.sub("", section)
        prose = INLINE_CODE_RE.sub("", prose)
        for line in prose.splitlines():
            if not is_signal_line(line):
                continue
            if PATH_RE.search(line):
                continue
            subject = extract_subject(line)
            if subject and subject in section_paths:
                continue
            findings.append({"fr_id": fr_id, "line": line.strip()})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="spec check-api-surface",
        description="檢查 spec 文件 FR 段落是否有 API 行為缺 endpoint 路徑定義",
    )
    parser.add_argument("spec_path", help="Spec 文件路徑")
    args = parser.parse_args(argv)

    spec_text = Path(args.spec_path).read_text(encoding="utf-8")
    findings = check_api_surface(spec_text)

    if not findings:
        print("API surface 檢核通過：所有提及 API 行為的段落皆有對應 endpoint 路徑定義")
        return 0

    print(f"API surface 檢核發現 {len(findings)} 處缺口：")
    for finding in findings:
        print(f"  [{finding['fr_id']}] {finding['line']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
