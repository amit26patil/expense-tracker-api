from __future__ import annotations

import json
import threading
from datetime import date, datetime
from typing import Optional

import boto3
import uuid
from botocore.exceptions import ClientError

from app.models import BulkTransactionResponse, Currency, Transaction, TransactionCreate, TransactionType, TransactionUpdate

S3_BUCKET = "expense-tracker-db-dev"

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
_s3_client: Optional[boto3.client] = None


def _get_s3_client() -> boto3.client:
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _s3_get_json(key: str) -> Optional[dict | list]:
    s3 = _get_s3_client()
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def _s3_put_json(key: str, data: dict | list) -> None:
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, indent=2, default=str).encode("utf-8"),
        ContentType="application/json",
    )


def _s3_delete(key: str) -> bool:
    s3 = _get_s3_client()
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def _transaction_key(user_email: str, tx_date: date) -> str:
    return f"{user_email}/transactions/{tx_date.year}/{tx_date.month:02d}/data.json"


def _load_transactions(user_email: str, year: int, month: int) -> list[dict]:
    key = _transaction_key(user_email, date(year, month, 1))
    data = _s3_get_json(key)
    if data is None:
        return []
    return data if isinstance(data, list) else []


def _save_transactions(user_email: str, year: int, month: int, transactions: list[dict]) -> None:
    key = _transaction_key(user_email, date(year, month, 1))
    _s3_put_json(key, transactions)


def _get_next_id(user_email: str) -> int:
    counter_key = f"{user_email}/transaction_id_counter.json"
    data = _s3_get_json(counter_key)
    if data is None:
        next_id = 1
    else:
        next_id = data.get("next_id", 1)
    _s3_put_json(counter_key, {"next_id": next_id + 1})
    return next_id


def _load_all_transactions(user_email: str) -> list[Transaction]:
    s3 = _get_s3_client()
    prefix = f"{user_email}/transactions/"
    transactions: list[Transaction] = []

    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith("/data.json"):
                    continue
                data = _s3_get_json(key)
                if data and isinstance(data, list):
                    for tx_dict in data:
                        tx_dict["date"] = date.fromisoformat(tx_dict["date"])
                        tx_dict["type"] = TransactionType(tx_dict["type"])
                        tx_dict["currency"] = Currency(tx_dict["currency"])
                        transactions.append(Transaction(**tx_dict))
    except ClientError:
        pass

    transactions.sort(key=lambda t: (t.date, t.id))
    return transactions


def list_transactions(
    user_email: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> list[Transaction]:
    with _lock:
        if year and month:
            tx_dicts = _load_transactions(user_email, year, month)
            transactions: list[Transaction] = []
            for tx_dict in tx_dicts:
                tx = Transaction(
                    id=tx_dict["id"],
                    date=date.fromisoformat(tx_dict["date"]),
                    type=TransactionType(tx_dict["type"]),
                    category=tx_dict["category"],
                    amount=tx_dict["amount"],
                    currency=Currency(tx_dict["currency"]),
                    description=tx_dict.get("description", ""),
                )
                if day and tx.date.day != day:
                    continue
                transactions.append(tx)
            transactions.sort(key=lambda t: (t.date, t.id))
            return transactions
        else:
            transactions = _load_all_transactions(user_email)
            if year:
                transactions = [t for t in transactions if t.date.year == year]
            if month:
                transactions = [t for t in transactions if t.date.month == month]
            if day:
                transactions = [t for t in transactions if t.date.day == day]
            return transactions


def get_transaction(user_email: str, tx_id: str) -> Optional[Transaction]:
    with _lock:
        transactions = _load_all_transactions(user_email)
        for tx in transactions:
            if tx.id == tx_id:
                return tx
        return None


def create_transaction(user_email: str, payload: TransactionCreate) -> Transaction:
    with _lock:
        tx_id = str(uuid.uuid7())
        now = datetime.now().isoformat(timespec="seconds")
        tx_dict = {
            "id": tx_id,
            "date": payload.date.isoformat(),
            "type": payload.type.value,
            "category": payload.category,
            "amount": payload.amount,
            "currency": payload.currency.value,
            "description": payload.description,
            "created_at": now,
        }

        year = payload.date.year
        month = payload.date.month
        tx_list = _load_transactions(user_email, year, month)
        tx_list.append(tx_dict)
        _save_transactions(user_email, year, month, tx_list)

        return Transaction(id=tx_id, **payload.model_dump())


def create_bulk_transactions(user_email: str, payloads: list[TransactionCreate]) -> BulkTransactionResponse:
    with _lock:
        created: list[Transaction] = []
        temp_payload = payloads[0] if payloads else None
        if temp_payload:
            year = temp_payload.date.year
            month = temp_payload.date.month
            tx_list = _load_transactions(user_email, year, month)
        
            for payload in payloads:
                tx_id = str(uuid.uuid7())
                now = datetime.now().isoformat(timespec="seconds")
                tx_dict = {
                    "id": tx_id,
                    "date": payload.date.isoformat(),
                    "type": payload.type.value,
                    "category": payload.category,
                    "amount": payload.amount,
                    "currency": payload.currency.value,
                    "description": payload.description,
                    "created_at": now,
                }
                tx_list.append(tx_dict)
                created.append(Transaction(id=tx_id, **payload.model_dump()))

            _save_transactions(user_email, year, month, tx_list)
        return BulkTransactionResponse(count=len(created), transactions=created)


def update_transaction(user_email: str, tx_id: str, payload: TransactionUpdate) -> Optional[Transaction]:
    with _lock:
        transactions = _load_all_transactions(user_email)
        for i, tx in enumerate(transactions):
            if tx.id == tx_id:
                updates = payload.model_dump(exclude_unset=True)
                data = tx.model_dump()
                data.update(updates)
                if "type" in updates and updates["type"] is not None:
                    data["type"] = updates["type"]
                if "currency" in updates and updates["currency"] is not None:
                    data["currency"] = updates["currency"]

                updated_tx = Transaction(**data)

                old_year, old_month = tx.date.year, tx.date.month
                new_year, new_month = updated_tx.date.year, updated_tx.date.month

                old_tx_list = _load_transactions(user_email, old_year, old_month)
                old_tx_list = [t for t in old_tx_list if t["id"] != tx_id]
                _save_transactions(user_email, old_year, old_month, old_tx_list)

                new_tx_dict = {
                    "id": updated_tx.id,
                    "date": updated_tx.date.isoformat(),
                    "type": updated_tx.type.value,
                    "category": updated_tx.category,
                    "amount": updated_tx.amount,
                    "currency": updated_tx.currency.value,
                    "description": updated_tx.description,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                new_tx_list = _load_transactions(user_email, new_year, new_month)
                new_tx_list.append(new_tx_dict)
                _save_transactions(user_email, new_year, new_month, new_tx_list)

                return updated_tx

        return None


def delete_transaction(user_email: str, tx_id: int) -> bool:
    with _lock:
        transactions = _load_all_transactions(user_email)
        for tx in transactions:
            if tx.id == tx_id:
                year, month = tx.date.year, tx.date.month
                tx_list = _load_transactions(user_email, year, month)
                tx_list = [t for t in tx_list if t["id"] != tx_id]
                _save_transactions(user_email, year, month, tx_list)
                return True
        return False


def list_categories(user_email: str, tx_type: Optional[str] = None) -> list[dict[str, str]]:
    with _lock:
        categories: list[dict[str, str]] = []

        for cat_type in ["expense", "income"]:
            if tx_type and cat_type != tx_type:
                continue
            key = f"{user_email}/{cat_type}_categories.json"
            data = _s3_get_json(key)
            if data is None:
                data = [
                    {"name": name, "type": t, "keywords": kw}
                    for name, t, kw in DEFAULT_CATEGORIES
                    if t == cat_type
                ]
                _s3_put_json(key, data)
            categories.extend(data)

        return categories


def create_category(user_email: str, name: str, cat_type: str, keywords: str = "") -> dict[str, str]:
    with _lock:
        key = f"{user_email}/{cat_type}_categories.json"
        data = _s3_get_json(key)
        if data is None:
            data = [
                {"name": n, "type": t, "keywords": kw}
                for n, t, kw in DEFAULT_CATEGORIES
                if t == cat_type
            ]

        for cat in data:
            if cat["name"] == name and cat["type"] == cat_type:
                return {"error": "Category already exists"}

        new_cat = {"name": name, "type": cat_type, "keywords": keywords}
        data.append(new_cat)
        _s3_put_json(key, data)
        return new_cat


def update_category(user_email: str, old_name: str, new_name: str, cat_type: str, keywords: Optional[str] = None) -> dict[str, str]:
    with _lock:
        key = f"{user_email}/{cat_type}_categories.json"
        data = _s3_get_json(key)
        if data is None:
            return {"error": "Category not found"}

        for cat in data:
            if cat["name"] == old_name and cat["type"] == cat_type:
                cat["name"] = new_name
                if keywords is not None:
                    cat["keywords"] = keywords
                _s3_put_json(key, data)
                return {"name": new_name, "type": cat_type, "keywords": cat.get("keywords", "")}

        return {"error": "Category not found"}


def delete_category(user_email: str, name: str, cat_type: str) -> bool:
    with _lock:
        key = f"{user_email}/{cat_type}_categories.json"
        data = _s3_get_json(key)
        if data is None:
            return False

        original_len = len(data)
        data = [cat for cat in data if not (cat["name"] == name and cat["type"] == cat_type)]

        if len(data) < original_len:
            _s3_put_json(key, data)
            return True
        return False


def list_currencies() -> list[str]:
    return [c.value for c in Currency]


def get_default_currency(user_email: str) -> str:
    with _lock:
        key = f"{user_email}/currency.json"
        data = _s3_get_json(key)
        if data is None:
            return "INR"
        return data.get("default_currency", "INR")


def set_default_currency(user_email: str, currency: str) -> str:
    with _lock:
        key = f"{user_email}/currency.json"
        data = _s3_get_json(key)
        if data is None:
            data = {}
        data["default_currency"] = currency
        _s3_put_json(key, data)
        return currency
