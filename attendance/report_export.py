"""
attendance/report_export.py
Export attendance records to CSV and XLSX.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config import EXPORT_DIR
from database import db_manager as db

logger = logging.getLogger(__name__)

COLUMNS = ["Date", "Entry Time", "Employee Name", "Employee ID"]


def _rows_to_df(rows) -> pd.DataFrame:
    data = []
    for row in rows:
        data.append({
            "Date":          row["attendance_date"],
            "Entry Time":    row["entry_time"],
            "Employee Name": row["name"],
            "Employee ID":   row["emp_id"],
        })
    return pd.DataFrame(data, columns=COLUMNS)


def export_to_csv(
    path: str,
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    emp_id:    Optional[str] = None,
    name_like: Optional[str] = None,
) -> Tuple[bool, str]:
    from typing import Tuple
    try:
        rows, total = db.get_attendance_filtered(date_from, date_to, emp_id, name_like, limit=100000)
        if total == 0:
            return False, "No records match the selected filters."
        df = _rows_to_df(rows)
        df.to_csv(path, index=False)
        logger.info("Exported %d rows to CSV: %s", total, path)
        return True, f"Exported {total} records to {path}"
    except PermissionError:
        return False, "Permission denied — close the file if it is open."
    except Exception as exc:
        logger.error("CSV export failed: %s", exc)
        return False, str(exc)


def export_to_excel(
    path: str,
    date_from: Optional[str] = None,
    date_to:   Optional[str] = None,
    emp_id:    Optional[str] = None,
    name_like: Optional[str] = None,
) -> tuple[bool, str]:
    try:
        rows, total = db.get_attendance_filtered(date_from, date_to, emp_id, name_like, limit=100000)
        if total == 0:
            return False, "No records match the selected filters."
        df = _rows_to_df(rows)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Attendance")
            ws = writer.sheets["Attendance"]
            for col in ws.columns:
                max_len = max(len(str(c.value or "")) for c in col) + 4
                ws.column_dimensions[col[0].column_letter].width = max_len
        logger.info("Exported %d rows to Excel: %s", total, path)
        return True, f"Exported {total} records to {path}"
    except PermissionError:
        return False, "Permission denied — close the file if it is open."
    except Exception as exc:
        logger.error("Excel export failed: %s", exc)
        return False, str(exc)


def today_csv_path() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return str(EXPORT_DIR / f"attendance_{today}.csv")


def today_excel_path() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return str(EXPORT_DIR / f"attendance_{today}.xlsx")
