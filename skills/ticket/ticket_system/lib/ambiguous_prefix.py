"""共用的 argparse 縮寫歧義攔截 helper（1.0.0-W1-028）。

## 背景

argparse 預設啟用 prefix matching（`allow_abbrev=True`）：當使用者輸入某個
旗標的唯一前綴時會自動展開。但若該前綴同時是多個完整旗標的前綴（例如
`--to` 同時撞 `--to-parent` / `--to-child` / `--to-sibling`），argparse 會吐出
原生英文 ambiguous 訊息，不說明各完整旗標的用途，對中文使用者不友善。

## 機制

顯式在 subparser 上以 `nargs="?"` 註冊該歧義 token，使 **exact match 優先於
縮寫展開**；命中時改以中文提示指引使用者改用完整旗標名。`help=argparse.SUPPRESS`
避免污染 `--help` 輸出。

## 作用域

helper 以「註冊在哪個 subparser」控制作用域。例如 `--all` 僅在 set-acceptance
subparser 攔截，不影響 list/stale-list/td-status/stuck-anas 等將 `--all` 作為
合法完整旗標的子命令（PM grep 實證 + 1.0.0-W1-028 約束 1）。
"""
import argparse
from typing import Optional


class AmbiguousPrefixAction(argparse.Action):
    """攔截縮寫歧義 token，輸出中文用途提示。

    透過 Action 屬性 `hint` 攜帶提示文字（由 `make_ambiguous_action` 建立的
    子類別在 class 層級設定），命中時呼叫 `parser.error(self.hint)` 終止解析。

    與 nargs="?" 搭配：使 exact match 優先於 argparse 的縮寫展開。
    """

    #: 中文用途提示；由 make_ambiguous_action 動態建立的子類別覆寫。
    hint: str = ""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: Optional[str] = None,
    ) -> None:
        parser.error(self.hint)


def make_ambiguous_action(hint: str) -> type:
    """建立帶有指定中文提示的 AmbiguousPrefixAction 子類別。

    argparse 的 `action=` 接受 Action 類別（而非實例），故以動態子類別在
    class 層級攜帶 `hint`，避免在 __init__ 傳參的相容性問題。

    Args:
        hint: 命中歧義 token 時顯示的中文用途提示。

    Returns:
        AmbiguousPrefixAction 子類別，可直接作為 `action=` 傳入。
    """
    return type(
        "AmbiguousPrefixActionWithHint",
        (AmbiguousPrefixAction,),
        {"hint": hint},
    )


def register_ambiguous_prefix(
    parser: argparse.ArgumentParser, option_string: str, hint: str
) -> None:
    """在指定 subparser 上註冊一個縮寫歧義攔截旗標。

    封裝 add_argument 的標準樣板（nargs="?" + SUPPRESS + 動態 Action），
    呼叫端只需提供 token 與中文提示。

    Args:
        parser: 要註冊的 subparser（決定攔截作用域）。
        option_string: 要攔截的歧義 token（如 "--to"、"--all"）。
        hint: 命中時顯示的中文用途提示。
    """
    parser.add_argument(
        option_string,
        nargs="?",
        action=make_ambiguous_action(hint),
        help=argparse.SUPPRESS,
    )
