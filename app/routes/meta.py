from typing import Optional

from fastapi import APIRouter, Query

from app import google_sheet_store as excel_store

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/categories")
def get_categories(type: Optional[str] = Query(default=None)) -> list[dict[str, str]]:
    return excel_store.list_categories(tx_type=type)


@router.get("/currencies")
def get_currencies() -> list[str]:
    return excel_store.list_currencies()

@router.get("/currencies1")
def get_currencies1() -> dict[str, str]:
    return excel_store.list_currencies()
