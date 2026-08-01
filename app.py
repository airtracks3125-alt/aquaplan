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
    "Main_Speed": {
        "code": "AN1",
        "color": "#ef4444",
        "label": "無酸素スプリント / Max",
    },
    "Main_Endurance": {
        "code": "AT",
        "color": "#f59e0b",
        "label": "無酸素作業閾値 / AT",
    },
    "Down": {"code": "A1", "color": "#10b981", "label": "ダウン / クールダウン"},
}


# ------------------------------------------------------------------------------
# 4. 高度サークル・距離計算ユーティリティ
# ------------------------------------------------------------------------------
def format_circle_time(seconds: int) -> str:
    """秒数を '1"15' や ''55"' 形式にフォーマット"""
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}'{secs:02d}\""
    return f"'{secs:02d}\""


def calc_circle_seconds(
    distance_m: int, base_100m: int, margin_sec: int
) -> int:
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
# 5. 高度メニュー自動生成エンジン (AquaPlan Engine PRO)
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
        d
        for d in drill_candidates
        if all(tool in available_tools for tool in d["tools"])
    ]
    if not valid_drills:
        valid_drills = [{"name": "Form Drill Choice", "tools": []}]

    for idx, sec in enumerate(sections):
        item = {"item_id": f"item_{idx}", "section": sec}

        if sec == "Warm up":
            dist = 400 if target_dist_m >= 3000 else 200
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 1
            item["style"] = "Choice Easy"
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, 40
            )
            item["intensity"] = INTENSITY_MAP["Warm up"]
            item["desc"] = "関節可動域とフォームチェック"

        elif sec == "Kick":
            dist = 50
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 8 if target_dist_m >= 3500 else 6
            tool_str = "Board " if "board" in available_tools else ""
            item["style"] = f"{tool_str}Kick IMO"
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, 25
            )
            item["intensity"] = INTENSITY_MAP["Kick"]
            item["desc"] = "Odd: Easy / Even: Hard"

        elif sec == "Pull":
            dist = 100
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 6 if target_dist_m >= 4000 else 4
            tool_str = "w/Paddle " if "paddle" in available_tools else ""
            item["style"] = f"Pull {tool_str}Hypoxic 3/5"
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, 15
            )
            item["intensity"] = INTENSITY_MAP["Pull"]
            item["desc"] = "体幹固定とキャッチの意識"

        elif sec == "Drill":
            dist = 50
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 6
            chosen = random.choice(valid_drills)
            item["style"] = chosen["name"]
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, 30
            )
            item["intensity"] = INTENSITY_MAP["Drill"]
            item["desc"] = "水感を捉える技術ドリル"

        elif sec == "Main":
            # --- ロングレップシステムの適用 ---
            if target_dist_m >= 6000:
                main_dist = 800
                main_reps = 4
            elif target_dist_m >= 4000:
                main_dist = 400
                main_reps = 6
            elif target_dist_m >= 3000:
                main_dist = 200
                main_reps = 8
            else:
                main_dist = 100 if endurance_factor >= 0.4 else 50
                main_reps = 8 if main_dist == 100 else 10

            item["distance_m"] = adjust_for_pool_length(main_dist, pool_length)
            item["reps"] = main_reps

            if speed_factor >= 0.4:
                item["style"] = f"{item['distance_m']}m All Out / Max"
                item["intensity"] = INTENSITY_MAP["Main_Speed"]
                item["circle_sec"] = calc_circle_seconds(
                    item["distance_m"], base_100m, 45
                )
                item["desc"] = "最高速度維持・完全レスト"
            else:
                item["style"] = f"{item['distance_m']}m Pace Hold (AT)"
                item["intensity"] = INTENSITY_MAP["Main_Endurance"]
                item["circle_sec"] = calc_circle_seconds(
                    item["distance_m"], base_100m, 15
                )
                item["desc"] = "ターゲットペースの厳守"

        elif sec == "Down":
            dist = 200
            item["distance_m"] = adjust_for_pool_length(dist, pool_length)
            item["reps"] = 1
            item["style"] = "Easy Choice"
            item["circle_sec"] = calc_circle_seconds(
                item["distance_m"], base_100m, 60
            )
            item["intensity"] = INTENSITY_MAP["Down"]
            item["desc"] = "心拍数の低下とクールダウン"

        total_sec = item["reps"] * item["circle_sec"]
        current_time += timedelta(seconds=total_sec)
        item["end_time"] = current_time.strftime("%H:%M")
        item["total_sec"] = total_sec
        item["total_dist"] = item["distance_m"] * item["reps"]

        lane_menu.append(item)

    # --------------------------------------------------------------------------
    # 自動距離バリデーター (目標距離から10%以内の誤差に補正)
    # --------------------------------------------------------------------------
    current_total_dist = sum(x["total_dist"] for x in lane_menu)
    diff_dist = target_dist_m - current_total_dist

    # Mainセクションを探して補正
    main_item = next((x for x in lane_menu if x["section"] == "Main"), None)
    if main_item:
        single_dist = main_item["distance_m"]
        reps_diff = round(diff_dist / single_dist)
        new_reps = max(1, main_item["reps"] + reps_diff)
        main_item["reps"] = new_reps
        main_item["total_dist"] = main_item["distance_m"] * new_reps

    recalculate_timeline(lane_menu, start_time_obj)
    return lane_menu
  # ------------------------------------------------------------------------------
# 6. AquaPlan PRO サイバーデザイン ＆ 印刷用 CSS (Dark Neon UI)
# ------------------------------------------------------------------------------
CYBER_THEME_CSS = """
<style>
/* ==========================================
   AquaPlan PRO サイバーデザイン (ダークネオン)
   ========================================== */
body, [data-testid="stAppViewContainer"] {
    background-color: #0b0f19 !important;
    color: #f1f5f9 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

[data-testid="stSidebar"] {
    background-color: #0f172a !important;
    border-right: 1px solid #1e293b !important;
}

/* レーンごとのネオンカラーテーマ */
.lane-card-A {
    border-top: 4px solid #3b82f6 !important;
    background: linear-gradient(180deg, rgba(59, 130, 246, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
}
.lane-card-B {
    border-top: 4px solid #06b6d4 !important;
    background: linear-gradient(180deg, rgba(6, 182, 212, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
}
.lane-card-C {
    border-top: 4px solid #10b981 !important;
    background: linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
}

/* 強度スタックバッジ */
.intensity-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.75rem;
    color: #ffffff;
    text-shadow: 0 0 4px rgba(0,0,0,0.5);
}

/* インプットフィールドのサイバーカスタマイズ */
div[data-baseweb="input"] {
    background-color: #1e293b !important;
    border-color: #334155 !important;
    color: #f8fafc !important;
}

/* ==========================================
   A4 Landscape 印刷専用メディアクエリ
   ========================================== */
@media print {
    @page {
        size: A4 landscape;
        margin: 8mm;
    }

    /* 不要UIの完全非表示 */
    [data-testid="stSidebar"],
    .stButton,
    .stSlider,
    header,
    footer,
    [data-testid="stHeader"] {
        display: none !important;
    }

    body, [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }

    /* 印刷時のクッキリ枠線とハイコントラスト表示 */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1.5px solid #000000 !important;
        border-radius: 4px !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        box-shadow: none !important;
        margin-bottom: 4px !important;
        padding: 4px !important;
    }

    code {
        background-color: #f1f5f9 !important;
        color: #000000 !important;
        border: 1px solid #94a3b8 !important;
        font-weight: bold !important;
    }

    .intensity-badge {
        border: 1px solid #000000 !important;
        color: #000000 !important;
        background-color: #e2e8f0 !important;
    }
}
</style>
"""

# ------------------------------------------------------------------------------
# 7. メインUI描画
# ------------------------------------------------------------------------------

# --- 【A】未認証画面 ---
if not st.session_state["authenticated"]:
    st.markdown(CYBER_THEME_CSS, unsafe_allow_html=True)
    st.title("⚡ AquaPlan PRO v4.0")
    st.subheader("競泳司令室 | セキュアアクセス")
    with st.form("auth_form"):
        user_input = st.text_input("アクセスコードを入力", type="password")
        if st.form_submit_button("司令室にログイン"):
            if user_input == SECRET_PASSPHRASE:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("アクセスコードが無効です。")

# --- 【B】メイン画面（競泳司令室）---
else:
    st.markdown(CYBER_THEME_CSS, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # サイドバー（設定パネル）
    # --------------------------------------------------------------------------
    with st.sidebar:
        st.title("⚡ AquaPlan PRO")
        st.caption("AquaPlan PRO v4.0 | Command Center")

        st.divider()

        st.subheader("1. 練習コンディション")
        start_time_val = st.time_input(
            "開始時刻", value=datetime.strptime("16:30", "%H:%M").time()
        )
        pool_length = st.radio(
            "プール長",
            options=[25, 50],
            format_func=lambda x: f"短水路 ({x}m)" if x == 25 else f"長水路 ({x}m)",
            horizontal=True,
        )

        st.divider()

        st.subheader("2. ターゲットディスタンス")
        target_distance = st.select_slider(
            "目標総距離 (m)",
            options=[2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 8000],
            value=4000,
        )

        st.divider()

        st.subheader("3. レーン & ベースタイム")
        num_lanes = st.radio(
            "使用レーン数", options=[1, 2, 3], index=2, horizontal=True
        )

        lane_colors = ["#3b82f6", "#06b6d4", "#10b981"]
        lane_base_times = {}

        for i in range(num_lanes):
            lane_char = chr(65 + i)
            lane_name = f"Lane {lane_char}"
            lane_base_times[lane_name] = st.number_input(
                f"{lane_name} 100mベース（秒）",
                min_value=40,
                max_value=180,
                value=75 + (i * 10),
                step=1,
                key=f"base_{i}",
            )

        st.divider()

        st.subheader("4. ギア・ツール")
        tool_checks = {
            "board": st.checkbox("ビート板", value=True),
            "buoy": st.checkbox("プルブイ", value=True),
            "paddle": st.checkbox("パドル", value=True),
            "fin": st.checkbox("フィン", value=True),
            "snorkel": st.checkbox("シュノーケル", value=False),
        }
        active_tools = [tool for tool, active in tool_checks.items() if active]

        st.divider()

        # LocalStorage 保存・復元
        st.subheader("💾 ストレージ管理")
        c_ls1, c_ls2 = st.columns(2)
        with c_ls1:
            if st.button("保存", use_container_width=True):
                if (
                    st.session_state["generated_menus"]
                    and local_storage is not None
                ):
                    payload = {
                        "date": datetime.today().strftime("%Y-%m-%d"),
                        "start_time": start_time_val.strftime("%H:%M"),
                        "lanes_data": st.session_state["generated_menus"],
                        "custom_presets": st.session_state["custom_presets"],
                    }
                    local_storage.setItem("aquaplan_data", json.dumps(payload))
                    st.toast("司令室データをローカルに保存しました！")

        with c_ls2:
            if st.button("復元", use_container_width=True):
                if local_storage is not None:
                    raw = local_storage.getItem("aquaplan_data")
                    if raw:
                        parsed = json.loads(raw)
                        st.session_state["generated_menus"] = parsed.get(
                            "lanes_data"
                        )
                        st.session_state["custom_presets"] = parsed.get(
                            "custom_presets", []
                        )
                        st.toast("データを復元しました！")
                        st.rerun()

        st.divider()
        if st.button("🔒 システムロック"):
            st.session_state["authenticated"] = False
            st.rerun()

    # --------------------------------------------------------------------------
    # メインコントロールエリア
    # --------------------------------------------------------------------------
    c_title, c_print = st.columns([3, 1])
    with c_title:
        st.title("⚡ 競泳最適化司令室 (AquaPlan Engine)")
        st.caption(
            f"プール環境: **{pool_length}m** | 目標距離: **{target_distance}m** | アクティブツール: **{len(active_tools)}種**"
        )

    with c_print:
        if st.button(
            "📄 SWIM SHEET 一括印刷", type="primary", use_container_width=True
        ):
            components.html(
                "<script>window.parent.print();</script>", height=0, width=0
            )

    # ターゲット比率調整スライダー
    st.subheader("🎯 トレーニング強度・フォーカス配分")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        endurance = st.slider("持久力 (Endurance)", 0, 100, 60, step=5)
    with col_f2:
        speed = st.slider("スピード (Speed / Max)", 0, 100, 20, step=5)
    with col_f3:
        technique = st.slider("技術・フォーム (Technique)", 0, 100, 20, step=5)

    total_ratio = endurance + speed + technique
    if total_ratio != 100:
        st.warning(f"⚠️ 強度配分合計: {total_ratio}% （100%に調整してください）")
    else:
        st.caption("✅ 強度配分: 100% (最適バランス)")

    if st.button(
        "🚀 AquaPlan PRO メニュー全自動最適化",
        type="secondary",
        use_container_width=True,
    ):
        if total_ratio != 100:
            st.error("配分合計を100%に調整してください。")
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
                    target_dist_m=target_distance,
                    pool_length=pool_length,
                    start_time_obj=start_datetime,
                    focus=focus_dict,
                    available_tools=active_tools,
                )

            st.session_state["generated_menus"] = all_lanes_result
            st.success("高度水泳工学アルゴリズムによる最適化が完了しました！")

    st.divider()

    # --------------------------------------------------------------------------
    # SWIM SHEET（レーン並列表示・インライン編集・リアルタイムタイムライン）
    # --------------------------------------------------------------------------
    st.subheader("📋 SWIM SHEET (マルチレーン司令ディスプレイ)")

    if st.session_state["generated_menus"] is None:
        st.info("「🚀 AquaPlan PRO メニュー全自動最適化」を実行してください。")
    else:
        start_datetime = datetime.combine(datetime.today(), start_time_val)

        # タイムライン即時更新
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

            lane_char = chr(65 + idx)
            card_class = f"lane-card-{lane_char}"

            with lane_cols[idx]:
                # レーンヘッダー
                st.markdown(
                    f"### <span style='color:{lane_colors[idx]}'>🏊 {lane_name}</span>",
                    unsafe_allow_html=True,
                )

                # メトリクス（リアルタイム再計算の反映）
                total_lane_dist = sum(item["total_dist"] for item in menu_items)
                total_lane_sec = sum(item["total_sec"] for item in menu_items)

                c_m1, c_m2 = st.columns(2)
                with c_m1:
                    st.metric("総距離", f"{total_lane_dist} m")
                with c_m2:
                    st.metric("総時間", f"{total_lane_sec // 60} 分")

                items_to_delete = []

                # メニューカードの描画
                for item_idx, item in enumerate(menu_items):
                    with st.container(border=True):
                        col_h1, col_h2 = st.columns([3, 1])
                        with col_h1:
                            intensity_info = item.get(
                                "intensity", INTENSITY_MAP["Warm up"]
                            )
                            st.markdown(
                                f"<span class='intensity-badge' style='background-color:{intensity_info['color']}'>{intensity_info['code']}</span> "
                                f"**【{item['section']}】** `{item['start_time']}-{item['end_time']}`",
                                unsafe_allow_html=True,
                            )
                        with col_h2:
                            if st.button(
                                "❌",
                                key=f"del_{lane_name}_{item_idx}",
                                help="削除",
                            ):
                                items_to_delete.append(item_idx)

                        c_e1, c_e2, c_e3 = st.columns([1, 1, 1])
                        with c_e1:
                            item["distance_m"] = st.number_input(
                                "距離(m)",
                                value=item["distance_m"],
                                step=25 if pool_length == 25 else 50,
                                key=f"dist_{lane_name}_{item_idx}",
                            )
                        with c_e2:
                            item["reps"] = st.number_input(
                                "本数",
                                value=item["reps"],
                                min_value=1,
                                step=1,
                                key=f"reps_{lane_name}_{item_idx}",
                            )
                        with c_e3:
                            item["circle_sec"] = st.number_input(
                                "サークル(秒)",
                                value=item["circle_sec"],
                                step=5,
                                key=f"circle_{lane_name}_{item_idx}",
                            )

                        st.caption(
                            f"サークル: **{format_circle_time(item['circle_sec'])}** | 小計: **{item['distance_m'] * item['reps']}m**"
                        )

                        item["style"] = st.text_input(
                            "内容・種目",
                            value=item["style"],
                            key=f"style_{lane_name}_{item_idx}",
                        )
                        item["desc"] = st.text_input(
                            "指示・ターゲット",
                            value=item["desc"],
                            key=f"desc_{lane_name}_{item_idx}",
                        )

                # インライン削除実行
                if items_to_delete:
                    for d_idx in reversed(items_to_delete):
                        menu_items.pop(d_idx)
                    recalculate_timeline(menu_items, start_datetime)
                    st.rerun()

                # --- プリセット追加セクション ---
                st.divider()
                st.markdown("➕ **定番セットの緊急注入**")
                preset_options = [p["name"] for p in DEFAULT_PRESETS] + [
                    cp["name"] for cp in st.session_state["custom_presets"]
                ]
                selected_preset = st.selectbox(
                    "プリセット選択",
                    options=preset_options,
                    key=f"pre_sel_{lane_name}",
                )

                if st.button("末尾に追加", key=f"add_pre_{lane_name}"):
                    target_item = None
                    for p in DEFAULT_PRESETS:
                        if p["name"] == selected_preset:
                            target_item = dict(p["item"])
                            target_item["intensity"] = INTENSITY_MAP.get(
                                target_item["section"], INTENSITY_MAP["Warm up"]
                            )
                            break
                    if target_item:
                        menu_items.append(target_item)
                        recalculate_timeline(menu_items, start_datetime)
                        st.toast(f"{lane_name} にプリセットを追加しました！")
                        st.rerun()
