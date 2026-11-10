#!/usr/bin/env python3
"""共用標記區段 markdown 表格回寫邏輯（供 fix_status.py / fix_version.py 共用）。

`fix-matrix`（軸 C：per-consumer 狀態，2 欄）與 `fix-versions`（軸 D：版本號
註記，3 欄）欄位形狀不同，解析/渲染邏輯各自保留；但「整段替換既有標記區段，
不存在則 append 於 body 末」這段邏輯結構完全相同（quality-common 1.4：
結構相同、參數不同 → 提取並參數化），故抽出為共用函式，避免兩份腳本各自
維護一份等價但獨立演化的 upsert 邏輯。
"""


def upsert_section(body: str, section_re, rendered: str) -> str:
    """把已渲染的區段字串寫回 body：既有區段整段替換，否則 append 於 body 末。

    section_re 為呼叫端定義的區段偵測 regex（含起訖標記，DOTALL）。
    """
    body = body or ""
    if section_re.search(body):
        return section_re.sub(lambda _: rendered, body, count=1)
    separator = "\n\n" if body and not body.endswith("\n") else "\n"
    return f"{body}{separator}{rendered}\n"
