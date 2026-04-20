"""AC 驗證結果資料結構（Ticket 0.18.0-W11-001.1.1）。

本模組定義 claim 命令執行 AC 驗證時的不可變資料結構：

- ``VerificationResult``：單一 AC 的驗證結果（含狀態、模板名稱、訊息、exit code）。
- ``VerificationSummary``：所有 AC 結果的聚合摘要（含四類計數與狀態標籤）。

設計理由：
    frozen dataclass 與既有 ``AC`` / ``ValidationCommand`` 的風格一致；
    ``VerificationSummary.status`` 是衍生聚合欄位，作為控制流分支依據
    （prompt / reject / passthrough）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ticket_system.lib.ac_parser import AC


# VerificationResult 的 status 集合
ResultStatus = Literal[
    "passed",
    "failed",
    "unverifiable",
    "no_template",
    "timeout",
    "env_error",
]

# VerificationSummary 的 status 集合
SummaryStatus = Literal[
    "all_passed",
    "has_failures",
    "none_verifiable",
    "no_ac",
]


@dataclass(frozen=True)
class VerificationResult:
    """單一 AC 的驗證結果（immutable）。

    Attributes:
        ac: 被驗證的 AC 物件（來自 ac_parser）。
        status: 驗證結果狀態。
        template_name: 匹配到的驗證模板名稱；``None`` 代表 no_template。
        message: 單行摘要（渲染用）。
        exit_code: subprocess 的 exit code；``None`` 代表未執行。
    """

    ac: AC
    status: ResultStatus
    template_name: str | None
    message: str
    exit_code: int | None


@dataclass(frozen=True)
class VerificationSummary:
    """所有 AC 結果的聚合摘要（immutable）。

    Attributes:
        total: AC 總數。
        passed: 通過驗證的 AC 數。
        failed: 驗證失敗的 AC 數。
        unverifiable: 無法驗證的 AC 數（含 no_template / unverifiable /
            timeout / env_error 四類合併）。
        status: 衍生的聚合狀態標籤。
    """

    total: int
    passed: int
    failed: int
    unverifiable: int
    status: SummaryStatus
