from datetime import date, datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"


def _parse_date(value: Union[str, date]) -> date:
    if isinstance(value, date):
        return value
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {value!r}")


class TransactionCreate(BaseModel):
    date: Union[str, date]
    type: TransactionType
    category: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    currency: Currency
    description: str = ""

    @field_validator("date", mode="before")
    @classmethod
    def coerce_date(cls, v: Union[str, date]) -> date:
        return _parse_date(v)


class TransactionUpdate(BaseModel):
    date: Optional[Union[str, date]] = None
    type: Optional[TransactionType] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    amount: Optional[float] = Field(default=None, gt=0)
    currency: Optional[Currency] = None
    description: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def coerce_date(cls, v: Union[str, date, None]) -> Optional[date]:
        if v is None:
            return None
        return _parse_date(v)


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


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: TransactionType
    keywords: Optional[str] = ""


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    keywords: Optional[str] = None


class CurrencySetting(BaseModel):
    currency: Currency


class BulkTransactionCreate(BaseModel):
    transactions: list[TransactionCreate]


class BulkTransactionResponse(BaseModel):
    count: int
    transactions: list[Transaction]
