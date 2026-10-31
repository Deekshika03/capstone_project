from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class Transaction(BaseModel):
    date: date
    description: str
    amount: float
    type: str
    category: Optional[str] = "Other"
    source: Optional[str] = None

    @field_validator("type")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        v = v.strip().capitalize()
        if v not in ("Income", "Expense"):
            raise ValueError(f"type must be 'Income' or 'Expense', got '{v}'")
        return v

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str) -> str:
        return v.strip() or "Unknown"
