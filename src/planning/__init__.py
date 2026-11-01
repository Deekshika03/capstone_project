"""
Planning package for Financial Friend AI.
Includes bill tracking, recurring EMI detection, cash outflow projection,
alert system, and emergency fund planner.
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

from src.planning.emergency_fund import (
    ActionStep,
    EmergencyCorpus,
    ExpenseProfile,
    FundGap,
    MilestoneReport,
    analyse_fund_gap,
    build_expense_profile,
    compute_emergency_corpus,
    generate_action_steps,
    generate_milestone_report,
)

__all__ = [
    # bill_tracker
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
    # emergency_fund
    "ActionStep",
    "EmergencyCorpus",
    "ExpenseProfile",
    "FundGap",
    "MilestoneReport",
    "analyse_fund_gap",
    "build_expense_profile",
    "compute_emergency_corpus",
    "generate_action_steps",
    "generate_milestone_report",
]
