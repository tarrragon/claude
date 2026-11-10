#!/usr/bin/env python3
"""error-pattern 內容相似度掃描（補 detect_pc_collision.py 軸 2 的判準邊界）。  # i18n-exempt

detect_pc_collision.py 軸 2「同 slug 異號」僅能抓到「重編號時 slug 未變」的孤兒重複
（如 ARCH-010/ARCH-021：兩檔案名 slug 皆為 module-assembly-omission）。若孤兒重複在
重編號時「同時改了 slug」，軸 2 的等值比對會漏檢——這正是本腳本要補的判準。

方法：對同一 category 內的檔案兩兩比較
  1. 標題相似度：首行標題（去除編號字面後）用 difflib.SequenceMatcher 算 ratio
  2. 內文詞彙相似度：全文（去除編號字面、frontmatter 分隔線、標點）轉小寫分詞後，
     以 Jaccard 相似度（交集/聯集）比較兩檔案的詞彙集合

兩指標皆為「候選值」而非「判定值」——本腳本只負責產出候選清單，真偽仍需人工比對
兩份檔案的實際文字內容（症狀/根因段落是否描述同一件事）。

已知判準邊界（必須在報告中同步揭露，不可宣稱全面）：
  - 詞彙 Jaccard 對「同根因不同表現」「刻意拆分的姊妹模式」一樣會給高分——這兩者
    命中但不是孤兒重複，需人工排除。
  - 對高度模板化的段落（如「相關文件」「Last Updated」等公版收尾）會拉高相似度，
    可能製造假陽性；本腳本已排除常見版頭/版尾樣板行以降低雜訊，但無法完全消除。
  - 僅比較「同 category 內」的檔案對，跨 category 的孤兒重複（如某教訓從
    process-compliance 挪到 architecture）不在本腳本掃描範圍內。

輸出：依相似度分數降冪列出候選配對，供人工逐一確認。
"""  # i18n-exempt
from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path

_FILENAME_RE = re.compile(r"^([A-Z]+)(?:-([A-Z0-9]+))?-(\d+)-(.+)\.md$")
_NUMBER_TOKEN_RE = re.compile(r"\b[A-Z]+(?:-[A-Z0-9]+)?-\d+\b")
_WORD_RE = re.compile(r"[a-zA-Z0-9一-鿿]+")  # i18n-exempt: 分詞正規表達式，非文案

# 公版樣板行字首清單（非 user-facing 字串，供內部比對用）  # i18n-exempt
_BOILERPLATE_PATTERNS = (
    "last updated",
    "version",
    "相關文件",  # i18n-exempt
    "來源",  # i18n-exempt
    "source",
    "---",
)


def parse_filename(name: str) -> tuple[str, str | None, str, str] | None:
    m = _FILENAME_RE.match(name)
    if not m:
        return None
    return m.groups()


_FRONTMATTER_TITLE_RE = re.compile(r"^title:\s*(.+)$")
_H1_HEADING_RE = re.compile(r"^#\s+[A-Z]+(?:-[A-Z0-9]+)?-\d+\s*:\s*(.+)$")


def extract_title(text: str) -> str:
    # 標題來源優先序：YAML frontmatter title 欄位 > 符合「# CAT-NNN: 標題」格式的 H1 行。  # i18n-exempt
    # 兩者皆缺（如 IMP-MON-003 只有程式碼範例註解的裸 "# " 行）則回傳空字串，避免誤把
    # 「## 症狀」這類各檔共有的區段標題，或程式碼註解裡的 "# 錯誤：" 誤判為檔案標題。
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            m = _FRONTMATTER_TITLE_RE.match(line.strip())
            if m:
                return _NUMBER_TOKEN_RE.sub("", m.group(1)).strip()
    for line in lines:
        m = _H1_HEADING_RE.match(line.strip())
        if m:
            return _NUMBER_TOKEN_RE.sub("", m.group(1)).strip()
    return ""


def extract_wordset(text: str) -> set[str]:
    # 全文正規化後轉詞彙集合，剔除編號字面與公版樣板行  # i18n-exempt
    kept_lines = []
    for line in text.split("\n"):
        low = line.strip().lower()
        if not low:
            continue
        if any(low.startswith(p) for p in _BOILERPLATE_PATTERNS):
            continue
        kept_lines.append(line)
    body = _NUMBER_TOKEN_RE.sub("", "\n".join(kept_lines))
    words = _WORD_RE.findall(body.lower())
    # 濾除長度 1 的雜訊 token（多為標點殘留或單一數字）
    return {w for w in words if len(w) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def scan(epdir: Path, title_threshold: float, jaccard_threshold: float) -> list[tuple]:
    by_category: dict[str, list[tuple[str, str, str, set[str], str]]] = {}
    for f in sorted(epdir.rglob("*.md")):
        if not f.is_file():
            continue
        parsed = parse_filename(f.name)
        if parsed is None:
            continue
        cat, prefix, num, slug = parsed
        text = f.read_text(encoding="utf-8", errors="replace")
        num_key = f"{cat}-{prefix + '-' if prefix else ''}{num}"
        title = extract_title(text)
        wordset = extract_wordset(text)
        by_category.setdefault(cat, []).append((num_key, slug, title, wordset, f.name))

    candidates = []
    for cat, entries in by_category.items():
        for (num_a, slug_a, title_a, words_a, fname_a), (num_b, slug_b, title_b, words_b, fname_b) in combinations(
            entries, 2
        ):
            if num_a == num_b:
                continue
            # 任一方標題缺失時不計 title_sim（避免兩個空字串比對得 1.0 假陽性）
            title_sim = SequenceMatcher(None, title_a, title_b).ratio() if title_a and title_b else 0.0
            word_sim = jaccard(words_a, words_b)
            if title_sim >= title_threshold or word_sim >= jaccard_threshold:
                candidates.append((cat, num_a, fname_a, num_b, fname_b, title_sim, word_sim, slug_a == slug_b))

    candidates.sort(key=lambda c: max(c[5], c[6]), reverse=True)
    return candidates


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    epdir = Path(args[0]) if args else Path.cwd() / ".claude" / "error-patterns"
    if not epdir.exists():
        sys.stderr.write(f"[ERROR] directory not found: {epdir}\n")
        return 2

    title_threshold = 0.55
    jaccard_threshold = 0.35
    candidates = scan(epdir, title_threshold, jaccard_threshold)

    print(f"===== content similarity scan: {epdir} =====")
    print(f"  threshold: title_sim >= {title_threshold} or word_jaccard >= {jaccard_threshold}")
    print(f"  candidate pairs: {len(candidates)}\n")
    for cat, num_a, fname_a, num_b, fname_b, title_sim, word_sim, same_slug in candidates:
        flag = " [same-slug, axis2-covered]" if same_slug else ""
        print(f"  [{cat}] {num_a} <-> {num_b}  title_sim={title_sim:.2f} word_jaccard={word_sim:.2f}{flag}")
        print(f"      {fname_a}")
        print(f"      {fname_b}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
