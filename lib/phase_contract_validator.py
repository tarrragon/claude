#!/usr/bin/env python3
"""
phase-contract-validator-hook.py

TDD Phase Contract 四層驗證 Hook

四層驗證邏輯：
1. Layer 1：存在性驗證 - 必要 artifact 檔案存在
2. Layer 2：格式驗證 - frontmatter YAML 格式正確
3. Layer 3：結構驗證 - 必要 Section 存在
4. Layer 4：內容驗證 - Section 內容符合規範（始終 WARNING）

Legacy vs Non-legacy 文件判定：
- Legacy 文件：mtime 嚴格早於 contracts.yaml 建立日期（包括日期邊界）
- 降級策略：legacy 文件 Layer 2/3 的 ERROR 降級為 WARNING
- 註：frontmatter 中 phase 欄位是 optional，缺少不代表 legacy（IMP-044 修復）

使用方式：
    from phase_contract_validator_hook import PhaseContractValidator

    validator = PhaseContractValidator(contracts_path=".claude/tdd/contracts.yaml")
    result = validator.validate(
        ticket_id="0.1.2-W1-002",
        phase="1",
        ticket_dir="docs/work-logs/v0.1.2/tickets/"
    )

    if result.can_proceed:
        print("Phase 轉移允許")
    else:
        print("Phase 轉移被阻止，錯誤：", result.errors)
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml",
# ]
# ///

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


@dataclass
class ValidationResult:
    """驗證結果容器"""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        """是否允許 Phase 轉移（errors 為空時允許）"""
        return len(self.errors) == 0


class PhaseContractValidator:
    """TDD Phase Contract 驗證器"""

    def __init__(self, contracts_path: str = ".claude/tdd/contracts.yaml"):
        """
        初始化驗證器

        Args:
            contracts_path: contracts.yaml 的路徑（相對於專案根目錄）
        """
        self.contracts_path = contracts_path
        self.contracts = self._load_contracts()
        self.compatibility = self.contracts.get("compatibility", {})
        self.legacy_threshold_date = self.compatibility.get("legacy_threshold_date")

    def _load_contracts(self) -> dict:
        """載入並解析 contracts.yaml"""
        try:
            with open(self.contracts_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data or {}
        except FileNotFoundError:
            # contracts.yaml 不存在時返回空字典，驗證會失敗
            return {}
        except yaml.YAMLError as e:
            # 雙通道輸出：stderr + 日誌（品質基線規則 4）
            error_msg = f"contracts.yaml YAML 解析失敗：{e}"
            sys.stderr.write(f"[ERROR] {error_msg}\n")
            raise ValueError(error_msg)

    def validate(
        self,
        ticket_id: str,
        phase: str,
        ticket_dir: str,
    ) -> ValidationResult:
        """
        執行四層驗證

        Args:
            ticket_id: Ticket ID（如 0.1.2-W1-002）
            phase: Phase 代號（"1" | "2" | "3a" | "3b"）
            ticket_dir: Ticket 文件所在目錄

        Returns:
            ValidationResult，errors 非空時阻止 Phase 轉移
        """
        result = ValidationResult()

        # 取得對應的 contract
        phase_contract_key = self._get_phase_contract_key(phase)
        if phase_contract_key not in self.contracts.get("contracts", {}):
            result.errors.append(
                f"contracts.yaml 中找不到 phase {phase} 的 contract 定義"
            )
            return result

        phase_contract = self.contracts["contracts"][phase_contract_key]
        artifacts = phase_contract.get("artifacts", [])

        # 對每個 artifact 執行四層驗證
        for artifact_spec in artifacts:
            artifact_name = artifact_spec.get("name")
            artifact_required = artifact_spec.get("required", False)

            # Layer 1：存在性驗證
            existence_errors = self._check_existence(
                ticket_id, artifact_spec, ticket_dir
            )
            if existence_errors:
                result.errors.extend(existence_errors)
                continue

            # 找到實際檔案路徑
            file_path = self._resolve_artifact_path(ticket_id, artifact_spec, ticket_dir)
            if not file_path:
                continue

            # 判斷是否為 legacy 文件
            is_legacy = self._is_legacy_artifact(file_path)

            # 一次讀取檔案內容，供 Layer 2/3/4 使用（優化：避免重複讀檔）
            file_content = self._read_file_safely(file_path)
            if file_content is None:
                # 無法讀取檔案
                msg = "P-FORMAT-002: 無法讀取檔案"
                if is_legacy:
                    result.warnings.append(f"[Legacy降級] {msg}")
                else:
                    result.errors.append(msg)
                continue

            # Layer 2：格式驗證
            format_errors, format_warnings = self._check_format(
                file_content, artifact_spec, is_legacy
            )
            result.errors.extend(format_errors)
            result.warnings.extend(format_warnings)

            # 如果格式驗證失敗，跳過結構和內容驗證
            if format_errors:
                continue

            # Layer 3：結構驗證
            structure_errors, structure_warnings = self._check_structure(
                file_content, artifact_spec, is_legacy
            )
            result.errors.extend(structure_errors)
            result.warnings.extend(structure_warnings)

            # Layer 4：內容驗證（始終為 WARNING，不阻止轉移）
            content_warnings = self._check_content(file_content, artifact_spec)
            result.warnings.extend(content_warnings)

        return result

    def _get_phase_contract_key(self, phase: str) -> str:
        """根據 phase 代號取得 contracts.yaml 中的 key"""
        mapping = {
            "1": "phase1_output",
            "2": "phase2_output",
            "3a": "phase3a_output",
            "3b": "phase3b_output",
        }
        return mapping.get(phase, "")

    def _resolve_artifact_path(
        self, ticket_id: str, artifact_spec: dict, ticket_dir: str
    ) -> str | None:
        """
        解析 path_pattern，找到實際檔案路徑（前綴匹配）

        IMP-011 核心：使用前綴匹配而非精確匹配，以正確處理帶後綴的格式變體
        """
        artifact_format = artifact_spec.get("format", {})
        path_pattern = artifact_format.get("path_pattern")

        if not path_pattern:
            return None

        # 處理 {ticket-id} 佔位符
        prefix = path_pattern.replace("{ticket-id}", ticket_id)

        # 移除 .md 或 .dart 後綴，以前綴匹配
        base = re.sub(r"\.(md|dart)$", "", prefix)

        # 列出目錄中所有檔案
        if not os.path.isdir(ticket_dir):
            return None

        try:
            candidates = [
                f for f in os.listdir(ticket_dir) if f.startswith(base)
            ]
            if candidates:
                # 返回第一個匹配的檔案
                return os.path.join(ticket_dir, candidates[0])
        except OSError:
            return None

        # 嘗試 alternate_patterns
        for alt_pattern in artifact_format.get("alternate_patterns", []):
            alt_prefix = alt_pattern.replace("{ticket-id}", ticket_id)
            alt_base = re.sub(r"\.(md|dart)$", "", alt_prefix)
            try:
                alt_candidates = [
                    f for f in os.listdir(ticket_dir) if f.startswith(alt_base)
                ]
                if alt_candidates:
                    return os.path.join(ticket_dir, alt_candidates[0])
            except OSError:
                continue

        return None

    def _read_file_safely(self, file_path: str) -> str | None:
        """
        安全讀取檔案內容

        Returns:
            檔案內容，或 None 若讀取失敗
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, IOError) as e:
            # 雙通道輸出：stderr + 日誌（品質基線規則 4）
            error_msg = f"無法讀取檔案 {file_path}：{e}"
            sys.stderr.write(f"[ERROR] {error_msg}\n")
            return None

    def _check_existence(
        self, ticket_id: str, artifact_spec: dict, ticket_dir: str
    ) -> list[str]:
        """Layer 1：存在性驗證"""
        errors = []
        artifact_name = artifact_spec.get("name")
        artifact_required = artifact_spec.get("required", False)

        file_path = self._resolve_artifact_path(ticket_id, artifact_spec, ticket_dir)
        if not file_path and artifact_required:
            errors.append(
                f"P-EXIST-001: 必要 artifact '{artifact_name}' 檔案不存在"
            )

        return errors

    def _check_format(
        self, content: str, artifact_spec: dict, is_legacy: bool
    ) -> tuple[list[str], list[str]]:
        """
        Layer 2：格式驗證，返回 (errors, warnings)

        Args:
            content: 檔案內容（已在 validate() 中讀取快取）
        """
        errors = []
        warnings = []

        artifact_format = artifact_spec.get("format", {})
        artifact_type = artifact_format.get("type")

        # 對 markdown 格式檔案驗證 frontmatter
        if artifact_type == "markdown":
            # 嘗試解析 frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    try:
                        yaml.safe_load(parts[1])
                    except yaml.YAMLError:
                        msg = "P-FORMAT-001: Frontmatter YAML 格式錯誤"
                        if is_legacy:
                            warnings.append(f"[Legacy降級] {msg}")
                        else:
                            errors.append(msg)

        return errors, warnings

    def _check_structure(
        self, content: str, artifact_spec: dict, is_legacy: bool
    ) -> tuple[list[str], list[str]]:
        """
        Layer 3：結構驗證，返回 (errors, warnings)

        支援 Section 替代名稱（IMP-045 擴展）：
        - 從 contracts.yaml 中的 alternate_names 欄位讀取允許的替代名稱
        - 精確匹配優先，不存在時嘗試替代名稱

        Args:
            content: 檔案內容（已在 validate() 中讀取快取）
        """
        errors = []
        warnings = []

        artifact_format = artifact_spec.get("format", {})
        artifact_type = artifact_format.get("type")

        # 對 markdown 檔案驗證必要 Section
        if artifact_type == "markdown":
            # 提取所有 Section（## 標題）
            sections = re.findall(r"^##\s+(.+?)$", content, re.MULTILINE)
            section_set = {s.strip() for s in sections}

            # 檢查必要 Section
            for section in artifact_spec.get("content_sections", []):
                section_name = section.get("name")
                section_required = section.get("required", False)

                if section_required:
                    # 檢查精確匹配或替代名稱
                    found = section_name in section_set
                    if not found:
                        # 從 contracts.yaml 中讀取替代名稱
                        alternate_names = section.get("alternate_names", [])
                        found = any(alias in section_set for alias in alternate_names)

                    if not found:
                        msg = f"P-STRUCT-001: 必要 Section '{section_name}' 缺失"
                        if is_legacy:
                            warnings.append(f"[Legacy降級] {msg}")
                        else:
                            errors.append(msg)

        return errors, warnings

    def _check_content(self, content: str, artifact_spec: dict) -> list[str]:
        """
        Layer 4：內容驗證，始終返回 warnings（無 errors）

        檢查項目：
        - 驗收條件至少 3 條
        - direction 欄位格式符合規範

        Args:
            content: 檔案內容（已在 validate() 中讀取快取）
        """
        warnings = []

        # 檢查驗收條件數量（Phase 1）
        acceptance_criteria = re.findall(
            r"^-\s+\[\s*\]\s+.+?$", content, re.MULTILINE
        )
        if len(acceptance_criteria) < 3:
            warnings.append(
                f"P-CONTENT-001: [WARNING] 驗收條件少於 3 條（目前 {len(acceptance_criteria)} 條）"
            )

        # 檢查 direction 欄位格式（Phase 3a）
        direction_pattern = r"direction:\s*['\"]?(.+?)['\"]?\s*$"
        direction_matches = re.findall(direction_pattern, content, re.MULTILINE)
        for direction_value in direction_matches:
            direction_value = direction_value.strip().strip("'\"")
            # 允許的格式：to-{type}[:target_id]
            if not re.match(
                r"^to-(sibling|parent|child|context-refresh)(?::[\w.-]+)?$",
                direction_value,
            ):
                warnings.append(
                    f"P-CONTENT-002: [WARNING] direction 欄位格式不符規範：'{direction_value}'"
                )

        return warnings

    def _is_legacy_artifact(self, file_path: str) -> bool:
        """
        判斷是否為 legacy 文件

        Legacy 判定標準：
        1. 檔案 mtime 嚴格早於 contracts.yaml 建立時間（日期邊界）
        2. 不檢查 frontmatter（phase 欄位是 optional，缺少不代表 legacy）

        IMP-044 修復：
        - 時間比較統一使用 UTC 時區序列化（與全系統一致，見 quality-baseline.md 規則 4）
        - 移除不合理的 frontmatter.phase 檢查（違反 schema optional 定義）
        """
        if not self.legacy_threshold_date:
            return True

        try:
            # 比較 mtime 與 threshold date（統一使用 UTC，與全系統時區處理一致）
            file_mtime = os.path.getmtime(file_path)
            # 使用 UTC 時區，避免時區混亂
            file_datetime = datetime.fromtimestamp(file_mtime, tz=timezone.utc)

            # 解析 threshold date 並設定為當天的 UTC 0:00:00（日期邊界）
            # 如 "2026-03-24" -> 2026-03-24 00:00:00 UTC
            threshold_datetime = (
                datetime.fromisoformat(self.legacy_threshold_date)
                .replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            )

            # legacy = 檔案 mtime 嚴格早於 threshold（不包含 threshold 當天）
            # 例如：threshold = 2026-03-24 00:00:00 UTC
            #  - 2026-03-23 23:59:59 UTC 之前的檔案 → legacy
            #  - 2026-03-24 00:00:00 UTC 及以後的檔案 → non-legacy
            if file_datetime < threshold_datetime:
                return True

        except (OSError, ValueError) as e:
            # 無法取得 mtime 時預設為 legacy（安全降級）
            # 雙通道輸出：stderr + 日誌（品質基線規則 4）
            error_msg = f"無法判定 legacy 狀態 {file_path}：{e}"
            sys.stderr.write(f"[WARNING] {error_msg}\n")
            return True

        return False


def format_validation_result(result: ValidationResult) -> str:
    """格式化驗證結果為輸出字串"""
    lines = []

    for error in result.errors:
        lines.append(f"[ERROR] {error}")

    for warning in result.warnings:
        lines.append(f"[WARNING] {warning}")

    return "\n".join(lines) if lines else "驗證通過"


if __name__ == "__main__":
    # 測試用途
    import sys

    if len(sys.argv) < 4:
        print("使用方式：python phase-contract-validator-hook.py <ticket_id> <phase> <ticket_dir>")
        sys.exit(1)

    ticket_id = sys.argv[1]
    phase = sys.argv[2]
    ticket_dir = sys.argv[3]

    validator = PhaseContractValidator()
    result = validator.validate(ticket_id, phase, ticket_dir)

    print(format_validation_result(result))
    sys.exit(0 if result.can_proceed else 1)
