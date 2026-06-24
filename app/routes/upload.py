import tempfile
from pathlib import Path

import xlrd
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["upload"])

HEADER_ROW = 12


class ExcelRecord(BaseModel):
    S_No: int | None = None
    Value_Date: str | None = None
    Transaction_Date: str | None = None
    Cheque_Number: str | None = None
    Transaction_Remarks: str | None = None
    Withdrawal_Amount_INR: float | None = None
    Deposit_Amount_INR: float | None = None
    Balance_INR: float | None = None


class ExcelUploadResponse(BaseModel):
    filename: str
    record_count: int
    records: list[dict]


def parse_xls(filepath: str) -> list[dict]:
    wb = xlrd.open_workbook(filepath)
    sh = wb.sheet_by_index(0)

    if sh.nrows <= HEADER_ROW:
        return []

    headers = [sh.cell_value(HEADER_ROW, c).strip() for c in range(sh.ncols)]

    records = []
    for r in range(HEADER_ROW + 1, sh.nrows):
        row_vals = [sh.cell_value(r, c) for c in range(sh.ncols)]
        sno_raw = row_vals[1]
        sno = str(sno_raw).strip()
        if not sno:
            continue
        try:
            int(sno)
        except ValueError:
            break

        record = {}
        for i, h in enumerate(headers):
            if not h:
                continue
            val = row_vals[i]
            if h == "S No.":
                val = int(sno_raw)
            elif h in ("Withdrawal Amount(INR)", "Deposit Amount(INR)", "Balance(INR)"):
                val = float(val) if val else 0.0
            record[h] = val
        records.append(record)

    return records


@router.post(
    "/upload-excel",
    response_model=ExcelUploadResponse,
    summary="Upload bank statement Excel",
    description="Upload an ICICI bank statement (.xls) file. The file is parsed and all transaction rows are returned as JSON.",
    responses={
        400: {"description": "Invalid file type"},
        422: {"description": "Failed to parse Excel file"},
    },
)
async def upload_excel(file: UploadFile = File(..., description="Bank statement .xls file")):
    if not file.filename or not file.filename.lower().endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xls and .xlsx files are supported")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        records = parse_xls(tmp_path)
    except xlrd.XLRDError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel file: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return ExcelUploadResponse(filename=file.filename, record_count=len(records), records=records)
