import streamlit as st

# ページ基本設定（スマホ表示を意識してタイトルとアイコンを設定）
st.set_page_config(
    page_title="競泳メニュー自動作成",
    page_icon="🏊‍♂️",
    layout="centered"
)

st.title("🏊‍♂️ 競泳メニュー自動作成")
st.caption("対象・テーマ・総距離を選ぶだけで、練習メニューを自動計算して出力します。")

# --- 1. 条件入力エリア ---
st.subheader("1. 条件の設定")

col1, col2 = st.columns(2)

with col1:
    level = st.selectbox(
        "対象者レベル",
        ["初級（ジュニア・初心者）", "中級（選手育成）", "上級（選手選抜）"]
    )

with col2:
    theme = st.selectbox(
        "今日のテーマ",
        ["スプリント（短距離・爆発力）", "持久力（長距離・耐乳酸）", "フォーム・ドリル（技術改善）", "総合（バランス）"]
    )

total_dist = st.select_slider(
    "目標の総距離 (m)",
    options=[1000, 1500, 2000, 2500, 3000, 4000, 5000],
    value=2000
)

# --- 2. メニュー生成ロジック関数 ---
def generate_workout(level_str, theme_str, total_d):
    # レベルごとのペース目安（50mあたりのサイクル時間など）
    pace_map = {
        "初級（ジュニア・初心者）": {"50m": "1'15\"", "100m": "2'30\"", "200m": "5'00\""},
        "中級（選手育成）": {"50m": "1'00\"", "100m": "2'00\"", "200m": "4'00\""},
        "上級（選手選抜）": {"50m": "0'45\"", "100m": "1'30\"", "200m": "3'00\""}
    }
    pace = pace_map[level_str]

    # テーマごとの距離分配割合 [W-up, Kick, Pull, Main, C-down]
    if "スプリント" in theme_str:
        ratios = [0.15, 0.25, 0.20, 0.30, 0.10]
    elif "持久力" in theme_str:
        ratios = [0.10, 0.15, 0.15, 0.50, 0.10]
    elif "フォーム" in theme_str:
        ratios = [0.15, 0.30, 0.30, 0.15, 0.10]
    else:  # 総合
        ratios = [0.15, 0.20, 0.20, 0.35, 0.10]

    # 50m単位で丸め処理
    w_dist = int(round(total_d * ratios[0] / 50) * 50)
    k_dist = int(round(total_d * ratios[1] / 50) * 50)
    p_dist = int(round(total_d * ratios[2] / 50) * 50)
    c_dist = int(round(total_d * ratios[4] / 50) * 50)
    m_dist = total_d - (w_dist + k_dist + p_dist + c_dist)  # 端数はMainに集約

    # 具体的なセット組み
    menu = {
        "W-up": f"{w_dist}m × 1本 (SKPS / Choice)",
        "Kick": f"50m × {k_dist // 50}本 ({pace['50m']}) Board Kick / Choice",
        "Pull": f"50m × {p_dist // 50}本 ({pace['50m']}) Form / Pad & Buoy",
        "Main": f"100m × {m_dist // 100}本 ({pace['100m']}) Target Pace / Hard!" if m_dist >= 400 else f"50m × {m_dist // 50}本 ({pace['50m']}) Max Sprint!",
        "C-down": f"{c_dist}m × 1本 Easy / Loosen"
    }

    breakdown = {
        "W-up": w_dist, "Kick": k_dist, "Pull": p_dist, "Main": m_dist, "C-down": c_dist
    }

    return menu, breakdown

# --- 3. メニュー生成＆表示エリア ---
st.markdown("---")

if st.button("🚀 練習メニューを自動生成する", use_container_width=True, type="primary"):
    menu, breakdown = generate_workout(level, theme, total_dist)

    st.subheader("2. 作成されたメニュー")
    
    # 概要カード
    st.success(f"**【{level.split('（')[0]}】** テーマ: **{theme.split('（')[0]}** / 総距離: **{total_dist}m**")

    # 距離の内訳を横並び表示
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("W-up", f"{breakdown['W-up']}m")
    c2.metric("Kick", f"{breakdown['Kick']}m")
    c3.metric("Pull", f"{breakdown['Pull']}m")
    c4.metric("Main", f"{breakdown['Main']}m")
    c5.metric("C-down", f"{breakdown['C-down']}m")

    st.markdown("### 📋 メニュー詳細")
    for block, item in menu.items():
        st.markdown(f"**【{block}】**")
        st.code(item, language=None)

    # LINE共有用テキスト出力
    st.markdown("### 📱 LINE・共有用テキスト")
    raw_text = f"【本日の練習メニュー】\n対象: {level.split('（')[0]} / テーマ: {theme.split('（')[0]}\n総距離: {total_dist}m\n-------------------\n"
    for block, item in menu.items():
        raw_text += f"[{block}] {item}\n"
    raw_text += "-------------------"
    
    st.text_area("そのままコピーして使えます", value=raw_text, height=180)
