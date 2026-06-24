from typing import Optional

from fastapi import APIRouter, Query

from app import google_sheet_store as excel_store

router = APIRouter(prefix="/api", tags=["meta"])


@router.get(
    "/categories",
    summary="List categories",
    description="Retrieve all transaction categories, optionally filtered by type (income/expense).",
)
def get_categories(type: Optional[str] = Query(default=None, description="Filter by type: income or expense")) -> list[dict[str, str]]:
    return excel_store.list_categories(tx_type=type)


@router.get(
    "/currencies",
    summary="List currencies",
    description="Retrieve all supported currency codes.",
)
def get_currencies() -> list[str]:
    return excel_store.list_currencies()
