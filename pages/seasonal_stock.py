import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="季節性株価分析ツール", layout="wide")

st.title("季節性株価分析ツール 📈")
st.markdown("指定した日本株銘柄の過去10年分の株価データの「月次平均」を算出し、年ごとに重ね合わせて季節性を分析するためのチャートを表示します。")

# サイドバーに入力を配置
st.sidebar.header("検索設定")
stock_code_input = st.sidebar.text_input("銘柄コードを入力 (例: 7203)", "7203")

if stock_code_input:
    # 四桁の数字であれば日本株とみなし、.T を付与
    if stock_code_input.isdigit() and len(stock_code_input) == 4:
        symbol = f"{stock_code_input}.T"
    else:
        symbol = stock_code_input
    
    with st.spinner(f"{symbol} の株価データを取得中..."):
        try:
            ticker = yf.Ticker(symbol)
            
            # 企業名を取得して表示
            info = ticker.info
            company_name = info.get('longName') or info.get('shortName') or '企業名称不明'
            st.write(f"### 対象銘柄: {symbol} - {company_name}")
            
            # 過去10年の日足データを取得
            hist = ticker.history(period="10y")
            
            if hist.empty:
                st.error("株価データが取得できませんでした。銘柄コードが正しいか確認してください。")
            else:
                # タイムゾーン情報を削除して扱いやすくする
                df = hist[['Close']].copy()
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                
                # 月次平均を集計
                df['Year'] = df.index.year
                df['Month'] = df.index.month
                monthly_avg = df.groupby(['Year', 'Month'])['Close'].mean().reset_index()
                
                # Plotlyでインタラクティブなチャートを作成
                fig = go.Figure()
                
                years = monthly_avg['Year'].unique()
                latest_year_in_data = years[-1]
                
                # 各年ごとの折れ線を描画
                for year in years:
                    year_data = monthly_avg[monthly_avg['Year'] == year]
                    
                    # 最新年は太線で強調して描画
                    is_latest = (year == latest_year_in_data)
                    line_width = 4 if is_latest else 1.5
                    opacity = 1.0 if is_latest else 0.5
                    
                    fig.add_trace(go.Scatter(
                        x=year_data['Month'],
                        y=year_data['Close'],
                        mode='lines+markers' if is_latest else 'lines',
                        name=f"{year}年",
                        line=dict(width=line_width),
                        opacity=opacity,
                        hovertemplate='月: %{x}月<br>平均株価: %{y:,.1f}円<extra></extra>'
                    ))
                
                # ------ 権利落ち日（配当月）の推測と描画 ------
                actions = ticker.actions
                freq_months = []
                if not actions.empty and 'Dividends' in actions.columns:
                    dividends = actions[actions['Dividends'] > 0]
                    if not dividends.empty:
                        # 過去の配当実績から月を抽出
                        if dividends.index.tz is not None:
                            div_months = dividends.index.tz_localize(None).month
                        else:
                            div_months = dividends.index.month
                        
                        # 頻出する月をカウント
                        month_counts = pd.Series(div_months).value_counts()
                        # 全体のデータ年数に対して一定割合以上（ここでは30%以上）配当が出ている月を「定例の権利月」と推測する
                        num_years = len(years)
                        freq_months = month_counts[month_counts >= (num_years * 0.3)].index.tolist()
                
                # 推定された配当権利月に「権利落ち注意」の垂直破線を引く
                # （日本株の場合、権利確定月の末日付近で権利落ちとなるため、対象月の位置に線を引く）
                for m in freq_months:
                    fig.add_vline(x=m, line_dash="dash", line_color="red", 
                                  annotation_text="権利落ち注意", annotation_position="top left",
                                  opacity=0.7)
                
                # ------ グラフの全体レイアウト設定 ------
                fig.update_layout(
                    title=f"【{symbol}】の季節性チャート推移（過去10年）",
                    xaxis_title="月",
                    yaxis_title="月次平均 株価 (円)",
                    xaxis=dict(
                        tickmode='array',
                        tickvals=list(range(1, 13)),
                        ticktext=[f"{i}月" for i in range(1, 13)]
                    ),
                    hovermode="x unified",
                    legend_title="年",
                    height=600,
                    margin=dict(l=40, r=40, t=60, b=40)
                )
                
                # UIへチャートを描画
                st.plotly_chart(fig, use_container_width=True)
                
                # 権利月情報のアナウンス
                if freq_months:
                    st.info(f"💡 yfinanceの過去の配当実績から自動判定した結果、主に **{', '.join(map(str, sorted(freq_months)))}月** に配当が行われ、権利落ちが発生する傾向があります。")
                else:
                    st.write("定例の配当月を特定できませんでした（無配銘柄または直近の配当データ不足の可能性があります）。")
                    
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
