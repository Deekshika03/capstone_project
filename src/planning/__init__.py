"""
Planning package for Financial Friend AI.
Includes bill tracking, recurring EMI detection, cash outflow projection, and alert system.
"""

from src.planning.bill_tracker import (
    AlertPriority,
    BillAlert,
    BillCategory,
    BillTracker,
    CashOutflowProjection,
    RecurringBill,
    UpcomingPayment,
    calculate_projected_cash_outflow,
    calculate_upcoming_payments,
    detect_recurring_bills,
    generate_priority_alerts,
    generate_simulated_transactions,
)

__all__ = [
    "AlertPriority",
    "BillAlert",
    "BillCategory",
    "BillTracker",
    "CashOutflowProjection",
    "RecurringBill",
    "UpcomingPayment",
    "calculate_projected_cash_outflow",
    "calculate_upcoming_payments",
    "detect_recurring_bills",
    "generate_priority_alerts",
    "generate_simulated_transactions",
]
