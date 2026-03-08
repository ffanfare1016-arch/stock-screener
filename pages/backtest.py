import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date

st.set_page_config(layout="wide", page_title="バックテスト｜シグナル検証")

# ===============================
# テクニカル計算
# ===============================
def compute_indicators(df):
    df = df.copy()
    # 既存MA
    df["MA_short"] = df["Close"].rolling(25).mean()
    df["MA_long"]  = df["Close"].rolling(75).mean()
    # 順張り用 超短期MA（9本）
    df["MA_fast"]  = df["Close"].rolling(9).mean()

    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]      = exp1 - exp2
    df["Signal"]    = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["Signal"]

    df["std"]      = df["Close"].rolling(20).std()
    df["BB_upper"] = df["MA_short"] + df["std"] * 2
    df["BB_lower"] = df["MA_short"] - df["std"] * 2
    df["Vol_avg"]  = df["Volume"].rolling(20).mean()

    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    df["RSI"] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    return df

# ===============================
# 足種別パラメータ
# ===============================
TF_PARAMS = {
    "1分足": dict(
        tp_rsi=68, tp_use_or=True,  tp_vol=1.3, tp_hist_pos=False,
        tb_ma_pct=0.9975, tb_rsi=55, tb_hist_neg=False,
        tb_cross_window=3, tp_cross_window=3, panic_rsi=30,
    ),
    "日足": dict(
        tp_rsi=75, tp_use_or=False, tp_vol=1.4, tp_hist_pos=True,
        tb_ma_pct=0.992,  tb_rsi=50, tb_hist_neg=False,
        tb_cross_window=3, tp_cross_window=3, panic_rsi=32,
    ),
}

# ===============================
# シグナル判定
# ===============================
def get_signal(idx, df, TF):
    row     = df.loc[idx]
    price   = row["Close"]
    rsi     = row["RSI"]
    ma_s    = row["MA_short"]
    ma_fast = row["MA_fast"]
    hist    = row["MACD_hist"]
    bb_low  = row["BB_lower"]
    bb_up   = row["BB_upper"]
    vol     = row["Volume"]
    vol_avg = row["Vol_avg"]

    if any(pd.isna(v) for v in [rsi, ma_s, ma_fast, hist, bb_low, bb_up, vol_avg]):
        return "OTHER"

    cur_pos   = df.index.get_loc(idx)
    prev_pos  = cur_pos - 1
    if prev_pos < 0:
        return "OTHER"
    prev_hist    = df.iloc[prev_pos]["MACD_hist"]
    prev_ma_fast = df.iloc[prev_pos]["MA_fast"]
    prev_ma_s    = df.iloc[prev_pos]["MA_short"]
    prev_rsi     = df.iloc[prev_pos]["RSI"]

    # ---- 売りシグナル ----
    w_tb = TF["tb_cross_window"]
    w_tp = TF["tp_cross_window"]
    prev_slice_tb = df.iloc[max(0, cur_pos - w_tb): cur_pos]
    prev_slice_tp = df.iloc[max(0, cur_pos - w_tp): cur_pos]

    just_broke_below_ma = (
        (prev_slice_tb["Close"] > prev_slice_tb["MA_short"]).any()
        if len(prev_slice_tb) > 0 else False
    )
    just_broke_above_bb = (
        (prev_slice_tp["Close"] < prev_slice_tp["BB_upper"]).any()
        if len(prev_slice_tp) > 0 else False
    )

    tp_hot     = (rsi > TF["tp_rsi"] or price > bb_up) if TF["tp_use_or"] \
                 else (rsi > TF["tp_rsi"] and price > bb_up)
    tp_hist_ok = (hist > 0 and hist < prev_hist) if TF["tp_hist_pos"] \
                 else (hist < prev_hist)
    if tp_hot and vol > vol_avg * TF["tp_vol"] and tp_hist_ok and just_broke_above_bb:
        return "TAKE_PROFIT"

    tb_hist_ok = (hist < 0 and hist < prev_hist) if TF["tb_hist_neg"] \
                 else (hist < prev_hist)
    if (price < ma_s * TF["tb_ma_pct"] and tb_hist_ok
            and rsi < TF["tb_rsi"] and just_broke_below_ma):
        return "TREND_BREAK"

    if rsi > 78 or price > bb_up:
        return "GREED"

    # ---- 買いシグナル（逆張り） ----
    if price < bb_low and (rsi < TF["panic_rsi"] or vol > vol_avg * 1.5):
        return "PANIC"

    start_pos   = max(0, cur_pos - 15)
    recent_data = df.iloc[start_pos: cur_pos + 1]
    had_panic   = (recent_data["Close"] < recent_data["BB_lower"]).any()
    if (had_panic and price > ma_s and
            hist > prev_hist and hist > 0 and 35 <= rsi <= 60):
        return "PLAN_ENTRY"

    # ---- 買いシグナル（順張り）: TREND_FOLLOW ----
    #
    # 条件①: 9MA が 25MA を「今まさに」下から上抜け（ゴールデンクロス）
    #         前足では 9MA < 25MA、今足では 9MA > 25MA
    gc_just_crossed = (prev_ma_fast < prev_ma_s) and (ma_fast > ma_s)
    #
    # 条件②: MACDヒストグラムがプラスで上向き（勢い継続）
    macd_rising = (hist > 0) and (hist > prev_hist)
    #
    # 条件③: RSIが50〜68（上昇モメンタム・過熱前）
    rsi_ok = 50 <= rsi <= 68
    #
    # 条件④: 出来高が20本平均の1.1倍超（動意あり）
    vol_ok = vol > vol_avg * 1.1
    #
    if gc_just_crossed and macd_rising and rsi_ok and vol_ok:
        return "TREND_FOLLOW"

    return "OTHER"

# ===============================
# バックテスト本体
# ===============================
def run_backtest(df, buy_signals, sell_signals, TF, is_intraday,
                 target_dates=None):
    df = df.copy()
    df["sig"] = [get_signal(idx, df, TF) for idx in df.index]

    if target_dates is not None:
        df_bt = df[[d in target_dates for d in df.index.date]].copy()
    else:
        df_bt = df.copy()

    trades      = []
    in_position = False
    buy_price = buy_date = buy_idx = buy_sig = None
    indices = list(df_bt.index)

    dt_fmt    = "%m/%d %H:%M" if is_intraday else "%Y/%m/%d"
    hold_unit = "分" if is_intraday else "日"

    for i, idx in enumerate(indices):
        row    = df_bt.loc[idx]
        sig    = row["sig"]
        next_i = i + 1

        # 1分足：日付をまたいだら強制決済
        if is_intraday and in_position:
            if idx.date() != buy_date.date():
                sell_price = row["Open"]
                actual_pnl = (sell_price - buy_price) / buy_price * 100
                hold_min   = int((idx - buy_date).total_seconds() / 60)
                trades.append(_make_trade(
                    buy_sig, buy_date, buy_price,
                    "日跨ぎ強制決済", idx, sell_price,
                    actual_pnl, hold_min, dt_fmt, hold_unit
                ))
                in_position = False
                buy_price   = None

        if not in_position:
            if sig in buy_signals and next_i < len(indices):
                next_idx  = indices[next_i]
                buy_price = df_bt.loc[next_idx, "Open"]
                buy_date  = next_idx
                buy_idx   = next_i
                buy_sig   = sig
                in_position = True
        else:
            if sig in sell_signals and next_i < len(indices):
                next_idx   = indices[next_i]
                sell_price = df_bt.loc[next_idx, "Open"]
                sell_date  = next_idx
                actual_pnl = (sell_price - buy_price) / buy_price * 100
                hold_val   = int((sell_date - buy_date).total_seconds() / 60) \
                             if is_intraday else (sell_date - buy_date).days
                trades.append(_make_trade(
                    buy_sig, buy_date, buy_price,
                    sig, sell_date, sell_price,
                    actual_pnl, hold_val, dt_fmt, hold_unit
                ))
                in_position = False
                buy_price   = None

        if i == len(indices) - 1 and in_position:
            current_price = row["Close"]
            actual_pnl    = (current_price - buy_price) / buy_price * 100
            hold_val = int((idx - buy_date).total_seconds() / 60) \
                       if is_intraday else (idx - buy_date).days
            trades.append(_make_trade(
                buy_sig, buy_date, buy_price,
                "保有中", idx, current_price,
                actual_pnl, hold_val, dt_fmt, hold_unit,
                holding=True
            ))

    return trades, df_bt

def _make_trade(buy_sig, buy_date, buy_price,
                sell_sig, sell_date, sell_price,
                pnl, hold_val, dt_fmt, hold_unit, holding=False):
    return {
        "買いシグナル":  buy_sig,
        "買い日時":      buy_date.strftime(dt_fmt),
        "買値":          round(buy_price, 1),
        "売りシグナル":  sell_sig if not holding else "保有中",
        "売り日時":      sell_date.strftime(dt_fmt) if not holding else "保有中",
        "売値":          round(sell_price, 1),
        "損益(%)":       round(pnl, 2),
        "損益(円)":      round((sell_price - buy_price) * 100, 0),
        f"保有{hold_unit}数": hold_val,
    }

# ===============================
# チャート描画
# ===============================
def build_chart(df_bt, trades, ticker_label, is_intraday):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.75, 0.25]
    )
    x_fmt = "%m/%d %H:%M" if is_intraday else "%Y/%m/%d"
    x = df_bt.index.strftime(x_fmt)

    fig.add_trace(go.Candlestick(
        x=x, open=df_bt["Open"], high=df_bt["High"],
        low=df_bt["Low"], close=df_bt["Close"], name="株価"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df_bt["MA_fast"],
        line=dict(color="cyan", width=1.0, dash="dot"), name="9MA(順張り)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df_bt["MA_short"],
        line=dict(color="orange", width=1.2), name="25MA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df_bt["MA_long"],
        line=dict(color="purple", width=1.2), name="75MA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df_bt["BB_upper"],
        line=dict(color="gray", width=0.8, dash="dot"),
        name="BB+2σ", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=df_bt["BB_lower"],
        line=dict(color="gray", width=0.8, dash="dot"),
        name="BB-2σ", fill="tonexty",
        fillcolor="rgba(128,128,128,0.05)"), row=1, col=1)

    buy_col  = "買い日時"
    sell_col = "売り日時"

    # シグナル別マーカー色
    buy_colors = {
        "PANIC":        "#1C83E1",   # 青
        "PLAN_ENTRY":   "#00C781",   # 緑
        "TREND_FOLLOW": "#FFD700",   # 金色（順張り専用）
    }

    for t in trades:
        pnl   = t["損益(%)"]
        pcol  = "#00C781" if pnl >= 0 else "#FF4B4B"
        bcol  = buy_colors.get(t["買いシグナル"], "#00FF88")
        fig.add_trace(go.Scatter(
            x=[t[buy_col]], y=[t["買値"] * 0.993],
            mode="markers+text",
            marker=dict(symbol="triangle-up", size=14, color=bcol,
                        line=dict(color="white", width=1)),
            text=[t["買いシグナル"]], textposition="bottom center",
            textfont=dict(size=8, color=bcol), showlegend=False
        ), row=1, col=1)
        if t[sell_col] != "保有中":
            fig.add_trace(go.Scatter(
                x=[t[sell_col]], y=[t["売値"] * 1.007],
                mode="markers+text",
                marker=dict(symbol="triangle-down", size=14, color=pcol,
                            line=dict(color="white", width=1)),
                text=[f"{'+' if pnl >= 0 else ''}{pnl:.1f}%"],
                textposition="top center",
                textfont=dict(size=9, color=pcol), showlegend=False
            ), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=df_bt["RSI"],
        line=dict(color="white", width=1.2), name="RSI"), row=2, col=1)
    fig.add_hline(y=68, line_dash="dot",  line_color="#FFD700",  line_width=1,   row=2, col=1)
    fig.add_hline(y=75, line_dash="dash", line_color="#FF2D2D",  line_width=1.5, row=2, col=1)
    fig.add_hline(y=50, line_dash="dot",  line_color="#FFD700",  line_width=1,   row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#1C83E1",  line_width=1,   row=2, col=1)

    nticks = 30 if is_intraday else 12
    fig.update_xaxes(type="category", nticks=nticks, tickangle=-45)
    fig.update_layout(
        height=640,
        title=dict(text=ticker_label, font=dict(size=16)),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(t=40, b=10, l=10, r=10),
        legend=dict(orientation="h", y=1.02)
    )
    return fig

# ===============================
# サイドバー
# ===============================
st.sidebar.title("⚙️ バックテスト設定")
code = st.sidebar.text_input("銘柄コード（4桁）", value="7203")

st.sidebar.markdown("**📊 足種**")
interval_label = st.sidebar.radio("足種選択", ["日足", "1分足"])
is_intraday = (interval_label == "1分足")

st.sidebar.markdown("**📅 分析期間**")

if is_intraday:
    st.sidebar.caption("⚠️ yFinance の1分足は直近7営業日のみ取得可能です")
    available_days = [(date.today() - timedelta(days=i)) for i in range(7, 0, -1)]
    available_days = [d for d in available_days if d.weekday() < 5]
    day_labels     = [d.strftime("%m/%d(%a)") for d in available_days]
    selected_labels = st.sidebar.multiselect(
        "分析する日を選択（複数可）",
        options=day_labels,
        default=day_labels[-1:],
    )
    selected_dates = {
        available_days[day_labels.index(l)] for l in selected_labels
    }
else:
    default_end   = date.today()
    default_start = default_end - timedelta(days=365)
    start_date = st.sidebar.date_input("開始日", value=default_start)
    end_date   = st.sidebar.date_input("終了日", value=default_end)

st.sidebar.markdown("**🟢 買いシグナル（複数選択可）**")
use_panic        = st.sidebar.checkbox("🛒 PANIC（投げ売り逆張り）",       value=False)
use_plan_entry   = st.sidebar.checkbox("💎 PLAN_ENTRY（反転確認・逆張り）", value=False)
use_trend_follow = st.sidebar.checkbox("🚀 TREND_FOLLOW（ゴールデンクロス順張り）", value=True)

st.sidebar.markdown("**🔴 売りシグナル（複数選択可）**")
use_take_profit = st.sidebar.checkbox("🔴 TAKE_PROFIT（天井利確）",    value=True)
use_trend_break = st.sidebar.checkbox("🟠 TREND_BREAK（シナリオ崩壊）", value=True)
use_greed       = st.sidebar.checkbox("🚨 GREED（過熱・中立寄り）",     value=True)

run_btn = st.sidebar.button("▶️ バックテスト実行", use_container_width=True)

# ===============================
# メインUI
# ===============================
st.title("📉 シグナル バックテスト")
exec_note = "翌足の始値で執行" if is_intraday else "翌営業日始値で執行"
st.caption(f"買いシグナルで買い → 売りシグナルで売る　|　現物・1ポジション・100株　|　{exec_note}")

# TREND_FOLLOW の条件説明を常時表示
with st.expander("🚀 TREND_FOLLOW（順張り）シグナルの条件", expanded=False):
    st.markdown("""
| # | 指標 | 条件 | 意味 |
|---|---|---|---|
| ① | **9MA vs 25MA** | 前足：9MA ＜ 25MA → 今足：9MA ＞ 25MA | ゴールデンクロス（上昇転換の初動） |
| ② | **MACDヒスト** | プラスかつ前足より拡大 | 上昇モメンタムが継続中 |
| ③ | **RSI** | 50〜68の範囲内 | 上昇の勢いあり・過熱はしていない |
| ④ | **出来高** | 20本平均の1.1倍超 | 動意を伴っている |

> **全4条件が同時に成立した足の翌足始値でエントリー**
> チャート上では **金色（🟡）の▲マーカー** で表示されます。
> RSIパネルの **金色の点線（50・68）** が目安ラインです。

**HyperSBI2での目視確認ポイント：**
- 9MA（水色点線）が25MA（オレンジ）を下から上抜け
- MACDヒストグラムがゼロ超えで棒が伸びている
- RSIが50を越えて上向き
- ローソク足の出来高棒が直近より太い
""")

if run_btn:
    buy_signals  = []
    sell_signals = []
    if use_panic:        buy_signals.append("PANIC")
    if use_plan_entry:   buy_signals.append("PLAN_ENTRY")
    if use_trend_follow: buy_signals.append("TREND_FOLLOW")
    if use_take_profit:  sell_signals.append("TAKE_PROFIT")
    if use_trend_break:  sell_signals.append("TREND_BREAK")
    if use_greed:        sell_signals.append("GREED")

    if not buy_signals:
        st.error("買いシグナルを1つ以上選択してください。"); st.stop()
    if not sell_signals:
        st.error("売りシグナルを1つ以上選択してください。"); st.stop()

    if is_intraday:
        if not selected_dates:
            st.error("分析する日を1日以上選択してください。"); st.stop()
    else:
        if start_date >= end_date:
            st.error("開始日は終了日より前にしてください。"); st.stop()

    TF = TF_PARAMS[interval_label]

    with st.spinner("データ取得・シグナル計算中..."):
        ticker = yf.Ticker(f"{code}.T")

        if is_intraday:
            df_raw = ticker.history(period="7d", interval="1m")
        else:
            fetch_start = start_date - timedelta(days=120)
            df_raw = ticker.history(
                start=fetch_start.strftime("%Y-%m-%d"),
                end=(end_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                interval="1d"
            )

        if df_raw.empty:
            st.error("データが取得できませんでした。銘柄コードを確認してください。"); st.stop()

        df_raw.columns = [c if not isinstance(c, tuple) else c[0] for c in df_raw.columns]
        if hasattr(df_raw.index, "tz") and df_raw.index.tz is not None:
            df_raw.index = df_raw.index.tz_convert("Asia/Tokyo")

        df_full      = compute_indicators(df_raw).dropna(subset=["RSI", "MA_short", "MA_fast", "MACD_hist"])
        name         = ticker.info.get("shortName") or ticker.info.get("longName") or code
        ticker_label = f"{name}（{code}）"

    if is_intraday:
        trades, df_bt = run_backtest(
            df_full, buy_signals, sell_signals, TF,
            is_intraday=True, target_dates=selected_dates
        )
    else:
        trades, df_bt = run_backtest(
            df_full, buy_signals, sell_signals, TF,
            is_intraday=False,
            target_dates=set(pd.date_range(start_date, end_date).date)
        )

    st.subheader(f"🔍 {ticker_label}　[{interval_label}]")
    buy_label  = " / ".join(buy_signals)
    sell_label = " / ".join(sell_signals)
    st.info(f"**買い：** {buy_label}　　**売り：** {sell_label}")

    if is_intraday:
        date_str = "、".join(sorted(d.strftime("%m/%d") for d in selected_dates))
        st.caption(f"📅 対象日：{date_str}　|　⚠️ 日をまたいだポジションは最終足で強制決済")

    # ===============================
    # サマリー
    # ===============================
    hold_col  = "保有分数" if is_intraday else "保有日数"
    completed = [t for t in trades if t["売り日時"] != "保有中"]
    wins      = [t for t in completed if t["損益(%)"] > 0]
    losses    = [t for t in completed if t["損益(%)"] <= 0]
    total_pnl = sum(t["損益(%)"] for t in completed)
    win_rate  = len(wins) / len(completed) * 100 if completed else 0
    avg_hold  = sum(t.get(hold_col, 0) for t in completed) / len(completed) if completed else 0
    avg_win   = sum(t["損益(%)"] for t in wins)   / len(wins)   if wins   else 0
    avg_loss  = sum(t["損益(%)"] for t in losses) / len(losses) if losses else 0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1: st.metric("総トレード数", f"{len(completed)} 回")
    with col2: st.metric("勝率",         f"{win_rate:.1f}%", delta=f"{len(wins)}勝{len(losses)}敗")
    with col3: st.metric("累計損益",      f"{total_pnl:+.1f}%")
    with col4: st.metric("平均利益",      f"{avg_win:+.1f}%")
    with col5: st.metric("平均損失",      f"{avg_loss:+.1f}%")
    with col6:
        hold_label = "平均保有分" if is_intraday else "平均保有日数"
        hold_unit  = "分" if is_intraday else "日"
        st.metric(hold_label, f"{avg_hold:.0f} {hold_unit}")

    st.markdown("---")
    st.markdown("#### 💴 100株で取引した場合の損益")
    total_yen   = sum(t["損益(円)"] for t in completed)
    avg_win_yen = sum(t["損益(円)"] for t in wins)   / len(wins)   if wins   else 0
    avg_los_yen = sum(t["損益(円)"] for t in losses) / len(losses) if losses else 0
    ca, cb, cc  = st.columns(3)
    with ca: st.metric("累計損益（円）", f"¥{total_yen:+,.0f}")
    with cb: st.metric("平均利益（円）", f"¥{avg_win_yen:+,.0f}")
    with cc: st.metric("平均損失（円）", f"¥{avg_los_yen:+,.0f}")
    st.markdown("---")

    if any(t["売り日時"] == "保有中" for t in trades):
        st.info("💡 期間終了時点で保有中のポジションがあります（累計損益・円換算から除外）")

    # ===============================
    # チャート
    # ===============================
    fig = build_chart(df_bt, trades, ticker_label, is_intraday)
    st.plotly_chart(fig, use_container_width=True)

    # ===============================
    # トレード履歴
    # ===============================
    if trades:
        st.markdown("### 📋 トレード履歴")
        df_trades = pd.DataFrame([{k: v for k, v in t.items()} for t in trades])
        df_trades.index += 1

        def color_row(row):
            styles = [""] * len(row)
            for col_name in ["損益(%)", "損益(円)"]:
                if col_name in df_trades.columns:
                    ci  = df_trades.columns.get_loc(col_name)
                    val = row.iloc[ci]
                    if isinstance(val, (int, float)):
                        styles[ci] = f"color: {'#00C781' if val > 0 else '#FF4B4B'}; font-weight: bold"
            return styles

        styled = df_trades.style.apply(color_row, axis=1)
        st.dataframe(styled, use_container_width=True, height=min(80 + len(df_trades) * 35, 500))
    else:
        st.warning("指定期間内に売買シグナルが発生しませんでした。期間を広げるか別銘柄をお試しください。")

    # ===============================
    # 損益分布グラフ
    # ===============================
    if completed:
        st.markdown("### 📊 損益分布（100株・円）")
        yen_values = [t["損益(円)"] for t in completed]
        bar_colors = ["#00C781" if p > 0 else "#FF4B4B" for p in yen_values]
        bar_labels = [
            f"{t['買い日時']}→{t['売り日時']}　({t['買いシグナル']}→{t['売りシグナル']})"
            for t in completed
        ]
        fig_bar = go.Figure(go.Bar(
            x=list(range(1, len(yen_values) + 1)),
            y=yen_values, marker_color=bar_colors,
            text=[f"¥{p:+,.0f}" for p in yen_values],
            textposition="outside",
            customdata=bar_labels,
            hovertemplate="%{customdata}<br>損益: ¥%{y:+,.0f}<extra></extra>"
        ))
        fig_bar.add_hline(y=0, line_color="white", line_width=1)
        fig_bar.update_layout(
            template="plotly_dark", height=300,
            xaxis_title="トレード番号", yaxis_title="損益（円）",
            margin=dict(t=10, b=30, l=10, r=10), showlegend=False
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # シグナル別集計
        st.markdown("### 🔬 シグナル別パフォーマンス")
        combo_stats = {}
        for t in completed:
            key = f"{t['買いシグナル']} → {t['売りシグナル']}"
            if key not in combo_stats:
                combo_stats[key] = {"回数": 0, "勝ち": 0, "累計(%)": 0.0}
            combo_stats[key]["回数"]    += 1
            combo_stats[key]["累計(%)"] += t["損益(%)"]
            if t["損益(%)"] > 0:
                combo_stats[key]["勝ち"] += 1
        rows = []
        for combo, s in combo_stats.items():
            rows.append({
                "売買パターン":  combo,
                "回数":          s["回数"],
                "勝率":          f"{s['勝ち']/s['回数']*100:.0f}%",
                "累計損益(%)":  f"{s['累計(%)']:+.1f}%",
                "平均損益(%)":  f"{s['累計(%)']/s['回数']:+.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

else:
    st.markdown("""
---
### 使い方
1. サイドバーで **足種・銘柄コード・期間・シグナル** を設定
2. **「▶️ バックテスト実行」** を押す

---
### 対応足種
| 足種 | データ期間 | 執行タイミング |
|--|--|--|
| 📅 日足 | 最大数年 | シグナル翌営業日の始値 |
| 🕐 1分足 | 直近7営業日 | シグナル翌足の始値 |

> 1分足は日をまたいだポジションをその日の最終足で強制決済します。

---
### 売買シグナル一覧

| シグナル | 種別 | 概要 |
|--|--|--|
| 🚀 **TREND_FOLLOW** | **買い（順張り）** | **9MAが25MAを上抜け（GC）＋MACD上向き＋RSI50〜68＋出来高増** |
| 🛒 PANIC | 買い（逆張り） | BB割れ＋売られすぎ |
| 💎 PLAN_ENTRY | 買い（逆張り） | パニック後の反転確認 |
| 🔴 TAKE_PROFIT | 売り | 天井圏でMACDが失速 |
| 🟠 TREND_BREAK | 売り | MA割れでシナリオ崩壊 |
| 🚨 GREED | 売り | RSI>78 or BB超え（過熱警戒） |
""")