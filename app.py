import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Google Sheets 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (캐시를 사용하지 않아야 실시간 반영 확인 가능)
df = conn.read(ttl=0) 

st.title("Google Sheets 데이터 관리")

# 3. 데이터 표시 및 수정 (st.data_editor 사용)
st.subheader("데이터 수정 및 삭제")
st.write("표에서 직접 수정하거나, 행을 선택해 Del 키로 삭제할 수 있습니다.")
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# 4. 변경사항 저장 버튼
if st.button("Google Sheets에 최종 저장"):
    try:
        # 변경된 데이터프레임을 구글 시트에 덮어쓰기
        conn.update(data=edited_df)
        st.success("시트가 성공적으로 업데이트되었습니다!")
        st.balloons()
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {e}")

# 5. 최신 데이터 확인
if st.checkbox("원본 데이터 보기"):
    st.dataframe(conn.read(ttl=0))
