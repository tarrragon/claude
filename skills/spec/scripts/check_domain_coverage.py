#!/usr/bin/env python3
"""spec validate 的 domain 覆蓋閘門：spec 的每個 FR 是否都被 domain map 的 FR->bundle 覆蓋表歸屬。

背景：0.1.0-W2-016 檢討發現 domain 規劃缺口——spec 定義 FR、UC 定義場景，但無 domain
bundle 邊界；且 spec FR 是否全數映射到某 bundle 缺工具強制（W2-014 靠人工四視角審查才
抓出 FR-25/26 漏覆蓋）。本檢核作為 /spec validate Layer 1 的擴充規則，機械掃描：
  1. spec 對應的 domain map 是否存在
  2. spec 每個 FR 是否出現在 domain map 的 FR 覆蓋（含標為 presentation/data 的非 domain FR）

domain map 定位：預設找 spec 同目錄的 domain-map.md，退化找 docs/domain-map.md。
"""

import argparse
import re
import sys
from pathlib import Path

# FR 標題容許 H3 以上任一層級（### / #### …）——真實 spec 常用 #### FR-XX:，
# 只認 H3 會使 extract_spec_frs 回空集、gate 靜默假通過（Round 2-C 實證）。
FR_HEADER_RE = re.compile(r"^#{3,}\s+(FR-\d+):", re.MULTILINE)
# 展開 FR token：FR-NN、逗號續列 FR-01,02,03、範圍 FR-13~17 / FR-13-17
FR_TOKEN_RE = re.compile(r"FR-(\d+)((?:\s*[~\-,]\s*\d+)*)")


def _expand_fr_token(head_num, tail):
    """展開單一 FR token 為 int 集合。head_num=起始號，tail=續列/範圍字串。"""
    nums = {int(head_num)}
    prev = int(head_num)
    for op, digits in re.findall(r"([~\-,])\s*(\d+)", tail):
        n = int(digits)
        if op == ",":
            nums.add(n)
            prev = n
        else:  # ~ 或 - 視為範圍
            for v in range(min(prev, n), max(prev, n) + 1):
                nums.add(v)
            prev = n
    return nums


def extract_fr_ids(text):
    """從文字抽出所有 FR 編號（int 集合），處理逗號續列與範圍。"""
    ids = set()
    for head, tail in FR_TOKEN_RE.findall(text):
        ids |= _expand_fr_token(head, tail)
    return ids


def extract_spec_frs(spec_text):
    """從 spec 的 `### FR-XX:` 標題抽出定義的 FR 編號（int 集合）。"""
    return {int(m.group(1).split("-")[1]) for m in FR_HEADER_RE.finditer(spec_text)}


def check_domain_coverage(spec_text, domain_map_text):
    """回傳 spec 定義但 domain map 未覆蓋的 FR 編號（排序 list）。"""
    spec_frs = extract_spec_frs(spec_text)
    covered = extract_fr_ids(domain_map_text)
    return sorted(spec_frs - covered)


def locate_domain_map(spec_path, explicit):
    """定位 domain map：優先 explicit，其次 spec 同目錄，最後 docs/domain-map.md。"""
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    same_dir = spec_path.parent / "domain-map.md"
    if same_dir.exists():
        return same_dir
    fallback = Path("docs/domain-map.md")
    return fallback if fallback.exists() else None


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="spec check-domain-coverage",
        description="檢查 spec 的每個 FR 是否被 domain map 的 FR->bundle 覆蓋表歸屬",
    )
    parser.add_argument("spec_path", help="Spec 文件路徑")
    parser.add_argument("--domain-map", help="domain map 路徑（省略則自動定位）")
    args = parser.parse_args(argv)

    spec_path = Path(args.spec_path)
    spec_text = spec_path.read_text(encoding="utf-8")

    domain_map_path = locate_domain_map(spec_path, args.domain_map)
    if domain_map_path is None:
        print(
            "domain 覆蓋檢核：找不到 domain map（spec 同目錄 domain-map.md 或 "
            "docs/domain-map.md）。依 version-bootstrap Step 2.5，規劃波應先產出 domain map。"
        )
        return 1

    uncovered = check_domain_coverage(spec_text, domain_map_path.read_text(encoding="utf-8"))
    if not uncovered:
        print(f"domain 覆蓋檢核通過：spec 全部 FR 皆在 {domain_map_path} 有 bundle 歸屬")
        return 0

    print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在 domain map 覆蓋：")
    for fr in uncovered:
        print(f"  FR-{fr:02d}")
    print(f"（domain map：{domain_map_path}）請於 domain map §7 FR->bundle 覆蓋表補上歸屬。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
