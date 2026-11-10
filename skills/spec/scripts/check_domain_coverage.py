#!/usr/bin/env python3
"""spec validate 的 domain 覆蓋閘門：spec 的每個 FR 是否都被 domain map 的 FR->bundle 覆蓋表歸屬。

背景：一次架構檢討發現 domain 規劃缺口——spec 定義 FR、UC 定義場景，但無 domain
bundle 邊界；且 spec FR 是否全數映射到某 bundle 缺工具強制（曾靠人工四視角審查才
抓出漏覆蓋的 FR）。本檢核作為 /spec validate Layer 1 的擴充規則，機械掃描：
  1. spec 對應的 domain map 是否存在
  2. spec 每個 FR 是否出現在 domain map 的 FR 覆蓋（含標為 presentation/data 的非 domain FR）

domain map 定位鏈：--domain-map 明示（唯一來源，不聯集）-> spec 同目錄 domain-map.md
與 docs/spec/*/domain-map.md 中 frontmatter source_specs 含本 SPEC id 者（同目錄為聯集
成員之一，並聯集 docs/system-layer.md；逐檔解析後於集合層合併）-> docs/domain-map.md。

另含可選檢核「事件流標定」（`--check-event-flow-labeling`）：spec 的 FR 段落若命中
事件流訊號詞（清單見 EVENT_FLOW_SIGNAL_WORDS，與 /spec validate Layer 2 維度 5「資源
競爭」共用同一份訊號詞，見 SKILL.md 維度 5 掃描說明），該 FR 須能在 domain map 的
「通道與協調圖」節（以標題文字定位，不依編號——章節編號在各專案可能已被既有內容
佔用）之「到達類別與級別實例」子表中找到對應的 FR 引用，缺者列為提醒，非阻擋。

實作依職責拆在 domain_coverage/ 套件（fr_extract／attribution／event_flow／map_locate）；
本檔保留 CLI 入口、報告輸出，並 re-export 原有名稱，既有 import 路徑不變。
"""

import argparse
import sys
from pathlib import Path

# 以下為相容 re-export（含底線開頭的內部名稱，維持原匯入路徑可用）。
from domain_coverage.attribution import (  # noqa: F401
    HEADING_RE, _ParsedMap, _line_fr_owners, _merged_attribution, _parse_maps, _uncovered_frs,
    check_domain_coverage_union, check_layer_coverage, describe_attribution_remedy,
    describe_default_assigned, extract_fr_attribution, warn_unattributed_uncovered,
)
from domain_coverage.event_flow import (  # noqa: F401
    ARRIVAL_LEVEL_TABLE_TITLE_RE, CHANNEL_SECTION_TITLE_RE, EVENT_FLOW_SIGNAL_WORDS,
    _extract_section_by_title, check_event_flow_labeling, check_event_flow_labeling_union,
    extract_arrival_level_table, extract_channel_section, extract_event_signaled_frs,
)
from domain_coverage.fr_extract import (  # noqa: F401
    DECLARATION_KEY, DECLARATION_LINE_RE, EXPECTED_HEADING_HINT, FENCE_OPEN_RE,
    FR_HEADER_RE, FR_LIKE_ATX_RE, FR_LIKE_SETEXT_TEXT_RE, FR_LIKE_STRONG_RE, FR_TOKEN_RE,
    FRONTMATTER_BLOCK_RE, FRONTMATTER_ID_LINE_RE, SETEXT_UNDERLINE_RE, SPEC_ID_RE,
    TOP_KEY_LINE_RE, _code_span_end, _declaration_occurrences, _expand_fr_token, _fence_closes,
    _fence_open, _fr_like_number, _frontmatter_line_count, _mask_fenced_blocks,
    _mask_html_comments, _scan_text, _unclosed_quote, extract_fr_ids, extract_spec_frs,
    extract_spec_id, find_skipped_fr_lines, find_unextracted_fr_lines, fr_like_lines,
    mask_fenced_blocks, read_fr_declaration,
)
from domain_coverage.map_locate import (  # noqa: F401
    BLOCK_ITEM_RE, DOMAIN_FIELD_RE, DOMAIN_MAP_GLOB_DIR, DOMAIN_NOT_SINGLE_NAME_RE,
    ID_UNRECOGNIZED_CAUSE, LEGACY_DOMAIN_FIELD_RE, LEGACY_DOMAIN_MAP_PATH, REASON_EXPLICIT_MISSING,
    REASON_ID_UNRECOGNIZED, REASON_NO_MAP, REASON_NOT_LISTED, REASON_SOURCE_SPECS_UNPARSEABLE,
    SOURCE_SPECS_KEY_RE, SYSTEM_LAYER_PATH, TRAILING_COMMENT_RE, YAML_NULL_LITERALS,
    _declared_domains, _diagnose_missing, _frontmatter_domain, _list_domain_maps,
    _map_frontmatter_domain, _parse_source_specs, _read_maps, _scan_listing_maps,
    _unlisted_unparseable, _unquote_domain, describe_layer_id_unrecognized,
    describe_missing_map, describe_missing_system_layer, domain_format_error, is_layer_spec,
    layer_banner, locate_domain_maps, locate_domain_maps_with_reason, warn_unparseable_maps,
)


def judge_fr_declaration(spec_text):
    """於 domain map 定位之前判定。回傳 exit code（已結束）或 None（續行覆蓋比對）。"""
    try:
        declared = read_fr_declaration(spec_text)
    except ValueError as exc:
        print(f"domain 覆蓋檢核失敗：{exc}")
        return 1
    for no, line in find_skipped_fr_lines(spec_text):
        sys.stderr.write(f"WARNING: 第 {no} 行形似 FR 定義但位於被略過的區段（圍欄程式碼區塊或 HTML 註解）內，不納入比對：{line}\n")
    extracted = extract_spec_frs(spec_text)
    if declared is False:
        loose = fr_like_lines(spec_text)
        if extracted or loose:
            print(f"domain 覆蓋檢核失敗：宣告 {DECLARATION_KEY}: false，但內容存在 FR 標題行（宣告與內容矛盾）：")
            for no, line, _ in loose:
                print(f"  第 {no} 行：{line}")
            return 1
        print(f"本 SPEC 宣告無 FR（{DECLARATION_KEY}: false），未執行覆蓋比對")
        return 0
    if not extracted:
        print("domain 覆蓋檢核失敗：未宣告無 FR，但未抽到任何 FR 標題（未執行覆蓋比對）。")
        print(EXPECTED_HEADING_HINT)
        return 1
    for no, line in find_unextracted_fr_lines(spec_text):
        sys.stderr.write(f"WARNING: 第 {no} 行形似 FR 定義但未被抽出（不納入比對）：{line}\n")
    return None


def _report_domain_coverage(spec_text, domain_map_paths, spec_path=None, layer_mode=False):
    """列印 FR->bundle 覆蓋檢核結果，回傳 exit code。"""
    domain_map_path = ", ".join(str(p) for p in domain_map_paths)
    named_texts = _read_maps(domain_map_paths)
    if layer_mode:
        uncovered = check_layer_coverage(spec_text, named_texts[0][1], spec_path)
    else:
        parsed_maps = _parse_maps(named_texts)
        uncovered = _uncovered_frs(spec_text, parsed_maps, spec_path)
    if not uncovered:
        print(f"domain 覆蓋檢核通過：spec 全部 FR 皆在 {domain_map_path} 有 bundle 歸屬")
        return 0

    if layer_mode:
        print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在系統層覆蓋：")
    else:
        print(f"domain 覆蓋檢核發現 {len(uncovered)} 個 FR 未在 domain map 覆蓋：")
    for fr in uncovered:
        print(f"  FR-{fr:02d}")
    spec_id = extract_spec_id(spec_text, spec_path)
    if layer_mode:
        print(f"（系統層：{domain_map_path}）層級 SPEC 以系統層判定，{describe_attribution_remedy('於系統層', spec_id)}")
        return 1
    warn_unattributed_uncovered(parsed_maps, uncovered)
    tail = describe_attribution_remedy('於 domain map ', spec_id) + describe_default_assigned(parsed_maps, spec_id)
    print(f"（domain map：{domain_map_path}）{tail}")
    return 1


def _report_event_flow_labeling(spec_text, domain_map_paths, layer_mode=False):
    """列印事件流標定檢核結果，回傳 exit code。性質為啟發式提醒，非阻擋。"""
    domain_map_path = ", ".join(str(p) for p in domain_map_paths)
    missing = check_event_flow_labeling_union(
        spec_text, [t for _, t in _read_maps(domain_map_paths)])
    if not missing:
        print("事件流標定檢核通過：命中事件流訊號詞的 FR 皆在通道與協調圖節有到達類別與級別標定")
        return 0

    print(f"事件流標定檢核發現 {len(missing)} 個 FR 命中事件流訊號詞但未見通道標定（提醒，非阻擋）：")
    for fr in missing:
        print(f"  FR-{fr:02d}")
    label = "系統層" if layer_mode else "domain map"
    print(f"（{label}：{domain_map_path}）請於「通道與協調圖」節之「到達類別與級別實例」子表補上標定。")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="spec check-domain-coverage",
        description="檢查 spec 的每個 FR 是否被 domain map 的 FR->bundle 覆蓋表歸屬",
    )
    parser.add_argument("spec_path", help="Spec 文件路徑")
    parser.add_argument("--domain-map", help="domain map 路徑（省略則自動定位）")
    parser.add_argument(
        "--check-event-flow-labeling",
        action="store_true",
        help="額外執行事件流標定檢核（可選，啟發式提醒，非阻擋）",
    )
    args = parser.parse_args(argv)

    spec_path = Path(args.spec_path)
    for label, path in (("spec 路徑", spec_path), ("--domain-map", Path(args.domain_map) if args.domain_map else None)):
        if path is not None and path.is_dir():
            print(f"domain 覆蓋檢核：{label} 是目錄，需為檔案：{path}")
            return 1
    spec_text = spec_path.read_text(encoding="utf-8")

    unclosed = mask_fenced_blocks(spec_text)[1]
    if unclosed is not None:
        print(f"domain 覆蓋檢核失敗：第 {unclosed} 行開啟的圍欄程式碼區塊未閉合，其後內容未被檢視（未執行覆蓋比對）")
        return 1

    early = judge_fr_declaration(spec_text)
    if early is not None:
        return early

    if args.domain_map == "":
        print("domain 覆蓋檢核：--domain-map 指定的檔案不存在：''（空字串不視為未帶旗標）")
        return 1
    domain_map_paths, reason, unparseable = locate_domain_maps_with_reason(
        spec_path, args.domain_map, extract_spec_id(spec_text, spec_path))
    layer_mode = not domain_map_paths and args.domain_map is None and is_layer_spec(spec_text)
    warn_unparseable_maps(_unlisted_unparseable(unparseable, domain_map_paths, reason, layer_mode))
    # 層級判定只在原定位鏈找不到任何 map、且 domain 欄非已宣告 domain 時成立；
    # 有 map 時照原鏈，無 map 但 domain 欄為已宣告 domain 是漏登記，維持紅
    if not domain_map_paths and args.domain_map is None:
        # domain 欄只在此處被消費（進入層級判定），格式檢查限於此路徑
        format_error = domain_format_error(spec_text)
        if format_error:
            print(format_error)
            return 1
    if layer_mode:
        print(layer_banner(spec_text, unparseable))
        if SYSTEM_LAYER_PATH.is_dir():
            print(f"domain 覆蓋檢核：系統層 {SYSTEM_LAYER_PATH} 是目錄，需為檔案。")
            return 1
        if not SYSTEM_LAYER_PATH.exists():
            print(describe_missing_system_layer())
            return 1
        if extract_spec_id(spec_text, spec_path) is None:
            print(describe_layer_id_unrecognized())
            return 1
        domain_map_paths = [SYSTEM_LAYER_PATH]
    if SYSTEM_LAYER_PATH in domain_map_paths and SYSTEM_LAYER_PATH.is_dir():
        print(f"domain 覆蓋檢核：系統層 {SYSTEM_LAYER_PATH} 是目錄，需為檔案。")
        return 1
    if not domain_map_paths:
        print(describe_missing_map(reason, args.domain_map, unparseable))
        return 1

    rc = _report_domain_coverage(spec_text, domain_map_paths, spec_path, layer_mode)
    if args.check_event_flow_labeling:
        rc = _report_event_flow_labeling(spec_text, domain_map_paths, layer_mode) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
