from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import google_sheet_store as excel_store
from app.models import CategoryCreate, CategoryUpdate, CurrencySetting

router = APIRouter(prefix="/api", tags=["meta"])


@router.get(
    "/categories",
    summary="List categories",
    description="Retrieve all transaction categories, optionally filtered by type (income/expense).",
)
def get_categories(type: Optional[str] = Query(default=None, description="Filter by type: income or expense")) -> list[dict[str, str]]:
    return excel_store.list_categories(tx_type=type)


@router.post(
    "/categories",
    summary="Create a category",
    description="Add a new transaction category.",
)
def create_category(payload: CategoryCreate) -> dict[str, str]:
    result = excel_store.create_category(payload.name, payload.type.value, payload.keywords or "")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put(
    "/categories/{old_name}",
    summary="Update a category",
    description="Update an existing transaction category name.",
)
def update_category(old_name: str, payload: CategoryUpdate, type: str = Query(..., description="Category type: income or expense")) -> dict[str, str]:
    result = excel_store.update_category(old_name, payload.name, type, payload.keywords)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete(
    "/categories/{name}",
    summary="Delete a category",
    description="Delete a transaction category.",
)
def delete_category(name: str, type: str = Query(..., description="Category type: income or expense")) -> bool:
    deleted = excel_store.delete_category(name, type)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")
    return deleted


@router.get(
    "/currencies",
    summary="List currencies",
    description="Retrieve all supported currency codes.",
)
def get_currencies() -> list[str]:
    return excel_store.list_currencies()


@router.get(
    "/settings/currency",
    summary="Get default currency",
    description="Retrieve the default currency for all transactions.",
)
def get_default_currency() -> dict[str, str]:
    currency = excel_store.get_default_currency()
    return {"currency": currency}


@router.put(
    "/settings/currency",
    summary="Set default currency",
    description="Update the default currency for all transactions.",
)
def set_default_currency(payload: CurrencySetting) -> dict[str, str]:
    currency = excel_store.set_default_currency(payload.currency.value)
    return {"currency": currency}
