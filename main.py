import streamlit as st

st.title('書き出し用アプリ')
st.caption('銘柄に関連する勝率を算出するツールです。')

st.write('**使い方**')
st.markdown(
    '<p style="line-height: 1.5;">'
    '①朝7時までにスクリーナーをかける<br>'
    '②個別分析で勝率を出す<br>'
    '</p>',
    unsafe_allow_html=True
)