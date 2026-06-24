from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import google_sheet_store as excel_store
from app.models import (
    Transaction,
    TransactionCreate,
    TransactionUpdate,
)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=list[Transaction],
    summary="List transactions",
    description="Retrieve transactions, optionally filtered by year, month, and day.",
)
def get_transactions(
    year: Optional[int] = Query(default=None, description="Filter by year"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="Filter by month"),
    day: Optional[int] = Query(default=None, ge=1, le=31, description="Filter by day"),
) -> list[Transaction]:
    return excel_store.list_transactions(year=year, month=month, day=day)


@router.get(
    "/{tx_id}",
    response_model=Transaction,
    summary="Get transaction by ID",
    description="Retrieve a single transaction by its ID.",
    responses={404: {"description": "Transaction not found"}},
)
def get_transaction(tx_id: int) -> Transaction:
    tx = excel_store.get_transaction(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.post(
    "",
    response_model=Transaction,
    status_code=201,
    summary="Create a transaction",
    description="Create a new expense or income transaction.",
)
def create_transaction(payload: TransactionCreate) -> Transaction:
    return excel_store.create_transaction(payload)


@router.put(
    "/{tx_id}",
    response_model=Transaction,
    summary="Update a transaction",
    description="Update an existing transaction by its ID.",
    responses={404: {"description": "Transaction not found"}},
)
def update_transaction(tx_id: int, payload: TransactionUpdate) -> Transaction:
    tx = excel_store.update_transaction(tx_id, payload)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.delete(
    "/{tx_id}",
    status_code=204,
    summary="Delete a transaction",
    description="Delete a transaction by its ID.",
    responses={404: {"description": "Transaction not found"}},
)
def delete_transaction(tx_id: int) -> None:
    if not excel_store.delete_transaction(tx_id):
        raise HTTPException(status_code=404, detail="Transaction not found")
