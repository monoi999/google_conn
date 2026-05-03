

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import json
import gspread
from datetime import datetime
from gspread_dataframe import set_with_dataframe

# 1. Google Sheets 연결 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (캐시를 사용하지 않아야 실시간 반영 확인 가능)
# Use spreadsheet URL from secrets when available to avoid `Spreadsheet must be specified` error
default_sheet_url = st.secrets.get("spreadsheet_url", "") if st.secrets else ""
if default_sheet_url:
    try:
        df = conn.read(spreadsheet=default_sheet_url, ttl=0)
    except Exception as e:
        st.warning(f"스프레드시트 읽기 실패: {e}")
        df = pd.DataFrame()
else:
    df = pd.DataFrame()

st.title("Google Sheets 데이터 관리")

# 디버깅
st.write("sheet URL:", default_sheet_url)
st.write("service account email:", json.loads(st.secrets["gcp_service_account"])["client_email"])


# 3. 데이터 표시 및 수정 (st.data_editor 사용)
st.subheader("데이터 수정 및 삭제")
st.write("표에서 직접 수정하거나, 행을 선택해 Del 키로 삭제할 수 있습니다.")
edited_df = st.data_editor(df, num_rows="dynamic", width='stretch', key="data_editor")



# 4. 변경사항 저장 버튼
if st.button("Google Sheets에 최종 저장"):
    # Prefer authenticated service-account write when available
    sa = st.secrets.get("gcp_service_account") if st.secrets else None
    if sa:
        try:
            sa_dict = json.loads(sa) if isinstance(sa, str) else sa
            client = gspread.service_account_from_dict(sa_dict)
            sheet_url_to_use = default_sheet_url
            sh = client.open_by_url(sheet_url_to_use)
            sheet_name = st.secrets.get("sheet_name", sh.sheet1.title) if st.secrets else sh.sheet1.title
            try:
                ws = sh.worksheet(sheet_name)
            except Exception:
                ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            ws.clear()
            set_with_dataframe(ws, edited_df, include_index=False, include_column_header=True)
            st.success("저장 성공")
        except Exception as e:
            st.error("저장 실패: " + str(e))
    else:
        try:
            conn.update(data=edited_df)
            st.success("저장 성공")
        except Exception as e:
            st.error("저장 실패: " + str(e))


