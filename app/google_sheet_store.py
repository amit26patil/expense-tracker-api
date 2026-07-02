from __future__ import annotations

import threading
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from app.models import BulkTransactionResponse, Currency, Transaction, TransactionCreate, TransactionType, TransactionUpdate

CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "expense-tracker-500203-1d10858a70af.json"
SPREADSHEET_NAME = "temp_expense_sheet"

TRANSACTION_HEADERS = [
    "id",
    "date",
    "type",
    "category",
    "amount",
    "currency",
    "description",
    "created_at",
]
CATEGORY_HEADERS = ["name", "type", "keywords"]
SETTINGS_HEADERS = ["key", "value"]

DEFAULT_CATEGORIES = [
    ("Food", "expense", ""),
    ("Transport", "expense", ""),
    ("Shopping", "expense", ""),
    ("Bills", "expense", ""),
    ("Entertainment", "expense", ""),
    ("Healthcare", "expense", ""),
    ("Other Expense", "expense", ""),
    ("Salary", "income", ""),
    ("Freelance", "income", ""),
    ("Investment", "income", ""),
    ("Other Income", "income", ""),
]

_lock = threading.Lock()
_client: Optional[gspread.Client] = None


def _get_client() -> gspread.Client:
    global _client
    if _client is None:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(CREDENTIALS_PATH), scope)
        _client = gspread.authorize(creds)
    return _client


def _get_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    return client.open(SPREADSHEET_NAME)


def _ensure_sheets() -> None:
    spreadsheet = _get_spreadsheet()

    try:
        tx_sheet = spreadsheet.worksheet("Transactions")
    except gspread.exceptions.WorksheetNotFound:
        tx_sheet = spreadsheet.add_worksheet(title="Transactions", rows=1000, cols=len(TRANSACTION_HEADERS))
        tx_sheet.append_row(TRANSACTION_HEADERS)

    try:
        cat_sheet = spreadsheet.worksheet("Categories")
    except gspread.exceptions.WorksheetNotFound:
        cat_sheet = spreadsheet.add_worksheet(title="Categories", rows=1000, cols=len(CATEGORY_HEADERS))
        cat_sheet.append_row(CATEGORY_HEADERS)
        for name, cat_type, keywords in DEFAULT_CATEGORIES:
            cat_sheet.append_row([name, cat_type, keywords])

    try:
        settings_sheet = spreadsheet.worksheet("Settings")
    except gspread.exceptions.WorksheetNotFound:
        settings_sheet = spreadsheet.add_worksheet(title="Settings", rows=100, cols=len(SETTINGS_HEADERS))
        settings_sheet.append_row(SETTINGS_HEADERS)
        settings_sheet.append_row(["default_currency", "INR"])


def _get_transactions_worksheet() -> gspread.Worksheet:
    _ensure_sheets()
    spreadsheet = _get_spreadsheet()
    return spreadsheet.worksheet("Transactions")


def _get_categories_worksheet() -> gspread.Worksheet:
    _ensure_sheets()
    spreadsheet = _get_spreadsheet()
    return spreadsheet.worksheet("Categories")


def _row_to_transaction(row: list) -> Transaction:
    return Transaction(
        id=int(row[0]),
        date=date.fromisoformat(str(row[1])),
        type=TransactionType(str(row[2])),
        category=str(row[3]),
        amount=float(row[4]),
        currency=Currency(str(row[5])),
        description=str(row[6] or ""),
    )


def _next_id(worksheet: gspread.Worksheet) -> int:
    all_values = worksheet.get_all_values()
    max_id = 0
    for row in all_values[1:]:
        if row[0]:
            max_id = max(max_id, int(row[0]))
    return max_id + 1


def list_transactions(
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> list[Transaction]:
    with _lock:
        worksheet = _get_transactions_worksheet()
        all_values = worksheet.get_all_values()
        transactions: list[Transaction] = []
        for row in all_values[1:]:
            if not row[0]:
                continue
            tx = _row_to_transaction(row)
            if year and tx.date.year != year:
                continue
            if month and tx.date.month != month:
                continue
            if day and tx.date.day != day:
                continue
            transactions.append(tx)
        transactions.sort(key=lambda t: (t.date, t.id))
        return transactions


def get_transaction(tx_id: int) -> Optional[Transaction]:
    with _lock:
        worksheet = _get_transactions_worksheet()
        all_values = worksheet.get_all_values()
        for row in all_values[1:]:
            if not row[0]:
                continue
            if int(row[0]) == tx_id:
                return _row_to_transaction(row)
        return None


def create_transaction(payload: TransactionCreate) -> Transaction:
    with _lock:
        worksheet = _get_transactions_worksheet()
        tx_id = _next_id(worksheet)
        now = datetime.now().isoformat(timespec="seconds")
        worksheet.append_row([
            tx_id,
            payload.date.isoformat(),
            payload.type.value,
            payload.category,
            payload.amount,
            payload.currency.value,
            payload.description,
            now,
        ])
        return Transaction(id=tx_id, **payload.model_dump())


def create_bulk_transactions(payloads: list[TransactionCreate]) -> BulkTransactionResponse:
    with _lock:
        worksheet = _get_transactions_worksheet()
        tx_id = _next_id(worksheet)
        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        created: list[Transaction] = []
        for payload in payloads:
            rows.append([
                tx_id,
                payload.date.isoformat(),
                payload.type.value,
                payload.category,
                payload.amount,
                payload.currency.value,
                payload.description,
                now,
            ])
            created.append(Transaction(id=tx_id, **payload.model_dump()))
            tx_id += 1
        worksheet.append_rows(rows)
        return BulkTransactionResponse(count=len(created), transactions=created)


def update_transaction(tx_id: int, payload: TransactionUpdate) -> Optional[Transaction]:
    with _lock:
        worksheet = _get_transactions_worksheet()
        all_values = worksheet.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if not row[0]:
                continue
            if int(row[0]) != tx_id:
                continue

            current = _row_to_transaction(row)
            updates = payload.model_dump(exclude_unset=True)
            data = current.model_dump()
            data.update(updates)
            if "type" in updates and updates["type"] is not None:
                data["type"] = updates["type"]
            if "currency" in updates and updates["currency"] is not None:
                data["currency"] = updates["currency"]

            row_num = idx
            worksheet.update_cell(row_num, 2, data["date"].isoformat())
            worksheet.update_cell(row_num, 3, data["type"].value)
            worksheet.update_cell(row_num, 4, data["category"])
            worksheet.update_cell(row_num, 5, data["amount"])
            worksheet.update_cell(row_num, 6, data["currency"].value)
            worksheet.update_cell(row_num, 7, data["description"])

            return Transaction(**data)

        return None


def delete_transaction(tx_id: int) -> bool:
    with _lock:
        worksheet = _get_transactions_worksheet()
        all_values = worksheet.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if not row[0]:
                continue
            if int(row[0]) == tx_id:
                worksheet.delete_rows(idx, idx)
                return True
        return False


def list_categories(tx_type: Optional[str] = None) -> list[dict[str, str]]:
    with _lock:
        worksheet = _get_categories_worksheet()
        all_values = worksheet.get_all_values()
        categories: list[dict[str, str]] = []
        for row in all_values[1:]:
            if not row[0]:
                continue
            name, cat_type = str(row[0]), str(row[1])
            keywords = str(row[2] or "") if len(row) > 2 else ""
            if tx_type and cat_type != tx_type:
                continue
            categories.append({"name": name, "type": cat_type, "keywords": keywords})
        return categories


def create_category(name: str, cat_type: str, keywords: str = "") -> dict[str, str]:
    with _lock:
        worksheet = _get_categories_worksheet()
        all_values = worksheet.get_all_values()
        for row in all_values[1:]:
            if row[0] == name and row[1] == cat_type:
                return {"error": "Category already exists"}
        worksheet.append_row([name, cat_type, keywords])
        return {"name": name, "type": cat_type, "keywords": keywords}


def update_category(old_name: str, new_name: str, cat_type: str, keywords: Optional[str] = None) -> dict[str, str]:
    with _lock:
        worksheet = _get_categories_worksheet()
        all_values = worksheet.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == old_name and row[1] == cat_type:
                worksheet.update_cell(idx, 1, new_name)
                if keywords is not None:
                    worksheet.update_cell(idx, 3, keywords)
                else:
                    keywords = str(row[2] or "") if len(row) > 2 else ""
                return {"name": new_name, "type": cat_type, "keywords": keywords}
        return {"error": "Category not found"}


def delete_category(name: str, cat_type: str) -> bool:
    with _lock:
        worksheet = _get_categories_worksheet()
        all_values = worksheet.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == name and row[1] == cat_type:
                worksheet.delete_rows(idx, idx)
                return True
        return False


def list_currencies() -> list[str]:
    return [c.value for c in Currency]


def get_default_currency() -> str:
    with _lock:
        _ensure_sheets()
        spreadsheet = _get_spreadsheet()
        settings_sheet = spreadsheet.worksheet("Settings")
        all_values = settings_sheet.get_all_values()
        for row in all_values[1:]:
            if row[0] == "default_currency":
                return row[1] if row[1] else "INR"
        return "INR"


def set_default_currency(currency: str) -> str:
    with _lock:
        _ensure_sheets()
        spreadsheet = _get_spreadsheet()
        settings_sheet = spreadsheet.worksheet("Settings")
        all_values = settings_sheet.get_all_values()
        for idx, row in enumerate(all_values[1:], start=2):
            if row[0] == "default_currency":
                settings_sheet.update_cell(idx, 2, currency)
                return currency
        settings_sheet.append_row(["default_currency", currency])
        return currency
