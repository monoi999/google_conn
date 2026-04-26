from pathlib import Path

import pandas as pd
import streamlit as st
import json

import gspread
import gspread_helpers as gh


DATA_PATH = Path(__file__).with_name("score.csv")
DISPLAY_COLUMNS = ["ID", "반", "이름", "이메일", "연락처", "평균", "등급"]
GRADE_ORDER = ["A", "B", "C", "D"]


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, encoding="cp949")
    df["반"] = df["반"].astype(str)
    df["평균"] = pd.to_numeric(df["평균"], errors="coerce")
    df["등급"] = df["등급"].astype(str)
    return df


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized_df = df.copy()

    for column in DISPLAY_COLUMNS:
        if column not in normalized_df.columns:
            normalized_df[column] = ""

    normalized_df = normalized_df[DISPLAY_COLUMNS]
    normalized_df["반"] = normalized_df["반"].astype(str).str.strip()
    normalized_df["등급"] = normalized_df["등급"].astype(str).str.strip().str.upper()
    normalized_df["평균"] = pd.to_numeric(normalized_df["평균"], errors="coerce")

    return normalized_df


def generate_new_id(existing_ids: set[str]) -> str:
    next_index = 1
    while True:
        candidate = f"user_new_{next_index:03d}"
        if candidate not in existing_ids:
            return candidate
        next_index += 1


def apply_editor_changes(
    original_df: pd.DataFrame,
    filtered_df: pd.DataFrame,
    edited_df: pd.DataFrame,
) -> pd.DataFrame:
    base_df = normalize_dataframe(original_df)
    filtered_base_df = normalize_dataframe(filtered_df)
    edited_base_df = normalize_dataframe(edited_df)

    filtered_ids = set(filtered_base_df["ID"].dropna().astype(str))
    existing_ids = set(base_df["ID"].dropna().astype(str))

    remaining_df = base_df[~base_df["ID"].astype(str).isin(filtered_ids)].copy()
    edited_rows = []

    for _, row in edited_base_df.iterrows():
        row_dict = row.to_dict()
        row_id = str(row_dict.get("ID", "")).strip()
        if not row_id or row_id == "nan" or row_id in {"None", ""}:
            row_id = generate_new_id(existing_ids)
        row_dict["ID"] = row_id
        existing_ids.add(row_id)
        edited_rows.append(row_dict)

    merged_df = pd.concat([remaining_df, pd.DataFrame(edited_rows)], ignore_index=True)
    return normalize_dataframe(merged_df)


def get_filtered_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    class_options = sorted(
        [class_name for class_name in df["반"].dropna().unique().tolist() if class_name],
        key=int,
    )
    grade_options = [grade for grade in GRADE_ORDER if grade in df["등급"].dropna().unique()]

    score_series = df["평균"].dropna()
    min_score = float(score_series.min()) if not score_series.empty else 0.0
    max_score = float(score_series.max()) if not score_series.empty else 100.0

    with st.sidebar:
        st.header("필터")
        st.subheader("반 선택")
        selected_classes = [
            class_name
            for class_name in class_options
            if st.checkbox(f"{class_name}반", value=True, key=f"class_{class_name}")
        ]
        selected_grades = st.multiselect(
            "등급 선택",
            options=grade_options,
            default=grade_options,
        )
        include_absent = st.radio(
            "결시생 포함 여부",
            options=["포함", "제외"],
            index=0,
            horizontal=True,
        )
        selected_score_range = st.slider(
            "평균 점수 범위",
            min_value=min_score,
            max_value=max_score,
            value=(min_score, max_score),
            step=0.01,
        )

    filtered_df = df.copy()
    filtered_df["결시생"] = filtered_df["평균"].fillna(0).eq(0)

    if selected_classes:
        filtered_df = filtered_df[filtered_df["반"].isin(selected_classes)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    if selected_grades:
        filtered_df = filtered_df[filtered_df["등급"].isin(selected_grades)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    filtered_df = filtered_df[
        filtered_df["평균"].between(selected_score_range[0], selected_score_range[1], inclusive="both")
    ]

    if include_absent == "제외":
        filtered_df = filtered_df[~filtered_df["결시생"]]

    return filtered_df.drop(columns=["결시생"])


def main() -> None:
    st.set_page_config(page_title="성적 데이터 편집 대시보드", layout="wide")
    st.title("성적 데이터 편집 대시보드")

    if "score_data" not in st.session_state:
        st.session_state.score_data = normalize_dataframe(load_data())

    filtered_df = get_filtered_dataframe(st.session_state.score_data)

    st.subheader("필터링 결과")
    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "반": st.column_config.SelectboxColumn("반", options=["1", "2", "3"], required=True),
            "등급": st.column_config.SelectboxColumn("등급", options=GRADE_ORDER, required=True),
            "평균": st.column_config.NumberColumn("평균", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
        },
        key="score_editor",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("편집 내용 전체 반영", use_container_width=True):
            st.session_state.score_data = apply_editor_changes(
                st.session_state.score_data,
                filtered_df,
                edited_df,
            )
            st.success("현재 필터링 결과를 기준으로 수정/삭제 내용을 반영했습니다.")
            st.rerun()
    with col2:
        if st.button("원본 데이터로 초기화", use_container_width=True):
            st.session_state.score_data = normalize_dataframe(load_data())
            st.success("원본 score.csv 기준으로 초기화했습니다.")
            st.rerun()

    st.caption(
        "테이블에서 셀 값을 직접 수정할 수 있고, 행을 삭제하거나 새 행을 추가할 수 있습니다. "
        "반영 버튼을 누르면 현재 필터링된 테이블 기준으로 데이터가 갱신됩니다."
    )

# ---------- Google Sheets 동기화 섹션 ----------
with st.expander("구글시트 동기화 (Streamlit Secrets 사용 권장)"):
    st.write("Streamlit `secrets`에 `gcp_service_account`(JSON object)와 `spreadsheet_url`을 설정하세요.")
    spreadsheet_url = st.text_input("스프레드시트 URL (비워두면 secrets에서 불러옵니다)", value="")
    sheet_name = st.text_input("시트 이름", value="Sheet1")

    # 우선순위: 입력 필드 -> secrets
    secrets_sa = None
    if "gcp_service_account" in st.secrets:
        secrets_sa = st.secrets["gcp_service_account"]

    if not spreadsheet_url and "spreadsheet_url" in st.secrets:
        spreadsheet_url = st.secrets["spreadsheet_url"]

    if st.button("구글시트에 저장", use_container_width=True):
        if not secrets_sa:
            st.error("서비스 계정 정보가 st.secrets에 없습니다. Streamlit Secrets에 `gcp_service_account`를 추가하세요.")
        elif not spreadsheet_url:
            st.error("스프레드시트 URL을 입력하거나 st.secrets에 `spreadsheet_url`을 설정하세요.")
        else:
            try:
                client = gh.client_from_service_account_dict(secrets_sa)
                sh = client.open_by_url(spreadsheet_url)
                try:
                    ws = sh.worksheet(sheet_name)
                except Exception:
                    # 시트가 없으면 새 시트 생성
                    ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")

                # 현재 세션의 데이터를 시트로 저장
                df_to_save = normalize_dataframe(st.session_state.score_data)
                # gspread_helpers 함수 사용
                gh.df_to_worksheet(ws, df_to_save, clear=True)
                st.success("구글시트에 저장되었습니다.")
            except Exception as e:
                st.error(f"구글시트 저장 중 오류 발생: {e}")

    stat_df = normalize_dataframe(edited_df)
    total_count = len(stat_df)
    average_score = float(stat_df["평균"].dropna().mean()) if total_count else 0.0
    grade_counts = (
        stat_df["등급"]
        .value_counts()
        .reindex(GRADE_ORDER, fill_value=0)
        .rename_axis("등급")
        .reset_index(name="인원수")
    )

    st.subheader("통계 / 시각화")
    spacer_left, stats_col, spacer_right = st.columns([1, 2, 1])
    with stats_col:
        metric_col1, metric_col2 = st.columns(2)
        metric_col1.metric("총인원수", f"{total_count}명")
        metric_col2.metric("평균점수", f"{average_score:.2f}점")

    st.bar_chart(grade_counts.set_index("등급"), use_container_width=True)


if __name__ == "__main__":
    main()