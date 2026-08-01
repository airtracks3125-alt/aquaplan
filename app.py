import json
import math
import random
from datetime import datetime, timedelta
import streamlit as st
import streamlit.components.v1 as components

# ローカルストレージ連携
try:
    from streamlit_local_storage import LocalStorage
    local_storage = LocalStorage()
except ImportError:
    local_storage = None

# ------------------------------------------------------------------------------
# 1. ページ基本設定
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AquaPlan PRO v4.0 | 競泳司令室",
    page_icon="⚡",
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
# 3. 強度スタック (Intensity Stack) 定義
# ------------------------------------------------------------------------------
INTENSITY_MAP = {
    "Warm up": {"code": "A1", "color": "#64748b", "label": "リカバリー/ウォーム"},
    "Kick": {"code": "A2", "color": "#3b82f6", "label": "有酸素基礎 / Endurance"},
    "Pull": {"code": "EN1", "color": "#06b6d4", "label": "持久力向上 / Aerobic"},
    "Drill": {"code": "A1", "color": "#a855f7", "label": "フォーム・技術習得"},
    "Main_Speed": {"code": "AN1", "color": "#ef4444", "label": "無酸素スプリント / Max"},
    "Main_Endurance": {"code": "AT", "color": "#f59e0b", "label": "無酸素作業閾値 / AT"},
    "Down": {"code": "A1", "color": "#10b981", "label": "ダウン / クールダウン"},
}

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
            "intensity": INTENSITY_MAP["Kick"]
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
            "intensity": INTENSITY_MAP["Pull"]
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
            "intensity": INTENSITY_MAP["Main_Speed"]
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
            "intensity": INTENSITY_MAP["Main_Endurance"]
        },
    },
]

# ------------------------------------------------------------------------------
# 5. 高度サークル・距離計算ユーティリティ
# ------------------------------------------------------------------------------
def format_circle_time(seconds: int) -> str:
    """秒数を '1"15' や ''55"' 形式にフォーマット"""
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}'{secs:02d}\""
    return f"'{secs:02d}\""


def calc_circle_seconds(distance_m: int, base_100m: int, margin_sec: int) -> int:
    """100mベースタイムから計算し、5秒単位に丸める"""
    base_for_dist = (base_100m / 100) * distance_m
    total_sec = int(base_for_dist + margin_sec)
    return max(15, round(total_sec / 5) * 5)


def adjust_for_pool_length(distance_m: int, pool_length: int) -> int:
    """長水路(50m)対応: 25m単位の距離を50m単位へ自動補正"""
    if pool_length == 50 and distance_m % 50 != 0:
        return max(50, round(distance_m / 50) * 50)
    return distance_m


def recalculate_timeline(lane_menu_items: list, start_time_obj: datetime):
    """リアルタイムタイムラインおよび総距離の再計算"""
    current_time = start_time_obj
    for item in lane_menu_items:
        item["start_time"] = current_time.strftime("%H:%M")
        total_sec = item["reps"] * item["circle_sec"]
        item["total_sec"] = total_sec
        current_time += timedelta(seconds=total_sec)
        item["end_time"] = current_time.strftime("%H:%M")
        item["total_dist"] = item["distance_m"] * item["reps"]


# ------------------------------------------------------------------------------
# 6. 高度メニュー自動生成エンジン (AquaPlan Engine PRO)
# ------------------------------------------------------------------------------
def generate_lane_menu(
    lane_name: str,
    base_100m: int,
    target_dist_m: int,
    pool_length: int,
    start_time_obj: datetime,
    focus: dict,
    available_tools: list,
) -> list:
    """ロングレップ、プール長補正、強度スタック、自動距離バリデーターを統合した生成エンジン"""
    sections = ["Warm up", "Kick", "Pull", "Drill", "Main", "Down"]
    lane_menu = []
    current_time = start_time_obj

    speed_factor = focus["speed"] / 100.0
    endurance_factor = focus["endurance"] / 100.0

    # ドリル / プルの道具候補フィルタリング
    drill_candidates = [
        {"name": "Form Drill IMO", "tools": []},
        {"name": "Sculling & Catch", "tools": []},
        {"name": "Board Kick & Drill", "tools": ["board"]},
        {"name": "Snorkel Drill", "tools": ["snorkel"]},
        {"name": "Paddle & Fin Drill", "tools": ["paddle", "fin"]},
    ]
    valid_drills = [
        d for d in drill_candidates if all(tool in available_tools for tool in d["tools"])
    ]
    if not valid_drills:
        valid_drills = [{"name": "Form Drill Choice", "tools": []}]

    fixed_distance_sum = 0

    for idx, sec in enumerate(sections):
        item = {"item_id": f"item_{idx}_{random.randint(1000, 9999)}", "section": sec}

        if sec == "Warm up":
            dist = 400 if target_dist_m >= 3000 else 200
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 1
            item["style"] = "Choice Easy"
            item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 40)
            item["intensity"] = INTENSITY_MAP["Warm up"]
            item["desc"] = "関節可動域とフォームチェック"
            fixed_distance_sum += item["distance_m"] * item["reps"]

        elif sec == "Kick":
            dist = 50
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 8 if target_dist_m >= 3500 else 6
            tool_str = "Board " if "board" in available_tools else ""
            item["style"] = f"{tool_str}Kick IMO"
            item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 25)
            item["intensity"] = INTENSITY_MAP["Kick"]
            item["desc"] = "Odd: Easy / Even: Hard"
            fixed_distance_sum += item["distance_m"] * item["reps"]

        elif sec == "Pull":
            dist = 100
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 6 if target_dist_m >= 4000 else 4
            tool_str = "w/Paddle " if "paddle" in available_tools else ""
            item["style"] = f"Pull {tool_str}Hypoxic 3/5"
            item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 15)
            item["intensity"] = INTENSITY_MAP["Pull"]
            item["desc"] = "体幹固定とキャッチの意識"
            fixed_distance_sum += item["distance_m"] * item["reps"]

        elif sec == "Drill":
            dist = 50
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 6
            chosen = random.choice(valid_drills)
            item["style"] = chosen["name"]
            item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 30)
            item["intensity"] = INTENSITY_MAP["Drill"]
            item["desc"] = "水感を捉える技術ドリル"
            fixed_distance_sum += item["distance_m"] * item["reps"]

        elif sec == "Main":
            # --- ロングレップシステムの一時割当 ---
            if target_dist_m >= 6000:
                main_dist = 800
            elif target_dist_m >= 4000:
                main_dist = 400
            elif target_dist_m >= 3000:
                main_dist = 200
            else:
                main_dist = 100 if endurance_factor >= 0.4 else 50

            item["distance_m"] = adjust_for_pool_length(main_dist, pool_length)
            item["reps"] = 4 # バリデーターで自動調整されるため初期値
            
            if speed_factor >= 0.4:
                item["style"] = f"{item['distance_m']}m All Out / Max"
                item["intensity"] = INTENSITY_MAP["Main_Speed"]
                item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 45)
                item["desc"] = "最高速度維持・完全レスト"
            else:
                item["style"] = f"{item['distance_m']}m Pace Hold (AT)"
                item["intensity"] = INTENSITY_MAP["Main_Endurance"]
                item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 15)
                item["desc"] = "ターゲットペースの厳守"

        elif sec == "Down":
            dist = 200
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 1
            item["style"] = "Easy Choice"
            item["circle_sec"] = calc_circle_seconds(item["distance_m"], base_100m, 40)
            item["intensity"] = INTENSITY_MAP["Down"]
            item["desc"] = "脈拍を整え疲労物質を除去"
            fixed_distance_sum += item["distance_m"] * item["reps"]

        lane_menu.append(item)

    # --- 距離バリデーター補正 (Mainの本数を目標に合わせる) ---
コードは注意してご使用ください。main_item = lane_menu[4]remaining_dist = target_dist_m - fixed_distance_sumadjusted_reps = max(1, round(remaining_dist / main_item["distance_m"]))main_item["reps"] = adjusted_repsrecalculate_timeline(lane_menu, start_time_obj)return lane_menu------------------------------------------------------------------------------7. AquaPlan PRO サイバーデザイン ＆ 印刷用 CSS (Dark Neon UI)------------------------------------------------------------------------------CYBER_THEME_CSS = """body, [data-testid="stAppViewContainer"] {background-color: #0b0f19 !important;color: #f1f5f9 !important;font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;}[data-testid="stSidebar"] {background-color: #0f172a !important;border-right: 1px solid #1e293b !important;}/* レーンごとのネオンカラーテーマ */.lane-card-A {border-radius: 12px;border: 1px solid #1e3a8a !important;border-top: 4px solid #3b82f6 !important;background: linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, rgba(15, 23, 42, 0.9) 100%) !important;padding: 15px;margin-bottom: 15px;}.lane-card-B {border-radius: 12px;border: 1px solid #0891b2 !important;border-top: 4px solid #06b6d4 !important;background: linear-gradient(180deg, rgba(6, 182, 212, 0.08) 0%, rgba(15, 23, 42, 0.9) 100%) !important;padding: 15px;margin-bottom: 15px;}.lane-card-C {border-radius: 12px;border: 1px solid #059669 !important;border-top: 4px solid #10b981 !important;background: linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.9) 100%) !important;padding: 15px;margin-bottom: 15px;}.intensity-badge {display: inline-block;padding: 2px 8px;border-radius: 4px;font-weight: 700;font-size: 0.75rem;color: #ffffff;}@media print {@page {size: A4 landscape;margin: 8mm;}[data-testid="stSidebar"], .stButton, .stSlider, header, footer, [data-testid="stHeader"] {display: none !important;}body, [data-testid="stAppViewContainer"] {background-color: #ffffff !important;color: #000000 !important;}.main .block-container {padding: 0 !important;max-width: 100% !important;}.lane-card-A, .lane-card-B, .lane-card-C {border: 2px solid #000000 !important;background: #ffffff !important;color: #000000 !important;box-shadow: none !important;}code {background-color: #f1f5f9 !important;color: #000000 !important;border: 1px solid #94a3b8 !important;}}"""------------------------------------------------------------------------------8. メインUI描画--------------------------------------------------------------------------------- 【A】未認証画面 ---if not st.session_state["authenticated"]:st.markdown(CYBER_THEME_CSS, unsafe_allow_html=True)st.title("⚡ AquaPlan PRO v4.0")st.subheader("競泳司令室 | セキュアアクセス")with st.form("auth_form"):user_input = st.text_input("アクセスコードを入力", type="password")if st.form_submit_button("司令室にログイン"):if user_input == SECRET_PASSPHRASE:st.session_state["authenticated"] = Truest.rerun()else:st.error("アクセスコードが無効です。")--- 【B】メイン画面（競泳司令室）---else:st.markdown(CYBER_THEME_CSS, unsafe_allow_html=True)# サイドバーパネルwith st.sidebar:st.title("⚡ AquaPlan PRO")st.caption("AquaPlan PRO v4.0 | Command Center")st.divider()st.subheader("1. 練習コンディション")start_time_val = st.time_input("開始時刻", value=datetime.strptime("16:30", "%H:%M").time())pool_length = st.radio("プール長", options=[25, 50], format_func=lambda x: f"短水路 ({x}m)" if x == 25 else f"長水路 ({x}m)", horizontal=True)st.divider()st.subheader("2. ターゲットディスタンス")target_distance = st.select_slider("目標総距離 (m)", options=[2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 8000], value=4000)st.divider()st.subheader("3. レーン & ベースタイム")num_lanes = st.radio("使用レーン数", options=[1, 2, 3], index=2, horizontal=True)lane_colors = ["#3b82f6", "#06b6d4", "#10b981"]lane_base_times = {}for i in range(num_lanes):lane_char = chr(65 + i)lane_name = f"Lane {lane_char}"lane_base_times[lane_name] = st.number_input(f"{lane_name} 100mベース（秒）", min_value=40, max_value=180, value=75 + (i * 10), step=1, key=f"base_{i}")st.divider()st.subheader("4. ギア・ツール")tool_checks = {"board": st.checkbox("ビート板", value=True),"buoy": st.checkbox("プルブイ", value=True),"paddle": st.checkbox("パドル", value=True),"fin": st.checkbox("フィン", value=True),"snorkel": st.checkbox("シュノーケル", value=False),}active_tools = [tool for tool, active in tool_checks.items() if active]st.divider()st.subheader("💾 ストレージ管理")c_ls1, c_ls2 = st.columns(2)with c_ls1:if st.button("保存", use_container_width=True):if st.session_state["generated_menus"] and local_storage is not None:payload = {"date": datetime.today().strftime("%Y-%m-%d"),"start_time": start_time_val.strftime("%H:%M"),"lanes_data": st.session_state["generated_menus"],"custom_presets": st.session_state["custom_presets"],}local_storage.setItem("aquaplan_data", json.dumps(payload))st.toast("司令室データをローカルに保存しました！")with c_ls2:if st.button("復元", use_container_width=True):if local_storage is not None:raw = local_storage.getItem("aquaplan_data")if raw:parsed = json.loads(raw)st.session_state["generated_menus"] = parsed.get("lanes_data")st.session_state["custom_presets"] = parsed.get("custom_presets", [])st.toast("データを復元しました！")st.rerun()st.divider()if st.button("🔒 システムロック"):st.session_state["authenticated"] = Falsest.rerun()# メインコントロールc_title, c_print = st.columns([3, 1])with c_title:st.title("⚡ 競泳最適化司令室 (AquaPlan Engine)")st.caption(f"プール環境: {pool_length}m | 目標距離: {target_distance}m | アクティブツール: {len(active_tools)}種")with c_print:if st.button("📄 SWIM SHEET 一括印刷", type="primary", use_container_width=True):components.html("window.parent.print();", height=0, width=0)st.subheader("🎯 トレーニング強度・フォーカス配分")col_f1, col_f2, col_f3 = st.columns(3)with col_f1:endurance = st.slider("持久力 (Endurance)", 0, 100, 50, step=5)with col_f2:speed = st.slider("スピード (Speed)", 0, 100, 30, step=5)with col_f3:technique = st.slider("技術・フォーム (Technique)", 0, 100, 20, step=5)total_ratio = endurance + speed + techniqueif total_ratio != 100:st.warning(f"⚠️ 配分合計: {total_ratio}% （100%に調整してください）")else:st.caption("✅ 配分合計: 100%")if st.button("✨ 司令室メニューを演算生成", type="secondary", use_container_width=True):if total_ratio != 100:st.error("合計比率を100%にする必要があります。")else:focus_dict = {"endurance": endurance, "speed": speed, "technique": technique}start_datetime = datetime.combine(datetime.today(), start_time_val)all_lanes_result = {}for lane_i in range(num_lanes):lane_char = chr(65 + lane_i)lane_name = f"Lane {lane_char}"all_lanes_result[lane_name] = generate_lane_menu(lane_name=lane_name,base_100m=lane_base_times[lane_name],target_dist_m=target_distance,pool_length=pool_length,start_time_obj=start_datetime,focus=focus_dict,available_tools=active_tools)st.session_state["generated_menus"] = all_lanes_resultst.success("メニューの演算生成が完了しました！")st.divider()# SWIM SHEET レーン描画if st.session_state["generated_menus"] is not None:start_datetime = datetime.combine(datetime.today(), start_time_val)# タイムライン最新化for lane_name in st.session_state["generated_menus"].keys():recalculate_timeline(st.session_state["generated_menus"][lane_name], start_datetime)lane_cols = st.columns(num_lanes)for idx, (lane_name, menu_items) in enumerate(st.session_state["generated_menus"].items()):if idx >= num_lanes:continuelane_char = chr(65 + idx)with lane_cols[idx]:# ダークネオン用ラッパー div の挿入st.markdown(f'', unsafe_allow_html=True)st.markdown(f"### 🏊 {lane_name}")total_lane_dist = sum(item["distance_m"] * item["reps"] for item in menu_items)total_lane_sec = sum(item["total_sec"] for item in menu_items)c_m1, c_m2 = st.columns(2)with c_m1:st.metric("実計算総距離", f"{total_lane_dist} m")with c_m2:st.metric("予定総時間", f"{total_lane_sec // 60} 分")items_to_delete = []for item_idx, item in enumerate(menu_items):with st.container(border=True):ch1, ch2 = st.columns([3, 1])with ch1:st.markdown(f"【{item['section']}】 {item['start_time']} - {item['end_time']}")with ch2:if st.button("❌", key=f"del_{lane_name}_{item_idx}"):items_to_delete.append(item_idx)# 強度スタックバッジの描画it_info = item["intensity"]st.markdown(f'<span class="intensity-badge" style="background-color: {it_info["color"]};">{it_info["code"]} : {it_info["label"]}', unsafe_allow_html=True)ce1, ce2, ce3 = st.columns(3)with ce1:item["distance_m"] = st.number_input("距離(m)", value=int(item["distance_m"]), step=25, key=f"dist_{lane_name}{item_idx}")with ce2:item["reps"] = st.number_input("本数", value=int(item["reps"]), min_value=1, key=f"reps{lane_name}{item_idx}")with ce3:item["circle_sec"] = st.number_input("サークル(秒)", value=int(item["circle_sec"]), step=5, key=f"circle{lane_name}_{item_idx}")st.caption(f"表記サークル: {format_circle_time(item['circle_sec'])}")item["style"] = st.text_input("スタイル/形式", value=item["style"], key=f"style_{lane_name}{item_idx}")item["desc"] = st.text_input("指導メモ", value=item["desc"], key=f"desc{lane_name}_{item_idx}")if st.button("⭐ プリセット登録", key=f"fav_{lane_name}_{item_idx}"):new_preset = {"name": f"【自作】{item['distance_m']}m×{item['reps']} {item['style']}","item": {"section": item["section"], "distance_m": item["distance_m"], "reps": item["reps"],"circle_sec": item["circle_sec"], "style": item["style"], "desc": item["desc"], "intensity": item["intensity"]}}if new_preset not in st.session_state["custom_presets"]:st.session_state["custom_presets"].append(new_preset)st.toast("オリジナルプリセットに登録しました！")st.rerun()if items_to_delete:for d_idx in reversed(items_to_delete):menu_items.pop(d_idx)recalculate_timeline(menu_items, start_datetime)st.rerun()# プリセット追加UIst.divider()st.markdown("➕ プリセットセットを挿入")preset_options = [p["name"] for p in DEFAULT_PRESETS] + [cp["name"] for cp in st.session_state["custom_presets"]]if preset_options:selected_p = st.selectbox("セット選択", options=preset_options, key=f"pre_sel_{lane_name}")if st.button("このレーンの末尾に追加", key=f"add_pre_{lane_name}"):target = Nonefor p in DEFAULT_PRESETS:if p["name"] == selected_p: target = dict(p["item"]); breakif not target:for cp in st.session_state["custom_presets"]:if cp["name"] == selected_p: target = dict(cp["item"]); breakif target:new_i = dict(target)new_i["item_id"] = f"preset_{random.randint(1000, 9999)}"st.session_state["generated_menus"][lane_name].append(new_i)recalculate_timeline(st.session_state["generated_menus"][lane_name], start_datetime)st.rerun()st.markdown('', unsafe_allow_html=True) # カラーカード閉じ
