import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
import json
from typing import Union


def client_from_service_account_dict(sa_dict: Union[dict, str]):
    """Create a gspread client from a service account dict (from Streamlit secrets).

    Accept either a dict or a JSON string (some deployment platforms store JSON as a
    multiline string). If a string is passed, attempt to parse it as JSON.
    """
    if isinstance(sa_dict, str):
        try:
            sa_dict = json.loads(sa_dict)
        except Exception as e:
            raise ValueError("Provided service account is a string but not valid JSON") from e

    return gspread.service_account_from_dict(sa_dict)


def open_sheet_by_url(client: gspread.Client, spreadsheet_url: str):
    """Open a spreadsheet by URL and return the Spreadsheet object."""
    return client.open_by_url(spreadsheet_url)


def worksheet_to_df(worksheet, evaluate_formulas: bool = True) -> pd.DataFrame:
    """Convert a gspread worksheet to a pandas DataFrame.

    Returns a normalized DataFrame (empty cells become NaN).
    """
    df = get_as_dataframe(worksheet, evaluate_formulas=evaluate_formulas, headers=0)
    # Drop completely empty rows that gspread may return
    if isinstance(df, pd.DataFrame):
        df = df.dropna(how="all").reset_index(drop=True)
    return df


def df_to_worksheet(worksheet, df: pd.DataFrame, clear: bool = True):
    """Write a DataFrame to the worksheet, optionally clearing first."""
    if clear:
        worksheet.clear()
    set_with_dataframe(worksheet, df, include_index=False, include_column_header=True)
