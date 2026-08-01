from datetime import datetime, timedelta
import json
import random
import streamlit as st
import streamlit.components.v1 as components

# ローカルストレージ連携ライブラリの読み込み
try:
    from streamlit_local_storage import LocalStorage

    local_storage = LocalStorage()
except ImportError:
    local_storage = None

# ------------------------------------------------------------------------------
# 1. ページ基本設定
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Swim Practice Planner",
    page_icon="🏊‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SECRET_PASSPHRASE = "swim2026"

# ------------------------------------------------------------------------------
# 2. セッション状態の初期化
# ------------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if "generated_menus" not in st.session_state:
    st.session_state["generated_menus"] = None

if "custom_presets" not in st.session_state:
    st.session_state["custom_presets"] = []


# ------------------------------------------------------------------------------
# 3. ユーティリティ関数（サークル計算・タイムライン再計算）
# ------------------------------------------------------------------------------
def format_circle_time(seconds: int) -> str:
    """秒数を '1"15' や ''55"' などの水泳特有のサークル表記に変換"""
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}'{secs:02d}\""
    else:
        return f"'{secs:02d}\""


def calc_circle_seconds(distance_m: int, base_100m: int, margin_sec: int) -> int:
    """100mベースタイムから距離ごとのサークル（秒）を計算"""
    base_for_dist = (base_100m / 100) * distance_m
    total_sec = int(base_for_dist + margin_sec)
    return max(15, round(total_sec / 5) * 5)


def recalculate_timeline(lane_menu_items: list, start_time_obj: datetime):
    """手動編集・削除・追加があった際に、タイムラインを上から順に再計算"""
    current_time = start_time_obj
    for item in lane_menu_items:
        item["start_time"] = current_time.strftime("%H:%M")
        total_sec = item["reps"] * item["circle_sec"]
        item["total_sec"] = total_sec
        current_time += timedelta(seconds=total_sec)
        item["end_time"] = current_time.strftime("%H:%M")


# ------------------------------------------------------------------------------
# 4. 標準プリセットデータ
# ------------------------------------------------------------------------------
DEFAULT_PRESETS = [
    {
        "name": "50m × 8 1'05\" Kick IMO",
        "item": {
            "section": "Kick",
            "distance_m": 50,
            "reps": 8,
            "circle_sec": 65,
            "style": "Board Kick IMO",
            "desc": "Odd: Easy / Even: Hard",
        },
    },
    {
        "name": "100m × 4 1'45\" Pull Hypoxic 3/5/7",
        "item": {
            "section": "Pull",
            "distance_m": 100,
            "reps": 4,
            "circle_sec": 105,
            "style": "Pull Hypoxic",
            "desc": "ブレス制限（3/5/7本交代）",
        },
    },
    {
        "name": "50m × 8 1'30\" Main All Out",
        "item": {
            "section": "Main",
            "distance_m": 50,
            "reps": 8,
            "circle_sec": 90,
            "style": "50m Max スプリント",
            "desc": "長めレストで全本数100%出力",
        },
    },
    {
        "name": "100m × 6 1'40\" Main Pace Hold",
        "item": {
            "section": "Main",
            "distance_m": 100,
            "reps": 6,
            "circle_sec": 100,
            "style": "100m Pace Hold",
            "desc": "ターゲットペースを落とさずに維持",
        },
    },
]


# ------------------------------------------------------------------------------
# 5. メニュー自動生成エンジン
# ------------------------------------------------------------------------------
def generate_lane_menu(
    lane_name: str,
    base_100m: int,
    start_time_obj: datetime,
    focus: dict,
    available_tools: list,
) -> list:
    sections = ["Warm up", "Kick", "Pull", "Drill", "Main", "Down"]
    lane_menu = []
    current_time = start_time_obj

    drill_candidates = [
        {"name": "Form Drill IMO", "tools": []},
        {"name": "Sculling & Catch", "tools": []},
        {"name": "Board Kick & Drill", "tools": ["board"]},
        {"name": "Snorkel Drill", "tools": ["snorkel"]},
        {"name": "Paddle & Fin Drill", "tools": ["paddle", "fin"]},
    ]

    pull_candidates = [
        {"name": "Pull Choice", "tools": ["buoy"]},
        {"name": "Pull Hypoxic (3/5/7)", "tools": ["buoy"]},
        {"name": "Pull w/Paddle", "tools": ["buoy", "paddle"]},
    ]

    valid_drills = [
        d
        for d in drill_candidates
        if all(tool in available_tools for tool in d["tools"])
    ]
    valid_pulls = [
        p
        for p in pull_candidates
        if all(tool in available_tools for tool in p["tools"])
    ]

    if not valid_drills:
        valid_drills = [{"name": "Form Drill Choice", "tools": []}]
    if not valid_pulls:
        valid_pulls = [{"name": "Pull Choice (No Buoy)", "tools": []}]

    speed_factor = focus["speed"] / 100.0
    endurance_factor = focus["endurance"] / 100.0

    for idx, sec in enumerate(sections):
        item = {"item_id": f"item_{idx}_{random.randint(1000, 9999)}"}
        item["section"] = sec
        item["start_time"] = current_time.strftime("%H:%M")

        if sec == "Warm up":
            item["distance_m"] = 400 if base_100m < 90 else 300
            item["reps"] = 1
            item["style"] = "Choice Easy"
            margin = 35 if base_100m < 90 else 45
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, margin
            )
            item["desc"] = "フォームチェック"

        elif sec == "Kick":
            item["distance_m"] = 50
            item["reps"] = 8 if endurance_factor > 0.4 else 6
            tool_name = "Board Kick" if "board" in available_tools else "Kick"
            item["style"] = f"{tool_name} IMO"
            margin = (
                20 + int(20 * (1 - endurance_factor)) + int(10 * speed_factor)
            )
            item["circle_sec"] = calc_circle_seconds(50, base_100m, margin)
            item["desc"] = (
                "Odd: Easy / Even: Hard" if speed_factor > 0.3 else "Des 1 to 4"
            )

        elif sec == "Pull":
            item["distance_m"] = 100
            item["reps"] = 4 if endurance_factor > 0.3 else 3
            chosen_pull = random.choice(valid_pulls)
            item["style"] = chosen_pull["name"]
            margin = 15 + int(10 * (1 - endurance_factor))
            item["circle_sec"] = calc_circle_seconds(100, base_100m, margin)
            item["desc"] = "Even Pace"

        elif sec == "Drill":
            item["distance_m"] = 50
            item["reps"] = 6
            chosen_drill = random.choice(valid_drills)
            item["style"] = chosen_drill["name"]
            margin = 25
            item["circle_sec"] = calc_circle_seconds(50, base_100m, margin)
            item["desc"] = "キャッチと水感を意識"

        elif sec == "Main":
            if speed_factor >= 0.4:
                item["distance_m"] = 50
                item["reps"] = 8
                item["style"] = "50m All Out / Max"
                margin = 40 + int(30 * speed_factor)
                item["desc"] = "1本目からMAX"
            else:
                item["distance_m"] = 100
                item["reps"] = 6 if endurance_factor >= 0.5 else 4
                item["style"] = "100m Pace Hold"
                margin = 15 + int(15 * (1 - endurance_factor))
                item["desc"] = "ターゲットタイムを維持"

            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, margin
            )

        elif sec == "Down":
            item["distance_m"] = 200
            item["reps"] = 1
            item["style"] = "Easy Choice"
            margin = 60
            item["circle_sec"] = calc_circle_seconds(200, base_100m, margin)
            item["desc"] = "脈拍を落としてストレッチ"

        total_sec = item["reps"] * item["circle_sec"]
        current_time += timedelta(seconds=total_sec)
        item["end_time"] = current_time.strftime("%H:%M")
        item["total_sec"] = total_sec

        lane_menu.append(item)

    return lane_menu


# ------------------------------------------------------------------------------
# 6. SWIM SHEET（A4印刷）用 カスタムCSS 注入
# ------------------------------------------------------------------------------
PRINT_CSS = """
<style>
@media print {
    /* 不要なUI（サイドバー、ボタン、スライダー、ヘッダー）を非表示 */
    [data-testid="stSidebar"],
    .stButton,
    .stSlider,
    header,
    footer,
    [data-testid="stHeader"] {
        display: none !important;
    }
    
    /* 印刷用紙（A4）の設定 */
    @page {
        size: A4 landscape; /* 横向き印刷（3コース並列） */
        margin: 10mm;
    }

    /* 背景色とテキストの最適化 */
    body {
        background-color: #ffffff !important;
        color: #000000 !important;
        font-family: "Helvetica Neue", Arial, sans-serif;
    }

    .main .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }

    /* カード枠線・高コントラスト化 */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #000000 !important;
        border-radius: 4px !important;
        margin-bottom: 4px !important;
        padding: 4px !important;
        background-color: #ffffff !important;
    }

    /* タイムライン用ハイライト */
    code {
        background-color: #f0f0f0 !important;
        color: #000000 !important;
        font-weight: bold !important;
        border: 1px solid #ccc !important;
    }

    /* 改ページ制御（A4 1枚に収める） */
    .stColumn {
        page-break-inside: avoid;
    }
}
</style>
"""

# ------------------------------------------------------------------------------
# 7. UI描画エリア
# ------------------------------------------------------------------------------

# --- 【A】未認証画面 ---
if not st.session_state["authenticated"]:
    st.title("🏊‍♂️ Swim Practice Planner")
