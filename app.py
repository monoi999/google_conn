import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json
import gspread
from datetime import datetime

# 1. Google Sheets 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (캐시를 사용하지 않아야 실시간 반영 확인 가능)
df = conn.read(ttl=0) 

st.title("Google Sheets 데이터 관리")

# --- 서비스 계정으로 간단 쓰기 테스트 (최소 검증용) ---
default_sheet_url = st.secrets.get("spreadsheet_url", "") if st.secrets else ""
test_sheet_url = st.text_input("테스트용 스프레드시트 URL", value=default_sheet_url)
if st.button("서비스계정으로 쓰기 테스트"):
    sa = st.secrets.get("gcp_service_account") if st.secrets else None
    if not sa:
        st.error("`gcp_service_account`가 Streamlit Secrets에 없습니다.")
    elif not test_sheet_url:
        st.error("테스트할 스프레드시트 URL을 입력하세요.")
    else:
        try:
            sa_dict = json.loads(sa) if isinstance(sa, str) else sa
            client = gspread.service_account_from_dict(sa_dict)
            sh = client.open_by_url(test_sheet_url)
            try:
                ws = sh.sheet1
            except Exception:
                ws = sh.worksheet("Sheet1")
            # append a single test row
            ws.append_row(["streamlit_test_write", datetime.now().isoformat()])
            st.success("서비스계정으로 쓰기 성공: 시트에 테스트 행을 추가했습니다.")
        except Exception as e:
            st.error(f"서비스계정 쓰기 테스트 실패: {e}")

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
