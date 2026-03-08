import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="日経シグナル バックテスター", page_icon="📈", layout="wide")

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
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; }
.metric-value.positive { color: #16a34a; }
.metric-value.negative { color: #dc2626; }
.metric-value.neutral  { color: #2563eb; }
.section-title {
    font-size: 12px; font-weight: 700; letter-spacing: 2px; color: #4f46e5;
    text-transform: uppercase; margin: 28px 0 12px; padding-bottom: 8px; border-bottom: 2px solid #e0e0ec;
}
.condition-tag {
    display: inline-block; background: #eff6ff; color: #1d4ed8;
    border: 1px solid #bfdbfe; border-radius: 20px;
    padding: 3px 12px; font-size: 12px; font-weight: 700; margin: 2px;
}
.result-header {
    background: #fff; border: 1px solid #e0e0ec; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 12px; font-size: 14px; line-height: 1.8;
}
section[data-testid="stSidebar"] { background: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# ─── pandas バージョン対応：resample 周期文字列 ──────────────
def month_resample_freq():
    """pandas のバージョンに合わせて 'ME' か 'M' を返す"""
    major, minor = [int(x) for x in pd.__version__.split(".")[:2]]
    return "ME" if (major, minor) >= (2, 2) else "M"

MONTH_FREQ = month_resample_freq()

# ─── 銘柄辞書（会社名 → コード） ─────────────────────────────
STOCK_DICT = {
    # 自動車
    "トヨタ自動車":       "7203",
    "ホンダ":             "7267",
    "日産自動車":         "7201",
    "スズキ":             "7269",
    "マツダ":             "7261",
    "SUBARU":             "7270",
    "三菱自動車":         "7211",
    # 電機・IT
    "ソニーグループ":     "6758",
    "パナソニック":       "6752",
    "日立製作所":         "6501",
    "東芝":               "6502",
    "三菱電機":           "6503",
    "富士通":             "6702",
    "NEC":                "6701",
    "キーエンス":         "6861",
    "ファナック":         "6954",
    "村田製作所":         "6981",
    "TDK":                "6762",
    "京セラ":             "6971",
    "ルネサスエレクトロニクス": "6723",
    "アドバンテスト":     "6857",
    "東京エレクトロン":   "8035",
    "信越化学工業":       "4063",
    # 通信・ネット
    "ソフトバンクグループ": "9984",
    "ソフトバンク":       "9434",
    "NTT":                "9432",
    "KDDI":               "9433",
    "楽天グループ":       "4755",
    "メルカリ":           "4385",
    "サイバーエージェント": "4751",
    "DeNA":               "2432",
    "GMOインターネット":  "9449",
    # 金融
    "三菱UFJフィナンシャル": "8306",
    "三井住友フィナンシャル": "8316",
    "みずほフィナンシャル":  "8411",
    "野村ホールディングス":  "8604",
    "大和証券グループ":      "8601",
    "オリックス":           "8591",
    "東京海上ホールディングス": "8766",
    "第一生命ホールディングス": "8750",
    "SBIホールディングス":   "8473",
    # 小売・消費
    "ファーストリテイリング": "9983",
    "セブン&アイ":          "3382",
    "イオン":               "8267",
    "ニトリホールディングス": "9843",
    "良品計画（無印良品）":  "7453",
    "パン・パシフィック":    "7532",
    "ヤマダホールディングス": "9831",
    # 食品・飲料
    "味の素":               "2802",
    "日清食品ホールディングス": "2897",
    "キリンホールディングス": "2503",
    "アサヒグループ":        "2502",
    "サントリー食品":        "2587",
    "明治ホールディングス":  "2269",
    "日本ハム":              "2282",
    # 化学・素材
    "三菱ケミカルグループ":  "4188",
    "旭化成":               "3407",
    "住友化学":              "4005",
    "花王":                  "4452",
    "資生堂":               "4911",
    # 重工・建設
    "三菱重工業":           "7011",
    "川崎重工業":           "7012",
    "IHI":                  "7013",
    "大林組":               "1802",
    "鹿島建設":             "1812",
    "清水建設":             "1803",
    # 不動産
    "三井不動産":           "8801",
    "住友不動産":           "8830",
    "三菱地所":             "8802",
    # エネルギー
    "ENEOSホールディングス": "5020",
    "出光興産":              "5019",
    # 医薬
    "武田薬品工業":         "4502",
    "アステラス製薬":       "4503",
    "第一三共":             "4568",
    "エーザイ":             "4523",
    "塩野義製薬":           "4507",
    "中外製薬":             "4519",
    # 物流・運輸
    "日本郵船":             "9101",
    "商船三井":             "9104",
    "川崎汽船":             "9107",
    "ヤマトホールディングス": "9064",
    "日本通運":             "9062",
    "ANAホールディングス":  "9202",
    "日本航空（JAL）":      "9201",
    # 鉄鋼・金属
    "日本製鉄":             "5401",
    "JFEホールディングス":  "5411",
    "住友金属鉱山":         "5713",
    # ゲーム・エンタメ
    "任天堂":               "7974",
    "カプコン":             "9697",
    "バンダイナムコ":       "7832",
    "スクウェア・エニックス": "9684",
    "コナミグループ":       "9766",
    # その他
    "リクルートホールディングス": "6098",
    "パーソルホールディングス":   "2181",
    "リクルート":                 "6098",
    "日本電産（ニデック）":       "6594",
    "ダイキン工業":               "6367",
}

# 表示用リスト（「会社名 (コード)」形式）
STOCK_OPTIONS = ["（直接入力）"] + [f"{name}  ({code})" for name, code in STOCK_DICT.items()]

# ─── サイドバー ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 基本設定")

    # 銘柄選択
    st.markdown("**銘柄を選ぶ**")
    search_word = st.text_input("🔍 会社名で絞り込み（例: トヨタ）", value="")

    # 絞り込みフィルター
    if search_word:
        filtered = [f"{name}  ({code})" for name, code in STOCK_DICT.items()
                    if search_word in name]
        filtered = ["（直接入力）"] + filtered if filtered else ["（直接入力）"]
    else:
        filtered = STOCK_OPTIONS

    selected_stock = st.selectbox("銘柄を選択", filtered)

    # コード決定
    if selected_stock == "（直接入力）":
        raw_code = st.text_input("証券コードを直接入力（例: 7203 または 7203.T）", value="7203")
        # .T がついていなければ自動付与
        ticker_input = raw_code.strip()
        if ticker_input and not ticker_input.endswith(".T") and not ticker_input.endswith(".F"):
            ticker_input = ticker_input + ".T"
    else:
        # 「会社名  (コード)」から括弧内のコードを取り出す
        code = selected_stock.split("(")[-1].rstrip(")")
        ticker_input = code.strip() + ".T"
        st.caption(f"使用コード: `{ticker_input}`")

    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("開始日", value=datetime.today() - timedelta(days=365*3))
    with c2:
        end_date = st.date_input("終了日", value=datetime.today())

    commission_pct = st.number_input("手数料（%）", value=0.05, step=0.01, format="%.2f") / 100
    shares         = st.number_input("取引株数", value=100, step=100)

    st.markdown("---")
    st.markdown("### 📡 条件を選ぶ（ANDで組み合わせ）")
    st.caption("チェックした条件がすべて一致した日にのみ買いエントリー")

    st.markdown("**日経平均の方向**")
    use_nk_up   = st.checkbox("☀️ 日経が上がった日",   value=False)
    use_nk_down = st.checkbox("🌧️ 日経が下がった日",   value=False)

    st.markdown("**RSI（売られすぎ指標）**")
    use_rsi = st.checkbox("📉 RSI がしきい値以下", value=False)
    rsi_threshold = st.slider("RSI しきい値", 10, 50, 30, disabled=not use_rsi)

    st.markdown("**移動平均からの乖離**")
    use_ma_dev  = st.checkbox("📊 移動平均から大きく下落", value=False)
    ma_period   = st.slider("移動平均の期間（日）", 5, 50, 25, disabled=not use_ma_dev)
    ma_dev_pct  = st.slider("乖離率（%以上 下落）", 1.0, 10.0, 3.0, step=0.5, disabled=not use_ma_dev)

    st.markdown("**ボリンジャーバンド**")
    use_bband  = st.checkbox("🎯 ボリンジャー下限を下回る", value=False)
    bb_period  = st.slider("ボリンジャー期間", 10, 30, 20, disabled=not use_bband)
    bb_sigma   = st.slider("σ（標準偏差）", 1.0, 3.0, 2.0, step=0.5, disabled=not use_bband)

    st.markdown("**前日の動き**")
    use_prev_down  = st.checkbox("↩️ 前日に大きく下げた翌日", value=False)
    prev_drop_pct  = st.slider("前日下落幅（%以上）", 1.0, 8.0, 3.0, step=0.5, disabled=not use_prev_down)

    st.markdown("**曜日**")
    use_weekday = st.checkbox("📅 特定の曜日だけ", value=False)
    weekday_map = {"月曜日": 0, "火曜日": 1, "水曜日": 2, "木曜日": 3, "金曜日": 4}
    selected_weekdays = st.multiselect("曜日を選択", list(weekday_map.keys()),
                                        default=["月曜日"], disabled=not use_weekday)

    st.markdown("---")
    run_btn = st.button("▶ バックテスト実行", use_container_width=True, type="primary")

# ─── データ取得 ───────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data(ticker, start, end):
    stock = yf.download(ticker,  start=start, end=end, auto_adjust=True, progress=False)
    nk    = yf.download("^N225", start=start, end=end, auto_adjust=True, progress=False)
    nkd   = yf.download("NKD=F", start=start, end=end, auto_adjust=True, progress=False)
    return stock, nk, nkd

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

# ─── シグナル構築 ─────────────────────────────────────────────
def build_combined_signal(stk, nk, nkd, params):
    close    = stk["Close"]
    signal   = pd.Series(True, index=stk.index)
    conditions = []

    # ── 先物シグナル（朝7時前に判定可能） ──────────────────────
    # NKD=F の終値（米国時間 ≒ 日本時間朝6時）を前日の ^N225 終値と比較
    # 日本営業日Dに対して：
    #   nkd_prev[D]  = NKD=F の D-1 終値（日本時間朝6時頃に確定）
    #   n225_prev[D] = ^N225 の D-1 終値（前日15:30に確定）
    nkd_close  = nkd["Close"].reindex(stk.index, method="ffill").shift(1)  # 前日CME終値
    n225_prev  = nk["Close"].reindex(stk.index, method="ffill").shift(1)   # 前日日経終値

    if params["use_nk_up"] and params["use_nk_down"]:
        return None, None, ["⚠️ 「先物が上がった日」と「下がった日」は同時に選べません"]
    if params["use_nk_up"]:
        signal &= (nkd_close > n225_prev).fillna(False)
        conditions.append("☀️ 先物が前日比プラス（朝6時時点）")
    if params["use_nk_down"]:
        signal &= (nkd_close < n225_prev).fillna(False)
        conditions.append("🌧️ 先物が前日比マイナス（朝6時時点）")

    if params["use_rsi"]:
        rsi = compute_rsi(close, 14)
        signal &= (rsi < params["rsi_threshold"]).fillna(False)
        conditions.append(f"📉 RSI {params['rsi_threshold']}以下")

    if params["use_ma_dev"]:
        ma  = close.rolling(params["ma_period"]).mean()
        dev = (close - ma) / ma * 100
        signal &= (dev < -params["ma_dev_pct"]).fillna(False)
        conditions.append(f"📊 {params['ma_period']}日MA から {params['ma_dev_pct']}%以上下落")

    if params["use_bband"]:
        bb_ma  = close.rolling(params["bb_period"]).mean()
        bb_std = close.rolling(params["bb_period"]).std()
        bb_low = bb_ma - params["bb_sigma"] * bb_std
        signal &= (close < bb_low).fillna(False)
        conditions.append(f"🎯 ボリンジャー -{params['bb_sigma']}σ 下抜け")

    if params["use_prev_down"]:
        prev_ret = close.pct_change() * 100
        signal &= (prev_ret.shift(1) < -params["prev_drop_pct"]).fillna(False)
        conditions.append(f"↩️ 前日 -{params['prev_drop_pct']}%以上下落の翌日")

    if params["use_weekday"] and params["selected_weekdays"]:
        dow_nums = [params["weekday_map"][w] for w in params["selected_weekdays"]]
        signal &= pd.Series(stk.index.dayofweek.isin(dow_nums), index=stk.index)
        conditions.append(f"📅 {'・'.join(params['selected_weekdays'])}")

    if not conditions:
        return None, None, ["条件が1つも選ばれていません"]

    return signal, " AND ".join(conditions), conditions

# ─── バックテスト ─────────────────────────────────────────────
def run_backtest(stk, signal, comm, qty):
    open_  = stk["Open"]
    close_ = stk["Close"]
    pnl    = pd.Series(0.0, index=stk.index)
    for d in stk.index[signal]:
        o = open_.get(d)
        c = close_.get(d)
        if o is None or c is None or pd.isna(o) or pd.isna(c) or o == 0:
            continue
        pnl[d] = (c - o) * qty - (o + c) * qty * comm
    return pnl

def calc_stats(pnl):
    active = pnl[pnl != 0]
    wins   = active[active > 0]
    losses = active[active < 0]
    n      = len(active)
    cum    = pnl.cumsum()
    dd     = (cum - cum.cummax()).min()
    pf     = (-wins.sum() / losses.sum()) if losses.sum() != 0 else np.inf
    return {
        "取引日数": n,
        "勝ち":    len(wins),
        "負け":    len(losses),
        "勝率":    len(wins) / n * 100 if n > 0 else 0,
        "合計損益":active.sum(),
        "平均利益":wins.mean()   if len(wins)   > 0 else 0,
        "平均損失":losses.mean() if len(losses) > 0 else 0,
        "PF":      round(pf, 2),
        "最大DD":  dd,
    }

def plot_heatmap(pnl_series):
    # pandas バージョン対応済み
    monthly = pnl_series[pnl_series != 0].resample(MONTH_FREQ).sum()
    if monthly.empty:
        return None
    dfm = monthly.reset_index()
    dfm.columns = ["Date", "pnl"]
    dfm["Year"]  = dfm["Date"].dt.year
    dfm["Month"] = dfm["Date"].dt.month
    years  = sorted(dfm["Year"].unique())
    months = list(range(1, 13))
    mnames = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]

    grid = pd.DataFrame(np.nan, index=years, columns=months)
    for _, row in dfm.iterrows():
        grid.loc[row["Year"], row["Month"]] = row["pnl"]

    text_grid = [[f"¥{grid.loc[y,m]:,.0f}" if not np.isnan(grid.loc[y,m]) else ""
                  for m in months] for y in years]

    fig = go.Figure(go.Heatmap(
        z=grid.values, x=mnames, y=[str(y) for y in years],
        colorscale=[[0,"#fca5a5"],[0.5,"#f5f5ff"],[1,"#86efac"]],
        text=text_grid, texttemplate="%{text}", showscale=True, zmid=0,
        hovertemplate="%{y}年%{x}<br>損益: %{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(color="#1a1a2e", family="Noto Sans JP"),
        height=max(200, 60 * len(years) + 80),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig

# ─── メインエリア ─────────────────────────────────────────────
if run_btn:
    params = dict(
        use_nk_up=use_nk_up, use_nk_down=use_nk_down,
        use_rsi=use_rsi, rsi_threshold=rsi_threshold,
        use_ma_dev=use_ma_dev, ma_period=ma_period, ma_dev_pct=ma_dev_pct,
        use_bband=use_bband, bb_period=bb_period, bb_sigma=bb_sigma,
        use_prev_down=use_prev_down, prev_drop_pct=prev_drop_pct,
        use_weekday=use_weekday, selected_weekdays=selected_weekdays,
        weekday_map=weekday_map,
    )

    with st.spinner("データ取得中..."):
        try:
            stock_df, nk_df, nkd_df = load_data(ticker_input, str(start_date), str(end_date))
        except Exception as e:
            st.error(f"データ取得エラー: {e}"); st.stop()

    if stock_df.empty or nk_df.empty:
        st.error("データが取得できませんでした。銘柄コードや期間を確認してください。"); st.stop()

    stk = flatten(stock_df.copy())
    nk  = flatten(nk_df.copy())
    nkd = flatten(nkd_df.copy()) if not nkd_df.empty else nk

    signal, label, conditions = build_combined_signal(stk, nk, nkd, params)

    if signal is None:
        st.error(conditions[0]); st.stop()

    st.markdown('<div class="section-title">🔍 検証中の条件（AND）</div>', unsafe_allow_html=True)
    tags = "".join([f'<span class="condition-tag">{c}</span>' for c in conditions])
    st.markdown(f'<div class="result-header">{tags}<br><span style="color:#888;font-size:12px">👆 上記の条件がすべて一致した日にのみ「始値で買い・大引けで売り」</span></div>',
                unsafe_allow_html=True)

    entry_count = int(signal.sum())
    if entry_count == 0:
        st.warning("条件に該当する日が1日もありませんでした。条件を緩めてみてください。"); st.stop()

    st.info(f"📅 該当日数: **{entry_count}日** / 全{len(signal)}営業日")

    pnl    = run_backtest(stk, signal, commission_pct, shares)
    s      = calc_stats(pnl)
    active_pnl = pnl[pnl != 0]

    st.markdown('<div class="section-title">🎯 パフォーマンス</div>', unsafe_allow_html=True)
    row1 = st.columns(4)
    row2 = st.columns(4)
    items = [
        ("取引日数",  f"{s['取引日数']}日",              "neutral"),
        ("勝率",      f"{s['勝率']:.1f}%",              "positive" if s["勝率"] >= 50 else "negative"),
        ("勝ち日数",  f"{s['勝ち']}日",                 "positive"),
        ("負け日数",  f"{s['負け']}日",                 "negative"),
        ("合計損益",  f"¥{s['合計損益']:,.0f}",          "positive" if s["合計損益"] >= 0 else "negative"),
        ("平均利益",  f"¥{s['平均利益']:,.0f}",          "positive"),
        ("平均損失",  f"¥{s['平均損失']:,.0f}",          "negative"),
        ("最大DD",    f"¥{s['最大DD']:,.0f}",            "negative"),
    ]
    for cols, batch in [(row1, items[:4]), (row2, items[4:])]:
        for c, (lbl, val, cls) in zip(cols, batch):
            with c:
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-label">{lbl}</div>
                    <div class="metric-value {cls}">{val}</div>
                </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-title">📈 累積損益推移（円）</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=active_pnl.index, y=active_pnl.values, name="日次損益",
        marker_color=["#16a34a" if v >= 0 else "#dc2626" for v in active_pnl.values],
        opacity=0.5,
        hovertemplate="%{x|%Y-%m-%d}<br>損益: ¥%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=active_pnl.index, y=active_pnl.cumsum(), name="累積損益",
        line=dict(color="#4f46e5", width=2.5), yaxis="y2",
        hovertemplate="%{x|%Y-%m-%d}<br>累積: ¥%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#ccc", line_width=1)
    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#f9f9fc",
        font=dict(color="#1a1a2e", family="Noto Sans JP"),
        legend=dict(bgcolor="#fff", bordercolor="#e0e0ec", borderwidth=1),
        xaxis=dict(gridcolor="#ebebf5"),
        yaxis=dict(gridcolor="#ebebf5", tickprefix="¥", tickformat=",.0f", title="日次損益"),
        yaxis2=dict(overlaying="y", side="right", tickprefix="¥", tickformat=",.0f", title="累積損益"),
        height=420, margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">🗓️ 月次損益ヒートマップ</div>', unsafe_allow_html=True)
    fig_hm = plot_heatmap(pnl)
    if fig_hm:
        st.plotly_chart(fig_hm, use_container_width=True)
    else:
        st.info("ヒートマップを表示できるデータが不足しています")

    st.markdown('<div class="section-title">📋 日別トレード一覧</div>', unsafe_allow_html=True)
    table = pd.DataFrame({
        "始値": stk["Open"].reindex(active_pnl.index),
        "終値": stk["Close"].reindex(active_pnl.index),
        "損益": active_pnl,
        "勝敗": active_pnl.apply(lambda v: "✅ 勝ち" if v > 0 else "❌ 負け"),
    })
    table.index = table.index.strftime("%Y-%m-%d")

    styled = table.style.format({
        "始値": "¥{:,.0f}", "終値": "¥{:,.0f}", "損益": "¥{:,.0f}",
    }).applymap(
        lambda v: ("color:#16a34a;font-weight:bold" if isinstance(v,(int,float)) and v > 0
                   else "color:#dc2626;font-weight:bold" if isinstance(v,(int,float)) and v < 0 else ""),
        subset=["損益"]
    )
    st.dataframe(styled, use_container_width=True, height=400)

else:
    st.markdown("""
    <div style="text-align:center; padding:70px 0;">
        <div style="font-size:60px; margin-bottom:16px;">🔬</div>
        <div style="font-size:18px; color:#888; margin-bottom:8px;">左のサイドバーで条件を選んで</div>
        <div style="font-size:24px; color:#4f46e5; font-weight:700;">▶ バックテスト実行</div>
        <div style="font-size:13px; color:#bbb; margin-top:28px; line-height:2.6;">
            会社名で銘柄を検索 ／ 複数の条件を <b style="color:#4f46e5">AND</b> で組み合わせ可能<br>
            例）📉 RSI 30以下　AND　☀️ 日経が上がった日<br>
            例）🎯 ボリンジャー下抜け　AND　↩️ 前日急落翌日
        </div>
    </div>
    """, unsafe_allow_html=True)