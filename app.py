import math
import random
from datetime import datetime, timedelta
import streamlit as st

# ==========================================
# 1. ページ基本設定（スマホ・PC両対応）
# ==========================================
st.set_page_config(
    page_title="Aqua Plan",
    page_icon="🏊‍♂️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==========================================
# 2. 種目・フレーズのバリエーション辞書
# ==========================================
VARIATION_PHRASES = {
    "フォーム": [
        "25m Scull / 25m Swim",
        "25m Drill / 25m Swim",
        "25m Kick / 25m Swim",
        "50m Form / 50m Build-up",
    ],
    "スプリント": [
        "15m Max / 35m Easy",
        "25m Easy / 25m Max",
        "25m Max / 25m Form",
    ],
    "個人メドレー": [
        "25m IMO / 25m Choice",
        "25m Fly / 25m Ba",
    ],
}


# ==========================================
# 3. 補助計算関数
# ==========================================
def ceil_to_5_seconds(seconds: float) -> int:
    """秒数を5秒単位に切り上げる関数 (例: 62秒 -> 65秒)"""
    return int(math.ceil(seconds / 5.0) * 5)


def format_seconds_to_cycle(seconds: int) -> str:
    """秒数をサークル表記に変換する関数 (例: 65秒 -> "1分05秒")"""
    minutes = seconds // 60
    rem_seconds = seconds % 60
    if minutes > 0:
        return f"{minutes}分{rem_seconds:02d}秒"
    return f"{rem_seconds}秒"


def format_seconds_to_duration(seconds: int) -> str:
    """秒数を「○分○秒」に変換する関数"""
    minutes = seconds // 60
    rem_seconds = seconds % 60
    if rem_seconds > 0:
        return f"{minutes}分{rem_seconds:02d}秒"
    return f"{minutes}分00秒"


# ==========================================
# 4. メニュー生成コアエンジン
# ==========================================
def generate_swimming_menu(
    start_time: str, end_time: str, best_time_50m: float, theme: str
) -> dict:
    # --- Step 1: 練習総時間の計算 ---
    time_format = "%H:%M"
    start_dt = datetime.strptime(start_time, time_format)
    end_dt = datetime.strptime(end_time, time_format)

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    total_seconds = int((end_dt - start_dt).total_seconds())

    # --- Step 2: 50mサークルの自動計算（5秒単位に切り上げ） ---
    if theme == "フォーム":
        base_cycle_50 = best_time_50m + 30.0
    elif theme == "スプリント":
        base_cycle_50 = best_time_50m + 55.0
    elif theme == "個人メドレー":
        base_cycle_50 = best_time_50m + 40.0
    else:
        base_cycle_50 = best_time_50m + 35.0

    cycle_50_sec = ceil_to_5_seconds(base_cycle_50)
    cycle_100_sec = cycle_50_sec * 2

    # --- Step 3: タイムボックス制による時間の自動分配 ---
    w_up_time_alloc = total_seconds * 0.20
    dkp_time_alloc = total_seconds * 0.30
    main_time_alloc = total_seconds * 0.40
    cdown_time_alloc = total_seconds * 0.10

    menu_results = {}

    # 【1】 W-up
    w_up_reps = max(1, int(w_up_time_alloc // cycle_50_sec))
    w_up_dist = w_up_reps * 50
    w_up_duration = w_up_reps * cycle_50_sec
    menu_results["W-up"] = {
        "section_name": "W-up (ウォームアップ)",
        "menu_text": f"{w_up_reps}本 × 50m ({format_seconds_to_cycle(cycle_50_sec)}サークル)\nChoice / SKPS",
        "distance_m": w_up_dist,
        "duration_sec": w_up_duration,
        "duration_str": format_seconds_to_duration(w_up_duration),
    }

    # 【2】 Drill / Kick / Pull
    dkp_reps = max(1, int(dkp_time_alloc // cycle_50_sec))
    dkp_dist = dkp_reps * 50
    dkp_duration = dkp_reps * cycle_50_sec
    phrases = VARIATION_PHRASES.get(theme, VARIATION_PHRASES["フォーム"])
    selected_phrase = random.choice(phrases)
    menu_results["Drill/Kick/Pull"] = {
        "section_name": "Drill / Kick / Pull",
        "menu_text": f"{dkp_reps}本 × 50m ({format_seconds_to_cycle(cycle_50_sec)}サークル)\n[{selected_phrase}]",
        "distance_m": dkp_dist,
        "duration_sec": dkp_duration,
        "duration_str": format_seconds_to_duration(dkp_duration),
    }

    # 【3】 Main
    pattern_choice = random.choice(["A", "B", "C"])
    if pattern_choice == "A":
        main_reps = max(1, int(main_time_alloc // cycle_50_sec))
        main_dist = main_reps * 50
        main_duration = main_reps * cycle_50_sec
        main_text = f"{main_reps}本 × 50m ({format_seconds_to_cycle(cycle_50_sec)}サークル)\nPace Keep / Hard!"
    elif pattern_choice == "B":
        one_set_time = (3 * cycle_50_sec) + (2 * cycle_100_sec)
        one_set_dist = (3 * 50) + (2 * 100)
        num_sets = max(1, int(main_time_alloc // one_set_time))
        main_dist = num_sets * one_set_dist
        main_duration = num_sets * one_set_time
        c50_str = format_seconds_to_cycle(cycle_50_sec)
        c100_str = format_seconds_to_cycle(cycle_100_sec)
        main_text = (
            f"(\n"
            f"   3本 × 50m  ({c50_str}サークル)  Build-up!\n"
            f"   2本 × 100m ({c100_str}サークル)  Target Max Pace!\n"
            f") × {num_sets}セット"
        )
    else:
        main_reps = max(1, int(main_time_alloc // cycle_50_sec))
        main_dist = main_reps * 50
        main_duration = main_reps * cycle_50_sec
        selected_main_phrase = random.choice(phrases)
        main_text = f"{main_reps}本 × 50m ({format_seconds_to_cycle(cycle_50_sec)}サークル)\n[{selected_main_phrase}]"

    menu_results["Main"] = {
        "section_name": f"Main (メイン - パターン{pattern_choice})",
        "menu_text": main_text,
        "distance_m": main_dist,
        "duration_sec": main_duration,
        "duration_str": format_seconds_to_duration(main_duration),
    }

    # 【4】 C-down
    cdown_reps = max(1, int(cdown_time_alloc // cycle_50_sec))
    cdown_dist = cdown_reps * 50
    cdown_duration = cdown_reps * cycle_50_sec
    menu_results["C-down"] = {
        "section_name": "C-down (クールダウン)",
        "menu_text": f"{cdown_dist}m × 1本 ({format_seconds_to_cycle(cdown_duration)})\nEasy / Loosen",
        "distance_m": cdown_dist,
        "duration_sec": cdown_duration,
        "duration_str": format_seconds_to_duration(cdown_duration),
    }

    # --- Step 4: 出力テキストの作成 ---
    total_menu_distance = sum(b["distance_m"] for b in menu_results.values())
    total_used_duration = sum(b["duration_sec"] for b in menu_results.values())

    formatted_text = f"【本日の練習メニュー - Aqua Plan】\n"
    formatted_text += f"■ 時間: {start_time} 〜 {end_time} ({format_seconds_to_duration(total_seconds)})\n"
    formatted_text += f"■ テーマ: {theme} | 50m持ちタイム: {best_time_50m}秒\n"
    formatted_text += f"■ 基準サークル: 50m={format_seconds_to_cycle(cycle_50_sec)} / 100m={format_seconds_to_cycle(cycle_100_sec)}\n"
    formatted_text += f"■ 総距離: {total_menu_distance}m (実稼働時間: {format_seconds_to_duration(total_used_duration)})\n"
    formatted_text += "-----------------------------------------\n"

    for block_val in menu_results.values():
        formatted_text += f"◆ {block_val['section_name']} [{block_val['distance_m']}m / {block_val['duration_str']}]\n"
        formatted_text += f"{block_val['menu_text']}\n\n"

    formatted_text += "-----------------------------------------"

    return {
        "summary": {
            "start_time": start_time,
            "end_time": end_time,
            "total_available_str": format_seconds_to_duration(total_seconds),
            "total_used_str": format_seconds_to_duration(total_used_duration),
            "theme": theme,
            "best_time_50m": best_time_50m,
            "cycle_50m_str": format_seconds_to_cycle(cycle_50_sec),
            "cycle_100m_str": format_seconds_to_cycle(cycle_100_sec),
            "total_distance_m": total_menu_distance,
        },
        "menu_blocks": menu_results,
        "formatted_text": formatted_text,
    }


# ==========================================
# 5. パスワード認証 & Streamlit UI 画面構築
# ==========================================
st.title("🏊‍♂️ Aqua Plan")

# セッション状態でログイン状態を保持
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# パスワード未認証の場合の認証画面
if not st.session_state.authenticated:
    st.caption("ご利用にはパスワードが必要です。")

    with st.form("login_form"):
        password_input = st.text_input("🔑 パスワードを入力してください", type="password")
        login_button = st.form_submit_button("ログイン", type="primary", use_container_width=True)

    if login_button:
        if password_input == "swim2026":
            st.session_state.authenticated = True
            st.success("ログイン成功！")
            st.rerun()
        else:
            st.error("パスワードが違います。正しいパスワードを入力してください。")

# 認証成功後のメニュー作成画面
else:
    st.caption("練習枠と50m持ちタイムから、時間にぴったり収まる練習メニューを全自動で計算します。")

    # 入力フォームエリア
    with st.form("menu_form"):
        st.subheader("📋 練習条件を入力")

        col1, col2 = st.columns(2)
        with col1:
            start_time_input = st.time_input(
                "開始時刻", datetime.strptime("10:00", "%H:%M").time()
            )
        with col2:
            end_time_input = st.time_input(
                "終了時刻", datetime.strptime("11:30", "%H:%M").time()
            )

        best_time = st.slider(
            "50m 持ちタイム (秒)",
            min_value=20.0,
            max_value=90.0,
            value=35.0,
            step=0.5,
        )

        theme_input = st.selectbox(
            "今日のテーマ", ["フォーム", "スプリント", "個人メドレー"]
        )

        submit_button = st.form_submit_button(
            "🚀 メニューを自動生成する", type="primary", use_container_width=True
        )

    # ボタン押下後の出力エリア
    if submit_button:
        start_str = start_time_input.strftime("%H:%M")
        end_str = end_time_input.strftime("%H:%M")

        # 生成結果をセッションに保存（トグル切替等で画面が再描画されてもデータを維持）
        st.session_state.menu_data = generate_swimming_menu(
            start_str, end_str, best_time, theme_input
        )

    # メニューデータが存在する場合の描画
    if "menu_data" in st.session_state:
        result = st.session_state.menu_data
        summary = result["summary"]

        st.markdown("---")
        st.subheader("🏊‍♂️ 作成されたメニュー")

        # トグルスイッチ：印刷用シート表示の切り替え
        show_print_sheet = st.toggle("🖨️ 印刷用シート (SWIM SHEET) を表示", value=False)

        # --------------------------------------------------
        # 印刷用シート (SWIM SHEET) の表示領域
        # --------------------------------------------------
        if show_print_sheet:
            today_str = datetime.now().strftime("%Y年%m月%d日")

            # 直挿入HTML/CSS（@media printで親画面の全要素を隠し、SWIM SHEETのみを最前面で印刷）
            print_html_css = f"""
            <style>
            /* 画面表示用スタイル */
            .swim-sheet-wrapper {{
                background-color: #ffffff;
                color: #111111;
                border: 2px solid #005580;
                border-radius: 8px;
                padding: 20px;
                margin: 15px 0;
                font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", sans-serif;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            }}
            .swim-sheet-title {{
                text-align: center;
                font-size: 26px;
                font-weight: bold;
                letter-spacing: 2px;
                margin-bottom: 14px;
                color: #004080;
                border-bottom: 3px double #004080;
                padding-bottom: 6px;
            }}
            .swim-sheet-meta {{
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                background-color: #f0f7ff;
                padding: 10px 14px;
                border-radius: 6px;
                margin-bottom: 16px;
                font-size: 13px;
                border: 1px solid #d0e4ff;
            }}
            .swim-sheet-meta-item {{
                margin: 3px 6px;
            }}
            .swim-sheet-table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .swim-sheet-table th, .swim-sheet-table td {{
                border: 1px solid #b0c4de;
                padding: 8px 10px;
                text-align: left;
                vertical-align: top;
            }}
            .swim-sheet-table th {{
                background-color: #005580;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }}
            .swim-sheet-table td {{
                font-size: 13px;
                line-height: 1.4;
            }}
            .swim-sheet-section-title {{
                font-weight: bold;
                color: #003366;
            }}
            .swim-sheet-menu-content {{
                white-space: pre-wrap;
                font-family: inherit;
                font-size: 13px;
                margin: 0;
            }}

            /* -------------------------------------------------- */
            /* @media print 印刷用特別設定 (バグ防止・最前面切り出し) */
            /* -------------------------------------------------- */
            @media print {{
                /* 用紙設定：A4縦 */
                @page {{
                    size: A4 portrait;
                    margin: 8mm;
                }}

                /* 画面上のすべての要素を非表示（フォーム、ボタン、ヘッダー含む） */
                body * {{
                    visibility: hidden !important;
                }}

                /* SWIM SHEETとその配下のみを絶対配置で可視化して全画面化 */
                .swim-sheet-wrapper, .swim-sheet-wrapper * {{
                    visibility: visible !important;
                }}

                .swim-sheet-wrapper {{
                    position: absolute !important;
                    left: 0 !important;
                    top: 0 !important;
                    width: 100% !important;
                    border: 2px solid #000000 !important;
                    box-shadow: none !important;
                    padding: 10px !important;
                    margin: 0 !important;
                    background: #ffffff !important;
                    color: #000000 !important;
                }}

                .swim-sheet-title {{
                    color: #000000 !important;
                    border-bottom-color: #000000 !important;
                    font-size: 22px !important;
                    margin-bottom: 10px !important;
                }}

                .swim-sheet-meta {{
                    background-color: #f8f8f8 !important;
                    border: 1px solid #cccccc !important;
                    color: #000000 !important;
                    padding: 8px !important;
                    font-size: 11px !important;
                    margin-bottom: 12px !important;
                }}

                .swim-sheet-table th {{
                    background-color: #e6e6e6 !important;
                    color: #000000 !important;
                    border-color: #333333 !important;
                    font-size: 11px !important;
                    padding: 6px 8px !important;
                }}

                .swim-sheet-table td {{
                    border-color: #333333 !important;
                    color: #000000 !important;
                    font-size: 11px !important;
                    padding: 6px 8px !important;
                }}

                .swim-sheet-section-title {{
                    color: #000000 !important;
                }}

                .swim-sheet-menu-content {{
                    font-size: 11px !important;
                }}
            }}
            </style>
            """

            # テーブル行の構築
            table_rows_html = ""
            for block in result["menu_blocks"].values():
                table_rows_html += f"""
                <tr>
                    <td style="width: 28%;">
                        <div class="swim-sheet-section-title">{block['section_name']}</div>
                    </td>
                    <td style="width: 22%; text-align: center;">
                        <strong>{block['distance_m']}m</strong><br>
                        <span style="font-size:11px; color:#555;">({block['duration_str']})</span>
                    </td>
                    <td style="width: 50%;">
                        <pre class="swim-sheet-menu-content">{block['menu_text']}</pre>
                    </td>
                </tr>
                """

            html_content = f"""
            {print_html_css}
            <div class="swim-sheet-wrapper">
                <div class="swim-sheet-title">SWIM SHEET</div>
                <div class="swim-sheet-meta">
                    <div class="swim-sheet-meta-item"><strong>日付:</strong> {today_str}</div>
                    <div class="swim-sheet-meta-item"><strong>時間:</strong> {summary['start_time']} 〜 {summary['end_time']} ({summary['total_available_str']})</div>
                    <div class="swim-sheet-meta-item"><strong>テーマ:</strong> {summary['theme']}</div>
                    <div class="swim-sheet-meta-item"><strong>総距離:</strong> {summary['total_distance_m']}m</div>
                </div>
                <table class="swim-sheet-table">
                    <thead>
                        <tr>
                            <th>セクション</th>
                            <th>距離 / 時間</th>
                            <th>メニュー内容</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
            """

            # Streamlit画面直出力（親DOMにスタイル適用）
            st.markdown(html_content, unsafe_allow_html=True)
            st.info("💡 **印刷機能:** キーボードの `Ctrl + P`（Macは `Cmd + P`）またはスマホブラウザの「印刷」を実行すると、上のSWIM SHEETのみがA4縦1枚で綺麗に印刷されます。")

        # --------------------------------------------------
        # 通常のアプリ画面表示（標準出力）
        # --------------------------------------------------
        st.success(
            f"**【{summary['theme']}】** {summary['start_time']}〜{summary['end_time']} "
            f"({summary['total_available_str']}) ｜ 予定総距離: **{summary['total_distance_m']}m**"
        )

        # 基準サークルのメトリクス表示
        m1, m2 = st.columns(2)
        m1.metric("50m 基準サークル", summary["cycle_50m_str"])
        m2.metric("100m 基準サークル", summary["cycle_100m_str"])

        # ブロックごとのメニュー詳細表示
        st.markdown("### 📋 セクション詳細")
        for block in result["menu_blocks"].values():
            st.markdown(
                f"#### ◆ {block['section_name']}  `{block['distance_m']}m` / `{block['duration_str']}`"
            )
            st.code(block["menu_text"], language=None)

        # コピペ・共有用テキストエリア
        st.markdown("### 📱 LINE・コピペ共有用テキスト")
        st.text_area(
            "タップして全選択コピーすればそのまま共有できます",
            value=result["formatted_text"],
            height=240,
        )
