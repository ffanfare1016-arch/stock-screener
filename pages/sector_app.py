import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 銘柄マスター（コード: 企業名） ---
STOCK_NAMES = {
    "1332.T": "ニッスイ", "1379.T": "ホクト", "1605.T": "INPEX", "1662.T": "石油資源開発",
    "1801.T": "大成建設", "1802.T": "大林組", "1803.T": "清水建設", "2502.T": "アサヒGHD",
    "2503.T": "キリンHD", "2802.T": "味の素", "3402.T": "東レ", "3407.T": "旭化成",
    "3101.T": "東洋紡", "3861.T": "王子HD", "3863.T": "日本製紙", "4063.T": "信越化学",
    "4188.T": "三菱ケミカル", "4911.T": "資生堂", "4502.T": "武田薬品", "4503.T": "アステラス",
    "4568.T": "第一三共", "5020.T": "ENEOS", "5019.T": "出光興産", "5108.T": "ブリヂストン",
    "5110.T": "住友ゴム", "5201.T": "AGC", "5333.T": "日本ガイシ", "5401.T": "日本製鉄",
    "5411.T": "JFE", "5406.T": "神戸鋼", "5713.T": "住友鉱", "5802.T": "住友電工",
    "5901.T": "東洋製罐", "3436.T": "SUMCO", "6103.T": "オークマ", "6301.T": "小松製作所",
    "6367.T": "ダイキン", "6758.T": "ソニーG", "6501.T": "日立", "8035.T": "東京エレク",
    "7203.T": "トヨタ", "7267.T": "ホンダ", "7201.T": "日産", "7741.T": "HOYA",
    "7733.T": "オリンパス", "4543.T": "テルモ", "7974.T": "任天堂", "7912.T": "大日本印刷",
    "9501.T": "東電HD", "9502.T": "中部電力", "9503.T": "関西電力", "9020.T": "JR東日本",
    "9022.T": "JR東海", "9005.T": "東急", "9101.T": "日本郵船", "9104.T": "商船三井",
    "9107.T": "川崎汽船", "9201.T": "JAL", "9202.T": "ANA", "9301.T": "三菱倉庫",
    "9302.T": "三井倉庫", "9432.T": "NTT", "9433.T": "KDDI", "9984.T": "SBG",
    "8001.T": "伊藤忠", "8031.T": "三井物産", "8058.T": "三菱商事", "7453.T": "良品計画",
    "3088.T": "マツキヨ", "9843.T": "ニトリHD", "8306.T": "三菱UFJ", "8316.T": "三井住友",
    "8411.T": "みずほ", "8604.T": "野村HD", "8601.T": "大和証券", "8766.T": "東京海上",
    "8725.T": "MS&AD", "8591.T": "オリックス", "8697.T": "JPX", "8801.T": "三井不動産",
    "8802.T": "三菱地所", "4385.T": "メルカリ", "6098.T": "リクルート", "4661.T": "オリランド"
}

# --- 東証33業種マップ ---
SECTOR_MAP = {
    "水産・農林業": {"idx": "1311.T", "stocks": ["1332.T", "1379.T"]},
    "鉱業": {"idx": "1605.T", "stocks": ["1605.T", "1662.T"]},
    "建設業": {"idx": "1612.T", "stocks": ["1801.T", "1802.T", "1803.T"]},
    "食料品": {"idx": "1611.T", "stocks": ["2502.T", "2503.T", "2802.T"]},
    "繊維製品": {"idx": "1622.T", "stocks": ["3402.T", "3407.T", "3101.T"]},
    "パルプ・紙": {"idx": "3861.T", "stocks": ["3861.T", "3863.T"]},
    "化学": {"idx": "1620.T", "stocks": ["4063.T", "4188.T", "4911.T"]},
    "医薬品": {"idx": "1621.T", "stocks": ["4502.T", "4503.T", "4568.T"]},
    "石油・石炭製品": {"idx": "1630.T", "stocks": ["5020.T", "5019.T"]},
    "ゴム製品": {"idx": "5108.T", "stocks": ["5108.T", "5110.T"]},
    "ガラス・土石製品": {"idx": "1624.T", "stocks": ["5201.T", "5333.T"]},
    "鉄鋼": {"idx": "1614.T", "stocks": ["5401.T", "5411.T", "5406.T"]},
    "非鉄金属": {"idx": "1628.T", "stocks": ["5713.T", "5802.T"]},
    "金属製品": {"idx": "5901.T", "stocks": ["5901.T", "3436.T"]},
    "機械": {"idx": "1625.T", "stocks": ["6103.T", "6301.T", "6367.T"]},
    "電気機器": {"idx": "1613.T", "stocks": ["6758.T", "6501.T", "8035.T"]},
    "輸送用機器": {"idx": "1610.T", "stocks": ["7203.T", "7267.T", "7201.T"]},
    "精密機器": {"idx": "1623.T", "stocks": ["7741.T", "7733.T", "4543.T"]},
    "その他製品": {"idx": "7974.T", "stocks": ["7974.T", "7912.T"]},
    "電気・ガス業": {"idx": "1619.T", "stocks": ["9501.T", "9502.T", "9503.T"]},
    "陸運業": {"idx": "1627.T", "stocks": ["9020.T", "9022.T", "9005.T"]},
    "海運業": {"idx": "1631.T", "stocks": ["9101.T", "9104.T", "9107.T"]},
    "空運業": {"idx": "9201.T", "stocks": ["9201.T", "9202.T"]},
    "倉庫・運輸関連": {"idx": "9301.T", "stocks": ["9301.T", "9302.T"]},
    "情報・通信業": {"idx": "1626.T", "stocks": ["9432.T", "9433.T", "9984.T"]},
    "卸売業": {"idx": "1629.T", "stocks": ["8001.T", "8031.T", "8058.T"]},
    "小売業": {"idx": "1618.T", "stocks": ["7453.T", "3088.T", "9843.T"]},
    "銀行業": {"idx": "1615.T", "stocks": ["8306.T", "8316.T", "8411.T"]},
    "証券・商品先物": {"idx": "1632.T", "stocks": ["8604.T", "8601.T"]},
    "保険業": {"idx": "1616.T", "stocks": ["8766.T", "8725.T"]},
    "その他金融業": {"idx": "8591.T", "stocks": ["8591.T", "8697.T"]},
    "不動産業": {"idx": "1633.T", "stocks": ["8801.T", "8802.T"]},
    "サービス業": {"idx": "1617.T", "stocks": ["4385.T", "6098.T", "4661.T"]},
}

st.set_page_config(page_title="TSE Sector Rotation", layout="wide")

# --- ① シグナル名の説明表 ---
st.title("📊 セクターローテーション解析ツール")

with st.expander("💡 シグナルの見方と判定ロジックについて", expanded=True):
    st.markdown("""
    | シグナル | 意味・示唆 | 判定ロジック（例） |
    | :--- | :--- | :--- |
    | **🚀 本命上昇** | セクター全体に満遍なく買いが入っている「本物」の上昇。 | 業種指数 > +1.5% かつ 中身の騰落率が高い |
    | **⚠️ ハリボテ警戒** | 一部の大型株のみ上昇。指数を吊り上げているだけの状態。 | 業種指数は上昇しているが、中身銘柄の平均が指数の半分以下 |
    | **🔥 加熱警戒** | 短期的に買われすぎ。いつ利確売りが来てもおかしくない。 | 短期的な急騰（当アプリでは指数+3%超えなど） |
    | **📉 出遅れ物色** | 指数には現れないが、セクター内で買いが広がり始めている初期段階。 | 指数は横ばいだが、中身の平均が指数を上回り始めた状態 |
    """)

# --- 解析実行 ---
if st.button('🚀 市場解析を開始する'):
    all_tickers = []
    for s in SECTOR_MAP.values():
        all_tickers.extend([s["idx"]] + s["stocks"])
    all_tickers = list(set(all_tickers))

    with st.spinner('データを取得中...'):
        data = yf.download(all_tickers, period="2d", interval="1d")['Close']
        
        if not data.empty:
            returns = data.pct_change().iloc[-1] * 100
            results = []

            for name, config in SECTOR_MAP.items():
                idx_ret = returns.get(config["idx"], 0)
                stock_rets = [returns.get(s, 0) for s in config["stocks"]]
                avg_stock_ret = sum(stock_rets) / len(stock_rets)
                
                # シグナル判定（簡略化版）
                diff = idx_ret - avg_stock_ret
                if idx_ret > 3.0: signal = "🔥 加熱警戒"
                elif idx_ret > 0.5 and diff > 0.8: signal = "⚠️ ハリボテ警戒"
                elif idx_ret > 1.5 and avg_stock_ret > 1.0: signal = "🚀 本命上昇"
                elif -0.5 < idx_ret < 0.5 and avg_stock_ret > 0.5: signal = "📉 出遅れ物色"
                elif idx_ret < -1.5: signal = "🌑 下落注意"
                else: signal = "-"

                # ② 代表銘柄に企業名を付け、株探リンクを作成
                stock_links = []
                for s_code in config["stocks"]:
                    clean_code = s_code.split('.')[0]
                    name_str = STOCK_NAMES.get(s_code, clean_code)
                    url = f"https://kabutan.jp/stock/?code={clean_code}"
                    # StreamlitのMarkdownリンク形式 [名前](URL)
                    stock_links.append(f"[{name_str}]({url})")

                results.append({
                    "セクター": name,
                    "指数(%)": round(idx_ret, 2),
                    "中身平均(%)": round(avg_stock_ret, 2),
                    "シグナル": signal,
                    "代表銘柄 (クリックで株探へ)": " / ".join(stock_links)
                })

            df_res = pd.DataFrame(results).sort_values("指数(%)", ascending=False)
            
            # テーブル表示（Markdownを有効にするため st.write ではなく column_config を使用）
            st.data_editor(
                df_res,
                column_config={
                    "代表銘柄 (クリックで株探へ)": st.column_config.LinkColumn(
                        "代表銘柄 (株探リンク)",
                        help="クリックすると株探の銘柄ページが開きます"
                    ),
                    "シグナル": st.column_config.TextColumn("シグナル")
                },
                hide_index=True,
                use_container_width=True,
                height=1200
            )
            st.success("解析完了！")