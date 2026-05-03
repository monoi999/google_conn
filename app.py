import json
from pathlib import Path

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

import gspread_helpers as gh


DATA_PATH = Path(__file__).with_name("score.csv")


st.set_page_config(page_title="구글시트 연동 예제", layout="wide")
st.title("Google Sheets 연동 데이터 편집")

# Optional overrides (defaults can come from st.secrets)
default_sheet_url = st.secrets.get("spreadsheet_url", "") if st.secrets else ""
spreadsheet_url = st.text_input("스프레드시트 URL", value=default_sheet_url)
sheet_name = st.text_input("시트 이름", value="Sheet1")

# Try to create a GSheets connection (used for convenient read/update when configured)
conn = None
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    conn = None


def load_df():
    if conn is not None:
        try:
            return conn.read(ttl=0)
        except Exception:
            pass
    try:
        return pd.read_csv(DATA_PATH, encoding="cp949")
    except Exception:
        return pd.DataFrame()


df = load_df()

st.subheader("데이터 편집 (테이블)")
st.write("표에서 직접 수정하거나, 행을 추가/삭제할 수 있습니다.")
edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("최종 저장", key="save_final"):
        sa = st.secrets.get("gcp_service_account") if st.secrets else None
        # If service account provided in secrets, prefer it for authenticated write
        if sa:
            try:
                client = gh.client_from_service_account_dict(sa)
                sh = client.open_by_url(spreadsheet_url)
                try:
                    ws = sh.worksheet(sheet_name)
                except Exception:
                    ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")

                gh.df_to_worksheet(ws, edited_df, clear=True)
                st.success("구글시트에 정상적으로 저장되었습니다.")
                st.balloons()
            except Exception as e:
                err = str(e)
                st.error(f"구글시트 저장 중 오류: {err}")
                if "Public Spreadsheet cannot be written to" in err or "cannot be written to" in err:
                    st.info(
                        "문제 원인: 공개(Anyone with link) 시트는 쓰기가 제한됩니다.\n"
                        "해결: 스프레드시트 소유자가 서비스 계정 이메일을 편집자로 추가하세요."
                    )
                if st.button("로컬 CSV로 저장 (대체)", key="fallback_after_sa_err"):
                    try:
                        edited_df.to_csv(DATA_PATH, index=False, encoding="cp949")
                        st.success(f"로컬 CSV로 저장되었습니다: {DATA_PATH}")
                    except Exception as e2:
                        st.error(f"로컬 저장 실패: {e2}")
        else:
            # No service account in secrets: try Streamlit GSheets connection if available
            if conn is not None:
                try:
                    conn.update(data=edited_df)
                    st.success("Streamlit GSheets 연결로 저장되었습니다.")
                except Exception as e:
                    st.error(f"저장 실패(연결 사용): {e}")
                    if st.button("로컬 CSV로 저장 (대체)", key="fallback_after_conn_err"):
                        try:
                            edited_df.to_csv(DATA_PATH, index=False, encoding="cp949")
                            st.success(f"로컬 CSV로 저장되었습니다: {DATA_PATH}")
                        except Exception as e2:
                            st.error(f"로컬 저장 실패: {e2}")
            else:
                st.error("서비스 계정 정보가 없습니다. Streamlit Secrets에 'gcp_service_account'를 설정하거나 Streamlit Connections에 GSheets를 구성하세요.")
                if st.button("로컬 CSV로 저장 (대체)", key="fallback_no_auth"):
                    try:
                        edited_df.to_csv(DATA_PATH, index=False, encoding="cp949")
                        st.success(f"로컬 CSV로 저장되었습니다: {DATA_PATH}")
                    except Exception as e2:
                        st.error(f"로컬 저장 실패: {e2}")
with col2:
    if st.button("로컬 CSV로 저장", key="local_save_button"):
        try:
            edited_df.to_csv(DATA_PATH, index=False, encoding="cp949")
            st.success(f"로컬 CSV로 저장되었습니다: {DATA_PATH}")
        except Exception as e:
            st.error(f"로컬 저장 실패: {e}")

st.divider()
if st.checkbox("원본 데이터 다시 불러오기 (실시간)"):
    st.dataframe(load_df(), use_container_width=True)
