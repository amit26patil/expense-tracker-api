from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"


class TransactionCreate(BaseModel):
    date: date
    type: TransactionType
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    currency: Currency
    description: str = ""


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    type: Optional[TransactionType] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[Currency] = None
    description: Optional[str] = None


class Transaction(BaseModel):
    id: int
    date: date
    type: TransactionType
    category: str
    amount: float
    currency: Currency
    description: str


class DaySummary(BaseModel):
    date: date
    income: dict[str, float]
    expense: dict[str, float]
    transactions: list[Transaction]


class MonthSummary(BaseModel):
    year: int
    month: int
    total_income: dict[str, float]
    total_expense: dict[str, float]
    net: dict[str, float]
    by_category: dict[str, dict[str, float]]
    days: list[DaySummary]


class CategoryDetail(BaseModel):
    category: str
    type: TransactionType
    totals: dict[str, float]
    count: int
    transactions: list[Transaction]


class MonthDetail(BaseModel):
    year: int
    month: int
    total_income: dict[str, float]
    total_expense: dict[str, float]
    net: dict[str, float]
    by_category: list[CategoryDetail]
