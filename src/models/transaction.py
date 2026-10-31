from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class Transaction(BaseModel):
    date: date
    amount: float
    type: str                    # "debit" or "credit"
    description: str
    balance: Optional[float] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"debit", "credit"}:
            raise ValueError(f"type must be 'debit' or 'credit', got '{v}'")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("amount must be non-negative")
        return v

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "amount": self.amount,
            "type": self.type,
            "description": self.description,
            "balance": self.balance,
        }
