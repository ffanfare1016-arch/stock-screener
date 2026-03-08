import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="朝のコンディション確認", page_icon="🌅", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=JetBrains+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif;
    background-color: #f7f8fc;
    color: #1a1a2e;
}
.stApp { background: #f7f8fc; }

/* ヘッダー */
.header-wrap {
    background: #fff;
    border-bottom: 1px solid #e5e7ef;
    padding: 20px 28px 18px;
    margin: -1rem -1rem 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.header-title { font-size: 22px; font-weight: 700; color: #1a1a2e; }
.header-date  { font-size: 13px; color: #888; }
.header-sub   { font-size: 12px; color: #aaa; margin-top: 2px; }

/* 指標カード */
.ind-card {
    background: #fff;
    border: 1.5px solid #e5e7ef;
    border-radius: 14px;
    padding: 20px 22px 16px;
    margin-bottom: 14px;
}
.ind-card.hit  { border-color: #16a34a; background: #f0fdf4; }
.ind-card.warn { border-color: #d97706; background: #fffbeb; }
.ind-card.miss { border-color: #e5e7ef; background: #fff; }

.ind-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 10px;
}
.ind-name {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #8888aa;
}
.badge {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 12px;
    border-radius: 20px;
    letter-spacing: 0.5px;
}
.badge-hit  { background: #dcfce7; color: #16a34a; border: 1px solid #86efac; }
.badge-miss { background: #f1f5f9; color: #94a3b8; border: 1px solid #e2e8f0; }

.ind-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 36px;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 6px;
}
.col-up     { color: #16a34a; }
.col-down   { color: #dc2626; }
.col-neutral{ color: #2563eb; }
.col-warn   { color: #d97706; }

.ind-meta {
    font-size: 12px;
    color: #888;
    margin-top: 4px;
}
.ind-threshold {
    display: inline-block;
    background: #f1f5f9;
    color: #64748b;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 11px;
    margin-top: 8px;
}

/* 曜日 */
.wd-row { display: flex; gap: 8px; margin-top: 6px; }
.wd-tile {
    flex: 1; text-align: center; padding: 10px 0;
    border-radius: 10px; font-size: 13px; font-weight: 700;
    border: 1.5px solid #e5e7ef; color: #bbb; background: #fafafa;
}
.wd-tile.today {
    background: #eff6ff; border-color: #2563eb; color: #2563eb;
}

/* 総合バナー */
.verdict {
    border-radius: 14px;
    padding: 20px 24px;
    display: flex;
    align-items: center;
    gap: 18px;
    margin-bottom: 24px;
    background: #fff;
    border: 1.5px solid #e5e7ef;
}
.verdict.active { border-color: #16a34a; background: #f0fdf4; }
.verdict-icon { font-size: 36px; }
.verdict-body {}
.verdict-label { font-size: 11px; color: #888; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 4px; }
.verdict-main  { font-size: 20px; font-weight: 700; color: #1a1a2e; }
.verdict-main.active { color: #16a34a; }
.verdict-sub   { font-size: 12px; color: #888; margin-top: 4px; }

/* セクションヘッダ */
.sec-head {
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: #4f46e5;
    padding-bottom: 8px; border-bottom: 2px solid #e5e7ef;
    margin: 24px 0 14px;
}

section[data-testid="stSidebar"] { background: #fff !important; border-right: 1px solid #e5e7ef; }
</style>
""", unsafe_allow_html=True)

WEEKDAY_JP  = ["月", "火", "水", "木", "金", "土", "日"]
today_dt    = datetime.today()
today_wd    = today_dt.weekday()
today_label = today_dt.strftime(f"%Y年%m月%d日（{WEEKDAY_JP[today_wd]}曜日）")

# ─── サイドバー：しきい値設定 ──────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ スクリーナーと同じしきい値を入力")
    st.caption("ここをスクリーナーの設定に合わせると、今日シグナルが出ているかを確認できます")

    rsi_th       = st.slider("📉 RSI しきい値",          10, 50, 30)
    ma_period    = st.slider("📊 移動平均期間（日）",      5, 50, 25)
    ma_dev_th    = st.slider("📊 MA乖離率しきい値（%）",  1.0, 10.0, 3.0, step=0.5)
    prev_drop_th = st.slider("↩️ 前日下落しきい値（%）",  1.0,  8.0, 3.0, step=0.5)

    st.markdown("---")
    refresh = st.button("🔄 データを今すぐ更新", use_container_width=True, type="primary")
    st.caption("データは5分間キャッシュされます")

# ─── データ取得 ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_nikkei():
    end   = datetime.today() + timedelta(days=1)
    start = end - timedelta(days=120)
    nk_raw  = yf.download("^N225", start=str(start.date()), end=str(end.date()),
                           auto_adjust=True, progress=False)
    nkd_raw = yf.download("NKD=F", start=str(start.date()), end=str(end.date()),
                           auto_adjust=True, progress=False)

    def flat(df):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df

    nk  = flat(nk_raw.copy())  if not nk_raw.empty  else pd.DataFrame()
    nkd = flat(nkd_raw.copy()) if not nkd_raw.empty else pd.DataFrame()
    return nk, nkd

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

if refresh:
    st.cache_data.clear()

with st.spinner("日経データ取得中…"):
    try:
        nk, nkd = fetch_nikkei()
        data_ok  = not nk.empty
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        data_ok = False

# ─── ヘッダー ─────────────────────────────────────────────────
last_nk  = float(nk["Close"].iloc[-1]) if data_ok else None
prev_nk  = float(nk["Close"].iloc[-2]) if (data_ok and len(nk) >= 2) else None
nk_chg   = (last_nk - prev_nk) if (last_nk and prev_nk) else None
nk_chg_p = nk_chg / prev_nk * 100 if (nk_chg and prev_nk) else None

if data_ok:
    sign = "+" if nk_chg >= 0 else ""
    col  = "#16a34a" if nk_chg >= 0 else "#dc2626"
    nk_str = f'<span style="font-family:JetBrains Mono,monospace;font-size:20px;font-weight:700;color:{col}">{last_nk:,.2f}　{sign}{nk_chg:,.2f}（{sign}{nk_chg_p:.2f}%）</span>'
else:
    nk_str = "<span style='color:#aaa'>取得失敗</span>"

st.markdown(f"""
<div style="background:#fff;border-bottom:1px solid #e5e7ef;padding:20px 0 16px;margin-bottom:28px">
    <div style="font-size:22px;font-weight:700;color:#1a1a2e;margin-bottom:6px">🌅 朝のコンディション確認</div>
    <div style="font-size:13px;color:#888">{today_label}　|　{nk_str}　<span style="color:#bbb;font-size:11px">（日経225 前日比）</span></div>
</div>
""", unsafe_allow_html=True)

if not data_ok:
    st.warning("データ取得に失敗しました。「データを今すぐ更新」ボタンを押してください。")
    st.stop()

# ─── 各指標の計算 ─────────────────────────────────────────────

# ① 先物 vs N225前日終値
nkd_latest = float(nkd["Close"].iloc[-1]) if not nkd.empty else None
nk_prev    = prev_nk  # N225の前日終値

if nkd_latest and nk_prev:
    fut_diff = nkd_latest - nk_prev
    fut_pct  = fut_diff / nk_prev * 100
    nk_up    = fut_diff > 0
    nk_down  = fut_diff < 0
else:
    fut_diff = fut_pct = None
    nk_up = nk_down = False

# ② 日経RSI
rsi_ser   = compute_rsi(nk["Close"])
rsi_today = float(rsi_ser.dropna().iloc[-1]) if not rsi_ser.dropna().empty else None
rsi_hit   = (rsi_today is not None) and (rsi_today < rsi_th)

# ③ 日経 MA乖離
ma_ser   = nk["Close"].rolling(ma_period).mean()
ma_today = float(ma_ser.dropna().iloc[-1]) if not ma_ser.dropna().empty else None
if ma_today and last_nk:
    ma_dev = (last_nk - ma_today) / ma_today * 100
    ma_hit = ma_dev < -ma_dev_th
else:
    ma_dev = None; ma_hit = False

# ④ 前日（昨日）の日経下落幅
if len(nk) >= 3:
    c_yday    = float(nk["Close"].iloc[-2])
    c_2day    = float(nk["Close"].iloc[-3])
    prev_drop = (c_yday - c_2day) / c_2day * 100
    prev_hit  = prev_drop < -prev_drop_th
else:
    c_yday = c_2day = None
    prev_drop = None; prev_hit = False

# ─── 総合判定 ─────────────────────────────────────────────────
hits = [nk_up or nk_down, rsi_hit, ma_hit, prev_hit]
hit_count = sum(hits)

if hit_count >= 3:
    icon = "🟢"; msg = f"{hit_count}/4 条件が重なっています"; sub = "スクリーナーで強いシグナルが出やすい状態です"; is_active = True
elif hit_count == 2:
    icon = "🟡"; msg = f"{hit_count}/4 条件が重なっています"; sub = "複数条件が一致。対象銘柄を確認してみましょう"; is_active = True
elif hit_count == 1:
    icon = "🔵"; msg = f"{hit_count}/4 条件のみ"; sub = "単一条件のみ一致"; is_active = False
else:
    icon = "⚪"; msg = "0/4 — 現在は該当なし"; sub = "設定したしきい値を満たす条件がありません"; is_active = False

st.markdown(f"""
<div class="verdict {'active' if is_active else ''}">
    <div class="verdict-icon">{icon}</div>
    <div class="verdict-body">
        <div class="verdict-label">総合コンディション</div>
        <div class="verdict-main {'active' if is_active else ''}">{msg}</div>
        <div class="verdict-sub">{sub}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── 指標カード ───────────────────────────────────────────────
st.markdown('<div class="sec-head">📊 各指標の状態（日経225ベース）</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

# ① 先物方向
with col1:
    if fut_diff is not None:
        sign  = "+" if fut_diff >= 0 else ""
        color = "col-up" if fut_diff > 0 else "col-down"
        hit_cls = "hit" if (nk_up or nk_down) else "miss"
        badge_cls = "badge-hit" if (nk_up or nk_down) else "badge-miss"
        direction = "☀️ 先物プラス（上昇）" if nk_up else ("🌧️ 先物マイナス（下落）" if nk_down else "→ フラット")
        st.markdown(f"""
        <div class="ind-card {hit_cls}">
            <div class="ind-top">
                <span class="ind-name">日経先物の方向</span>
                <span class="badge {badge_cls}">{direction}</span>
            </div>
            <div class="ind-value {color}">{sign}{fut_pct:.2f}%</div>
            <div class="ind-meta">先物（NKD=F）: <b>{nkd_latest:,.0f}</b>　／　N225前日終値: <b>{nk_prev:,.0f}</b></div>
            <span class="ind-threshold">差分 {sign}{fut_diff:,.0f} 円</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="ind-card miss"><div class="ind-name">日経先物の方向</div><div class="ind-value col-neutral">N/A</div></div>', unsafe_allow_html=True)

# ② RSI
with col2:
    if rsi_today is not None:
        color = "col-down" if rsi_today < 30 else ("col-warn" if rsi_today < 50 else "col-up")
        hit_cls   = "hit" if rsi_hit else "miss"
        badge_cls = "badge-hit" if rsi_hit else "badge-miss"
        badge_txt = f"✅ {rsi_th}以下（売られすぎ）" if rsi_hit else f"— {rsi_th}超"
        st.markdown(f"""
        <div class="ind-card {hit_cls}">
            <div class="ind-top">
                <span class="ind-name">RSI（14日）</span>
                <span class="badge {badge_cls}">{badge_txt}</span>
            </div>
            <div class="ind-value {color}">{rsi_today:.1f}</div>
            <div class="ind-meta">30以下 → 売られすぎ　／　70以上 → 買われすぎ</div>
            <span class="ind-threshold">しきい値: RSI &lt; {rsi_th}</span>
        </div>
        """, unsafe_allow_html=True)

# ③ MA乖離
with col1:
    if ma_dev is not None:
        sign  = "+" if ma_dev >= 0 else ""
        color = "col-down" if ma_dev < -3 else ("col-warn" if ma_dev < 0 else "col-up")
        hit_cls   = "hit" if ma_hit else "miss"
        badge_cls = "badge-hit" if ma_hit else "badge-miss"
        badge_txt = f"✅ -{ma_dev_th}%以上乖離" if ma_hit else f"— -{ma_dev_th}%未満"
        st.markdown(f"""
        <div class="ind-card {hit_cls}">
            <div class="ind-top">
                <span class="ind-name">{ma_period}日移動平均 乖離率</span>
                <span class="badge {badge_cls}">{badge_txt}</span>
            </div>
            <div class="ind-value {color}">{sign}{ma_dev:.2f}%</div>
            <div class="ind-meta">N225: <b>{last_nk:,.2f}</b>　／　{ma_period}日MA: <b>{ma_today:,.2f}</b></div>
            <span class="ind-threshold">しきい値: 乖離率 &lt; -{ma_dev_th}%</span>
        </div>
        """, unsafe_allow_html=True)

# ④ 前日下落幅
with col2:
    if prev_drop is not None:
        sign  = "+" if prev_drop >= 0 else ""
        color = "col-down" if prev_drop < -3 else ("col-warn" if prev_drop < 0 else "col-up")
        hit_cls   = "hit" if prev_hit else "miss"
        badge_cls = "badge-hit" if prev_hit else "badge-miss"
        badge_txt = f"✅ -{prev_drop_th}%以上下落" if prev_hit else f"— -{prev_drop_th}%未満"
        st.markdown(f"""
        <div class="ind-card {hit_cls}">
            <div class="ind-top">
                <span class="ind-name">前日（昨日）の日経下落幅</span>
                <span class="badge {badge_cls}">{badge_txt}</span>
            </div>
            <div class="ind-value {color}">{sign}{prev_drop:.2f}%</div>
            <div class="ind-meta">昨日終値: <b>{c_yday:,.2f}</b>　／　一昨日終値: <b>{c_2day:,.2f}</b></div>
            <span class="ind-threshold">しきい値: 前日変化率 &lt; -{prev_drop_th}%</span>
        </div>
        """, unsafe_allow_html=True)

# ─── 曜日 ─────────────────────────────────────────────────────
st.markdown('<div class="sec-head">📅 今日の曜日</div>', unsafe_allow_html=True)
tiles = "".join([
    f'<div class="wd-tile {"today" if i == today_wd else ""}">{d}曜日</div>'
    for i, d in enumerate(["月", "火", "水", "木", "金"])
])
st.markdown(f'<div class="wd-row">{tiles}</div>', unsafe_allow_html=True)
st.markdown(f'<div style="font-size:12px;color:#aaa;margin-top:8px">スクリーナーで曜日フィルタを使う場合の参考</div>', unsafe_allow_html=True)

# ─── フッター ─────────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:32px;padding-top:14px;border-top:1px solid #e5e7ef;
            display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:11px;color:#bbb">
        データソース: Yahoo Finance（^N225、NKD=F）
    </div>
    <div style="font-size:11px;color:#bbb">
        最終更新: {datetime.now().strftime("%H:%M:%S")}　／　5分間キャッシュ
    </div>
</div>
""", unsafe_allow_html=True)