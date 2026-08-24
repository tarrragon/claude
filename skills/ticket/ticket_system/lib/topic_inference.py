"""主題歸屬推導與參數驗證。

主題是 ticket 的附加分組資訊，全程存於 side-channel 檔案（topics-registry.txt
與 topic-assignments.txt），不進 ticket frontmatter。本模組承擔兩件事：
判斷新票應歸屬哪個主題（推導判準 S1/S2/S3），以及驗證使用者顯式給定的主題
參數是否合法。

自 commands/create.py 抽出（0.2.1-W3-831）：該檔已達 1684 行，主題推導與建票
流程協調屬不同 domain，且推導邏輯可被 topic_backfill 等命令重用於批次指派建議。
抽出過程不改變任何行為，由 test_create_topic_selection 的 36 項測試作回歸保護。

判準來源為 0.2.1-W3-826 分析：
- S1 上游繼承：source_ticket 或 parent_id 的上游已有主題（2026-08-24
  全量模擬 448 張已指派票：結構上可觸及 79.7%、實際命中 45.5%，命中時
  主題正確率 91.7%——優先序依據是命中精度而非覆蓋廣度）
- S2 檔案叢集：where.files 與某主題既有涵蓋路徑交集達門檻特異性
- S3 ANA 標記：ANA 必然 spawn 衍生票，未歸屬會使整串後續票一併失明
"""
from __future__ import annotations

import argparse


# S2 判準的交集特異性門檻：共同深度未達此段數視為過泛，不算命中。
# 對齊 track parallel-check 的「共同祖先深度 >= 3 段」慣例。
MIN_CLUSTER_PATH_DEPTH = 3

# S2 判準的主題涵蓋度門檻：路徑同時出現在達此數量的不同主題叢集中，視為
# hub 檔案（如 SKILL.md、track.py），涵蓋度過廣使其對「該票屬於哪個主題」
# 失去鑑別力，排除其匹配資格。全量量測顯示 hub 檔案（3 個以上主題共用）
# 的判準精度遠低於 non-hub 檔案，且平手集合中固定主題因字串排序恆勝出，
# 造成系統性偏壓指派。門檻定於 3 對齊該量測的 hub 定義；不使用連續加權
# （IDF），因後者需重設計 tie-break、對既有測試影響範圍過大。
HUB_TOPIC_COVERAGE_THRESHOLD = 3


def build_topic_file_clusters() -> dict:
    """從已指派票反推「主題 -> where.files 路徑集合」，供判準 S2 比對。

    只讀已指派票，不掃全部票：未指派票對叢集形狀零貢獻，讀它們純屬浪費
    （0.2.1-W3-828 實測 231 張已指派 351 ms，全量 895 張 2218 ms）。
    不設快取為用戶裁示（2026-08-20），改以 S1 優先短路壓低本函式呼叫
    頻率；成本隨已指派票數線性成長，需要快取時再依當時票數評估。
    """
    from ticket_system.lib.id_parser import extract_id_components
    from ticket_system.lib.parser import load_ticket
    from ticket_system.lib.topic_assignments import list_assignments

    clusters: dict = {}
    for assigned_id, assigned_topic in list_assignments().items():
        components = extract_id_components(assigned_id)
        if not components:
            continue
        ticket = load_ticket(components["version"], assigned_id)
        if not ticket:
            continue
        paths = (ticket.get("where") or {}).get("files") or []
        clusters.setdefault(assigned_topic, set()).update(paths)
    return clusters


def path_depth(path: str) -> int:
    """路徑段數，空段不計（與 file_conflict 的段數比較慣例一致）。"""
    return len([part for part in (path or "").strip("/").split("/") if part])


def build_file_topic_coverage(clusters: dict) -> dict:
    """反查每個已知路徑出現於幾個不同主題叢集，供 hub 檔案排除判斷。

    涵蓋度只計「不同主題數」，非路徑出現次數：同一主題內同路徑重複
    對鑑別力無新增資訊，只有跨主題共用才代表該路徑失去區辨能力。
    """
    coverage: dict = {}
    for topic, known_paths in clusters.items():
        for path in known_paths:
            coverage.setdefault(path, set()).add(topic)
    return {path: len(topics) for path, topics in coverage.items()}


def infer_topic_from_files(where_files) -> tuple:
    """判準 S2：where.files 與某既有主題涵蓋路徑有交集時推導該主題。

    交集的特異性以雙方較淺的一方計：真實票庫存在 docs/ 與 .claude/hooks/
    這類淺層 where.files，它們與該目錄下任何路徑都相交。若不設門檻，
    擁有淺層路徑的主題會成為所有新票的推導結果，推導從「找出相關主題」
    退化為「總是指向同一個主題」（0.2.1-W3-828 實測：docs/spec/ 下的
    新票因 docs/ 而誤指 skill-sync 主題）。

    同深度多主題命中時以主題名排序決定勝者：真實票庫中同一檔案可能見於
    多個主題的票（如 lease.py），若依 dict 迭代順序取首個，結果會隨映射
    表寫入順序改變，同樣輸入在不同時間給出不同主題，使推導無法被測試。

    hub 檔案（涵蓋度達 HUB_TOPIC_COVERAGE_THRESHOLD 個以上主題，如
    SKILL.md、track.py）在比對前即排除：這類路徑幾乎被所有主題觸及，
    深度足夠但涵蓋度過廣，對「該票屬於哪個主題」無鑑別力，與淺層路徑
    造成的過泛問題同構，故用獨立門檻處理（不與 MIN_CLUSTER_PATH_DEPTH
    合併，兩者針對不同軸線：深度篩「路徑本身夠不夠具體」，涵蓋度篩
    「路徑是否被太多主題共用」）。
    """
    from ticket_system.lib.file_conflict import files_intersect

    paths = [p.strip() for p in (where_files or "").split(",") if p.strip()]
    if not paths:
        return None, None

    clusters = build_topic_file_clusters()
    coverage = build_file_topic_coverage(clusters)

    matches = []
    for candidate_topic, known_paths in clusters.items():
        for path in paths:
            for known in known_paths:
                if coverage.get(known, 0) >= HUB_TOPIC_COVERAGE_THRESHOLD:
                    continue
                specificity = min(path_depth(path), path_depth(known))
                if specificity < MIN_CLUSTER_PATH_DEPTH:
                    continue
                if not files_intersect(path, known):
                    continue
                matches.append((specificity, candidate_topic, path, known))

    if not matches:
        return None, None
    matches.sort(key=lambda match: (-match[0], match[1]))
    _, matched_topic, matched_path, matched_known = matches[0]
    return matched_topic, (
        f"S2 檔案叢集（{matched_path} 與該主題既有 {matched_known} 交集）"
    )


def infer_topic(args: argparse.Namespace) -> tuple:
    """依 0.2.1-W3-826 判準推導主題，回傳 (topic, basis)。

    S1 上游繼承優先於 S2 檔案叢集：S1 只需讀映射表與一個鍵（實測 35 ms），
    S2 需反推全部已指派票的路徑集合（351 ms），且 S1 的語意更強——衍生票
    與上游處理同一機制，主題必然相同，而路徑交集只是相關性推測。S1 命中
    率非優先序依據（結構可觸及僅 79.7%、實際命中僅 45.5%，見模組
    docstring），優先序依據是成本與語意強度，S1 命中時的高精度（91.7%）
    是命中後可信賴的佐證，非命中率本身。
    判準 S3（ANA 型應歸屬）不在此推導：它判定「應歸屬」而非「屬於哪個
    主題」，無從產出主題名，由呼叫端另行標記。

    `--discovered-during` 短路 S1：該旗標標記發現衍生（執行中撞到跨主題
    問題），上游主題只反映「當時剛好在改哪個檔案」，與新票的實際內容無關，
    S1 在此情境下必然給錯答案。跳過 S1 後仍落回 S2——S2 依新票自身的
    where_files 推導，與上游無關，語意不受影響。
    """
    from ticket_system.lib.topic_assignments import list_assignments

    if not getattr(args, "discovered_during", None):
        assignments = None
        for attr, label in (("source_ticket", "source_ticket"), ("parent", "parent_id")):
            upstream = getattr(args, attr, None)
            if not upstream:
                continue
            if assignments is None:
                assignments = list_assignments()
            inherited = assignments.get(upstream)
            if inherited:
                return inherited, f"S1 上游繼承（{label}={upstream}）"

    return infer_topic_from_files(getattr(args, "where_files", None))


def requires_topic_assignment(args: argparse.Namespace) -> bool:
    """判準 S3：ANA 型票未歸屬不得靜默略過。

    ANA 必然 spawn 衍生票，其主題經 S1 放大到整串後續票；ANA 自身未歸屬
    會使整串後續票一併失明。本函式只判定「應歸屬」，實際的要求邏輯
    （旗標三選一）由 0.2.1-W3-829 承接。
    """
    return (getattr(args, "type", None) or "IMP").upper() == "ANA"


def validate_topic_selection(args: argparse.Namespace) -> tuple:
    """驗證 --topic / --new-topic 參數合法性，回傳 (topic, error, new_topic)。

    主題為建票的附加資訊，全程不寫入任何 ticket frontmatter 欄位：既有
    主題寫入 topics-registry.txt 的 side-channel 由 topic_registry 模組
    負責。本函式只做參數合法性檢查，不觸及任何持久化——實際的
    `append_assignment()` 呼叫（同時完成主題名註冊與 ticket_id -> topic
    映射寫入）延後至呼叫端確認建票成功（`rc == 0`）後才執行：若在此驗證
    階段就寫入，checklist 等後續步驟導致建票失敗時主題已寫入 append-only
    清單且無法清除，留下無對應票的孤兒主題。

    - `--topic NAME`：只能選中央清單既有主題（正規化比對），未命中時拒絕
      並在錯誤訊息列出既有主題名供選。
    - `--new-topic NAME`：新增主題須經此獨立顯式旗標，不接受從 `--topic`
      自由輸入新名稱（自由輸入會讓同一主題產生多個拼寫變體，使清單失去
      分組能力）。本函式只驗證名稱非空白，不寫入清單。
    - 兩者同時指定視為參數衝突，直接拒絕。
    - 皆未指定時回傳 (None, None, None)：未指派主題不阻擋建票，由呼叫端
      在報告階段明確表示「未指派」狀態。

    Returns:
        (topic, error_message, new_topic_to_register)：
        - error_message 非 None 時代表驗證失敗，呼叫端須中止建票，不得
          進入任何持久化步驟（含 append_assignment）。
        - new_topic_to_register 非 None 時代表為新增主題（與 topic 同值），
          呼叫端於建票成功後統一以 `topic` 呼叫 `append_assignment`
          落實新增與映射寫入，不需另外區分處理。
    """
    from ticket_system.lib.topic_registry import list_topics, normalize_topic_name

    topic_arg = getattr(args, "topic", None)
    new_topic_arg = getattr(args, "new_topic", None)

    no_topic_arg = bool(getattr(args, "no_topic", False))
    if no_topic_arg and (topic_arg or new_topic_arg):
        return None, (
            "--no-topic 與 --topic / --new-topic 不可同時指定："
            "--no-topic 是明示不指派主題，與指定主題互相矛盾"
        ), None

    if topic_arg and new_topic_arg:
        return None, (
            "--topic 與 --new-topic 不可同時指定："
            "--topic 只能選既有主題，--new-topic 才能新增主題"
        ), None

    if new_topic_arg:
        stripped = new_topic_arg.strip()
        if not normalize_topic_name(stripped):
            return None, "--new-topic 無效：主題名不可為空白字串", None
        return stripped, None, stripped

    if topic_arg:
        existing = list_topics()
        existing_keys = {normalize_topic_name(t): t for t in existing}
        key = normalize_topic_name(topic_arg)
        if key not in existing_keys:
            hint = (
                "既有主題：" + "、".join(existing)
                if existing
                else "目前尚無任何既有主題，請改用 --new-topic 新增"
            )
            return None, f"--topic 指定的主題「{topic_arg}」不存在。{hint}", None
        return existing_keys[key], None, None

    return None, None, None
