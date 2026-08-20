"""Ticket ID 與 wave 的解析與配號。

建票時 ticket ID 可由使用者指定序號，或在未指定時自動配號。自動配號須跨三個
來源掃描既有序號以避免碰撞——本地 tickets 目錄、main ref 上的檔案清單、
以及同層 worktree——因為並行 session 各自持有工作區，只看本地會配出重複 ID。

自 commands/create.py 抽出（0.2.1-W3-834 分群結論第 A 群）：本群有 39 項專屬測試
（id_allocation_race / id_scan_main_ref / id_sibling_worktree_scan / auto_seq_collision
四檔），是該次分群中回歸保護最厚的一群，且介面單純——輸入 args 與版本，輸出
(版本, ticket_id, wave) 三元組。
"""
from __future__ import annotations

import argparse
from typing import Optional

from ticket_system.lib.constants import (
    MAX_CHILDREN_WARNING_THRESHOLD,
    MAX_TICKET_DEPTH,
)
from ticket_system.lib.depth import compute_depth
from ticket_system.lib.messages import (
    ErrorEnvelope,
    WarningMessages,
    format_error,
    format_warning,
)
from ticket_system.lib.ticket_builder import (
    format_child_ticket_id,
    format_ticket_id,
    get_next_child_seq,
    get_next_seq,
)
from ticket_system.lib.ticket_loader import get_ticket_path
from ticket_system.lib.ticket_validator import (
    extract_wave_from_ticket_id,
    validate_ticket_id,
)


def resolve_ticket_id_and_wave(args: argparse.Namespace, version: str) -> Optional[tuple]:
    """Step 1: 解析版本和 Ticket ID。

    Args:
        args: 命令行參數
        version: 已解析的版本號

    Returns:
        (version, ticket_id, wave) 或 None（失敗）
    """
    wave = args.wave

    if args.parent:
        # 建立子任務 ID（總是自動遞增，忽略 --seq）
        child_seq = get_next_child_seq(args.parent)
        if args.seq is not None:
            print(format_warning(
                WarningMessages.SEQ_IGNORED_WITH_PARENT,
                seq=args.seq,
                child_seq=child_seq,
            ))
        ticket_id = format_child_ticket_id(args.parent, child_seq)

        # 深度上限檢查（W1-056.5 協議 v2 D3）：沿 parent_id 鏈計算新子任務深度，
        # 達/超過 MAX_TICKET_DEPTH 時 warn（不硬擋，留旁路）。深度沿 parent_id 鏈
        # 而非 ID 字串數點（linux F1 fatal 教訓）。
        new_depth = compute_depth(args.parent, version) + 1
        if new_depth >= MAX_TICKET_DEPTH:
            print(format_warning(
                WarningMessages.DEPTH_LIMIT_REACHED,
                ticket_id=ticket_id,
                depth=new_depth,
                max_depth=MAX_TICKET_DEPTH,
            ))

        # 扇出 warning（W5-005 F7/D11）：父票 children 數超閾值時 warn（不硬擋）。
        existing_children_count = child_seq - 1
        if existing_children_count >= MAX_CHILDREN_WARNING_THRESHOLD:
            print(format_warning(
                WarningMessages.CHILDREN_COUNT_HIGH,
                parent_id=args.parent,
                count=existing_children_count,
                threshold=MAX_CHILDREN_WARNING_THRESHOLD,
            ))

        # 從 parent_id 中提取 wave
        extracted_wave = extract_wave_from_ticket_id(args.parent)
        if extracted_wave is not None:
            wave = extracted_wave
    else:
        # 建立根任務 ID
        if not wave:
            print(format_error(ErrorEnvelope(
                component="create",
                action="resolve_ticket_id",
                errno="MISSING_WAVE_PARAMETER",
                hint="建立根任務必須提供 --wave 參數（子任務則用 --parent 自動繼承 wave）",
            )))
            return None

        if args.seq is None:
            # auto-seq 模式：get_next_seq 回傳值已內部保證可用（W1-051 內聚
            # collision guard 至 get_next_seq 降級分支），caller 不再兜底。
            # 防護 W1-042：兩來源（本地 glob + main ref）同時掃空降級時，
            # get_next_seq 內的 resolve_available_seq 推進至本地檔案系統可用
            # 序號——僅保證本地 FS 可用，main-only 票不在保證範圍（W1-052 措辭
            # 對齊；PC-152 collision 家族；消除 caller while-loop 特例外洩）。
            seq = get_next_seq(version, wave)
            ticket_id = format_ticket_id(version, wave, seq)
        else:
            # 顯式 --seq 模式：尊重用戶意圖，撞號報錯退出（不覆寫、不自動跳號）。
            seq = args.seq
            ticket_id = format_ticket_id(version, wave, seq)
            if get_ticket_path(version, ticket_id).exists():
                print(format_error(ErrorEnvelope(
                    component="create",
                    action="resolve_ticket_id",
                    errno="TICKET_ID_ALREADY_EXISTS",
                    hint=(
                        f"顯式 --seq {seq} 對應的 Ticket ID 已存在: {ticket_id}。"
                        f"請改用其他 --seq，或省略 --seq 由系統自動配下一個可用序號"
                    ),
                )))
                return None

    # 驗證 Ticket ID
    if not validate_ticket_id(ticket_id):
        print(format_error(ErrorEnvelope(
            component="create",
            action="resolve_ticket_id",
            errno="INVALID_TICKET_ID_FORMAT",
            hint=f"Ticket ID 格式無效: {ticket_id}（預期: <version>-W<wave>-<seq>）",
        )))
        return None

    return (version, ticket_id, wave)
