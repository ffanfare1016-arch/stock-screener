import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

st.set_page_config(layout="wide", page_title="感情の罠・実戦診断")

# ===============================
# サイドバーUI
# ===============================
st.sidebar.title("📈 心理分析・日本株")
code = st.sidebar.text_input("銘柄コード（4桁）", value="7203")

interval_label = st.sidebar.radio(
    "足種選択",
    ["1分足", "3分足", "5分足", "日足", "週足", "月足"]
)

interval_map = {
    "1分足":  ("1m",  "7d"),
    "3分足":  ("3m",  "7d"),
    "5分足":  ("5m",  "5d"),
    "日足":   ("1d",  "1y"),
    "週足":   ("1wk", "2y"),
    "月足":   ("1mo", "5y"),
}
interval, period = interval_map[interval_label]
ticker_symbol = f"{code}.T"
is_intraday = interval_label in ["1分足", "3分足", "5分足"]

# --- 自動更新設定 ---
st.sidebar.markdown("---")
st.sidebar.markdown("**🔄 自動更新**")
auto_refresh = st.sidebar.checkbox("自動更新を有効にする", value=False)

refresh_interval_map = {
    "1分足":  60,
    "3分足":  90,
    "5分足":  120,
    "日足":   600,
    "週足":   1800,
    "月足":   3600,
}
refresh_sec = refresh_interval_map[interval_label]

if auto_refresh:
    st.sidebar.caption(f"⏱ {refresh_sec}秒ごとに更新")

# ===============================
# 🔔 通知設定（サイドバー）
# ===============================
st.sidebar.markdown("---")
st.sidebar.markdown("**🔔 シグナル通知設定**")
notify_plan_entry = st.sidebar.checkbox("💎 PLAN_ENTRY で通知", value=True)
notify_take_profit = st.sidebar.checkbox("🔴 TAKE_PROFIT で通知", value=False)
notify_trend_break = st.sidebar.checkbox("🟠 TREND_BREAK で通知", value=False)
notify_sound = st.sidebar.checkbox("🔊 サウンドアラートも鳴らす", value=True)

# ===============================
# TTL設定（足種ごとに最適化）
# ===============================
ttl_map = {
    "1分足":  55,
    "3分足":  85,
    "5分足":  115,
    "日足":   600,
    "週足":   1800,
    "月足":   3600,
}

@st.cache_data(ttl=ttl_map[interval_label])
def load_data(symbol, iv, pd_, _cache_buster):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=pd_, interval=iv)
    df.columns = [col if not isinstance(col, tuple) else col[0] for col in df.columns]
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("Asia/Tokyo")
    return df

@st.cache_data(ttl=3600)
def get_company_name(symbol):
    try:
        t = yf.Ticker(symbol)
        return t.info.get("longName") or t.info.get("shortName") or symbol
    except:
        return symbol

cache_buster = int(time.time() / ttl_map[interval_label])

df = load_data(ticker_symbol, interval, period, cache_buster)
company_name = get_company_name(ticker_symbol)

if df.empty:
    st.error("データが取得できませんでした。銘柄コードを確認してください。")
    st.stop()

# ===============================
# テクニカル計算
# ===============================
short_ma_len = 13 if interval_label in ["週足", "月足"] else 25
long_ma_len  = 26 if interval_label in ["週足", "月足"] else 75

df["MA_short"] = df["Close"].rolling(short_ma_len).mean()
df["MA_long"]  = df["Close"].rolling(long_ma_len).mean()

exp1 = df["Close"].ewm(span=12, adjust=False).mean()
exp2 = df["Close"].ewm(span=26, adjust=False).mean()
df["MACD"]      = exp1 - exp2
df["Signal"]    = df["MACD"].ewm(span=9, adjust=False).mean()
df["MACD_hist"] = df["MACD"] - df["Signal"]

df["std"]      = df["Close"].rolling(window=20).std()
df["BB_upper"] = df["MA_short"] + df["std"] * 2
df["BB_lower"] = df["MA_short"] - df["std"] * 2
df["Vol_avg"]  = df["Volume"].rolling(20).mean()

delta = df["Close"].diff()
gain  = delta.clip(lower=0)
loss  = -delta.clip(upper=0)
df["RSI"]    = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
df["MA_dev"] = (df["Close"] - df["MA_short"]) / df["MA_short"]
recent_high  = df["High"].rolling(window=20).max()

# ===============================
# 表示期間フィルタリング
# ===============================
if interval_label in ["1分足", "5分足"]:
    last_day   = df.index[-1].date()
    df_display = df[df.index.date == last_day].copy()
elif interval_label == "3分足":
    last_day   = df.index[-1].date()
    df_display = df[df.index.date == last_day].copy()
else:
    df_display = df.tail(100).copy()

# ===============================
# 足種別パラメータ定義
# ===============================
if interval_label in ["1分足", "5分足"]:
    TF = dict(
        tp_rsi=68,  tp_use_or=True,  tp_vol=1.3, tp_hist_pos=False,
        tb_ma_pct=0.9975, tb_rsi=55, tb_hist_neg=False,
        tb_cross_window=3, tp_cross_window=3, panic_rsi=30,
    )
elif interval_label == "3分足":
    TF = dict(
        tp_rsi=72,  tp_use_or=False, tp_vol=1.4, tp_hist_pos=False,
        tb_ma_pct=0.994,  tb_rsi=50, tb_hist_neg=False,
        tb_cross_window=4, tp_cross_window=4, panic_rsi=28,
    )
else:
    TF = dict(
        tp_rsi=75,  tp_use_or=False, tp_vol=1.4, tp_hist_pos=True,
        tb_ma_pct=0.992,  tb_rsi=50, tb_hist_neg=False,
        tb_cross_window=3, tp_cross_window=3, panic_rsi=32,
    )

# ===============================
# 心理診断ロジック
# ===============================
def diagnose_psychology(idx, full_df, high_20_series):
    row     = full_df.loc[idx]
    price   = row["Close"]
    rsi     = row["RSI"]
    ma_s    = row["MA_short"]
    hist    = row["MACD_hist"]
    bb_low  = row["BB_lower"]
    bb_up   = row["BB_upper"]
    vol     = row["Volume"]
    vol_avg = row["Vol_avg"]

    cur_pos   = full_df.index.get_loc(idx)
    prev_pos  = cur_pos - 1
    prev_hist = full_df.iloc[prev_pos]["MACD_hist"] if prev_pos >= 0 else 0

    w_tb = TF["tb_cross_window"]
    w_tp = TF["tp_cross_window"]
    prev_slice_tb = full_df.iloc[max(0, cur_pos - w_tb): cur_pos]
    prev_slice_tp = full_df.iloc[max(0, cur_pos - w_tp): cur_pos]
    just_broke_below_ma = (prev_slice_tb["Close"] > prev_slice_tb["MA_short"]).any()
    just_broke_above_bb = (prev_slice_tp["Close"] < prev_slice_tp["BB_upper"]).any()

    tp_hot = (rsi > TF["tp_rsi"] or price > bb_up) if TF["tp_use_or"] \
             else (rsi > TF["tp_rsi"] and price > bb_up)
    tp_hist_ok = (hist > 0 and hist < prev_hist) if TF["tp_hist_pos"] \
                 else (hist < prev_hist)
    if tp_hot and vol > vol_avg * TF["tp_vol"] and tp_hist_ok and just_broke_above_bb:
        return "TAKE_PROFIT", "#FF2D2D"

    tb_hist_ok = (hist < 0 and hist < prev_hist) if TF["tb_hist_neg"] \
                 else (hist < prev_hist)
    if (price < ma_s * TF["tb_ma_pct"] and tb_hist_ok
            and rsi < TF["tb_rsi"] and just_broke_below_ma):
        return "TREND_BREAK", "#FF8C00"

    if rsi > 78 or price > bb_up:
        return "GREED", "#FF4B4B"

    if price < bb_low and (rsi < TF["panic_rsi"] or vol > vol_avg * 1.5):
        return "PANIC", "#1C83E1"

    start_pos = max(0, cur_pos - 15)
    recent_data = full_df.iloc[start_pos:cur_pos + 1]
    had_panic   = (recent_data["Close"] < recent_data["BB_lower"]).any()

    if (had_panic and price > ma_s and
            hist > prev_hist and hist > 0 and 35 <= rsi <= 60):
        return "PLAN_ENTRY", "#00C781"

    if price >= high_20_series.loc[idx] * 0.97 and 45 < rsi < 65:
        return "FEAR", "#FFA500"

    return "NEUTRAL", "#808495"

df_display["psych_status"] = [
    diagnose_psychology(idx, df, recent_high)[0] for idx in df_display.index
]

latest_idx    = df.index[-1]
status, color = diagnose_psychology(latest_idx, df, recent_high)
latest        = df.iloc[-1]

action_map = {
    "TAKE_PROFIT": ("🔴 利確・売り強推奨",  "天井でMACDが失速。欲が出る場面こそ売り時。"),
    "TREND_BREAK": ("🟠 損切り・撤退検討",  "上昇シナリオ崩壊。「まだ戻る」は最大の罠。"),
    "GREED":       ("🚨 売り・利確検討",    "大衆が熱狂。利益があるなら確定を。"),
    "PANIC":       ("🛒 打診買い検討",      "投げ売り発生。逆張りの好機。"),
    "PLAN_ENTRY":  ("💎 積極買い",          "【青丸】嵐が去った後の反転ポイント。"),
    "FEAR":        ("✊ 継続保有",          "同値撤退の誘惑。ここはホールド。"),
    "NEUTRAL":     ("☕ 様子見",            "指標は中央圏。次のPLAN ENTRYを待機。"),
}
action, msg = action_map[status]

delay_note = {
    "1分足":  "⚠️ Yahoo Finance 約15〜20分遅延",
    "3分足":  "⚠️ Yahoo Finance 約15〜20分遅延",
    "5分足":  "⚠️ Yahoo Finance 約15〜20分遅延",
    "日足":   "✅ 当日終値（引け後更新）",
    "週足":   "✅ 当日終値（引け後更新）",
    "月足":   "✅ 当日終値（引け後更新）",
}

# ===============================
# 🔔 通知ロジック
# ===============================
# session_state で「前回通知したステータス」を記憶
# → ステータスが変化した瞬間だけ通知（毎リフレッシュで連打しない）
if "last_notified_status" not in st.session_state:
    st.session_state.last_notified_status = None
if "last_notified_ticker" not in st.session_state:
    st.session_state.last_notified_ticker = None

notify_target = (status in ["PLAN_ENTRY", "TAKE_PROFIT", "TREND_BREAK"])
status_just_changed = (
    status != st.session_state.last_notified_status or
    ticker_symbol != st.session_state.last_notified_ticker
)

should_notify = (
    notify_target and
    status_just_changed and
    (
        (status == "PLAN_ENTRY"  and notify_plan_entry)  or
        (status == "TAKE_PROFIT" and notify_take_profit) or
        (status == "TREND_BREAK" and notify_trend_break)
    )
)

if should_notify:
    st.session_state.last_notified_status = status
    st.session_state.last_notified_ticker = ticker_symbol

# シグナル別の通知メッセージ
notify_messages = {
    "PLAN_ENTRY":  {"title": "💎 ローリスクエントリー！",   "body": f"{company_name}({code}) に PLAN_ENTRY シグナルが出ました！反転ポイントの可能性あり。"},
    "TAKE_PROFIT": {"title": "🔴 利確タイミング！",          "body": f"{company_name}({code}) に TAKE_PROFIT シグナルが出ました！天井圏でMACDが失速中。"},
    "TREND_BREAK": {"title": "🟠 トレンド崩壊警告！",        "body": f"{company_name}({code}) に TREND_BREAK シグナルが出ました！上昇シナリオ崩壊の可能性。"},
}

# ブラウザ通知＋サウンドを HTML コンポーネントで発火
if should_notify:
    notif = notify_messages[status]
    sound_js = """
    // Web Audio API で「ピコン」系のアラート音を生成
    (function() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const freqs  = [880, 1100, 1320];
            const delays = [0, 0.15, 0.30];
            freqs.forEach((freq, i) => {
                const osc  = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, ctx.currentTime + delays[i]);
                gain.gain.setValueAtTime(0.4, ctx.currentTime + delays[i]);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delays[i] + 0.3);
                osc.start(ctx.currentTime + delays[i]);
                osc.stop(ctx.currentTime + delays[i] + 0.35);
            });
        } catch(e) { console.warn('AudioContext error:', e); }
    })();
    """ if notify_sound else ""

    components.html(f"""
    <script>
    (function() {{
        const title = {repr(notif['title'])};
        const body  = {repr(notif['body'])};

        // --- ブラウザ通知 ---
        function sendNotification() {{
            try {{
                new Notification(title, {{
                    body: body,
                    icon: "https://cdn-icons-png.flaticon.com/512/1828/1828884.png"
                }});
            }} catch(e) {{ console.warn('Notification error:', e); }}
        }}

        if (!("Notification" in window)) {{
            console.warn("このブラウザはデスクトップ通知に非対応です");
        }} else if (Notification.permission === "granted") {{
            sendNotification();
        }} else if (Notification.permission !== "denied") {{
            Notification.requestPermission().then(function(permission) {{
                if (permission === "granted") sendNotification();
            }});
        }}

        // --- サウンドアラート ---
        {sound_js}
    }})();
    </script>
    """, height=0)

# ===============================
# UI表示
# ===============================
st.subheader(f"🔍 {company_name} ({code})")

# シグナル発火時に画面上にも目立つバナーを表示
if should_notify:
    banner_colors = {
        "PLAN_ENTRY":  ("#00C781", "💎 PLAN_ENTRY シグナル発生！積極買いのタイミングです。"),
        "TAKE_PROFIT": ("#FF2D2D", "🔴 TAKE_PROFIT シグナル発生！利確を検討してください。"),
        "TREND_BREAK": ("#FF8C00", "🟠 TREND_BREAK シグナル発生！損切り・撤退を検討してください。"),
    }
    bc, bm = banner_colors[status]
    st.markdown(
        f"""
        <div style="
            background-color:{bc}22;
            border:2px solid {bc};
            border-radius:10px;
            padding:14px 20px;
            margin-bottom:12px;
            font-size:17px;
            font-weight:bold;
            color:{bc};
            animation: blink 1s step-start 0s 3;
        ">
            🔔 {bm}
        </div>
        <style>
        @keyframes blink {{
            50% {{ opacity: 0; }}
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

col_status, col_action, col_info = st.columns([1, 1, 1])
with col_status:
    st.markdown(
        f"<p style='margin-bottom:0;font-size:14px;color:#808495;'>🧠 現在の状態</p>"
        f"<h3 style='color:{color};margin-top:0;'>{status}</h3>",
        unsafe_allow_html=True
    )
with col_action:
    st.markdown(
        f"<p style='margin-bottom:0;font-size:14px;color:#808495;'>⚖️ 売買アドバイス</p>"
        f"<span style='color:white;background-color:{color};padding:3px 12px;"
        f"border-radius:6px;font-weight:bold;font-size:18px;'>{action}</span>",
        unsafe_allow_html=True
    )
with col_info:
    now_str = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f"<p style='margin-bottom:0;font-size:14px;color:#808495;'>📡 データ状況</p>"
        f"<p style='margin-top:4px;font-size:13px;color:#e0e0e0;'>"
        f"{delay_note[interval_label]}<br>🕐 画面更新: {now_str}</p>",
        unsafe_allow_html=True
    )

st.caption(
    f"**分析結果:** {msg} "
    f"(RSI:{latest.RSI:.1f} / 乖離:{latest.MA_dev*100:.1f}%)"
)

# ===============================
# チャート描画
# ===============================
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True,
    vertical_spacing=0.04, row_heights=[0.75, 0.25]
)

x_labels = (
    df_display.index.strftime("%m/%d %H:%M")
    if is_intraday else
    df_display.index.strftime("%Y/%m/%d")
)

fig.add_trace(go.Candlestick(
    x=x_labels,
    open=df_display["Open"], high=df_display["High"],
    low=df_display["Low"],   close=df_display["Close"],
    name="株価"
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=x_labels, y=df_display["MA_short"],
    line=dict(color="orange", width=1.5), name="短期MA"
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=x_labels, y=df_display["MA_long"],
    line=dict(color="purple", width=1.5), name="長期MA"
), row=1, col=1)

plan_entries = df_display[df_display["psych_status"] == "PLAN_ENTRY"]
if not plan_entries.empty:
    plan_x = (
        plan_entries.index.strftime("%m/%d %H:%M")
        if is_intraday else
        plan_entries.index.strftime("%Y/%m/%d")
    )
    fig.add_trace(go.Scatter(
        x=plan_x, y=plan_entries["Low"] * 0.998,
        mode="markers",
        marker=dict(color="#00C781", size=10, symbol="circle"),
        name="Low Risk Entry ▲"
    ), row=1, col=1)

take_profits = df_display[df_display["psych_status"] == "TAKE_PROFIT"]
if not take_profits.empty:
    tp_x = (
        take_profits.index.strftime("%m/%d %H:%M")
        if is_intraday else
        take_profits.index.strftime("%Y/%m/%d")
    )
    fig.add_trace(go.Scatter(
        x=tp_x, y=take_profits["High"] * 1.002,
        mode="markers",
        marker=dict(color="#FF2D2D", size=11, symbol="triangle-down"),
        name="Take Profit ▼"
    ), row=1, col=1)

trend_breaks = df_display[df_display["psych_status"] == "TREND_BREAK"]
if not trend_breaks.empty:
    tb_x = (
        trend_breaks.index.strftime("%m/%d %H:%M")
        if is_intraday else
        trend_breaks.index.strftime("%Y/%m/%d")
    )
    fig.add_trace(go.Scatter(
        x=tb_x, y=trend_breaks["High"] * 1.002,
        mode="markers",
        marker=dict(color="#FF8C00", size=11, symbol="triangle-down"),
        name="Trend Break ▼"
    ), row=1, col=1)

fig.add_trace(go.Scatter(
    x=x_labels, y=df_display["RSI"],
    line=dict(color="white", width=1.5), name="RSI"
), row=2, col=1)
fig.add_hline(y=75, line_dash="dash", line_color="#FF2D2D",  line_width=1.5, row=2, col=1)
fig.add_hline(y=70, line_dash="dot",  line_color="#FF4B4B",  line_width=1,   row=2, col=1)
fig.add_hline(y=30, line_dash="dash", line_color="#1C83E1",  line_width=1.5, row=2, col=1)

fig.add_annotation(
    x=x_labels[-1], y=latest.Close,
    text=f" {status} ", showarrow=True,
    arrowhead=2, arrowcolor=color, bgcolor=color,
    font=dict(color="white", size=12),
    ax=-50, ay=-30, row=1, col=1
)

fig.update_xaxes(type="category", nticks=10, tickangle=0)
fig.update_layout(
    height=650,
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    template="plotly_dark",
    margin=dict(t=10, b=10, l=10, r=10)
)

st.plotly_chart(fig, use_container_width=True)

# ===============================
# シグナル凡例
# ===============================
with st.expander("📖 シグナル説明"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🔴 売りシグナル")
        st.markdown("""
| マーカー | 状態 | 条件 |
|---|---|---|
| 赤▼ | **TAKE_PROFIT** | RSI>75 or BB超え ＋ MACD失速 ＋ 出来高増 |
| 橙▼ | **TREND_BREAK** | MA割れ ＋ MACD下向き ＋ RSI<50 |
""")
    with col2:
        st.markdown("#### 🟢 買いシグナル")
        st.markdown("""
| マーカー | 状態 | 条件 |
|---|---|---|
| 緑〇 | **PLAN_ENTRY** | 直近15本以内にPANIC発生 ＋ MA上回る ＋ MACDヒスト正値で上向き ＋ RSI 35〜60 |
| 青  | **PANIC** | BB下限割れ ＋ RSI売られすぎ（足種別閾値）または 出来高20日平均の1.5倍超 |
""")

with st.expander("🔔 通知について"):
    st.markdown("""
**ブラウザ通知の許可が必要です：**
1. 初回シグナル発火時にブラウザが「通知を許可しますか？」と聞いてきます
2. **「許可する」** をクリックしてください
3. 以降はシグナルが出るたびにデスクトップ通知 ＋ アラート音が鳴ります

> ⚠️ **自動更新と組み合わせると最も効果的です。**  
> サイドバーの「自動更新を有効にする」をオンにすると、  
> 定期的にデータを再取得してシグナルを監視し続けます。

**通知対象シグナルはサイドバーで個別にON/OFF可能です。**
""")

# ===============================
# 自動更新カウントダウン
# ===============================
if auto_refresh:
    progress_bar   = st.progress(0)
    countdown_text = st.empty()
    for i in range(refresh_sec):
        progress_bar.progress((i + 1) / refresh_sec)
        countdown_text.caption(f"🔄 次の更新まで {refresh_sec - i - 1} 秒...")
        time.sleep(1)
    countdown_text.empty()
    progress_bar.empty()
    st.rerun()