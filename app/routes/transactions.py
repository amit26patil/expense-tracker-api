import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from google.genai import types

from app import s3_store as excel_store
from app.auth import UserModel, get_current_user
from app.models import (
    BulkTransactionCreate,
    BulkTransactionResponse,
    Transaction,
    TransactionCreate,
    TransactionUpdate,
)
from app.routes.upload import get_or_create_session, runner

router = APIRouter(
    prefix="/api/transactions",
    tags=["transactions"],
    dependencies=[Depends(get_current_user)],
)



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
    user: UserModel = Depends(get_current_user),
) -> list[Transaction]:
    return excel_store.list_transactions(user.email, year=year, month=month, day=day)


@router.get(
    "/{tx_id}",
    response_model=Transaction,
    summary="Get transaction by ID",
    description="Retrieve a single transaction by its ID.",
    responses={404: {"description": "Transaction not found"}},
)
def get_transaction(tx_id: str, user: UserModel = Depends(get_current_user)) -> Transaction:
    tx = excel_store.get_transaction(user.email, tx_id)
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
def create_transaction(payload: TransactionCreate, user: UserModel = Depends(get_current_user)) -> Transaction:
    return excel_store.create_transaction(user.email, payload)


@router.post(
    "/bulk",
    response_model=BulkTransactionResponse,
    status_code=201,
    summary="Create transactions in bulk",
    description="Create multiple expense or income transactions at once.",
)
def create_bulk_transactions(payload: BulkTransactionCreate, user: UserModel = Depends(get_current_user)) -> BulkTransactionResponse:
    if not payload.transactions:
        return BulkTransactionResponse(count=0, transactions=[])
    return excel_store.create_bulk_transactions(user.email, payload.transactions)


@router.put(
    "/{tx_id}",
    response_model=Transaction,
    summary="Update a transaction",
    description="Update an existing transaction by its ID.",
    responses={404: {"description": "Transaction not found"}},
)
def update_transaction(tx_id: str, payload: TransactionUpdate, user: UserModel = Depends(get_current_user)) -> Transaction:
    tx = excel_store.update_transaction(user.email, tx_id, payload)
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
def delete_transaction(tx_id: str, user: UserModel = Depends(get_current_user)) -> None:
    if not excel_store.delete_transaction(user.email, tx_id):
        raise HTTPException(status_code=404, detail="Transaction not found")


# ---------------------------------------------------------------------------
# Categorize Transactions
# ---------------------------------------------------------------------------

class TransactionLine(BaseModel):
    id: str
    to: str = ""
    comments: str = ""
    withdrawal: float = 0.0


class CategorizeRequest(BaseModel):
    transactions: list[TransactionLine]
    categories: str


class CategorizedTransaction(BaseModel):
    index: int
    category: str


def _build_categorize_prompt(transactions: list[TransactionLine], categories: str) -> str:
    lines = []
    for t in transactions:
        lines.append(f"{t.id}. To: {t.to or 'N/A'}, Comments: {t.comments}, Amount: {t.withdrawal}")

    transaction_block = "\n".join(lines)

    return (
        "You are a personal-finance categorizer.\n"
        "Categorize each transaction below into one of the listed categories.\n\n"
        f"Categories: {categories}\n\n"
        f"Transactions:\n{transaction_block}\n\n"
        "Return ONLY a JSON array of objects, each with:\n"
        '  "index": the original transaction id (1-based)\n'
        '  "category": one of the category names from the list\n\n'
        "No markdown, no explanation, only the JSON array."
    )


async def _categorize_with_llm(
    transactions: list[TransactionLine],
    categories: str,
) -> list[CategorizedTransaction]:
    user_id = "categorize_user"
    session_id = "categorize_session"

    await get_or_create_session(user_id, session_id)

    prompt = _build_categorize_prompt(transactions, categories)

    message = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )

    final_text = ""
    events = runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    )
    for event in events:
        if event.is_final_response():
            final_text = event.content.parts[0].text
            break
    
    print(f"LLM final response: {final_text}")
    # Extract JSON array from the response (handles markdown code-fences)
    match = re.search(r"\[.*\]", final_text, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail="LLM returned invalid response")

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON response")

    return [CategorizedTransaction(index=item["index"], category=item["category"]) for item in parsed]


@router.post(
    "/categorize",
    response_model=list[CategorizedTransaction],
    summary="Categorize transactions using LLM",
    description=(
        "Accepts a batch of transaction lines and a category list. "
        "Returns each transaction mapped to a category via LLM inference."
    ),
)
async def categorize_transactions(payload: CategorizeRequest) -> list[CategorizedTransaction]:
    if not payload.transactions:
        return []

    return await _categorize_with_llm(payload.transactions, payload.categories)
