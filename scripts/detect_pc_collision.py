#!/usr/bin/env python3
"""PC 碰撞偵測腳本（1.0.0-W1-022，正式化自 W1-019.5 prototype）。

跨專案共享 repo 知識庫（.claude/error-patterns/）因各專案獨立累加 error-pattern
編號，會在 round-trip sync 時產生碰撞。本腳本對單一專案的 error-patterns 目錄掃描，
偵測三軸碰撞並輸出可執行清單，供各專案本地端 / CI / sync-pull gate 使用。

三偵測軸：
  1. 同號異義（same number, different meaning）
     同一 (CAT, prefix, NNN) 對應 2+ 不同 slug → 同編號指不同教訓，編號完整性受威脅。
  2. 同 slug 異號（same slug, different number）
     同一 (CAT, slug) 出現於 2+ 不同編號 → 同一 pattern 被重複收錄為不同號。
  3. 異號同義（different number, same content）
     不同編號的檔案內容雷同（正規化首行去除編號差異後雜湊相同）→ 疑似重複匯入。

content-hash 軸刻意不複用 sync_exclude_manifest.compute_content_hash：後者是「整目錄」
雜湊（產生單一目錄指紋），不適合 per-file 兩兩比對。本腳本改用 per-file sha256，且
雜湊前正規化首行（去除 PC-NNN 編號字面），才能偵測「僅編號不同、內容相同」。

exit code：0 = 無碰撞 / 1 = 任一軸偵出碰撞（CI / gate 友善）。

使用：
  python3 .claude/scripts/detect_pc_collision.py [error-patterns 目錄]
  （省略參數時預設為 cwd 下的 .claude/error-patterns/）
"""
from __future__ import annotations

import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

# 檔名格式：<CAT>-<NNN>-slug.md 或 <CAT>-<PROJ>-<NNN>-slug.md
# group: CAT / 選填 PROJ 前綴 / NNN / slug
_FILENAME_RE = re.compile(r"^([A-Z]+)(?:-([A-Z0-9]+))?-(\d+)-(.+)\.md$")

# 正規化首行時用來剝除編號字面（如 PC-165 / ARCH-V1-010），避免「僅編號不同」干擾內容雜湊
_NUMBER_TOKEN_RE = re.compile(r"\b[A-Z]+(?:-[A-Z0-9]+)?-\d+\b")


def parse_filename(name: str) -> tuple[str, str | None, str, str] | None:
    """解析 error-pattern 檔名，回傳 (CAT, prefix, num, slug)；不符格式回 None。

    prefix 為選填的專案前綴（如 V1 / APP），flat 格式時為 None。
    """
    m = _FILENAME_RE.match(name)
    if not m:
        return None
    cat, prefix, num, slug = m.groups()
    return cat, prefix, num, slug


def _normalize_first_line(text: str) -> str:
    """正規化內容用於雜湊：剝除首行的編號字面，使「僅編號不同」的雷同檔產生相同雜湊。

    僅針對首行（id/標題慣例承載編號）做剝除，其餘內容原樣保留以避免誤判。
    """
    lines = text.split("\n", 1)
    first = _NUMBER_TOKEN_RE.sub("", lines[0])
    rest = lines[1] if len(lines) > 1 else ""
    return first + ("\n" + rest if len(lines) > 1 else "")


def compute_file_content_hash(path: Path) -> str:
    """計算單一檔案的內容雜湊（正規化首行去除編號差異後 sha256）。

    刻意不複用 sync_exclude_manifest.compute_content_hash（整目錄雜湊，不適合 per-file 比對）。
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = _normalize_first_line(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _num_key_str(cat: str, prefix: str | None, num: str) -> str:
    """組出人類可讀的編號鍵（如 PC-010 或 PC-V1-001）。"""
    pfx = f"{prefix}-" if prefix else ""
    return f"{cat}-{pfx}{num}"


def scan(epdir: Path) -> dict:
    """掃描 error-patterns 目錄，回傳三軸碰撞結果。

    回傳結構：
      {
        "total": int,                       # 解析成功的檔案數
        "same_number": [(num_key, [slug...]), ...],     # 軸 1
        "same_slug": [((cat, slug), [num_key...]), ...], # 軸 2
        "same_content": [(content_hash, [num_key...]), ...], # 軸 3
      }
    所有清單已排序，方便穩定輸出與測試斷言。
    """
    by_num: dict[tuple[str, str | None, str], list[str]] = defaultdict(list)
    by_slug: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_content: dict[str, list[str]] = defaultdict(list)

    total = 0
    for f in sorted(epdir.rglob("*.md")):
        if not f.is_file():
            continue
        parsed = parse_filename(f.name)
        if parsed is None:
            continue
        total += 1
        cat, prefix, num, slug = parsed
        num_key = _num_key_str(cat, prefix, num)
        by_num[(cat, prefix, num)].append(slug)
        by_slug[(cat, slug)].append(num_key)
        by_content[compute_file_content_hash(f)].append(num_key)

    same_number = [
        (_num_key_str(cat, prefix, num), sorted(set(slugs)))
        for (cat, prefix, num), slugs in by_num.items()
        if len(set(slugs)) > 1
    ]
    same_slug = [
        ((cat, slug), sorted(set(nums)))
        for (cat, slug), nums in by_slug.items()
        if len(set(nums)) > 1
    ]
    same_content = [
        (chash, sorted(set(nums)))
        for chash, nums in by_content.items()
        if len(set(nums)) > 1
    ]

    return {
        "total": total,
        "same_number": sorted(same_number),
        "same_slug": sorted(same_slug),
        "same_content": sorted(same_content),
    }


def has_collision(result: dict) -> bool:
    """三軸任一非空即視為有碰撞。"""
    return bool(
        result["same_number"] or result["same_slug"] or result["same_content"]
    )


def format_report(epdir: Path, result: dict) -> str:
    """產出三類可執行清單的人類可讀報告。"""
    lines: list[str] = []
    lines.append(f"===== PC 碰撞偵測：{epdir} =====")
    lines.append(f"  解析檔案數: {result['total']}")

    lines.append(f"  [軸 1 同號異義] {len(result['same_number'])} 組:")
    for num_key, slugs in result["same_number"]:
        lines.append(f"    {num_key}: {slugs}")

    lines.append(f"  [軸 2 同 slug 異號] {len(result['same_slug'])} 組:")
    for (cat, slug), nums in result["same_slug"]:
        lines.append(f"    {cat} '{slug[:40]}': {nums}")

    lines.append(f"  [軸 3 異號同義] {len(result['same_content'])} 組:")
    for chash, nums in result["same_content"]:
        lines.append(f"    {chash[:12]}: {nums}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：掃描指定（或預設）error-patterns 目錄並輸出報告。

    回傳 exit code：0 = 無碰撞 / 1 = 有碰撞 / 2 = 目錄不存在。
    """
    args = sys.argv[1:] if argv is None else argv
    if args:
        epdir = Path(args[0])
    else:
        epdir = Path.cwd() / ".claude" / "error-patterns"

    if not epdir.exists():
        sys.stderr.write(f"[ERROR] 目錄不存在: {epdir}\n")
        return 2

    result = scan(epdir)
    print(format_report(epdir, result))

    if has_collision(result):
        print("\n[FAIL] 偵出碰撞，請依上列清單 remediation（exit 1）")
        return 1
    print("\n[OK] 無碰撞（exit 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
