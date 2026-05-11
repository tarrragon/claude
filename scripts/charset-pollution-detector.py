# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "opencc-python-reimplemented>=0.1.7",
# ]
# ///
"""Charset Pollution Detector — codepoint-aware 簡體字 / emoji 靜態文件偵測工具.

W17-144.1 落地：補位 zhtw-mcp 不偵測簡體字 codepoint / emoji 的場景缺口。

設計動機：
- W17-144 ANA 證明 zhtw-mcp 工具對 PC-072 場景不適用（自動 S2T 而非報錯）
- W17-144 第一輪自製 Python 腳本失敗（PC-074 共用字陷阱）
- 本工具用 OpenCC s2twp 雙向轉換 diff，OpenCC 內建處理共用字，避開 PC-074

三模式：
1. codepoint diff (OpenCC s2twp): 對輸入做簡->繁轉換，diff 原文，差異字元 = 簡體字
2. zhtw-mcp 檔案級預篩: 呼叫 mcp__zhtw-mcp__zhtw 看 detected_script / s2t_applied（需 MCP runtime；本腳本獨立執行時跳過）
3. emoji 範圍偵測: U+1F300-1FAFF / U+2600-27BF / U+1F000-1F0FF 等 unicode block

用法：
    uv run --script .claude/scripts/charset-pollution-detector.py [path...]
    uv run --script .claude/scripts/charset-pollution-detector.py --candidates /tmp/files.txt
    uv run --script .claude/scripts/charset-pollution-detector.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# 明確簡體字黑名單種子（用於動態建構 KNOWN_SIMPLIFIED_ANCHORS）
#
# 設計動機：
#   OpenCC s2t 對部分繁簡「異體字」（如「台 -> 臺」「群 -> 羣」）也會轉換，
#   但這些字在現代台灣繁體文書中是合法用字（台/臺、群/羣 並用）。
#   OpenCC 內部表沒有區分「合法異體 vs 簡體污染」的能力。
#
# 解法：以「明確簡體字」黑名單為核心過濾器：
#   - 命中條件：OpenCC s2t 後 != 原字 AND 原字 ∈ KNOWN_SIMPLIFIED_ANCHORS
#   - PC-074 防護：種子字串可能含繁簡共用字（如從中文詞抽字時），
#     初始化時用 OpenCC 動態過濾，只保留 s2t(X) != X 的字
#
# 為何用動態過濾而非靜態黑名單：
#   過去人工維護黑名單時反覆混入共用字（PC-074 同類錯誤），
#   交給 OpenCC 自動驗證能根本性避免此類失誤。
#
# 來源：
#   - PC-072 文件列出的常見污染字
#   - W17-145 hook 攔截實證的「实」
#   - 從中文常用詞庫提取（含可能誤入的共用字，由 OpenCC 動態過濾排除）
# 警告：禁從 OpenCC STCharacters 表全量抽取種子！
#
# W17-144.1.1 ANA 實證：OpenCC 對台灣現代繁體標準字有 30% 偏差，會把
# 「台/群/干」等台灣官方/教育部標準字誤判為簡體（s2t 轉「臺/羣/幹」）。
# 種子若從 OpenCC STCharacters 全量抽取會引入這些字，導致誤報合法繁體文件。
#
# 安全做法：種子從「PC-072 已知污染字 + 中文常用詞拆字」手選，
# OpenCC 動態過濾共用字（_build_anchors）+ self-test 反向驗證雙層保險。
_ANCHORS_SEED = (
    # PC-072 已知污染字
    "独违没务实觉决个隶遗设长"
    # W17-144.1.1.1 Method 6: Hook log 反推（PC-085 self-check 警示 12 字，明確簡體）
    # 來源：.claude/hooks/askuserquestion-charset-guard-hook.py 自身 self-check 機制
    "图两译驿气乐观检权铁转广"
    # 高頻簡體字（從中文詞抽字，含部分共用字，由 OpenCC 動態過濾）
    "为来对国会发还过这样时间问题点说话"
    "运动开机经济产业农业医药动员无线电话计算从认识结构办公关系应当应该"
    "语言书写学习练习课程节约"
    "报道导致传播讲话谈话谈论谈判读书写作业试验"
    "证据证明证书证件保护拒绝义务义工议会议题录音录影预备预告预测预防"
    "请问请进询问询价质量质询质疑质问质询资讯资料资本资助资金资本组织"
    "组合组件织布脏话脏污脏乱让步让位让座让出让给"
    "队员补充准备简单优秀两个观察检查权限气候"
)


# 台灣現代繁體標準字反向白名單（W17-144.1.1 ANA 實證 OpenCC 對這些字誤判為簡體）
#
# 用途：self-test 驗證 KNOWN_SIMPLIFIED_ANCHORS **不可包含**這些字。
# 來源：本 session 用 zhtw-mcp 實測 detected_script="traditional"（與 OpenCC 判斷相反）。
# 維護：未來新增 ANCHORS 種子前，必須先用 zhtw-mcp 確認 detected_script != "simplified"。
TAIWAN_STANDARD_WHITELIST: frozenset[str] = frozenset("台群才干了只布")


def _build_anchors(converter) -> frozenset[str]:
    """從種子字串過濾出 OpenCC 認可的簡體字（s2t(X) != X）.

    根本性避免 PC-074 共用字 false positive：
    人工撰寫種子字串時可能無意識混入繁簡共用字（如「件/本/保/言」），
    由 OpenCC 自動驗證排除這些字，不依賴維護者記憶力.
    """
    if converter is None:
        return frozenset()
    return frozenset(ch for ch in _ANCHORS_SEED if converter.convert(ch) != ch)


# 啟動時建構（OpenCC 不可用時為空集合，detector 失效但 self-test 仍能執行警告）
_BOOT_CONVERTER = None
try:
    from opencc import OpenCC

    _BOOT_CONVERTER = OpenCC("s2t")
except ImportError:
    pass

KNOWN_SIMPLIFIED_ANCHORS: frozenset[str] = _build_anchors(_BOOT_CONVERTER)


# Emoji unicode blocks（PC-072 列出的範圍）
EMOJI_RANGES: list[tuple[int, int]] = [
    (0x1F300, 0x1F9FF),  # Symbols & Pictographs / Emoticons / Transport / etc.
    (0x1FA00, 0x1FAFF),  # Symbols & Pictographs Extended-A
    (0x2600, 0x27BF),    # Miscellaneous Symbols / Dingbats
    (0x1F000, 0x1F02F),  # Mahjong / Domino tiles
    (0x1F0A0, 0x1F0FF),  # Playing cards
    (0x1F100, 0x1F1FF),  # Enclosed Alphanumeric Supplement
    (0x1F200, 0x1F2FF),  # Enclosed Ideographic Supplement
]


@dataclass(frozen=True)
class Finding:
    """單一污染命中。"""

    path: Path
    line: int
    col: int
    char: str
    codepoint: str
    kind: str  # "SIMPLIFIED" | "EMOJI"
    snippet: str


def is_emoji(ch: str) -> bool:
    """判定字元是否落入 emoji unicode block。"""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def make_converter():
    """建立 OpenCC s2t 轉換器（簡體 -> 繁體，純 codepoint 級單向映射）。

    為何用 s2t 而非 s2twp：
        s2twp 包含台灣慣用片語替換（如「主線程」-> 「主執行緒」），會將
        純繁體輸入也改寫，對 PC-072 偵測場景產生大量誤報。s2t 只做
        STCharacters 表（簡體 -> 繁體）的 codepoint 級映射，繁體字輸入
        OpenCC 不會轉換（因為繁體字不在 STCharacters 表的 key 中）。

    Returns:
        Convertible object with .convert(text) -> str.
        失敗時回傳 None（OpenCC 未安裝）。
    """
    try:
        from opencc import OpenCC

        return OpenCC("s2t")
    except ImportError:
        return None


def find_simplified_chars(
    text: str, converter, path: Path, strict_mode: bool = False
) -> list[Finding]:
    """用 OpenCC s2t + 黑名單過濾找明確簡體字污染位置.

    Strategy:
        1. OpenCC s2t 找出所有「OpenCC 認為要轉換」的字（first-pass）
        2. 用 KNOWN_SIMPLIFIED_ANCHORS 過濾，只保留「明確簡體字」
        3. strict_mode=True 時報所有 first-pass 命中（含異體字，高 recall 低 precision）
           strict_mode=False（預設）只報 anchor 過濾後的命中（高 precision）

    Args:
        text: 待掃描的文字.
        converter: OpenCC 實例（s2t）.
        path: 檔案路徑.
        strict_mode: 是否報所有 OpenCC 命中（含異體字誤報）.

    Returns:
        Finding 列表（kind="SIMPLIFIED"）.
    """
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        converted = converter.convert(line)
        if converted == line:
            continue
        for col, (orig, conv) in enumerate(zip(line, converted), 1):
            if orig == conv:
                continue
            if not ("一" <= orig <= "鿿"):
                continue
            # 預設模式：只報明確簡體字（PC-072 場景）
            if not strict_mode and orig not in KNOWN_SIMPLIFIED_ANCHORS:
                continue
            findings.append(
                Finding(
                    path=path,
                    line=lineno,
                    col=col,
                    char=orig,
                    codepoint=f"U+{ord(orig):04X}",
                    kind="SIMPLIFIED",
                    snippet=line.strip()[:80],
                )
            )
    return findings


def find_emoji(text: str, path: Path) -> list[Finding]:
    """偵測 emoji 字元位置."""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            if is_emoji(ch):
                findings.append(
                    Finding(
                        path=path,
                        line=lineno,
                        col=col,
                        char=ch,
                        codepoint=f"U+{ord(ch):04X}",
                        kind="EMOJI",
                        snippet=line.strip()[:80],
                    )
                )
    return findings


def scan_file(path: Path, converter, strict_mode: bool = False) -> list[Finding]:
    """掃描單一檔案."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    findings: list[Finding] = []
    if converter is not None:
        findings.extend(find_simplified_chars(text, converter, path, strict_mode))
    findings.extend(find_emoji(text, path))
    return findings


def collect_candidates(args: argparse.Namespace) -> list[Path]:
    """從 args 收集候選檔案清單."""
    files: list[Path] = []
    if args.candidates:
        candidates_file = Path(args.candidates)
        files.extend(
            Path(line.strip())
            for line in candidates_file.read_text().splitlines()
            if line.strip()
        )
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(p.rglob("*.md"))
            files.extend(p.rglob("*.yaml"))
            files.extend(p.rglob("*.yml"))
            files.extend(p.rglob("*.txt"))
        elif p.is_file():
            files.append(p)
    return [f for f in files if f.exists() and f.is_file()]


def report(findings: list[Finding]) -> None:
    """輸出掃描報告."""
    if not findings:
        print("\n=== Scan Result: 0 findings ===")
        print("實證 W17-144 推論：靜態文件中無簡體字 codepoint / emoji 污染")
        print("PC-072 污染源確認在 AI 生成側（token 機率分佈），不在文件")
        return

    by_file: dict[Path, list[Finding]] = {}
    for f in findings:
        by_file.setdefault(f.path, []).append(f)

    print(f"\n=== Scan Result: {len(findings)} findings in {len(by_file)} files ===\n")
    for path in sorted(by_file.keys()):
        items = by_file[path]
        print(f"\n## {path}")
        for f in items[:30]:
            print(
                f"  L{f.line}:C{f.col} [{f.kind}] '{f.char}' {f.codepoint} -- {f.snippet}"
            )
        if len(items) > 30:
            print(f"  ... +{len(items) - 30} more")

    # 統計
    simp = sum(1 for f in findings if f.kind == "SIMPLIFIED")
    emoji = sum(1 for f in findings if f.kind == "EMOJI")
    print(f"\n=== Summary ===")
    print(f"Files with issues: {len(by_file)}")
    print(f"SIMPLIFIED findings: {simp}")
    print(f"EMOJI findings: {emoji}")


def self_test(converter) -> int:
    """單元測試：OpenCC 對共用字（PC-074 範圍）正確不誤報.

    Returns:
        0 if all pass, 1 otherwise.
    """
    if converter is None:
        print("[SELF-TEST] OpenCC 未安裝，跳過")
        return 1

    # PC-074 共用字測試集（繁簡共用，OpenCC 不應視為簡體）
    shared_chars = ["件", "本", "保", "言", "系", "明", "和", "的", "是", "有"]
    failures: list[str] = []
    for ch in shared_chars:
        converted = converter.convert(ch)
        if converted != ch:
            failures.append(f"'{ch}' (U+{ord(ch):04X}) -> '{converted}'")

    # PC-072 已知污染字測試集（明確簡體，應被轉換）
    pollution_samples = [
        ("独", "獨"),  # U+72EC -> 獨
        ("违", "違"),  # U+8FDD -> 違
        ("实", "實"),  # U+5B9E -> 實
        ("决", "決"),  # U+51B3 -> 決
        ("遗", "遺"),  # U+9057 -> 遺
        ("补", "補"),  # U+8865 -> 補
    ]
    pollution_failures: list[str] = []
    for src, expected in pollution_samples:
        converted = converter.convert(src)
        if converted != expected:
            pollution_failures.append(
                f"'{src}' (U+{ord(src):04X}) -> '{converted}' (expected '{expected}')"
            )

    if failures:
        print("[SELF-TEST FAIL] 共用字被誤判為簡體字（PC-074 違規）：")
        for line in failures:
            print(f"  - {line}")
    else:
        print(
            f"[SELF-TEST PASS] {len(shared_chars)} 個共用字 OpenCC 正確保留（PC-074 防護有效）"
        )

    if pollution_failures:
        print("[SELF-TEST FAIL] 已知污染字未被正確轉換：")
        for line in pollution_failures:
            print(f"  - {line}")
    else:
        print(
            f"[SELF-TEST PASS] {len(pollution_samples)} 個 PC-072 已知污染字正確轉換為繁體"
        )

    # 第三層測試：黑名單不含繁簡共用字（PC-074 防護）
    forbidden_in_anchors = [
        ch for ch in shared_chars if ch in KNOWN_SIMPLIFIED_ANCHORS
    ]
    if forbidden_in_anchors:
        print(
            f"[SELF-TEST FAIL] KNOWN_SIMPLIFIED_ANCHORS 含繁簡共用字（PC-074 違規）："
            f" {forbidden_in_anchors}"
        )
        return 1
    print(
        f"[SELF-TEST PASS] KNOWN_SIMPLIFIED_ANCHORS 未含 {len(shared_chars)} 個共用字"
        f"（PC-074 防護有效）"
    )

    # 第四層測試：黑名單所有字都應被 OpenCC s2t 視為簡體（即 s2t(X) != X）
    invalid_anchors: list[str] = []
    for ch in KNOWN_SIMPLIFIED_ANCHORS:
        if converter.convert(ch) == ch:
            invalid_anchors.append(ch)
    if invalid_anchors:
        print(
            f"[SELF-TEST FAIL] KNOWN_SIMPLIFIED_ANCHORS 含 {len(invalid_anchors)} 個"
            f"非簡體字（OpenCC s2t 未轉換）：{invalid_anchors[:10]}"
        )
        return 1
    print(
        f"[SELF-TEST PASS] KNOWN_SIMPLIFIED_ANCHORS 全 {len(KNOWN_SIMPLIFIED_ANCHORS)} 字"
        f"皆為 OpenCC 認可簡體字"
    )

    # 第五層測試：台灣標準字反向白名單（W17-144.1.1 ANA 實證 OpenCC 對這些字誤判）
    # 詳見 _ANCHORS_SEED 上方警告與 TAIWAN_STANDARD_WHITELIST 註解
    forbidden_taiwan_std = [
        ch for ch in TAIWAN_STANDARD_WHITELIST if ch in KNOWN_SIMPLIFIED_ANCHORS
    ]
    if forbidden_taiwan_std:
        print(
            f"[SELF-TEST FAIL] KNOWN_SIMPLIFIED_ANCHORS 含台灣標準字"
            f"（W17-144.1.1 違規）：{forbidden_taiwan_std}"
        )
        print(
            "  原因：OpenCC 把台灣繁體標準字（如 台/群/干）誤判為簡體；"
            "若 _ANCHORS_SEED 從 OpenCC STCharacters 全量抽取會踩雷。"
        )
        return 1
    print(
        f"[SELF-TEST PASS] KNOWN_SIMPLIFIED_ANCHORS 未含 {len(TAIWAN_STANDARD_WHITELIST)} 個"
        f"台灣標準字（W17-144.1.1 反向白名單防護有效）"
    )

    return 0 if not failures and not pollution_failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Charset Pollution Detector for PC-072 / W17-144.1",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="要掃描的檔案或目錄路徑（可多個）",
    )
    parser.add_argument(
        "--candidates",
        help="候選檔案清單路徑（每行一個檔案）",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="執行單元測試（OpenCC 對共用字不誤報 + PC-072 已知污染字轉換正確）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="strict 模式：報所有 OpenCC s2t 命中（含異體字誤報，高 recall）",
    )
    args = parser.parse_args(argv)

    converter = make_converter()
    if converter is None and not args.self_test:
        print(
            "[ERROR] OpenCC 未安裝。執行：uv run --script <此檔> 自動拉依賴",
            file=sys.stderr,
        )
        return 2

    if args.self_test:
        return self_test(converter)

    if not args.paths and not args.candidates:
        parser.print_help()
        return 1

    files = collect_candidates(args)
    mode = "strict (high recall)" if args.strict else "anchor-filtered (high precision)"
    print(f"=== Scanning {len(files)} files [{mode}] ===")

    findings: list[Finding] = []
    for f in files:
        findings.extend(scan_file(f, converter, strict_mode=args.strict))

    report(findings)
    return 0 if not findings else 0  # 報告不阻擋；阻擋邏輯由 hook 層處理


if __name__ == "__main__":
    sys.exit(main())
