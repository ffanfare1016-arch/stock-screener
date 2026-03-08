import streamlit as st
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

st.set_page_config(layout="wide", page_title="買い場スクリーナー｜日本株プライム")

# ===============================
# 主要プライム銘柄リスト（約500件）
# 日経225 + JPX-Nikkei400 主要構成銘柄
# ===============================
PRIME_STOCKS = list(dict.fromkeys([
    "1332","1333","1605","1721","1801","1802","1803","1808","1812","1925",
    "1928","1963","2002","2269","2282","2413","2432","2501","2502","2503",
    "2531","2768","2801","2802","2871","2914","3382","3401","3402","3405",
    "3407","3436","3659","3861","3863","4004","4005","4021","4042","4043",
    "4061","4062","4063","4183","4188","4208","4272","4452","4502","4503",
    "4506","4507","4519","4523","4543","4568","4578","4601","4661","4689",
    "4704","4751","4755","4901","4902","4911","5019","5020","5101","5105",
    "5108","5201","5202","5214","5232","5233","5301","5332","5333","5401",
    "5406","5411","5413","5631","5706","5707","5711","5713","5714","5801",
    "5802","5803","6098","6103","6113","6146","6178","6301","6302","6305",
    "6326","6361","6366","6367","6471","6472","6473","6501","6503","6504",
    "6506","6532","6586","6594","6645","6674","6701","6702","6703","6706",
    "6724","6752","6753","6762","6770","6841","6857","6861","6902","6903",
    "6920","6952","6954","6963","6971","6976","6981","7003","7004","7011",
    "7012","7013","7186","7201","7202","7203","7205","7211","7261","7267",
    "7269","7270","7272","7731","7733","7735","7741","7751","7762","7832",
    "7911","7912","7951","8001","8002","8003","8007","8008","8015","8031",
    "8035","8053","8058","8233","8252","8253","8267","8303","8304","8306",
    "8308","8309","8316","8331","8354","8355","8377","8411","8601","8604",
    "8630","8697","8725","8729","8750","8766","8795","8802","8803","8804",
    "8830","9001","9005","9007","9008","9009","9020","9021","9022","9064",
    "9101","9104","9107","9202","9301","9432","9433","9434","9501","9502",
    "9503","9531","9532","9602","9613","9735","9766","9983","9984",
    "1375","1377","1379","1382","1414","1420","1429","1436","1449","1451",
    "1514","1515","1518","1522","1540","1570","1571","1575","1579","1589",
    "1593","1615","1617","1618","1619","1620","1621","1622","1623","1624",
    "1625","1626","1627","1628","1629","1698","1699","1726","1730","1736",
    "1739","1745","1766","1780","1783","1790","1796","1798","1814","1815",
    "1820","1822","1824","1826","1827","1829","1833","1835","1840","1841",
    "1847","1860","1861","1870","1878","1879","1881","1883","1884","1885",
    "1887","1888","1890","1893","1897","1898","1899","1900","1904","1905",
    "1906","1908","1909","1911","1912","1914","1915","1916","1917","1919",
    "1921","1922","1923","1924","1926","1929","1930","1934","1939","1941",
    "1942","1944","1945","1946","1948","1949","1950","1951","1952","1954",
    "1955","1957","1959","1960","1961","1964","1965","1966","1967","1968",
    "1969","1971","1972","1973","1975","1976","1979","1980","1981","1982",
    "1983","1984","1985","1986","1987","1988","1989","1990","1991","1992",
    "2003","2004","2006","2009","2010","2014","2015","2016","2020","2024",
    "2025","2030","2031","2053","2055","2060","2061","2062","2063","2075",
    "2108","2114","2115","2117","2120","2124","2127","2128","2130","2132",
    "2133","2136","2137","2138","2139","2140","2141","2148","2150","2153",
    "2154","2158","2160","2162","2163","2164","2165","2167","2168","2170",
    "2171","2174","2175","2176","2178","2180","2181","2183","2186","2193",
    "2196","2200","2201","2206","2207","2208","2209","2211","2212","2213",
    "2214","2215","2216","2217","2220","2221","2222","2224","2226","2229",
    "2232","2233","2236","2237","2240","2241","2242","2243","2246","2264",
    "2267","2270","2275","2281","2284","2286","2288","2289","2292","2294",
]))

# ===============================
# テクニカル計算
# ===============================
def compute_indicators(df):
    df = df.copy()
    df["MA_short"] = df["Close"].rolling(25).mean()
    df["MA_long"]  = df["Close"].rolling(75).mean()
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]      = exp1 - exp2
    df["Signal"]    = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["Signal"]
    df["std"]      = df["Close"].rolling(20).std()
    df["BB_upper"] = df["MA_short"] + df["std"] * 2
    df["BB_lower"] = df["MA_short"] - df["std"] * 2
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    df["RSI"] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
    return df

def is_plan_entry(idx, df):
    row = df.loc[idx]
    price, rsi, ma_s = row["Close"], row["RSI"], row["MA_short"]
    hist, bb_low, bb_up = row["MACD_hist"], row["BB_lower"], row["BB_upper"]

    if any(pd.isna(v) for v in [rsi, ma_s, hist, bb_low]):
        return False
    pos = df.index.get_loc(idx)
    if pos < 1:
        return False
    prev_hist = df.iloc[pos - 1]["MACD_hist"]
    if rsi > 78 or price > bb_up:
        return False
    start     = max(0, pos - 15)
    had_panic = (df.iloc[start:pos + 1]["Close"] < df.iloc[start:pos + 1]["BB_lower"]).any()
    return (
        had_panic and
        price > ma_s and
        hist > prev_hist and
        hist > 0 and
        35 <= rsi <= 60
    )

def scan_single(code):
    try:
        ticker = yf.Ticker(f"{code}.T")
        df = ticker.history(period="1y", interval="1d")
        if df.empty or len(df) < 80:
            return None
        df.columns = [c if not isinstance(c, tuple) else c[0] for c in df.columns]
        if df.index.tz is not None:
            df.index = df.index.tz_convert("Asia/Tokyo")

        df = compute_indicators(df).dropna(
            subset=["RSI", "MA_short", "MACD_hist", "BB_lower"]
        )

        # 直近3営業日でシグナル確認
        signal_idx = None
        for idx in reversed(df.index[-3:]):
            if is_plan_entry(idx, df):
                signal_idx = idx
                break
        if signal_idx is None:
            return None

        # 銘柄情報（配当利回り含む）
        info      = ticker.info
        div_yield = info.get("dividendYield") or 0   # None → 0 に統一
        name      = info.get("shortName") or info.get("longName") or code

        row_sig = df.loc[signal_idx]
        latest  = df.iloc[-1]

        return {
            "code":        code,
            "name":        name,
            "yahoo_url": f"https://finance.yahoo.co.jp/quote/{code}.T",
            "signal_date": signal_idx.strftime("%Y/%m/%d"),
            "close":       round(float(latest["Close"]), 1),
            "rsi":         round(float(row_sig["RSI"]), 1),
            "ma_dev":      round(
                (float(latest["Close"]) - float(latest["MA_short"]))
                / float(latest["MA_short"]) * 100, 2
            ),
            "div_yield":   round(div_yield * 100, 2),
        }
    except Exception:
        return None

# ===============================
# サイドバー
# ===============================
st.sidebar.title("🔍 買い場スクリーナー")
st.sidebar.caption(f"対象：主要プライム {len(PRIME_STOCKS)} 銘柄 ／ 日足")
st.sidebar.caption("条件：PLAN_ENTRY（直近3営業日以内）")
st.sidebar.markdown("---")

sort_key = st.sidebar.selectbox(
    "並び替え",
    ["シグナル日（新しい順）", "配当利回り（高い順）", "RSI（低い順）"]
)
max_workers = st.sidebar.slider("並列数（多いほど速い・負荷大）", 5, 20, 10)
run_btn     = st.sidebar.button("🚀 スキャン開始", use_container_width=True)

# ===============================
# メインUI
# ===============================
st.title("📊 買い場シグナル スクリーナー")
st.caption(
    "PLAN_ENTRY（BB・MACD・RSI 複合判定）　｜　"
    "「📊 株探」列をクリックで銘柄詳細ページへ"
)

today_key = datetime.now().strftime("%Y%m%d")
cache_key  = f"results_{today_key}"

if cache_key in st.session_state:
    results  = st.session_state[cache_key]
    cached_t = st.session_state.get(f"time_{today_key}", "")
    st.success(
        f"✅ 本日 {cached_t} のスキャン結果（キャッシュ）を表示中。"
        "再スキャンはサイドバーから。"
    )
    run_btn = False
else:
    results = None

# ===============================
# スキャン実行
# ===============================
if run_btn:
    results, completed_cnt = [], 0
    total = len(PRIME_STOCKS)
    st.info(f"🔄 {total} 銘柄をスキャン中... 初回は1〜2分かかります。")
    progress_bar = st.progress(0)
    status_text  = st.empty()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_single, c): c for c in PRIME_STOCKS}
        for future in as_completed(futures):
            completed_cnt += 1
            progress_bar.progress(completed_cnt / total)
            status_text.caption(f"進捗: {completed_cnt} / {total} 銘柄完了")
            r = future.result()
            if r:
                results.append(r)

    progress_bar.empty()
    status_text.empty()
    now_str = datetime.now().strftime("%H:%M")
    st.session_state[cache_key]            = results
    st.session_state[f"time_{today_key}"]  = now_str
    st.success(f"✅ スキャン完了（{now_str}）｜シグナル検出: {len(results)} 銘柄")

# ===============================
# 結果表示
# ===============================
if results is not None:
    if not results:
        st.warning("現在シグナルが出ている銘柄は見つかりませんでした。")
    else:
        df_r = pd.DataFrame(results)

        # ソート
        if sort_key == "シグナル日（新しい順）":
            df_r = df_r.sort_values("signal_date", ascending=False)
        elif sort_key == "配当利回り（高い順）":
            df_r = df_r.sort_values("div_yield", ascending=False)
        else:
            df_r = df_r.sort_values("rsi", ascending=True)
        df_r = df_r.reset_index(drop=True)
        df_r.index += 1

        st.markdown(f"### 🎯 シグナル銘柄一覧 ｜ {len(df_r)} 件")

        df_show = pd.DataFrame({
            "コード":        df_r["code"],
            "銘柄名":        df_r["name"],
            "YF":   df_r["yahoo_url"],
            "シグナル日":    df_r["signal_date"],
            "現在値":        df_r["close"],
            "RSI":           df_r["rsi"],
            "MA乖離(%)":     df_r["ma_dev"],
            "配当利回り(%)": df_r["div_yield"],
        })

        st.dataframe(
            df_show,
            use_container_width=True,
            height=min(80 + len(df_show) * 35, 650),
            column_config={
                "コード":        st.column_config.TextColumn(width="small"),
                "銘柄名":        st.column_config.TextColumn(width="medium"),
                "YF":   st.column_config.LinkColumn("📈 Yahoo!Finance", width="small"),
                "シグナル日":    st.column_config.TextColumn(width="small"),
                "現在値":        st.column_config.NumberColumn(format="¥%.1f", width="small"),
                "RSI":           st.column_config.NumberColumn(format="%.1f", width="small"),
                "MA乖離(%)":     st.column_config.NumberColumn(format="%.2f%%", width="small"),
                "配当利回り(%)": st.column_config.NumberColumn(format="%.2f%%", width="small"),
            }
        )

        st.markdown("---")
        st.markdown("---")
        st.markdown("**📋 銘柄コード ワンクリックコピー**")
        codes = df_r["code"].tolist()
        names = df_r["name"].tolist()
        cols  = st.columns(5)
        for i, (code, name) in enumerate(zip(codes, names)):
            with cols[i % 5]:
                st.caption(name[:10])   # 銘柄名（長い場合は10文字で切る）
                st.code(code, language=None)  # 右上のアイコンでワンクリックコピー

else:
    st.markdown("""
---
### 使い方
1. サイドバーの **「🚀 スキャン開始」** を押す
2. 初回は **1〜2分** かかります（当日2回目以降はキャッシュで即表示）
3. **「📊 株探」** 列をクリックすると株探の銘柄ページが開きます
4. 「配当利回り（高い順）」に並び替えると高配当×買い場の候補が上位に来ます

---
### PLAN_ENTRY 判定条件
| 条件 | 内容 |
|------|------|
| ① パニック確認 | 直近15日以内に BB -2σ 割れがあること |
| ② 価格回復 | 現在値が短期 MA（25日）を上回っていること |
| ③ MACD 改善 | ヒストグラムがプラスかつ前日比改善 |
| ④ RSI 適正 | RSI が 35〜60 の範囲内 |
| ⑤ 対象期間 | 直近3営業日以内にシグナル発生 |
""")