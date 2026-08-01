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
st.subheader("アクセス認証")
with st.form("auth_form"):
user_input = st.text_input("合言葉を入力", type="password")
submit_button = st.form_submit_button("ログイン")
if submit_button:
if user_input == SECRET_PASSPHRASE:
st.session_state["authenticated"] = True
st.rerun()
else:
st.error("合言葉が違います。")
--- 【B】メイン画面 ---
else:
# カスタムCSSの注入
st.markdown(PRINT_CSS, unsafe_allow_html=True)
# --------------------------------------------------------------------------
# サイドバー（設定パネル）
# --------------------------------------------------------------------------
with st.sidebar:
st.header("⚙️ 練習設定")
st.subheader("1. 練習時間")
start_time_val = st.time_input(
"開始時刻", value=datetime.strptime("16:30", "%H:%M").time()
)
duration_min = st.number_input(
"目標時間（分）", min_value=15, max_value=240, value=90, step=15
)
st.divider()
st.subheader("2. コース設定")
num_lanes = st.radio(
"使用レーン数", options=[1, 2, 3], index=2, horizontal=True
)
lane_base_times = {}
for i in range(num_lanes):
lane_name = f"コース {chr(65+i)}"
lane_base_times[lane_name] = st.number_input(
f"{lane_name} 100mベース（秒）",
min_value=40,
max_value=180,
value=80 + (i * 15),
step=1,
key=f"base_{i}",
)
st.divider()
st.subheader("3. 使用可能な道具")
tool_checks = {
"board": st.checkbox("ビート板", value=True),
"buoy": st.checkbox("プルブイ", value=True),
"paddle": st.checkbox("パドル", value=True),
"fin": st.checkbox("フィン", value=True),
"snorkel": st.checkbox("シュノーケル", value=False),
}
active_tools = [tool for tool, active in tool_checks.items() if active]
st.divider()
# Local Storage 保存・読み込みコントロール
st.subheader("💾 データ保存 / 復元")
col_ls1, col_ls2 = st.columns(2)
with col_ls1:
if st.button("保存", use_container_width=True):
if (
st.session_state["generated_menus"]
and local_storage is not None
):
save_payload = {
"date": datetime.today().strftime("%Y-%m-%d"),
"start_time": start_time_val.strftime("%H:%M"),
"lanes_data": st.session_state["generated_menus"],
"custom_presets": st.session_state["custom_presets"],
}
local_storage.setItem(
"swim_app_data", json.dumps(save_payload)
)
st.toast("ローカルストレージにデータを保存しました！")
with col_ls2:
if st.button("復元", use_container_width=True):
if local_storage is not None:
raw_data = local_storage.getItem("swim_app_data")
if raw_data:
parsed = json.loads(raw_data)
st.session_state["generated_menus"] = parsed.get(
"lanes_data"
)
st.session_state["custom_presets"] = parsed.get(
"custom_presets", []
)
st.toast("保存されたデータを復元しました！")
st.rerun()
else:
st.toast("保存データが見つかりませんでした。")
st.divider()
if st.button("🔒 ログアウト"):
st.session_state["authenticated"] = False
st.session_state["generated_menus"] = None
st.rerun()
# --------------------------------------------------------------------------
# メインエリア
# --------------------------------------------------------------------------
st.title("🏊‍♂️ 競泳練習メニュー自動作成")
# A4一括印刷ボタン（上部配置）
col_p1, col_p2 = st.columns([3, 1])
with col_p2:
if st.button(
"📄 SWIM SHEET を一括印刷", type="primary", use_container_width=True
):
components.html(
"window.parent.print();", height=0, width=0
)
st.subheader("🎯 メニューのフォーカス配分")
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
endurance = st.slider("持久力 (Endurance)", 0, 100, 50, step=5)
with col_f2:
speed = st.slider("スピード (Speed)", 0, 100, 30, step=5)
with col_f3:
technique = st.slider("技術・フォーム (Technique)", 0, 100, 20, step=5)
total_ratio = endurance + speed + technique
if total_ratio != 100:
st.warning(
f"⚠️ 配分合計: {total_ratio}% （100%になるように調整してください）"
)
else:
st.caption("✅ 配分合計: 100%")
if st.button(
"✨ メニューを自動生成する", type="secondary", use_container_width=True
):
if total_ratio != 100:
st.error("配分の合計を100%にしてから生成ボタンを押してください。")
else:
focus_dict = {
"endurance": endurance,
"speed": speed,
"technique": technique,
}
start_datetime = datetime.combine(datetime.today(), start_time_val)
all_lanes_result = {}
for lane_name, base_time in lane_base_times.items():
all_lanes_result[lane_name] = generate_lane_menu(
lane_name=lane_name,
base_100m=base_time,
start_time_obj=start_datetime,
focus=focus_dict,
available_tools=active_tools,
)
st.session_state["generated_menus"] = all_lanes_result
st.success("メニューの自動計算が完了しました！")
st.divider()
# --------------------------------------------------------------------------
# SWIM SHEET 表示 ＆ 手動編集 ＆ プリセット追加エリア
# --------------------------------------------------------------------------
st.subheader("📋 本日の練習メニュー（SWIM SHEET）")
if st.session_state["generated_menus"] is None:
st.info(
"上の「✨ メニューを自動生成する」ボタンを押すか、サイドバーの「復元」ボタンを押してください。"
)
else:
start_datetime = datetime.combine(datetime.today(), start_time_val)
# 全レーンのタイムライン最新化
for lane_name in st.session_state["generated_menus"].keys():
recalculate_timeline(
st.session_state["generated_menus"][lane_name], start_datetime
)
lane_cols = st.columns(num_lanes)
for idx, (lane_name, menu_items) in enumerate(
st.session_state["generated_menus"].items()
):
if idx >= num_lanes:
continue
with lane_cols[idx]:
st.markdown(f"### 🏊 {lane_name}")
st.caption(f"100mベース: {lane_base_times.get(lane_name, 80)}秒")
total_lane_sec = sum(item["total_sec"] for item in menu_items)
st.metric("予定総時間", f"{total_lane_sec // 60} 分")
# 各セクションカードの描画 ＆ インライン編集UI
items_to_delete = []
for item_idx, item in enumerate(menu_items):
with st.container(border=True):
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
st.markdown(
f"【{item['section']}】 {item['start_time']} - {item['end_time']}"
)
with col_h2:
if st.button(
"❌",
key=f"del_{lane_name}_{item_idx}",
help="このセクションを削除",
):
items_to_delete.append(item_idx)
col_e1, col_e2, col_e3 = st.columns([1, 1, 1])
with col_e1:
item["distance_m"] = st.number_input(
"距離(m)",
value=int(item["distance_m"]),
step=25,
key=f"dist_{lane_name}{item_idx}",
)
with col_e2:
item["reps"] = st.number_input(
"本数",
value=int(item["reps"]),
min_value=1,
step=1,
key=f"reps{lane_name}{item_idx}",
)
with col_e3:
item["circle_sec"] = st.number_input(
"サークル(秒)",
value=int(item["circle_sec"]),
step=5,
key=f"circle{lane_name}_{item_idx}",
)
st.caption(
f"サークル表記: {format_circle_time(item['circle_sec'])}"
)
item["style"] = st.text_input(
"内容・スタイル",
value=item["style"],
key=f"style_{lane_name}{item_idx}",
)
item["desc"] = st.text_input(
"メモ・指示",
value=item["desc"],
key=f"desc{lane_name}_{item_idx}",
)
# ★ 補完機能：この特定のセットを新しく自作プリセットとして登録する
if st.button(
"⭐ このセットをプリセット登録",
key=f"fav_{lane_name}_{item_idx}",
):
new_preset = {
"name": f"【自作】{item['distance_m']}m×{item['reps']} {item['style']}",
"item": {
"section": item["section"],
"distance_m": item["distance_m"],
"reps": item["reps"],
"circle_sec": item["circle_sec"],
"style": item["style"],
"desc": item["desc"],
},
}
if new_preset not in st.session_state["custom_presets"]:
st.session_state["custom_presets"].append(
new_preset
)
st.toast("オリジナルプリセットに登録しました！")
st.rerun()
# 削除処理の実行
if items_to_delete:
for d_idx in reversed(items_to_delete):
menu_items.pop(d_idx)
recalculate_timeline(menu_items, start_datetime)
st.rerun()
# --- プリセット追加コントロール（★力尽きた部分を完全補完） ---
st.divider()
st.markdown("➕ 定番・プリセットメニューを追加")
preset_options = [p["name"] for p in DEFAULT_PRESETS] + [
cp["name"] for cp in st.session_state["custom_presets"]
]
selected_preset_name = st.selectbox(
"追加するセットを選択",
options=preset_options,
key=f"preset_sel_{lane_name}",
)
if st.button("このセットを末尾に追加", key=f"add_pre_{lane_name}"):
target_item = None
for p in DEFAULT_PRESETS:
if p["name"] == selected_preset_name:
target_item = dict(p["item"])
break
if not target_item:
for cp in st.session_state["custom_presets"]:
if cp["name"] == selected_preset_name:
target_item = dict(cp["item"])
break
if target_item:
# 完全に独立した新しい辞書データとしてコピーを生成し、IDを付与
new_item = dict(target_item)
new_item["item_id"] = (
f"preset_{random.randint(1000, 9999)}"
)
# コースの末尾にセットを追加
st.session_state["generated_menus"][lane_name].append(
new_item
)
# 追加後に即座にタイムラインをリフレッシュ
recalculate_timeline(
st.session_state["generated_menus"][lane_name],
start_datetime,
)
st.toast(f"{lane_name} にプリセットを追加しました！")

