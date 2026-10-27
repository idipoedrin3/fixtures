from enum import Enum


class InventoryLogChangeTypeEnum(Enum):
    """
    Enum for Inventory Log Change Types.
    """

    PURCHASE = "purchase"
    SALE = "sale"
    ADDITION = "addition"
    REMOVAL = "removal"
    TRANSFER = "transfer"
    STOCKUPDATE = "stockupdate"


class TransactionTitle(Enum):
    LOAN_DISBURSEMENT = "Loan Disbursement"
    LOAN_REPAYMENT = "Loan Repayment"


class TransactionType(Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountType(Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class CashFlowClassification(Enum):
    INVESTING_ACTIVITIES = "INVESTING_ACTIVITIES"
    FINANCING_ACTIVITIES = "FINANCING_ACTIVITIES"
    OPERATING_ACTIVITIES = "OPERATING_ACTIVITIES"


class IncomeStatementClassification(Enum):
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class AccountGroup(Enum):
    CURRENT_ASSETS = "CURRENT_ASSETS"
    FIXED_ASSETS = "FIXED_ASSETS"
    CURRENT_LIABILITIES = "CURRENT_LIABILITIES"
    LONG_TERM_LIABILITIES = "LONG_TERM_LIABILITIES"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"
