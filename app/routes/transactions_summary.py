from collections import defaultdict

from fastapi import APIRouter, Depends, Query

from app import s3_store as excel_store
from app.auth import UserModel, get_current_user
from app.models import (
    CategoryDetail,
    DaySummary,
    MonthDetail,
    MonthSummary,
    Transaction,
    TransactionType,
)

summary_router = APIRouter(
    prefix="/api/transaction-summary",
    tags=["transaction_summary"],
    dependencies=[Depends(get_current_user)],
)


@summary_router.get(
    "/summary/month",
    response_model=MonthSummary,
    summary="Monthly summary",
    description="Get a summary of all transactions for a given month, including totals by category and daily breakdowns.",
)
def get_month_summary(
    year: int = Query(..., ge=2000, description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    user: UserModel = Depends(get_current_user),
) -> MonthSummary:
    transactions = excel_store.list_transactions(user.email, year=year, month=month)

    total_income: dict[str, float] = defaultdict(float)
    total_expense: dict[str, float] = defaultdict(float)
    by_category: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_day: dict[str, list[Transaction]] = defaultdict(list)

    for tx in transactions:
        by_day[tx.date.isoformat()].append(tx)
        bucket = by_category[tx.category]
        if tx.type == TransactionType.INCOME:
            total_income[tx.currency.value] += tx.amount
            bucket[f"income_{tx.currency.value}"] += tx.amount
        else:
            total_expense[tx.currency.value] += tx.amount
            bucket[f"expense_{tx.currency.value}"] += tx.amount

    currencies = set(total_income) | set(total_expense)
    net = {c: total_income.get(c, 0.0) - total_expense.get(c, 0.0) for c in currencies}

    days: list[DaySummary] = []
    for day_key in sorted(by_day.keys()):
        day_txs = by_day[day_key]
        day_income: dict[str, float] = defaultdict(float)
        day_expense: dict[str, float] = defaultdict(float)
        for tx in day_txs:
            if tx.type == TransactionType.INCOME:
                day_income[tx.currency.value] += tx.amount
            else:
                day_expense[tx.currency.value] += tx.amount
        days.append(
            DaySummary(
                date=day_txs[0].date,
                income=dict(day_income),
                expense=dict(day_expense),
                transactions=day_txs,
            )
        )

    return MonthSummary(
        year=year,
        month=month,
        total_income=dict(total_income),
        total_expense=dict(total_expense),
        net=dict(net),
        by_category={k: dict(v) for k, v in by_category.items()},
        days=days,
    )


@summary_router.get(
    "/detail/monthly",
    response_model=MonthDetail,
    summary="Monthly detail by category",
    description="Get a detailed breakdown of transactions for a given month, grouped by category with per-category totals.",
)
def get_month_detail(
    year: int = Query(..., ge=2000, description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    user: UserModel = Depends(get_current_user),
) -> MonthDetail:
    transactions = excel_store.list_transactions(user.email, year=year, month=month)

    total_income: dict[str, float] = defaultdict(float)
    total_expense: dict[str, float] = defaultdict(float)
    grouped: dict[str, dict[str, list[Transaction]]] = defaultdict(lambda: defaultdict(list))

    for tx in transactions:
        grouped[tx.category][tx.type.value].append(tx)
        if tx.type == TransactionType.INCOME:
            total_income[tx.currency.value] += tx.amount
        else:
            total_expense[tx.currency.value] += tx.amount

    currencies = set(total_income) | set(total_expense)
    net = {c: total_income.get(c, 0.0) - total_expense.get(c, 0.0) for c in currencies}

    by_category: list[CategoryDetail] = []
    for category_name, types in sorted(grouped.items()):
        for tx_type in ["income", "expense"]:
            txs = types.get(tx_type, [])
            if not txs:
                continue
            totals: dict[str, float] = defaultdict(float)
            for tx in txs:
                totals[tx.currency.value] += tx.amount
            by_category.append(
                CategoryDetail(
                    category=category_name,
                    type=TransactionType(tx_type),
                    totals=dict(totals),
                    count=len(txs),
                    transactions=txs,
                )
            )

    return MonthDetail(
        year=year,
        month=month,
        total_income=dict(total_income),
        total_expense=dict(total_expense),
        net=dict(net),
        by_category=by_category,
    )
