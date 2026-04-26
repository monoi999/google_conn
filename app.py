import streamlit as st
import pandas as pd
from typing import Set
from streamlit_gsheets import GSheetsConnection
import gspread_helpers as gh
from datetime import datetime
from typing import Any


DATA_DISPLAY_COLUMNS = ["ID", "반", "이름", "이메일", "연락처", "평균", "등급"]
GRADE_ORDER = ["A", "B", "C", "D"]


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in DATA_DISPLAY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[DATA_DISPLAY_COLUMNS]
    df["반"] = df["반"].astype(str).str.strip()
    df["등급"] = df["등급"].astype(str).str.strip().str.upper()
    df["평균"] = pd.to_numeric(df["평균"], errors="coerce")
    return df


def generate_new_id(existing_ids: Set[str]) -> str:
    idx = 1
    while True:
        candidate = f"user_new_{idx:03d}"
        if candidate not in existing_ids:
            return candidate
        idx += 1


def apply_editor_changes(original_df: pd.DataFrame, filtered_df: pd.DataFrame, edited_df: pd.DataFrame) -> pd.DataFrame:
    base_df = normalize_dataframe(original_df)
    filtered_base = normalize_dataframe(filtered_df)
    edited_base = normalize_dataframe(edited_df)

    filtered_ids = set(filtered_base["ID"].dropna().astype(str))
    existing_ids = set(base_df["ID"].dropna().astype(str))

    remaining = base_df[~base_df["ID"].astype(str).isin(filtered_ids)].copy()
    edited_rows = []

    for _, row in edited_base.iterrows():
        rd = row.to_dict()
        rid = str(rd.get("ID", "")).strip()
        if not rid or rid in {"nan", "None", ""}:
            rid = generate_new_id(existing_ids)
        rd["ID"] = rid
        existing_ids.add(rid)
        edited_rows.append(rd)

    merged = pd.concat([remaining, pd.DataFrame(edited_rows)], ignore_index=True)
    return normalize_dataframe(merged)


def get_filtered_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    class_options = sorted([c for c in df["반"].dropna().unique().tolist() if c], key=lambda x: str(x))
    grade_options = [g for g in GRADE_ORDER if g in df["등급"].dropna().unique()]

    score_series = df["평균"].dropna()
    min_score = float(score_series.min()) if not score_series.empty else 0.0
    max_score = float(score_series.max()) if not score_series.empty else 100.0

    with st.sidebar:
        st.header("필터")
        st.subheader("반 선택")
        selected_classes = [
            c for c in class_options if st.checkbox(f"{c}반", value=True, key=f"class_{c}")
        ]
        selected_grades = st.multiselect("등급 선택", options=grade_options, default=grade_options)
        include_absent = st.radio("결시생 포함 여부", options=["포함", "제외"], index=0, horizontal=True)
        selected_score_range = st.slider("평균 점수 범위", min_value=min_score, max_value=max_score, value=(min_score, max_score), step=0.01)

    filtered = df.copy()
    filtered["결시생"] = filtered["평균"].fillna(0).eq(0)

    if selected_classes:
        filtered = filtered[filtered["반"].isin(selected_classes)]
    else:
        filtered = filtered.iloc[0:0]

    if selected_grades:
        filtered = filtered[filtered["등급"].isin(selected_grades)]
    else:
        filtered = filtered.iloc[0:0]

    filtered = filtered[filtered["평균"].between(selected_score_range[0], selected_score_range[1], inclusive="both")]

    if include_absent == "제외":
        filtered = filtered[~filtered["결시생"]]

    return filtered.drop(columns=["결시생"])


def main():
    st.set_page_config(page_title="성적 데이터 편집 (GSheets)", layout="wide")
    st.title("성적 데이터 편집 대시보드 (GSheets)")

    # GSheets connection using Streamlit Connections
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Allow user to provide spreadsheet URL/ID (overrides Connection default)
    spreadsheet_url_input = st.text_input(
        "스프레드시트 URL 또는 ID (빈칸이면 Connection 기본 사용)",
        value="https://docs.google.com/spreadsheets/d/1bMrnsXU_cUuLOK40znbFK44WTiUXFMoadW8kvZ9DHDo/edit?usp=sharing",
    )

    # Load sheet data with fallback to gspread_helpers when streamlit_gsheets fails
    @st.cache_data
    def load_data_ttl():
        load_logs = []
        # Try streamlit_gsheets first
        try:
            # If user provided spreadsheet URL/ID, pass it explicitly
            spreadsheet = spreadsheet_url_input or (st.secrets.get("spreadsheet_url") if "spreadsheet_url" in st.secrets else None)
            if spreadsheet:
                raw = conn.read(spreadsheet=spreadsheet, ttl=0)
                load_logs.append(f"conn.read(spreadsheet=...) returned type: {type(raw)}")
            else:
                raw = conn.read(ttl=0)
                load_logs.append(f"conn.read() returned type: {type(raw)}")

            if isinstance(raw, pd.DataFrame):
                st.session_state.setdefault("_load_logs", []).extend(load_logs)
                return normalize_dataframe(raw)
        except Exception as e:
            load_logs.append(f"conn.read() raised: {e}")

        # Fallback: try gspread via gspread_helpers using st.secrets
        try:
            sa = st.secrets.get("gcp_service_account") if "gcp_service_account" in st.secrets else None
            url = st.secrets.get("spreadsheet_url") if "spreadsheet_url" in st.secrets else None
            if sa and url:
                try:
                    client = gh.client_from_service_account_dict(sa)
                    sh = client.open_by_url(url)
                    ws = sh.sheet1
                    df = gh.worksheet_to_df(ws)
                    load_logs.append(f"gspread read returned type: {type(df)}")
                    st.session_state.setdefault("_load_logs", []).extend(load_logs)
                    return normalize_dataframe(df) if isinstance(df, pd.DataFrame) else pd.DataFrame(columns=DATA_DISPLAY_COLUMNS)
                except Exception as e:
                    load_logs.append(f"gspread fallback failed: {e}")
        except Exception as e:
            load_logs.append(f"gspread setup failed: {e}")

        st.session_state.setdefault("_load_logs", []).extend(load_logs)
        return pd.DataFrame(columns=DATA_DISPLAY_COLUMNS)

    if "score_data" not in st.session_state:
        st.session_state.score_data = load_data_ttl()

    # --- 디버그: 시트 로드 상태 표시 ---
    with st.expander("디버그: 시트 로드 상태 확인"):
        st.write("GSheets 연결 객체:", type(conn))
        st.write("로드 로그:", st.session_state.get("_load_logs", []))
        try:
            raw = conn.read(ttl=0)
            st.write("conn.read() 반환 타입:", type(raw))
            if isinstance(raw, pd.DataFrame):
                st.write("데이터프레임 크기:", raw.shape)
                st.write("컬럼:", list(raw.columns))
                st.write("데이터 샘플:")
                st.dataframe(raw.head(5), width="stretch")
            else:
                st.write("conn.read()가 DataFrame을 반환하지 않았습니다. 값:")
                st.write(raw)
        except Exception as e:
            st.write("conn.read() 호출 중 예외:", e)

        # 현재 정규화된 세션 데이터 상태
        sdf = st.session_state.get("score_data")
        if isinstance(sdf, pd.DataFrame):
            st.write("정규화된 세션 데이터 크기:", sdf.shape)
            st.write("정규화된 컬럼:", list(sdf.columns))
            missing = [c for c in DATA_DISPLAY_COLUMNS if c not in sdf.columns]
            if missing:
                st.warning(f"필요한 컬럼이 누락되었습니다: {missing}")
        else:
            st.write("세션에 저장된 score_data가 DataFrame이 아닙니다:", type(sdf))

    def safe_rerun():
        try:
            rerun = getattr(st, "experimental_rerun", None)
            if callable(rerun):
                rerun()
            else:
                # Fallback: update query params to force a rerun in environments
                # where `experimental_rerun` is unavailable.
                try:
                    st.experimental_set_query_params(_refresh=str(datetime.now().timestamp()))
                except Exception:
                    st.session_state.setdefault("_rerun_failed", True)
        except Exception:
            st.session_state.setdefault("_rerun_failed", True)

    filtered_df = get_filtered_dataframe(st.session_state.score_data)

    st.subheader("필터링 결과")
    # Dynamic column configs: set Selectbox options from data
    class_opts = sorted([c for c in st.session_state.score_data["반"].dropna().unique() if c], key=str)
    class_opts = class_opts or ["1", "2", "3"]

    edited_df = st.data_editor(
        filtered_df,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "반": st.column_config.SelectboxColumn("반", options=class_opts, required=True),
            "등급": st.column_config.SelectboxColumn("등급", options=GRADE_ORDER, required=True),
            "평균": st.column_config.NumberColumn("평균", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        },
        key="score_editor",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("편집 내용 전체 반영", width="stretch"):
            st.session_state.score_data = apply_editor_changes(
                st.session_state.score_data, filtered_df, edited_df
            )
            st.success("수정/삭제 내용이 반영되었습니다.")
            safe_rerun()
    with c2:
        if st.button("원본(시트)으로 초기화", width="stretch"):
            st.session_state.score_data = load_data_ttl()
            st.success("시트 원본으로 초기화했습니다.")
            safe_rerun()

    st.caption("테이블에서 셀을 수정하거나 행을 추가/삭제한 후 '편집 내용 전체 반영'을 눌러 반영하세요.")

    # Save to GSheets
    with st.expander("구글시트 저장 / 동기화"):
        st.write("Streamlit Connections로 연결된 Google Sheet에 데이터를 저장합니다.")
        if st.button("구글시트에 저장", width="stretch"):
            try:
                df_to_save = normalize_dataframe(st.session_state.score_data)
                conn.update(data=df_to_save)
                st.cache_data.clear()
                st.success("구글시트에 저장되었습니다.")
            except Exception as e:
                st.error(f"구글시트 저장 중 오류 발생: {e}")

    # 통계
    stat_df = normalize_dataframe(edited_df)
    total_count = len(stat_df)
    average_score = float(stat_df["평균"].dropna().mean()) if total_count else 0.0
    grade_counts = stat_df["등급"].value_counts().reindex(GRADE_ORDER, fill_value=0).rename_axis("등급").reset_index(name="인원수")

    st.subheader("통계 / 시각화")
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        mc1, mc2 = st.columns(2)
        mc1.metric("총인원수", f"{total_count}명")
        mc2.metric("평균점수", f"{average_score:.2f}점")
        st.bar_chart(grade_counts.set_index("등급"), width="stretch")


if __name__ == "__main__":
    main()
