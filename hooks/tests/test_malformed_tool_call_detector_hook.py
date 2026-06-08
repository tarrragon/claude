#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""malformed-tool-call-detector-hook.py 測試

涵蓋：
  W2-011.1 false-positive 修復：strip_code_regions 須剝除
    根因 A：4-space 縮排 code block（縮排引述標記不應命中 signature）
    根因 B：跨行 backtick 引述（多行反引號內標記不應命中 signature）
  W2-011.2 內嵌 self-test：--self-test 分支與 _self_test() 真陽真陰 fixtures

DRY：真陽/真陰 fixtures 不在本檔重複定義，改引用 hook 模組的
  SELF_TEST_TRUE_NEGATIVES / SELF_TEST_TRUE_POSITIVES（單一事實來源），
  避免 fixture 與 hook 內嵌版本漂移。

同時回歸驗證真陽偵測形態仍 100% 攔截，且 signature 4（游離 token 接
invoke）不被削弱。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "malformed-tool-call-detector-hook.py"


def _load_hook_module():
    """動態載入 Hook 模組（檔名含 `-` 不能用一般 import）。"""
    spec = importlib.util.spec_from_file_location("malformed_detector_hook", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hook_mod():
    return _load_hook_module()


# ---------------------------------------------------------------------------
# 真陰：被引述的標記字面不應命中（fixtures 來自 hook 模組，DRY）
# ---------------------------------------------------------------------------


def test_true_negative_not_detected(hook_mod):
    """真陰：引述標記字面不應命中任何簽章（4 種引述形態）。"""
    for name, text in hook_mod.SELF_TEST_TRUE_NEGATIVES.items():
        assert hook_mod.detect(text) == "", f"真陰 fixture '{name}' 誤命中"


# ---------------------------------------------------------------------------
# 真陽：真實寫壞的標記必須命中（fixtures 來自 hook 模組，DRY）
# ---------------------------------------------------------------------------


def test_true_positive_detected(hook_mod):
    """真陽：真實寫壞的工具標記必須命中（3 種形態）。"""
    for name, text in hook_mod.SELF_TEST_TRUE_POSITIVES.items():
        assert hook_mod.detect(text) != "", f"真陽 fixture '{name}' 漏抓"


def test_signature_five_paired_close_present(hook_mod):
    """signature 5（成對閉合 <invoke>…</invoke>）必須存在且涵蓋非行首完整 invoke。

    W2-011.4：涵蓋「漏 antml 前綴的完整 invoke 字面」缺口。pattern 須能在散文
    夾住的完整工具呼叫（非行首）命中，且不誤觸 fenced 引述的成對標記。
    """
    patterns = [p.pattern for p in hook_mod.SIGNATURE_PATTERNS]
    assert any(
        "invoke" in p and "</" in p and "*?" in p for p in patterns
    ), "signature 5（成對閉合非貪婪 <invoke>…</invoke>）遺失"
    # 真陽：非行首完整 invoke 須命中
    tp = hook_mod.SELF_TEST_TRUE_POSITIVES["paired_close_non_linestart"]
    assert hook_mod.detect(tp) != "", "成對閉合非行首真陽應被攔截"
    # 真陰：fenced 引述的成對標記不應命中（strip 後消失）
    tn = hook_mod.SELF_TEST_TRUE_NEGATIVES["paired_close_fenced_prose"]
    assert hook_mod.detect(tn) == "", "fenced 引述的成對標記不應誤觸 signature 5"


def test_signature_four_preserved(hook_mod):
    """signature 4（游離 token 接 invoke）必須存在且仍可攔截（禁削弱）。"""
    patterns = [p.pattern for p in hook_mod.SIGNATURE_PATTERNS]
    assert any("invoke" in p and r"\n" in p for p in patterns), (
        "signature 4（游離 token \\n <invoke）已遺失，違反 thyme F3 證偽結論"
    )
    stray = hook_mod.SELF_TEST_TRUE_POSITIVES["stray_token_invoke"]
    assert hook_mod.detect(stray) != ""


# ---------------------------------------------------------------------------
# meta-context 豁免（W2-011.3，PC-099 對齊）
# ---------------------------------------------------------------------------


def _residual_meta_prose(hook_mod):
    """構造 IMP .1 strip 修復後仍殘留的誤報：純散文嵌入裸標記（無 code 包覆）。"""
    open_tag = hook_mod._OPEN  # "<invoke"（字串拼接組裝，避免本檔被掃描誤觸）
    return (
        "本 hook 偵測的問題是這樣：模型輸出時若把標記寫成\n"
        f"{open_tag} name=\"Foo\"> 這種裸形式（漏 antml 前綴），harness 無法解析。"
    )


def test_residual_meta_prose_without_marker_still_detected(hook_mod):
    """真陽保留：無 exempt marker 的散文裸標記仍須命中（豁免不削弱攔截力）。"""
    text = _residual_meta_prose(hook_mod)
    assert hook_mod.detect(text) != "", "殘留 meta 散文（無 marker）應仍被攔截"


def test_meta_context_marker_suppresses_detection(hook_mod):
    """治本：同一散文加上顯式 exempt marker → 整段豁免（回傳空字串）。"""
    text = _residual_meta_prose(hook_mod)
    marked = "<!-- malformed-detector-exempt: 討論偵測本身 -->\n" + text
    assert hook_mod.detect(marked) == "", "含 exempt marker 的 meta 散文應被豁免"


def test_marker_does_not_suppress_real_malformed_call(hook_mod):
    """真陽不被誤豁免：真實壞呼叫（無 marker）不受豁免機制影響。

    豁免僅在訊息顯式含 marker 時生效；真正寫壞的工具呼叫由 harness 渲染而成，
    絕不含此 meta 註解，故 true-positive 攔截力不被削弱。
    """
    for name, text in hook_mod.SELF_TEST_TRUE_POSITIVES.items():
        assert "malformed-detector-exempt" not in text
        assert hook_mod.detect(text) != "", f"真陽 fixture '{name}' 不應受豁免影響"


# ---------------------------------------------------------------------------
# 內嵌 self-test（W2-011.2 acceptance）
# ---------------------------------------------------------------------------


def test_self_test_function_passes(hook_mod):
    """_self_test() 應回傳空清單（所有內嵌 fixtures 通過）。"""
    failures = hook_mod._self_test()
    assert failures == [], f"_self_test 回報失敗：{failures}"


def test_self_test_cli_exit_zero():
    """--self-test 分支應 exit 0 並印通過訊息（CI 接線路徑）。"""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--self-test 非 0 退出：rc={result.returncode} stderr={result.stderr}"
    )
    assert "self-test 通過" in result.stdout
