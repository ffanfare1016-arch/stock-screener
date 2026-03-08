import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="銘柄スクリーナー", page_icon="🔭", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;700&family=JetBrains+Mono:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; background-color: #f5f6fa; color: #1a1a2e; }
.stApp { background: #f5f6fa; }
.metric-card {
    background: #fff; border: 1px solid #e0e0ec; border-radius: 10px;
    padding: 16px 10px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.05); margin-bottom: 6px;
}
.metric-label { font-size: 10px; color: #999; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 5px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700; }
.metric-value.positive { color: #16a34a; }
.metric-value.negative { color: #dc2626; }
.metric-value.neutral  { color: #2563eb; }
.section-title {
    font-size: 12px; font-weight: 700; letter-spacing: 2px; color: #4f46e5;
    text-transform: uppercase; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #e0e0ec;
}
.rank-badge {
    display: inline-block; width: 32px; height: 32px; line-height: 32px;
    border-radius: 50%; text-align: center; font-weight: 700; font-size: 14px;
}
.rank-1  { background: #fbbf24; color: #fff; }
.rank-2  { background: #9ca3af; color: #fff; }
.rank-3  { background: #b45309; color: #fff; }
.rank-other { background: #e0e0ec; color: #444; }
.condition-tag {
    display: inline-block; background: #eff6ff; color: #1d4ed8;
    border: 1px solid #bfdbfe; border-radius: 20px;
    padding: 3px 12px; font-size: 12px; font-weight: 700; margin: 2px;
}
section[data-testid="stSidebar"] { background: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# ─── 銘柄辞書 ─────────────────────────────────────────────────
STOCK_DICT = {
    "トヨタ自動車":             "7203",
    "ホンダ":                   "7267",
    "日産自動車":               "7201",
    "スズキ":                   "7269",
    "マツダ":                   "7261",
    "SUBARU":                   "7270",
    "三菱自動車":               "7211",
    "ソニーグループ":           "6758",
    "パナソニック":             "6752",
    "日立製作所":               "6501",
    "東芝":                     "6502",
    "三菱電機":                 "6503",
    "富士通":                   "6702",
    "NEC":                      "6701",
    "キーエンス":               "6861",
    "ファナック":               "6954",
    "村田製作所":               "6981",
    "TDK":                      "6762",
    "京セラ":                   "6971",
    "ルネサスエレクトロニクス": "6723",
    "アドバンテスト":           "6857",
    "東京エレクトロン":         "8035",
    "信越化学工業":             "4063",
    "ソフトバンクグループ":     "9984",
    "ソフトバンク":             "9434",
    "NTT":                      "9432",
    "KDDI":                     "9433",
    "楽天グループ":             "4755",
    "メルカリ":                 "4385",
    "サイバーエージェント":     "4751",
    "DeNA":                     "2432",
    "GMOインターネット":        "9449",
    "三菱UFJフィナンシャル":    "8306",
    "三井住友フィナンシャル":   "8316",
    "みずほフィナンシャル":     "8411",
    "野村ホールディングス":     "8604",
    "大和証券グループ":         "8601",
    "オリックス":               "8591",
    "東京海上ホールディングス": "8766",
    "第一生命ホールディングス": "8750",
    "SBIホールディングス":      "8473",
    "ファーストリテイリング":   "9983",
    "セブン&アイ":              "3382",
    "イオン":                   "8267",
    "ニトリホールディングス":   "9843",
    "良品計画（無印良品）":     "7453",
    "パン・パシフィック":       "7532",
    "ヤマダホールディングス":   "9831",
    "味の素":                   "2802",
    "日清食品ホールディングス": "2897",
    "キリンホールディングス":   "2503",
    "アサヒグループ":           "2502",
    "サントリー食品":           "2587",
    "明治ホールディングス":     "2269",
    "日本ハム":                 "2282",
    "三菱ケミカルグループ":     "4188",
    "旭化成":                   "3407",
    "住友化学":                 "4005",
    "花王":                     "4452",
    "資生堂":                   "4911",
    "三菱重工業":               "7011",
    "川崎重工業":               "7012",
    "IHI":                      "7013",
    "大林組":                   "1802",
    "鹿島建設":                 "1812",
    "清水建設":                 "1803",
    "三井不動産":               "8801",
    "住友不動産":               "8830",
    "三菱地所":                 "8802",
    "ENEOSホールディングス":    "5020",
    "出光興産":                 "5019",
    "武田薬品工業":             "4502",
    "アステラス製薬":           "4503",
    "第一三共":                 "4568",
    "エーザイ":                 "4523",
    "塩野義製薬":               "4507",
    "中外製薬":                 "4519",
    "日本郵船":                 "9101",
    "商船三井":                 "9104",
    "川崎汽船":                 "9107",
    "ヤマトホールディングス":   "9064",
    "日本通運":                 "9062",
    "ANAホールディングス":      "9202",
    "日本航空（JAL）":          "9201",
    "日本製鉄":                 "5401",
    "JFEホールディングス":      "5411",
    "住友金属鉱山":             "5713",
    "任天堂":                   "7974",
    "カプコン":                 "9697",
    "バンダイナムコ":           "7832",
    "スクウェア・エニックス":   "9684",
    "コナミグループ":           "9766",
    "リクルートホールディングス": "6098",
    "日本電産（ニデック）":     "6594",
    "ダイキン工業":             "6367",
}

def month_resample_freq():
    major, minor = [int(x) for x in pd.__version__.split(".")[:2]]
    return "ME" if (major, minor) >= (2, 2) else "M"

MONTH_FREQ = month_resample_freq()

# ─── サイドバー ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ スキャン設定")

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("開始日", value=datetime.today() - timedelta(days=365*3))
    with c2:
        end_date = st.date_input("終了日", value=datetime.today())

    commission_pct = st.number_input("手数料（%）", value=0.05, step=0.01, format="%.2f") / 100
    shares         = st.number_input("取引株数", value=100, step=100)

    min_trades = st.slider("最低取引日数（これ未満は除外）", 5, 50, 20,
                            help="サンプルが少なすぎる銘柄を除外します")

    st.markdown("---")
    st.markdown("### 📡 スキャン条件（AND）")
    st.caption("選んだ条件をすべて満たした日にのみ買い")

    st.markdown("**日経平均の方向**")
    use_nk_up   = st.checkbox("☀️ 先物が前日比プラス（朝6時時点）",   value=False)
    use_nk_down = st.checkbox("🌧️ 先物が前日比マイナス（朝6時時点）",   value=False)

    st.markdown("**RSI**")
    use_rsi       = st.checkbox("📉 RSI がしきい値以下", value=False)
    rsi_threshold = st.slider("RSI しきい値", 10, 50, 30, disabled=not use_rsi)

    st.markdown("**移動平均乖離**")
    use_ma_dev = st.checkbox("📊 移動平均から大きく下落", value=False)
    ma_period  = st.slider("移動平均期間（日）", 5, 50, 25, disabled=not use_ma_dev)
    ma_dev_pct = st.slider("乖離率（%以上）", 1.0, 10.0, 3.0, step=0.5, disabled=not use_ma_dev)

    st.markdown("**ボリンジャーバンド**")
    use_bband = st.checkbox("🎯 ボリンジャー下限を下回る", value=False)
    bb_period = st.slider("ボリンジャー期間", 10, 30, 20, disabled=not use_bband)
    bb_sigma  = st.slider("σ（標準偏差）", 1.0, 3.0, 2.0, step=0.5, disabled=not use_bband)

    st.markdown("**前日の動き**")
    use_prev_down = st.checkbox("↩️ 前日に大きく下げた翌日", value=False)
    prev_drop_pct = st.slider("前日下落幅（%以上）", 1.0, 8.0, 3.0, step=0.5, disabled=not use_prev_down)

    st.markdown("**曜日**")
    use_weekday = st.checkbox("📅 特定の曜日だけ", value=False)
    weekday_map = {"月曜日":0,"火曜日":1,"水曜日":2,"木曜日":3,"金曜日":4}
    selected_weekdays = st.multiselect("曜日を選択", list(weekday_map.keys()),
                                        default=["月曜日"], disabled=not use_weekday)

    st.markdown("---")
    st.markdown("### 🏆 ランキング基準")
    rank_by = st.radio("並び順", ["勝率（高い順）", "合計損益（高い順）"], horizontal=True)
    top_n   = st.slider("上位何銘柄を表示", 5, 30, 20)

    st.markdown("---")
    run_btn = st.button("🔭 全銘柄スキャン開始", use_container_width=True, type="primary")

# ─── ユーティリティ ───────────────────────────────────────────
def flatten(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def build_signal(stk, nk, nkd, params):
    close  = stk["Close"]
    signal = pd.Series(True, index=stk.index)
    # NKD=F 前日終値（日本時間朝6時確定）vs ^N225 前日終値（15:30確定）
    nkd_prev = nkd["Close"].reindex(stk.index, method="ffill").shift(1)
    n225_prev = nk["Close"].reindex(stk.index, method="ffill").shift(1)

    if params["use_nk_up"]:
        signal &= (nkd_prev > n225_prev).fillna(False)
    if params["use_nk_down"]:
        signal &= (nkd_prev < n225_prev).fillna(False)
    if params["use_rsi"]:
        signal &= (compute_rsi(close) < params["rsi_threshold"]).fillna(False)
    if params["use_ma_dev"]:
        ma  = close.rolling(params["ma_period"]).mean()
        dev = (close - ma) / ma * 100
        signal &= (dev < -params["ma_dev_pct"]).fillna(False)
    if params["use_bband"]:
        bm  = close.rolling(params["bb_period"]).mean()
        bs  = close.rolling(params["bb_period"]).std()
        signal &= (close < bm - params["bb_sigma"] * bs).fillna(False)
    if params["use_prev_down"]:
        pr = close.pct_change() * 100
        signal &= (pr.shift(1) < -params["prev_drop_pct"]).fillna(False)
    if params["use_weekday"] and params["selected_weekdays"]:
        dnums = [params["weekday_map"][w] for w in params["selected_weekdays"]]
        signal &= pd.Series(stk.index.dayofweek.isin(dnums), index=stk.index)

    return signal

def run_backtest(stk, signal, comm, qty):
    pnl = pd.Series(0.0, index=stk.index)
    for d in stk.index[signal]:
        o = stk["Open"].get(d)
        c = stk["Close"].get(d)
        if o is None or c is None or pd.isna(o) or pd.isna(c) or o == 0:
            continue
        pnl[d] = (c - o) * qty - (o + c) * qty * comm
    return pnl

def calc_stats(pnl, name, code):
    active = pnl[pnl != 0]
    wins   = active[active > 0]
    losses = active[active < 0]
    n      = len(active)
    if n == 0:
        return None
    cum = pnl.cumsum()
    dd  = (cum - cum.cummax()).min()
    pf  = (-wins.sum() / losses.sum()) if losses.sum() != 0 else np.inf
    return {
        "銘柄名":   name,
        "コード":   code,
        "取引日数": n,
        "勝ち":     len(wins),
        "負け":     len(losses),
        "勝率":     round(len(wins) / n * 100, 1),
        "合計損益": round(active.sum(), 0),
        "平均利益": round(wins.mean(), 0)   if len(wins)   > 0 else 0,
        "平均損失": round(losses.mean(), 0) if len(losses) > 0 else 0,
        "PF":       round(pf, 2) if pf != np.inf else 999,
        "最大DD":   round(dd, 0),
        "pnl_series": pnl,
    }

# ─── メインエリア ─────────────────────────────────────────────
st.markdown("## 🔭 銘柄スクリーナー")
st.markdown("<span style='color:#666;font-size:13px'>選んだ条件で全80銘柄を一括スキャン → 勝率・損益の上位銘柄をランキング表示</span>",
            unsafe_allow_html=True)

with st.expander("💡 使い方"):
    st.markdown("""
    1. **左のサイドバー**でスキャン条件（RSI・日経方向・ボリンジャーなど）を選ぶ
    2. **「全銘柄スキャン開始」** を押すと80銘柄を順番に検証（2〜3分かかります）
    3. 条件を満たした日に「始値で買い・大引けで売り」した場合の成績でランキング化
    4. 気になった銘柄は **バックテストアプリ** で詳細確認！
    """)

if run_btn:
    # 条件チェック
    params = dict(
        use_nk_up=use_nk_up, use_nk_down=use_nk_down,
        use_rsi=use_rsi, rsi_threshold=rsi_threshold,
        use_ma_dev=use_ma_dev, ma_period=ma_period, ma_dev_pct=ma_dev_pct,
        use_bband=use_bband, bb_period=bb_period, bb_sigma=bb_sigma,
        use_prev_down=use_prev_down, prev_drop_pct=prev_drop_pct,
        use_weekday=use_weekday, selected_weekdays=selected_weekdays,
        weekday_map=weekday_map,
    )

    if use_nk_up and use_nk_down:
        st.error("「先物プラス」と「先物マイナス」は同時に選べません"); st.stop()

    any_cond = any([use_nk_up, use_nk_down, use_rsi, use_ma_dev, use_bband, use_prev_down, use_weekday])
    if not any_cond:
        st.warning("条件を1つ以上選択してください"); st.stop()

    # 使用中の条件ラベル
    cond_labels = []
    if use_nk_up:   cond_labels.append("☀️ 先物が前日比プラス（朝6時時点）")
    if use_nk_down: cond_labels.append("🌧️ 先物が前日比マイナス（朝6時時点）")
    if use_rsi:     cond_labels.append(f"📉 RSI {rsi_threshold}以下")
    if use_ma_dev:  cond_labels.append(f"📊 {ma_period}日MA から {ma_dev_pct}%以上下落")
    if use_bband:   cond_labels.append(f"🎯 ボリンジャー -{bb_sigma}σ 下抜け")
    if use_prev_down: cond_labels.append(f"↩️ 前日 -{prev_drop_pct}%以上下落の翌日")
    if use_weekday and selected_weekdays: cond_labels.append(f"📅 {'・'.join(selected_weekdays)}")

    tags = "".join([f'<span class="condition-tag">{c}</span>' for c in cond_labels])
    st.markdown(f'<div style="background:#fff;border:1px solid #e0e0ec;border-radius:10px;padding:14px 18px;margin-bottom:16px">{tags}</div>',
                unsafe_allow_html=True)

    # 日経データ・先物データは1回だけ取得
    with st.spinner("日経平均・先物データを取得中..."):
        try:
            nk_raw  = yf.download("^N225", start=str(start_date), end=str(end_date),
                                   auto_adjust=True, progress=False)
            nkd_raw = yf.download("NKD=F", start=str(start_date), end=str(end_date),
                                   auto_adjust=True, progress=False)
            nk  = flatten(nk_raw.copy())
            nkd = flatten(nkd_raw.copy()) if not nkd_raw.empty else nk
        except Exception as e:
            st.error(f"日経データ取得エラー: {e}"); st.stop()

    # 進捗バー
    st.markdown('<div class="section-title">⏳ スキャン中...</div>', unsafe_allow_html=True)
    progress_bar  = st.progress(0)
    status_text   = st.empty()

    results = []
    stocks  = list(STOCK_DICT.items())
    total   = len(stocks)

    for i, (name, code) in enumerate(stocks):
        ticker = code + ".T"
        status_text.markdown(f"**{i+1}/{total}** 処理中: `{name}` ({ticker})")
        progress_bar.progress((i + 1) / total)

        try:
            raw = yf.download(ticker, start=str(start_date), end=str(end_date),
                               auto_adjust=True, progress=False, timeout=10)
            if raw.empty:
                continue
            stk = flatten(raw.copy())
            sig = build_signal(stk, nk, nkd, params)

            if sig.sum() < min_trades:
                continue  # サンプル不足はスキップ

            pnl  = run_backtest(stk, sig, commission_pct, shares)
            stat = calc_stats(pnl, name, code)
            if stat:
                results.append(stat)
        except Exception:
            pass  # 取得失敗は無視してスキップ

        time.sleep(0.1)  # API制限を避けるための短い待機

    progress_bar.empty()
    status_text.empty()

    if not results:
        st.warning("条件に該当する銘柄が見つかりませんでした。条件を緩めてみてください。")
        st.stop()

    # ランキング
    df_res = pd.DataFrame(results)
    sort_col = "勝率" if rank_by == "勝率（高い順）" else "合計損益"
    df_res = df_res.sort_values(sort_col, ascending=False).reset_index(drop=True)
    df_top = df_res.head(top_n).copy()

    # ── サマリーカード ────────────────────────────────────────
    st.markdown(f'<div class="section-title">🏆 上位{top_n}銘柄（{rank_by}）</div>', unsafe_allow_html=True)

    scanned  = len(results)
    best_wr  = df_top["勝率"].max()
    best_pnl = df_top["合計損益"].max()

    c1, c2, c3 = st.columns(3)
    for c, (lbl, val, cls) in zip([c1,c2,c3], [
        ("スキャン銘柄数", f"{scanned}社", "neutral"),
        ("最高勝率",       f"{best_wr:.1f}%", "positive"),
        ("最高合計損益",   f"¥{best_pnl:,.0f}", "positive" if best_pnl >= 0 else "negative"),
    ]):
        with c:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">{lbl}</div>
                <div class="metric-value {cls}">{val}</div>
            </div>""", unsafe_allow_html=True)

    # ── ランキング棒グラフ ─────────────────────────────────────
    st.markdown('<div class="section-title">📊 ランキンググラフ</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["勝率", "合計損益"])

    with tab1:
        fig_wr = go.Figure(go.Bar(
            x=df_top["勝率"],
            y=df_top["銘柄名"],
            orientation="h",
            marker_color=["#fbbf24" if i==0 else "#9ca3af" if i==1 else "#b45309" if i==2 else "#4f46e5"
                          for i in range(len(df_top))],
            text=[f"{v:.1f}%" for v in df_top["勝率"]],
            textposition="outside",
            hovertemplate="%{y}<br>勝率: %{x:.1f}%<extra></extra>",
        ))
        fig_wr.add_vline(x=50, line_dash="dash", line_color="#dc2626", line_width=1.5,
                          annotation_text="50%", annotation_position="top")
        fig_wr.update_layout(
            paper_bgcolor="#ffffff", plot_bgcolor="#f9f9fc",
            font=dict(color="#1a1a2e", family="Noto Sans JP"),
            xaxis=dict(gridcolor="#ebebf5", title="勝率（%）", range=[0, max(df_top["勝率"])+10]),
            yaxis=dict(autorange="reversed"),
            height=max(400, top_n * 28 + 80),
            margin=dict(l=10, r=80, t=20, b=10),
        )
        st.plotly_chart(fig_wr, use_container_width=True)

    with tab2:
        colors_pnl = ["#16a34a" if v >= 0 else "#dc2626" for v in df_top["合計損益"]]
        fig_pnl = go.Figure(go.Bar(
            x=df_top["合計損益"],
            y=df_top["銘柄名"],
            orientation="h",
            marker_color=colors_pnl,
            text=[f"¥{v:,.0f}" for v in df_top["合計損益"]],
            textposition="outside",
            hovertemplate="%{y}<br>合計損益: ¥%{x:,.0f}<extra></extra>",
        ))
        fig_pnl.add_vline(x=0, line_dash="solid", line_color="#888", line_width=1)
        fig_pnl.update_layout(
            paper_bgcolor="#ffffff", plot_bgcolor="#f9f9fc",
            font=dict(color="#1a1a2e", family="Noto Sans JP"),
            xaxis=dict(gridcolor="#ebebf5", title="合計損益（円）", tickprefix="¥", tickformat=",.0f"),
            yaxis=dict(autorange="reversed"),
            height=max(400, top_n * 28 + 80),
            margin=dict(l=10, r=120, t=20, b=10),
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

    # ── 詳細テーブル ──────────────────────────────────────────
    st.markdown('<div class="section-title">📋 詳細ランキング表</div>', unsafe_allow_html=True)

    display_df = df_top[["銘柄名","コード","取引日数","勝ち","負け","勝率","合計損益","平均利益","平均損失","PF","最大DD"]].copy()
    display_df.index = range(1, len(display_df) + 1)
    display_df.index.name = "順位"

    def style_row(row):
        styles = [""] * len(row)
        wr_idx = list(row.index).index("勝率")
        pnl_idx = list(row.index).index("合計損益")
        styles[wr_idx]  = "color:#16a34a;font-weight:bold" if row["勝率"] >= 50 else "color:#dc2626;font-weight:bold"
        styles[pnl_idx] = "color:#16a34a;font-weight:bold" if row["合計損益"] >= 0 else "color:#dc2626;font-weight:bold"
        return styles

    styled = display_df.style.format({
        "勝率":    "{:.1f}%",
        "合計損益": "¥{:,.0f}",
        "平均利益": "¥{:,.0f}",
        "平均損失": "¥{:,.0f}",
        "最大DD":  "¥{:,.0f}",
    }).apply(style_row, axis=1)

    st.dataframe(styled, use_container_width=True, height=500)

    # ── 上位5銘柄の累積損益グラフ ─────────────────────────────
    st.markdown('<div class="section-title">📈 上位5銘柄 累積損益推移</div>', unsafe_allow_html=True)

    COLORS = ["#fbbf24","#4f46e5","#16a34a","#dc2626","#0891b2"]
    fig_cum = go.Figure()
    for i, row in df_top.head(5).iterrows():
        pnl = row["pnl_series"]
        active = pnl[pnl != 0]
        if active.empty:
            continue
        fig_cum.add_trace(go.Scatter(
            x=active.index, y=active.cumsum(),
            name=f"{i+1}位 {row['銘柄名']}",
            line=dict(color=COLORS[i % 5], width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>累積: ¥%{y:,.0f}<extra></extra>",
        ))
    fig_cum.add_hline(y=0, line_dash="dash", line_color="#ccc", line_width=1)
    fig_cum.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#f9f9fc",
        font=dict(color="#1a1a2e", family="Noto Sans JP"),
        legend=dict(bgcolor="#fff", bordercolor="#e0e0ec", borderwidth=1),
        xaxis=dict(gridcolor="#ebebf5"),
        yaxis=dict(gridcolor="#ebebf5", tickprefix="¥", tickformat=",.0f"),
        height=420, margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_cum, use_container_width=True)

    # ── CSV ダウンロード ───────────────────────────────────────
    st.markdown('<div class="section-title">💾 結果をダウンロード</div>', unsafe_allow_html=True)
    csv_df = display_df.drop(columns=[], errors="ignore")
    csv = csv_df.to_csv(encoding="utf-8-sig")
    st.download_button(
        label="📥 ランキング結果を CSV でダウンロード",
        data=csv,
        file_name=f"screening_{datetime.today().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

else:
    st.markdown("""
    <div style="text-align:center; padding:70px 0;">
        <div style="font-size:64px; margin-bottom:16px;">🔭</div>
        <div style="font-size:18px; color:#888; margin-bottom:8px;">条件を設定して</div>
        <div style="font-size:24px; color:#4f46e5; font-weight:700;">🔭 全銘柄スキャン開始</div>
        <div style="font-size:13px; color:#bbb; margin-top:28px; line-height:2.4;">
            80銘柄を一括チェックして勝率・損益でランキング<br>
            スキャンには <b style="color:#4f46e5">2〜3分</b> ほどかかります<br>
            結果は CSV でダウンロードも可能
        </div>
    </div>
    """, unsafe_allow_html=True)