"""
Context Bundle 自動抽取模組

從 target ticket 的 source_ticket / blocked_by / related_to 欄位
自動抽取相關來源 ticket 的 what / why / where.files / acceptance，
渲染為 Context Bundle markdown，並支援幂等合併。

Linux kernel ELF loader 類比：自動載入依賴 context，降低 PM 手填成本。

權威規格：
- Phase 1 v2 §v2.0-§v2.7 + v3 §v3.1-§v3.5
- Phase 2 v2 15 場景（sage-test-architect）
- Phase 3a 策略（pepper-test-implementer）
- W17-002.1 P2 風格與增強（placeholder list、opt-out、--json、metric hook、ac_parser 整合、專屬 Exception）
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, List, Literal, Optional, Tuple

from ..constants import (
    CONTEXT_BUNDLE_EXTRACT_STATUSES,
    CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD,
    CONTEXT_BUNDLE_MAX_TOTAL_CHARS,
    CONTEXT_BUNDLE_OPT_OUT_KEY,
    CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL,
    CONTEXT_BUNDLE_PLACEHOLDER_VALUES,
    CONTEXT_BUNDLE_SKIP_REASONS,
    CONTEXT_BUNDLE_SOURCE_KINDS,
)
from .parser import load_ticket, save_ticket
from .paths import get_ticket_path
from .ticket_validator import extract_version_from_ticket_id


# ============================================================================
# 常數區（§v2.1 BLK-2：內嵌常數，但枚舉值集中於 lib/constants.py 以利他處 import）
# ============================================================================

SourceKind = Literal["source_ticket", "blocked_by", "related_to"]

# SOURCE_PRIORITY 順序 = constants.CONTEXT_BUNDLE_SOURCE_KINDS；
# 保留本模組常數名以保持既有 API（tests 直接 import SOURCE_PRIORITY）。
SOURCE_PRIORITY: Tuple[SourceKind, ...] = CONTEXT_BUNDLE_SOURCE_KINDS  # type: ignore[assignment]

# 規模限制（rationale 見 constants.CONTEXT_BUNDLE_MAX_TOTAL_CHARS 註解）
MAX_TOTAL_CHARS: int = CONTEXT_BUNDLE_MAX_TOTAL_CHARS
MAX_ITEMS_PER_FIELD: int = CONTEXT_BUNDLE_MAX_ITEMS_PER_FIELD
TRUNCATE_INDICATOR: str = "... (truncated, see source ticket)"

# 幂等標記
AUTO_MARKER_PREFIX: str = "<!-- auto-extracted:"
AUTO_EXTRACTED_BLOCK_PATTERN = re.compile(
    r"<!--\s*auto-extracted:[^>]*-->.*?(?=^## |\Z)",
    flags=re.MULTILINE | re.DOTALL,
)

ExtractStatus = Literal[
    "no_source",
    "all_sources_missing",
    "partial",
    "success",
    "self_reference",
    "opt_out",
]

SkipReason = Literal[
    "source_missing",
    "source_field_undefined",
    "self_reference",
    "opt_out",
]


# ============================================================================
# 專屬 Exception（W17-002.1 acceptance #5）
# ============================================================================
#
# 取代原本 yaml.YAMLError / RuntimeError 直接透出：caller 可 except 本類別
# 獲得明確語義，且 traceback chain 保留原因（from original_exc）。
class ContextBundleExtractionError(Exception):
    """Context Bundle 抽取過程的專屬例外。

    non-raising 設計下，僅 extract_and_write 的 target load 失敗才會拋出。
    source ticket load 失敗會收集至 result.warnings，不拋本例外。
    """


# ============================================================================
# Metric Event Hook（W17-002.1 acceptance #8）
# ============================================================================
#
# Tripwire T1（W17-002 母 ticket 規格）依賴可觀測數據：每次抽取的
# sources_declared / sources_ok / total_chars / truncated 數量。
# 注入模式（而非 import）保持 lib 模組的純粹性與可測試性。
MetricEvent = dict
MetricSink = Callable[[str, MetricEvent], None]

# 預設 sink：no-op。CLI 可替換為寫檔 / 寄 metric server。
_metric_sink: MetricSink = lambda event_type, payload: None  # noqa: E731


def set_metric_sink(sink: Optional[MetricSink]) -> None:
    """設定全域 metric sink。傳 None 清空為 no-op。"""
    global _metric_sink
    _metric_sink = sink if sink is not None else (
        lambda event_type, payload: None  # noqa: E731
    )


def _emit(event_type: str, payload: MetricEvent) -> None:
    """內部 metric 發送 helper，吞掉 sink 例外不影響主流程。"""
    try:
        _metric_sink(event_type, payload)
    except Exception:  # noqa: BLE001 - metric 失敗不可影響主流程
        # 明確靜默：metric 副作用失敗寫 stderr 單行提示但不拋（規則 4 擴充）
        sys.stderr.write("[Context Bundle] metric sink 失敗，已略過\n")


# ============================================================================
# Dataclass 區（§v2.2 SIMP-4：ExtractedField 儲存 raw_value）
# ============================================================================


@dataclass(frozen=True)
class ExtractableFieldRule:
    """單一欄位抽取規則。

    is_list=True → 套用 MAX_ITEMS_PER_FIELD（§v3.3 BLK-v3-3 統一套用）。
    use_ac_parser=True → 透過 ac_parser 過濾已 checked 的 acceptance 項（W17-002.1 #6）。
    """

    source_field: str
    target_subsection: str
    format_template: str
    is_list: bool = False
    dedup: bool = False
    use_ac_parser: bool = False


EXTRACTABLE_FIELDS: Tuple[ExtractableFieldRule, ...] = (
    ExtractableFieldRule(
        source_field="what",
        target_subsection="Task Reference",
        format_template="- {source_id} what: {value}",
    ),
    ExtractableFieldRule(
        source_field="why",
        target_subsection="Rationale Chain",
        format_template="- {source_id} why: {value}",
    ),
    ExtractableFieldRule(
        source_field="where.files",
        target_subsection="Related Files",
        format_template="- {value}  # from {source_id}",
        is_list=True,
        dedup=True,
    ),
    ExtractableFieldRule(
        source_field="acceptance",
        target_subsection="Source Acceptance (reference)",
        format_template="- [ref] {value}  # from {source_id}",
        is_list=True,
        use_ac_parser=True,
    ),
)


@dataclass
class ExtractedField:
    source_id: str
    source_kind: SourceKind
    source_field: str
    target_subsection: str
    raw_value: Any  # str | list[str]
    truncated: bool = False


@dataclass
class SkipRecord:
    """略過記錄（W17-002.1 acceptance #4 dataclass 化，取代早期 list[dict]）。"""

    source_id: str
    source_kind: SourceKind
    reason: SkipReason
    detail: str = ""


@dataclass
class ExtractResult:
    status: ExtractStatus
    target_ticket_id: str
    extracted: List[ExtractedField] = field(default_factory=list)
    skipped: List[SkipRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sources_declared: int = 0
    sources_ok: int = 0
    total_chars_estimate: int = 0


# ============================================================================
# 內部 helper
# ============================================================================


def _read_nested(ticket: dict, dotted_field: str) -> Any:
    """支援 where.files 等巢狀欄位讀取。"""
    parts = dotted_field.split(".")
    cur: Any = ticket
    for p in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _is_placeholder(value: Any) -> bool:
    """偵測 placeholder / None / 空 list。

    W17-002.1 acceptance #10：placeholder 擴為 list，涵蓋常見變體
    （"待定義" / "TBD" / "TODO" / "待填寫" 等），由 constants 定義。
    """
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        return stripped in CONTEXT_BUNDLE_PLACEHOLDER_VALUES
    if isinstance(value, list):
        return len(value) == 0
    return False


def _detect_opt_out(target: dict) -> bool:
    """偵測 opt-out 標記（W17-002.1 acceptance #9）。

    frontmatter 中 `context-bundle: manual`（或 YAML 解析後的 `context_bundle: manual`）
    表示 PM 明示手動維護，自動抽取應略過。
    支援連字號與底線兩種 key 形式以容納 YAML 風格差異。
    """
    for key in (CONTEXT_BUNDLE_OPT_OUT_KEY, "context-bundle"):
        val = target.get(key)
        if isinstance(val, str) and val.strip() == CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL:
            return True
    return False


def _filter_acceptance_with_ac_parser(raw: Any, source_id: str) -> list:
    """使用 checkbox 語義過濾 acceptance（W17-002.1 acceptance #6）。

    以 ac_parser 的 checkbox 解析邏輯過濾已勾選項目（只保留 [ ] 未完成項），
    讓自動抽取聚焦於承接者實際要處理的部分。

    設計取捨：此處不呼叫 ac_parser.parse_ac（那會再次 load_ticket 造成重複 I/O），
    改用 ac_parser 使用的同一份 checkbox_utils 工具，確保語義一致。
    """
    if not isinstance(raw, list):
        return [str(raw)]
    try:
        from ticket_system.lib import checkbox_utils
    except Exception:
        # 降級：若 checkbox_utils 不可用，回傳原字串列表
        return [str(x) for x in raw]

    filtered: list = []
    for item in raw:
        item_str = str(item)
        # acceptance 常以 "- [x] text" 或 "[x] text" 形式儲存；
        # 剝除前導 "- " 後再解析 checkbox 狀態。
        probe = item_str.lstrip()
        if probe.startswith("- "):
            probe = probe[2:].lstrip()
        checked, _text = checkbox_utils.strip_checkbox_prefix(probe)
        if checked:
            # 已完成的 AC 對接手者價值低，略過
            continue
        # 保留原始字串（含 checkbox 標記），render 端直接顯示
        filtered.append(item_str)
    return filtered


def _collect_source_ids(target: dict) -> list:
    """依 SOURCE_PRIORITY + YAML 出現順序收集 (source_id, source_kind)。"""
    collected: list = []
    for kind in SOURCE_PRIORITY:
        v = target.get(kind)
        if v is None:
            continue
        if isinstance(v, str):
            if v.strip():
                collected.append((v, kind))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.strip():
                    collected.append((item, kind))
    return collected


def _dedup_items(items: list, seen: set) -> list:
    """與 seen set 合併去重，保留順序；副作用：更新 seen。"""
    result = []
    for x in items:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def _build_target_seen(target: dict, subsection: str) -> set:
    """初始化去重 seen set：僅 Related Files 納入 target.where.files。"""
    seen: set = set()
    if subsection == "Related Files":
        target_files = _read_nested(target, "where.files") or []
        if isinstance(target_files, list):
            for x in target_files:
                if isinstance(x, str):
                    seen.add(x)
    return seen


def _count_field_chars(f: ExtractedField) -> int:
    """統一字元計算（W17-002.1 cinnamon 補充項：避免 _estimate_chars / _apply_total_chars_limit 邏輯重疊）。"""
    if isinstance(f.raw_value, list):
        return sum(len(str(x)) for x in f.raw_value)
    return len(str(f.raw_value))


def _estimate_chars(extracted: list) -> int:
    return sum(_count_field_chars(f) for f in extracted)


def _apply_total_chars_limit(result: ExtractResult) -> None:
    """§S9 決策：raw 階段累計並截斷末端 ExtractedField。"""
    running = 0
    truncated_at: Optional[int] = None
    for idx, f in enumerate(result.extracted):
        running += _count_field_chars(f)
        if running > MAX_TOTAL_CHARS:
            truncated_at = idx
            break
    if truncated_at is not None:
        kept = result.extracted[:truncated_at]
        overflow = result.extracted[truncated_at]
        if isinstance(overflow.raw_value, list) and len(overflow.raw_value) > 1:
            overflow.raw_value = overflow.raw_value[: max(1, len(overflow.raw_value) // 2)]
        elif isinstance(overflow.raw_value, str):
            remain = MAX_TOTAL_CHARS - sum(_count_field_chars(x) for x in kept)
            if remain > 0:
                overflow.raw_value = overflow.raw_value[:remain]
            else:
                overflow.raw_value = ""
        overflow.truncated = True
        kept.append(overflow)
        result.extracted = kept
        result.warnings.append(
            f"抽取結果超過 MAX_TOTAL_CHARS={MAX_TOTAL_CHARS}，已截斷；{TRUNCATE_INDICATOR}"
        )
    result.total_chars_estimate = _estimate_chars(result.extracted)


# ============================================================================
# 公開函式 1：detect_self_reference（BLK-5）
# ============================================================================


def detect_self_reference(target_ticket: dict) -> bool:
    """檢查任一 source_ticket/blocked_by/related_to id 是否等於 target id。"""
    target_id = target_ticket.get("id")
    if not target_id:
        return False
    for kind in SOURCE_PRIORITY:
        v = target_ticket.get(kind)
        if v is None:
            continue
        ids = [v] if isinstance(v, str) else list(v) if isinstance(v, list) else []
        if target_id in ids:
            return True
    return False


# ============================================================================
# 公開函式 2：extract_context_bundle（主入口，non-raising）
# ============================================================================


def extract_context_bundle(target_ticket: dict) -> ExtractResult:
    """核心抽取函式。Non-raising：異常收集至 warnings/skipped。"""
    target_id = target_ticket.get("id", "")
    result = ExtractResult(status="no_source", target_ticket_id=target_id)

    # Opt-out 短路（W17-002.1 acceptance #9）
    if _detect_opt_out(target_ticket):
        result.status = "opt_out"
        result.skipped.append(
            SkipRecord(
                source_id=target_id,
                source_kind="source_ticket",
                reason="opt_out",
                detail=f"{CONTEXT_BUNDLE_OPT_OUT_KEY}={CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL}",
            )
        )
        result.warnings.append(
            f"偵測 opt-out 標記（{CONTEXT_BUNDLE_OPT_OUT_KEY}: "
            f"{CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL}），略過自動抽取"
        )
        _emit("context_bundle.extract", _build_metric_payload(result))
        return result

    # Self-reference 短路（S17）
    if detect_self_reference(target_ticket):
        result.status = "self_reference"
        result.skipped.append(
            SkipRecord(
                source_id=target_id,
                source_kind="source_ticket",
                reason="self_reference",
                detail="",
            )
        )
        result.warnings.append(f"偵測 self-reference：{target_id}，停止抽取")
        _emit("context_bundle.extract", _build_metric_payload(result))
        return result

    source_list = _collect_source_ids(target_ticket)
    result.sources_declared = len(source_list)
    if not source_list:
        result.warnings.append("本 ticket 無可抽取來源")
        _emit("context_bundle.extract", _build_metric_payload(result))
        return result

    dedup_seen: dict = {}

    for src_id, src_kind in source_list:
        try:
            version = extract_version_from_ticket_id(src_id)
        except Exception as exc:
            result.skipped.append(
                SkipRecord(
                    source_id=src_id,
                    source_kind=src_kind,
                    reason="source_missing",
                    detail=f"version parse failed: {exc}",
                )
            )
            result.warnings.append(f"source {src_id} 版本號解析失敗，略過")
            continue

        if not version:
            result.skipped.append(
                SkipRecord(
                    source_id=src_id,
                    source_kind=src_kind,
                    reason="source_missing",
                    detail="version=None",
                )
            )
            result.warnings.append(f"source {src_id} 版本號缺失，略過")
            continue

        try:
            source = load_ticket(version, src_id)
        except Exception as exc:
            source = None
            result.warnings.append(f"load_ticket({src_id}) 失敗：{exc}")

        if source is None:
            result.skipped.append(
                SkipRecord(
                    source_id=src_id,
                    source_kind=src_kind,
                    reason="source_missing",
                    detail=f"version={version}",
                )
            )
            result.warnings.append(f"source {src_id} 不存在於 {version}，略過")
            continue

        result.sources_ok += 1
        for rule in EXTRACTABLE_FIELDS:
            raw = _read_nested(source, rule.source_field)
            if _is_placeholder(raw):
                result.skipped.append(
                    SkipRecord(
                        source_id=src_id,
                        source_kind=src_kind,
                        reason="source_field_undefined",
                        detail=rule.source_field,
                    )
                )
                continue
            if rule.is_list:
                if rule.use_ac_parser:
                    items = _filter_acceptance_with_ac_parser(raw, src_id)
                else:
                    items = (
                        [str(x) for x in raw] if isinstance(raw, list) else [str(raw)]
                    )
                if rule.dedup:
                    if rule.target_subsection not in dedup_seen:
                        dedup_seen[rule.target_subsection] = _build_target_seen(
                            target_ticket, rule.target_subsection
                        )
                    items = _dedup_items(items, dedup_seen[rule.target_subsection])
                truncated = False
                if len(items) > MAX_ITEMS_PER_FIELD:
                    total_items = len(items)
                    items = items[:MAX_ITEMS_PER_FIELD]
                    truncated = True
                    result.warnings.append(
                        f"source {src_id} 的 {rule.source_field} 共 {total_items} 項，"
                        f"已截斷保留前 {MAX_ITEMS_PER_FIELD} 項"
                    )
                if not items:
                    continue
                result.extracted.append(
                    ExtractedField(
                        source_id=src_id,
                        source_kind=src_kind,
                        source_field=rule.source_field,
                        target_subsection=rule.target_subsection,
                        raw_value=items,
                        truncated=truncated,
                    )
                )
            else:
                result.extracted.append(
                    ExtractedField(
                        source_id=src_id,
                        source_kind=src_kind,
                        source_field=rule.source_field,
                        target_subsection=rule.target_subsection,
                        raw_value=raw,
                        truncated=False,
                    )
                )

    _apply_total_chars_limit(result)

    if result.sources_ok == 0:
        result.status = "all_sources_missing"
        result.warnings.append("所有宣告來源皆不存在")
    elif result.sources_ok < result.sources_declared:
        result.status = "partial"
    else:
        result.status = "success"

    _emit("context_bundle.extract", _build_metric_payload(result))
    return result


def _build_metric_payload(result: ExtractResult) -> MetricEvent:
    """建構 metric event payload（W17-002.1 acceptance #8）。

    固定欄位：status / sources_declared / sources_ok / fields_extracted /
    total_chars / truncated_count / target_ticket_id。
    """
    return {
        "target_ticket_id": result.target_ticket_id,
        "status": result.status,
        "sources_declared": result.sources_declared,
        "sources_ok": result.sources_ok,
        "fields_extracted": len(result.extracted),
        "total_chars": result.total_chars_estimate,
        "truncated_count": sum(1 for f in result.extracted if f.truncated),
        "warnings_count": len(result.warnings),
        "skipped_count": len(result.skipped),
    }


# ============================================================================
# 公開函式 3：render_context_bundle_markdown
# ============================================================================


def render_context_bundle_markdown(result: ExtractResult) -> str:
    """渲染 ExtractResult 為 markdown。

    status in (no_source, self_reference, all_sources_missing, opt_out) → 回傳空字串（§v2.3 不寫入）。
    """
    if result.status in (
        "no_source",
        "self_reference",
        "all_sources_missing",
        "opt_out",
    ):
        return ""

    sources_sorted = sorted({f.source_id for f in result.extracted})
    header = (
        f"<!-- auto-extracted: v1 | sources: {','.join(sources_sorted)} | "
        f"chars: {result.total_chars_estimate} -->"
    )
    lines = [header, ""]
    for rule in EXTRACTABLE_FIELDS:
        fields = [f for f in result.extracted if f.target_subsection == rule.target_subsection]
        if not fields:
            continue
        lines.append(f"### {rule.target_subsection}")
        for f in fields:
            if rule.is_list:
                for item in f.raw_value:
                    lines.append(
                        rule.format_template.format(source_id=f.source_id, value=item)
                    )
            else:
                lines.append(
                    rule.format_template.format(source_id=f.source_id, value=f.raw_value)
                )
            if f.truncated:
                lines.append(f"  {TRUNCATE_INDICATOR}")
        lines.append("")
    return "\n".join(lines)


# ============================================================================
# 公開函式 4：merge_auto_extracted_block（§v3.1/§v3.2）
# ============================================================================


def _parse_sources_from_marker(marker_block: str) -> list:
    """從 `<!-- auto-extracted: v1 | sources: A,B | chars: N -->` 解析 sources。"""
    match = re.search(r"sources:\s*([^|>]*)", marker_block)
    if not match:
        return []
    raw = match.group(1).strip()
    raw = raw.rstrip("-").rstrip(">").rstrip("|").strip()
    return [s.strip() for s in raw.split(",") if s.strip()]


def merge_auto_extracted_block(
    existing_section_body: str, new_extracted_markdown: str
) -> Tuple[str, list]:
    """合併抽取結果到既有 Context Bundle section body。

    §v3.1 regex EOF 邊界 + §v3.2 sources 主鍵幂等。
    """
    if not new_extracted_markdown:
        return existing_section_body, ["no_change_empty_new"]

    match = AUTO_EXTRACTED_BLOCK_PATTERN.search(existing_section_body or "")
    if match is None:
        sep = ""
        if existing_section_body and not existing_section_body.endswith("\n\n"):
            sep = "\n\n" if existing_section_body.endswith("\n") else "\n\n"
        merged = (existing_section_body or "") + sep + new_extracted_markdown
        return merged, ["appended_new_block"]

    existing_sources = _parse_sources_from_marker(match.group(0))
    new_match = AUTO_EXTRACTED_BLOCK_PATTERN.search(new_extracted_markdown)
    new_sources = (
        _parse_sources_from_marker(new_match.group(0)) if new_match else []
    )

    if sorted(existing_sources) == sorted(new_sources):
        return existing_section_body, ["no_change_idempotent"]

    merged = (
        existing_section_body[: match.start()]
        + new_extracted_markdown
        + existing_section_body[match.end() :]
    )
    notes = ["replaced_auto_block"]
    if AUTO_EXTRACTED_BLOCK_PATTERN.search(existing_section_body, match.end()):
        notes.append("warning: multiple auto-extracted markers detected")
    return merged, notes


# ============================================================================
# 程式化入口：extract_and_write（CLI create/track claim 呼叫點）
# ============================================================================


CONTEXT_BUNDLE_SECTION_HEADING = "## Context Bundle"


def _replace_section_body(body: str, section_heading: str, new_body_content: str) -> str:
    """在 ticket body 中替換指定 section 的內容。"""
    pattern = re.compile(
        rf"({re.escape(section_heading)}\s*\n)(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    if match is None:
        sep = "\n\n" if body and not body.endswith("\n\n") else ""
        return body + sep + section_heading + "\n\n" + new_body_content + "\n"
    return (
        body[: match.start()]
        + match.group(1)
        + new_body_content
        + "\n"
        + body[match.end():]
    )


def _read_section_body(body: str, section_heading: str) -> str:
    pattern = re.compile(
        rf"{re.escape(section_heading)}\s*\n(.*?)(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1) if match else ""


def format_cli_summary(
    result: ExtractResult, quiet: bool = True, verbose: bool = False
) -> str:
    """依 quiet/verbose 三檔輸出抽取摘要。

    W17-002.1 acceptance #1：quiet **預設**為 True（單行輸出），避免
    PM 例行 claim 流程被多行訊息淹沒；需詳細訊息時傳 verbose=True 或
    quiet=False 顯式切換。

    - quiet（預設）：單行 `[Context Bundle] 已抽取（N 項，M 字元）`
    - quiet=False：多行，含來源清單與欄位數
    - verbose：多行 + 每欄位前 80 字元預覽（自動關閉 quiet）
    """
    # verbose 隱含關閉 quiet（verbose 優先）
    if verbose:
        quiet = False

    n_fields = len(result.extracted)
    n_chars = result.total_chars_estimate

    if quiet:
        if result.status == "no_source":
            return "[Context Bundle] 無來源，略過抽取"
        if result.status == "opt_out":
            return "[Context Bundle] opt-out（manual），略過抽取"
        if result.status == "self_reference":
            return "[Context Bundle] self-reference，略過抽取"
        if result.status == "all_sources_missing":
            return "[Context Bundle] 所有來源不存在，略過抽取"
        return f"[Context Bundle] 已抽取（{n_fields} 項，{n_chars} 字元）"

    # 非 quiet 狀態分支
    if result.status == "no_source":
        return (
            "[Context Bundle] 未執行自動抽取：\n"
            "  原因：本 ticket 無 source_ticket/blocked_by/related_to 欄位"
        )
    if result.status == "opt_out":
        return (
            "[Context Bundle] 偵測 opt-out 標記，略過自動抽取：\n"
            f"  原因：{CONTEXT_BUNDLE_OPT_OUT_KEY}: {CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL}（PM 手動維護）"
        )
    if result.status == "self_reference":
        return (
            f"[Context Bundle] 偵測 self-reference，已略過抽取：\n"
            f"  原因：本 ticket id {result.target_ticket_id} 出現在自己的來源欄位"
        )
    if result.status == "all_sources_missing":
        detail = "\n".join(
            f"  - {sk.source_kind}={sk.source_id}：{sk.detail or '檔案不存在'}"
            for sk in result.skipped
        )
        return (
            "[Context Bundle] 所有宣告來源皆不存在：\n"
            f"{detail}\n"
            "  建議：確認 source id 拼寫或版本號正確"
        )

    source_ids = sorted({f.source_id for f in result.extracted})
    lines = [
        f"[Context Bundle] 已從 {len(source_ids)} 個來源抽取 {n_fields} 項欄位：",
    ]
    for sid in source_ids:
        fields_for_sid = [f.source_field for f in result.extracted if f.source_id == sid]
        kind = next(
            (f.source_kind for f in result.extracted if f.source_id == sid),
            "source",
        )
        lines.append(f"  - {kind}={sid}（抽取 {'/'.join(fields_for_sid)}）")
    lines.append(f"  寫入位置：Context Bundle section（共 {n_chars} 字元）")
    if verbose:
        lines.append("  預覽：")
        for f in result.extracted:
            raw_str = (
                ", ".join(str(x) for x in f.raw_value)
                if isinstance(f.raw_value, list)
                else str(f.raw_value)
            )
            preview = raw_str[:80]
            lines.append(f"    {f.source_id} {f.source_field}: {preview}")
    return "\n".join(lines)


def format_cli_summary_json(result: ExtractResult) -> str:
    """JSON 結構化輸出（W17-002.1 acceptance #7）。

    對齊其他 ticket 指令的 --json 輸出慣例，讓 PM / CI / metric pipeline
    能以穩定 schema 消費結果。

    Schema：
        {
          "target_ticket_id": str,
          "status": str,
          "sources_declared": int,
          "sources_ok": int,
          "total_chars_estimate": int,
          "extracted": [ {source_id, source_kind, source_field, target_subsection, truncated, value} ],
          "skipped": [ {source_id, source_kind, reason, detail} ],
          "warnings": [str, ...]
        }
    """
    extracted_payload = []
    for f in result.extracted:
        extracted_payload.append(
            {
                "source_id": f.source_id,
                "source_kind": f.source_kind,
                "source_field": f.source_field,
                "target_subsection": f.target_subsection,
                "truncated": f.truncated,
                "value": f.raw_value,
            }
        )
    skipped_payload = [asdict(sk) for sk in result.skipped]
    payload = {
        "target_ticket_id": result.target_ticket_id,
        "status": result.status,
        "sources_declared": result.sources_declared,
        "sources_ok": result.sources_ok,
        "total_chars_estimate": result.total_chars_estimate,
        "extracted": extracted_payload,
        "skipped": skipped_payload,
        "warnings": list(result.warnings),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def extract_and_write_context_bundle(
    version: str, ticket_id: str
) -> Tuple[ExtractResult, list]:
    """程式化入口：讀 target ticket → extract → render → merge → 寫回。

    Returns:
        (result, notes) 其中 notes 為 merge_auto_extracted_block 回傳 notes。

    Non-raising 契約：
        - source ticket load 失敗 → 收集至 result.warnings，不拋例外。
        - target ticket load 失敗（load_ticket 拋例外）→ 拋 ContextBundleExtractionError
          （W17-002.1 acceptance #5）。原先直接透出原始例外類別（yaml.YAMLError 等）
          導致 caller 難以 except，改為統一專屬 Exception 並保留原因鏈。
    """
    try:
        target = load_ticket(version, ticket_id)
    except Exception as exc:
        raise ContextBundleExtractionError(
            f"load target ticket {ticket_id} 失敗：{exc}"
        ) from exc

    if target is None:
        result = ExtractResult(status="no_source", target_ticket_id=ticket_id)
        result.warnings.append(f"target ticket {ticket_id} 不存在")
        return result, []

    result = extract_context_bundle(target)
    rendered = render_context_bundle_markdown(result)
    notes: list = []
    if not rendered:
        return result, notes

    body = target.get("_body", "") or ""
    existing_section = _read_section_body(body, CONTEXT_BUNDLE_SECTION_HEADING)
    merged_section, notes = merge_auto_extracted_block(existing_section, rendered)
    if "no_change_idempotent" in notes:
        return result, notes

    new_body = _replace_section_body(
        body, CONTEXT_BUNDLE_SECTION_HEADING, merged_section
    )
    target["_body"] = new_body
    ticket_path = get_ticket_path(version, ticket_id)
    save_ticket(target, ticket_path)
    return result, notes


# ============================================================================
# 模組級 __all__（明示公開 API，便於 tooling / IDE 識別）
# ============================================================================

__all__ = [
    # Constants / Types
    "AUTO_EXTRACTED_BLOCK_PATTERN",
    "AUTO_MARKER_PREFIX",
    "CONTEXT_BUNDLE_EXTRACT_STATUSES",
    "CONTEXT_BUNDLE_OPT_OUT_KEY",
    "CONTEXT_BUNDLE_OPT_OUT_VALUE_MANUAL",
    "CONTEXT_BUNDLE_SECTION_HEADING",
    "CONTEXT_BUNDLE_SKIP_REASONS",
    "CONTEXT_BUNDLE_SOURCE_KINDS",
    "EXTRACTABLE_FIELDS",
    "MAX_ITEMS_PER_FIELD",
    "MAX_TOTAL_CHARS",
    "SOURCE_PRIORITY",
    "TRUNCATE_INDICATOR",
    # Dataclasses
    "ExtractableFieldRule",
    "ExtractedField",
    "ExtractResult",
    "SkipRecord",
    # Exception
    "ContextBundleExtractionError",
    # Public API
    "detect_self_reference",
    "extract_and_write_context_bundle",
    "extract_context_bundle",
    "format_cli_summary",
    "format_cli_summary_json",
    "merge_auto_extracted_block",
    "render_context_bundle_markdown",
    "set_metric_sink",
]
