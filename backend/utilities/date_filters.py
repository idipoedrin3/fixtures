from datetime import date, timedelta
from django.utils import timezone
import calendar

from items.models import FiscalYear


class TimePeriod:
    """Defines standard keys for relative date filtering."""

    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    LAST_7_DAYS = "LAST_7_DAYS"
    FORTNIGHT = "FORTNIGHT"
    THIS_WEEK = "THIS_WEEK"
    LAST_WEEK = "LAST_WEEK"
    THIS_MONTH = "THIS_MONTH"
    LAST_MONTH = "LAST_MONTH"
    THIS_QUARTER = "THIS_QUARTER"
    LAST_QUARTER = "LAST_QUARTER"
    THIS_YEAR = "THIS_YEAR"
    LAST_YEAR = "LAST_YEAR"
    FISCAL_YEAR = "FISCAL_YEAR"


# --- Pure Date Calculation Utility (Layer 1: The Calculator) ---


def _get_start_and_end_of_month(target_date):
    """Utility to get the first and last day of a month."""
    start_of_month = target_date.replace(day=1)
    _, num_days = calendar.monthrange(target_date.year, target_date.month)
    end_of_month = target_date.replace(day=num_days)
    return start_of_month, end_of_month


def calculate_date_range(period_key, reference_date=None):
    """
    Calculates the start and end dates for STANDARD time periods.
    Does NOT handle FISCAL periods.
    """
    today = reference_date if reference_date else date.today()
    period_key = period_key.upper()
    start_date, end_date = None, None

    # --- Absolute and Rolling Periods ---
    if period_key == TimePeriod.TODAY:
        start_date, end_date = today, today

    elif period_key == TimePeriod.YESTERDAY:
        yesterday = today - timedelta(days=1)
        start_date, end_date = yesterday, yesterday

    elif period_key == TimePeriod.LAST_7_DAYS:
        start_date = today - timedelta(days=6)
        end_date = today

    elif period_key == TimePeriod.FORTNIGHT:
        start_date = today - timedelta(days=13)
        end_date = today

    # --- Weekly Periods (Assumes week starts Monday, 0) ---
    elif period_key == TimePeriod.THIS_WEEK:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

    elif period_key == TimePeriod.LAST_WEEK:
        last_week_end = today - timedelta(days=today.weekday() + 1)
        last_week_start = last_week_end - timedelta(days=6)
        start_date, end_date = last_week_start, last_week_end

    # --- Monthly Periods ---
    elif period_key == TimePeriod.THIS_MONTH:
        start_date, _ = _get_start_and_end_of_month(today)
        end_date = today  # Use today as the end date for the current period

    elif period_key == TimePeriod.LAST_MONTH:
        first_day_of_this_month = today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
        start_date, end_date = _get_start_and_end_of_month(last_day_of_last_month)

    # --- Quarterly Periods ---
    elif period_key == TimePeriod.THIS_QUARTER:
        current_month = today.month
        quarter_start_month = ((current_month - 1) // 3) * 3 + 1
        start_date = date(today.year, quarter_start_month, 1)
        end_date = today  # End is today for the current period

    elif period_key == TimePeriod.LAST_QUARTER:
        current_month = today.month
        quarter_start_month = ((current_month - 1) // 3) * 3 + 1
        current_quarter_start = date(today.year, quarter_start_month, 1)
        last_quarter_end = current_quarter_start - timedelta(days=1)
        last_quarter_start_month = ((last_quarter_end.month - 1) // 3) * 3 + 1
        start_date = date(last_quarter_end.year, last_quarter_start_month, 1)
        end_date = last_quarter_end

    # --- Yearly Periods ---
    elif period_key == TimePeriod.THIS_YEAR:
        start_date = today.replace(month=1, day=1)
        end_date = today

    elif period_key == TimePeriod.LAST_YEAR:
        last_year = today.year - 1
        start_date = date(last_year, 1, 1)
        end_date = date(last_year, 12, 31)

    return start_date, end_date


# --- THE CORE REUSABLE FILTER UTILITY (Layer 2: Lookup and Query) ---


def apply_date_period_filter(
    queryset,
    field_name,
    institution_id,
    period_key=None,
    date_from=None,
    date_to=None,
    fiscal_year_model=None,
):
    start_date, end_date = None, None
    today = timezone.now()

    # Handle FISCAL Periods (Database Lookup using is_current)
    if period_key == TimePeriod.FISCAL_YEAR:
        if not fiscal_year_model:
            print("ERROR: FISCAL_YEAR requested but no fiscal_year_model provided.")
            return queryset.none()

        # Lookup the active FiscalYear for the specific institution
        fiscal_object = FiscalYear.objects.filter(
            institution__id=institution_id, is_current=True
        ).first()

        if fiscal_object:
            # Filter from the Fiscal Year start date up to today (for current period)
            start_date = fiscal_object.start_date.isoformat()
            end_date = today.isoformat()
        else:
            print(
                f"Warning: No current Fiscal Year found for institution {institution_id}."
            )
            return queryset.none()

    # Handle Standard Periods (Pure Calculation)
    elif period_key:
        calculated_start, calculated_end = calculate_date_range(period_key, today)
        start_date = calculated_start.isoformat() if calculated_start else None
        end_date = calculated_end.isoformat() if calculated_end else None

    # Handle Explicit Dates (Fallback)
    else:
        start_date = date_from
        end_date = date_to

    # Apply filters dynamically
    if start_date:
        queryset = queryset.filter(**{f"{field_name}__gte": start_date})

    if end_date:
        queryset = queryset.filter(**{f"{field_name}__lte": end_date})

    return queryset
