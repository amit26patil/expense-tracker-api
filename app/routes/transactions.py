from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import google_sheet_store as excel_store
from app.models import (
    CategoryDetail,
    DaySummary,
    MonthDetail,
    MonthSummary,
    Transaction,
    TransactionCreate,
    TransactionUpdate,
    TransactionType,
)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[Transaction])
def get_transactions(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    day: Optional[int] = Query(default=None, ge=1, le=31),
) -> list[Transaction]:
    return excel_store.list_transactions(year=year, month=month, day=day)


@router.get("/{tx_id}", response_model=Transaction)
def get_transaction(tx_id: int) -> Transaction:
    tx = excel_store.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.post("", response_model=Transaction, status_code=201)
def create_transaction(payload: TransactionCreate) -> Transaction:
    return excel_store.create_transaction(payload)


@router.put("/{tx_id}", response_model=Transaction)
def update_transaction(tx_id: int, payload: TransactionUpdate) -> Transaction:
    tx = excel_store.update_transaction(tx_id, payload)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(tx_id: int) -> None:
    if not excel_store.delete_transaction(tx_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
