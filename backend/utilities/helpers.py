import datetime
import re
from urllib.parse import urlparse
from django.utils import timezone
from django.http import HttpResponseForbidden
from functools import wraps
import secrets
import hashlib
from .email_client import EmailClient
from users.models import OneTimePassword
from django.core.mail import send_mail
from django.conf import settings
import logging
from urllib.parse import urlparse
import secrets
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
import datetime
from datetime import date as dt_date, timedelta
from django.utils.timezone import now
from decimal import Decimal
from system.exceptions import SystemValidationError
import pandas as pd
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import uuid
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db import IntegrityError, transaction
import pytz
from typing import Any, Mapping
import json

logger = logging.getLogger(__name__)


def quantize_decimal(
    value,
    decimal_places: int = 20,
    rounding=ROUND_HALF_UP,
) -> Decimal:
    value = Decimal(str(value))

    precision = Decimal("1").scaleb(-decimal_places)

    return value.quantize(
        precision,
        rounding=rounding,
    )


def format_currency(value, symbol: str = "") -> str:
    if value is None:
        return f"{symbol}0.00"
    try:
        return f"{symbol}{Decimal(str(value)):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return f"{symbol}{value}"


def format_currency_numbers_in_text(value: str) -> str:
    if not value:
        return value

    return re.sub(
        r"(?<![\w.,])[-+]?\d+\.\d+(?![\w.,])",
        lambda match: format_currency(match.group()),
        value,
    )


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def normalize_url(url):
    if not url:
        return None
    url = url.strip()

    if not urlparse(url).scheme:
        if url.startswith("www."):
            url = "http://" + url
        else:
            url = "http://" + url

    return url


def get_institution_timezone(institution=None):
    if institution and institution.timezone:
        try:
            return pytz.timezone(institution.timezone)
        except pytz.UnknownTimeZoneError:
            pass

    return pytz.timezone(settings.TIME_ZONE)


MAX_PAYMENT_TERM_DAYS = 18250
MAX_DATE = datetime.date(9999, 12, 31)


def _validate_payment_term_days(days: int, field_name: str = "Payment term") -> None:
    if not isinstance(days, int) or isinstance(days, bool):
        raise validation_error(
            f"{field_name} must be a whole number between 0 and 18,250 days (50 years)."
        )
    if days < 0 or days > MAX_PAYMENT_TERM_DAYS:
        raise validation_error(
            f"{field_name} must be a whole number between 0 and 18,250 days (50 years)."
        )


def _validate_due_date_not_exceed_max(
    issue_date: datetime.date, days: int, context: str = ""
) -> None:
    message = (
        f"This setting produces a date beyond the supported date range. "
        f"Update {context} or correct the issue date."
        if context
        else (
            "This payment term produces a due date beyond the supported date range. "
            "Reduce the payment term or correct the issue date."
        )
    )
    try:
        due_date = issue_date + timedelta(days=days)
    except OverflowError:
        raise validation_error(message)
    if due_date > MAX_DATE:
        raise validation_error(message)


def get_due_date_based_on_payment_terms(payment_term, issue_date: datetime.date = None):
    if issue_date is None:
        issue_date = timezone.now().date()

    if payment_term is not None:
        days_from_issue_date = payment_term.days_until_due
        _validate_payment_term_days(days_from_issue_date, "Payment term")
        _validate_due_date_not_exceed_max(issue_date, days_from_issue_date)
    else:
        days_from_issue_date = 0

    return issue_date + timedelta(days=days_from_issue_date)


def format_2dp(value: float) -> str:
    return f"{value:.2f}"


class UUIDRelatedField(serializers.PrimaryKeyRelatedField):
    def __init__(self, queryset, uuid_field="base_uuid", **kwargs):
        self.uuid_field = uuid_field
        kwargs["pk_field"] = serializers.UUIDField()
        super().__init__(queryset=queryset, **kwargs)

    def to_internal_value(self, data):
        try:
            return self.get_queryset().get(**{self.uuid_field: data})
        except self.get_queryset().model.DoesNotExist:
            raise validation_error(f"Object with UUID {data} does not exist.")


def to_money_decimal(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError):
        d = Decimal("0")
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BaseReportFilterSerializer(serializers.Serializer):
    date_fields = {}

    date_field = serializers.ChoiceField(
        choices=[],
        required=False,
    )
    start_date = serializers.DateField(
        required=False,
    )
    end_date = serializers.DateField(
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.date_fields:
            self.fields["date_field"].choices = [
                (name, label) for name, (label, _) in self.date_fields.items()
            ]
        else:
            self.fields.pop("date_field", None)
            self.fields.pop("start_date", None)
            self.fields.pop("end_date", None)

    def to_internal_value(self, data):
        cleaned_data = {
            key: value
            for key, value in data.items()
            if value is not None and value != ""
        }
        return super().to_internal_value(cleaned_data)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and not end_date:
            end_date = timezone.localdate()
            attrs["end_date"] = end_date

        if (start_date or end_date) and not attrs.get("date_field"):
            raise validation_error({"date_field": "Select the date field to filter."})

        if start_date and end_date and start_date > end_date:
            raise validation_error(
                {"end_date": "End date must be greater than or equal to start date."}
            )

        return attrs

    def filter_queryset(self, queryset):
        filters = dict(self.validated_data)

        date_field = filters.pop("date_field", None)
        start_date = filters.pop("start_date", None)
        end_date = filters.pop("end_date", None)

        queryset = queryset.filter(**filters)

        if not date_field:
            return queryset

        lookup = self.date_fields[date_field][1]

        if start_date:
            queryset = queryset.filter(**{f"{lookup}__gte": start_date})

        if end_date:
            queryset = queryset.filter(**{f"{lookup}__lte": end_date})

        return queryset


def validation_error(message, field=None, code="validation_error"):
    def clean_message(val):
        if isinstance(val, ErrorDetail):
            return str(val)
        elif isinstance(val, (list, tuple)):
            return ", ".join(clean_message(v) for v in val)
        elif isinstance(val, dict):
            parts = []
            for k, v in val.items():
                parts.append(clean_message(v))
            return ", ".join(parts)
        return str(val)

    def flatten_errors(msg, parent_field=None):
        errors = []
        if isinstance(msg, dict):
            for k, v in msg.items():
                if isinstance(v, dict):
                    nested = flatten_errors(v)
                    for e in nested:
                        field_name = f"{k}.{e['field']}" if e.get("field") else k
                        entry = {"field": field_name, "message": e["message"]}
                        errors.append(entry)
                elif isinstance(v, (list, tuple)):
                    for item in v:
                        errors.append({"field": k, "message": clean_message(item)})
                else:
                    errors.append({"field": k, "message": clean_message(v)})
        elif isinstance(msg, (list, tuple)):
            for item in msg:
                entry = {"message": clean_message(item)}
                if parent_field:
                    entry["field"] = parent_field
                errors.append(entry)
        else:
            entry = {"message": clean_message(msg)}
            if parent_field:
                entry["field"] = parent_field
            errors.append(entry)
        return errors

    if isinstance(message, dict):
        errors_list = flatten_errors(message)
    elif field:
        errors_list = [{"field": field, "message": clean_message(message)}]
    else:
        errors_list = [{"message": clean_message(message)}]

    detail = {
        "success": False,
        "error_summary": "Validation error",
        "errors": errors_list,
    }

    raise SystemValidationError(detail=detail, code=code)


def serialize_value(val):
    from uuid import UUID
    from decimal import Decimal
    import datetime
    from django.db.models import Model
    from django.db.models.fields.files import FieldFile
    from django.core.files.uploadedfile import InMemoryUploadedFile

    if val is None:
        return None
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime.date, datetime.datetime, datetime.time)):
        return val.isoformat()
    if isinstance(val, Model):
        return str(val.pk)
    if isinstance(val, FieldFile):
        return val.name or ""
    if isinstance(val, dict):
        return {k: serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [serialize_value(v) for v in val]
    if isinstance(val, InMemoryUploadedFile):
        return {
            "filename": val.name,
            "content_type": val.content_type,
            "size": val.size,
        }
    return val


def parse_json_or_dict(item):
    import json

    if isinstance(item, str):
        return json.loads(item)
    return item


def generate_unique_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def has_access(user, institution, permission_code, profile_institution=None):
    if not user or not user.is_authenticated or not institution:
        return False

    if institution.institution_owner_id == user.id:
        return True

    if profile_institution is None:
        return False

    if profile_institution.institution_id != institution.id:
        return False

    if profile_institution.profile.user_id != user.id:
        return False

    return user.has_system_perm(permission_code, profile_institution)


def split_period_by_frequency(start_date: dt_date, end_date: dt_date, frequency: str):
    periods = []
    current = start_date

    while current <= end_date:
        if frequency == "DAILY":
            next_date = current
        elif frequency == "WEEKLY":
            next_date = current + timedelta(days=6)
        elif frequency == "MONTHLY":
            next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
            next_date = next_month - timedelta(days=1)
        elif frequency == "ANNUALLY":
            next_date = end_date
        else:
            raise ValueError("Invalid frequency")

        period_end = min(next_date, end_date)
        periods.append((current, period_end))
        current = period_end + timedelta(days=1)

    return periods


def get_fiscal_year(
    institution,
    date=None,
):
    from items.models import FiscalYear

    date = date or now().date()
    fiscal_start_month = institution.fiscal_year_start_month or 1

    fiscal_year = FiscalYear.objects.filter(
        institution=institution,
        start_date__lte=date,
        end_date__gte=date,
    ).first()
    if fiscal_year:
        return fiscal_year

    year = date.year
    if date.month < fiscal_start_month:
        year -= 1

    fiscal_year_start = dt_date(year, fiscal_start_month, 1)
    fiscal_year_end = fiscal_year_start + relativedelta(years=1) - timedelta(days=1)
    fiscal_year_name = f"{fiscal_year_start.year}/{fiscal_year_end.year}"

    try:
        with transaction.atomic():
            fiscal_year, _ = FiscalYear.objects.get_or_create(
                institution=institution,
                name=fiscal_year_name,
                defaults={
                    "start_date": fiscal_year_start,
                    "end_date": fiscal_year_end,
                    "is_current": (
                        True
                        if not FiscalYear.objects.filter(
                            institution=institution, is_current=True
                        ).exists()
                        else False
                    ),
                    "is_closed": False,
                },
            )
    except IntegrityError:
        fiscal_year = FiscalYear.objects.get(
            institution=institution, name=fiscal_year_name
        )

    if not fiscal_year.is_current:
        FiscalYear.objects.filter(institution=institution, is_current=True).update(
            is_current=False
        )
        fiscal_year.is_current = True
        fiscal_year.save()

    return fiscal_year


def resolve_reporting_period(
    institution, fiscal_year=None, start_date=None, end_date=None
):
    if fiscal_year:
        if fiscal_year.institution != institution:
            validation_error(
                "Fiscal year does not belong to the specified institution."
            )
        return fiscal_year.start_date, fiscal_year.end_date

    if start_date and end_date:
        return start_date, end_date

    raise validation_error(
        "You must provide a fiscal_year, or both start_date and end_date."
    )


def get_institution(request):
    return getattr(request, "institution", None)


def permission_required(perm_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.has_permission(
                perm_name
            ):
                return HttpResponseForbidden("Forbidden")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def get_date_range_from_filter(filter_key, institution=None):
    today = timezone.localdate()
    start = end = None

    if filter_key == "all":
        return None, None

    if filter_key == "today":
        start = end = today

    elif filter_key == "yesterday":
        start = end = today - timedelta(days=1)

    elif filter_key == "this_week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    elif filter_key == "this_week_to_date":
        start = today - timedelta(days=today.weekday())
        end = today

    elif filter_key == "last_week":
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)

    elif filter_key == "last_week_to_date":
        start = today - timedelta(days=today.weekday() + 7)
        end = today - timedelta(days=today.weekday() + 1)

    elif filter_key == "this_month":
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)

    elif filter_key == "this_month_to_date":
        start = today.replace(day=1)
        end = today

    elif filter_key == "last_month":
        start = today.replace(day=1) - relativedelta(months=1)
        end = today.replace(day=1) - timedelta(days=1)

    elif filter_key == "last_month_to_date":
        start = today.replace(day=1) - relativedelta(months=1)
        last_day_of_last_month = (today.replace(day=1) - timedelta(days=1)).day
        end_day = min(today.day, last_day_of_last_month)
        end = start.replace(day=end_day)

    elif filter_key == "this_year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)

    elif filter_key == "this_year_to_date":
        start = today.replace(month=1, day=1)
        end = today

    elif filter_key == "last_year":
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)

    elif filter_key == "last_year_to_date":
        start = today.replace(year=today.year - 1, month=1, day=1)
        try:
            end = today.replace(year=today.year - 1)
        except ValueError:
            end = today.replace(year=today.year - 1, day=28)

    elif (
        filter_key
        in {
            "this_fiscal_year",
            "this_fiscal_year_to_date",
            "this_fiscal_year_to_last_month",
            "last_fiscal_year",
            "last_fiscal_year_to_date",
        }
        and institution
    ):

        fiscal_year = get_fiscal_year(institution, today)

        if filter_key == "this_fiscal_year" and fiscal_year:
            start, end = fiscal_year.start_date, fiscal_year.end_date

        elif filter_key == "this_fiscal_year_to_date" and fiscal_year:
            start, end = fiscal_year.start_date, today

        elif filter_key == "this_fiscal_year_to_last_month" and fiscal_year:
            start = fiscal_year.start_date
            end = today.replace(day=1) - timedelta(days=1)

        elif filter_key == "last_fiscal_year" and fiscal_year:
            start = fiscal_year.start_date - relativedelta(years=1)
            end = fiscal_year.end_date - relativedelta(years=1)

        elif filter_key == "last_fiscal_year_to_date" and fiscal_year:
            start = fiscal_year.start_date - relativedelta(years=1)
            last_fy_end = fiscal_year.end_date - relativedelta(years=1)
            end = min(today - relativedelta(years=1), last_fy_end)

    elif filter_key == "current_fiscal_year" and institution:
        fiscal_year = get_fiscal_year(institution, today)
        if fiscal_year:
            start, end = fiscal_year.start_date, fiscal_year.end_date

    return start, end


def generate_otp(length=6):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_otp(user_id, otp):
    raw_string = f"{user_id}-{otp}"
    return hashlib.sha256(raw_string.encode()).hexdigest()


def create_and_institution_otp(user_id, purpose=None, expiry_minutes=15):
    otp = generate_otp()
    otp_hash = hash_otp(user_id, otp)

    expiry_time = timezone.now() + datetime.timedelta(minutes=expiry_minutes)

    if purpose:
        cleanup_existing_otps(user_id, purpose)

    OneTimePassword.objects.create(
        value=otp_hash, expires_at=expiry_time, purpose=purpose
    )

    return otp


def cleanup_existing_otps(user_id, purpose):
    if purpose:
        OneTimePassword.objects.filter(purpose=purpose, is_used=False).delete()


def cleanup_expired_otps():
    """
    Utility function to clean up expired OTPs
    This can be called periodically via a scheduled task
    """
    now = timezone.now()
    deleted_count, _ = OneTimePassword.objects.filter(expires_at__lt=now).delete()
    return deleted_count


def verify_otp(identifier, received_otp):
    otp_hash = hash_otp(identifier, received_otp)
    logger.debug(f"Verifying OTP hash: {otp_hash}")

    try:
        otp_entry = OneTimePassword.objects.get(value=otp_hash, is_used=False)

        if otp_entry.is_expired():
            logger.warning(f"OTP expired for hash: {otp_hash}")
            return False, "OTP has expired"

        otp_entry.delete()
        logger.info(f"OTP verified and deleted successfully for hash: {otp_hash}")
        return True, "OTP verified successfully"

    except OneTimePassword.DoesNotExist:
        logger.warning(f"Invalid OTP attempt with hash: {otp_hash}")
        return False, "Invalid OTP"


def send_plain_email(receivers, subject, body, fail_silently=False):
    """
    Send plain text email to list of receivers using Gmail SMTP

    Args:
        receivers: List of email addresses or single email address as string
        subject: Email subject
        body: Plain text email body
        fail_silently: If True, exceptions will be suppressed

    Returns:
        Number of successfully sent emails (0 or 1)
    """
    if isinstance(receivers, str):
        receivers = [receivers]

        num_sent = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=receivers,
            fail_silently=fail_silently,
        )

        if num_sent > 0:
            logger.info(f"Email sent to {receivers} with subject: {subject}")
        else:
            logger.warning(f"Email failed to send to {receivers}")

        return num_sent


def send_otp_to_user(user, otp):
    subject = "Verify Your Account"

    context = {
        "fullname": user.fullname,
        "otp_code": otp,
        "year": datetime.datetime.now().year,
    }

    try:
        EmailClient.send(
            subject,
            [user.email],
            template_html="users/emails/signup_otp_verification.html",
            template_txt=None,
            context=context,
            attachments=None,
        )

        return True

    except Exception as e:
        logger.error(f"Error sending OTP email to {user.email}: {e}")
        return False


def build_password_link(request, token: str) -> str:
    frontend_origin = request.headers.get("Origin")
    if frontend_origin:
        parts = urlparse(frontend_origin)
        base_link = f"{parts.scheme}://{parts.netloc}"
    else:
        base_link = f"{request.scheme}://{request.get_host()}"

    return f"{base_link.rstrip('/')}/reset-password/{token}"


def create_and_institution_token(user, purpose="registration", expiry_minutes=5):
    from users.models import OneTimePassword

    token = secrets.token_urlsafe(32)

    OneTimePassword.objects.create(
        user=user,
        value=token,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )

    return token


def send_password_link_to_user(user, link):
    try:
        subject = "Set Your Password"
        context = {
            "link": link,
            "fullname": user.fullname,
            "year": datetime.datetime.now().year,
        }

        EmailClient.send(
            subject=subject,
            recipients=[user.email],
            template_html="institution/emails/signup_link_email.html",
            context=context,
        )

        return True
    except Exception as e:
        print("Error sending email:", e)
        return False


def to_uuid_str(obj):
    uuid_val = getattr(obj, "base_uuid", None)
    return str(uuid) if uuid_val is None else str(obj.id)


def send_password_reset_link_to_user(user, link):
    try:
        subject = "Set Your Password"
        context = {
            "link": link,
            "fullname": user.fullname,
            "year": datetime.datetime.now().year,
        }

        EmailClient.send(
            subject=subject,
            recipients=[user.email],
            template_html="forgot-password/password-reset.html",
            context=context,
        )

        return True
    except Exception as e:
        print("Error sending email:", e)
        return False


accounts_increased_by_debits = [
    "Asset",
    "Expense",
]

accounts_increased_by_credits = [
    "Liability",
    "Equity",
    "Revenue",
]


def calculate_line_item_tax(line_item, institution):
    """Calculates tax based on the applicable TaxRule."""

    subtotal = line_item.quantity * line_item.unit_price
    tax_amount = Decimal("0.00")
    tax_rate_for_total = Decimal(
        "0.00"
    )  # Not strictly necessary for total_amount, but useful for context

    if line_item.tax:
        # Find the applicable rule based on the subtotal range
        # This calls the method you provided on the TaxType model
        applicable_rule = line_item.tax.get_applicable_rule(subtotal, institution)

        if applicable_rule:
            rate = applicable_rule.tax_rate

            if applicable_rule.tax_method == "PERCENTAGE":
                tax_rate_for_total = rate / Decimal("100.00")
                tax_amount = subtotal * tax_rate_for_total

            elif applicable_rule.tax_method == "PER_UNIT":
                tax_amount = rate * line_item.quantity

            elif applicable_rule.tax_method == "FIXED_AMOUNT":
                tax_amount = rate

    return subtotal, tax_amount, tax_rate_for_total


def get_due_date(institution, payment_term=None, issue_date=None):
    if not institution:
        raise validation_error({"institution": "Institution is required"})

    if issue_date is None:
        issue_date = timezone.now().date()

    days_from_issue_date = (
        payment_term.days_until_due
        if payment_term
        else institution.default_invoice_due_days
    )

    if payment_term:
        _validate_payment_term_days(days_from_issue_date, "Payment term")
    else:
        _validate_payment_term_days(
            days_from_issue_date, "Institution default invoice due days"
        )

    _validate_due_date_not_exceed_max(
        issue_date,
        days_from_issue_date,
        context="" if payment_term else "Institution default invoice due days",
    )

    return issue_date + timedelta(days=days_from_issue_date)


def get_quotation_expiry_date(institution, issue_date):
    if institution is None:
        raise validation_error({"institution": "Institution is required"})

    days = institution.quotation_default_expiry_days
    setting = "Institution quotation default expiry days"
    _validate_payment_term_days(days, setting)
    _validate_due_date_not_exceed_max(issue_date, days, context=setting)
    return issue_date + timedelta(days=days)


def create_and_store_token(user, purpose="registration", expiry_minutes=15):
    from users.models import OneTimePassword

    token = secrets.token_urlsafe(32)
    OneTimePassword.objects.create(
        user=user,
        value=token,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    )
    return token


DEFAULT_PRECISION = Decimal("0.000001")


def convert_currency(
    *,
    institution,
    target_currency,
    amount: Decimal,
    override_rate: Decimal | None = None,
    precision: Decimal = DEFAULT_PRECISION,
):

    if amount is None:
        raise validation_error("Amount is required for currency conversion.")

    try:
        amount = Decimal(amount)
    except Exception:
        raise validation_error("Invalid amount value.")

    institution_currency = institution.currency

    if not institution_currency:
        raise validation_error("Institution base currency is not configured.")

    if not target_currency or institution_currency == target_currency:
        return {
            "original_amount": amount,
            "converted_amount": amount,
            "rate": Decimal("1.000000"),
            "from_currency": institution_currency,
            "to_currency": institution_currency,
            "converted": False,
        }

    if override_rate is not None:
        try:
            rate = Decimal(override_rate)
        except Exception:
            raise validation_error("Invalid override exchange rate.")
    else:
        try:
            rate = institution.institution_supported_currencies.get(
                currency=target_currency
            ).rate
        except Exception:
            raise validation_error(
                f"{target_currency.code} is not supported by this institution."
            )

    if rate <= 0:
        raise validation_error("Exchange rate must be greater than zero.")

    operation = (
        target_currency.institution_currencies.filter(institution=institution)
        .first()
        .determine_operation(direction="from_base")
    )

    if operation == "multiply":
        converted_amount = (amount * rate).quantize(precision, rounding=ROUND_HALF_UP)
    elif operation == "divide":
        converted_amount = (amount / rate).quantize(precision, rounding=ROUND_HALF_UP)
    else:
        raise validation_error("Invalid operation.")

    return {
        "original_amount": amount,
        "converted_amount": converted_amount,
        "rate": rate,
        "from_currency": institution_currency,
        "to_currency": target_currency,
        "converted": True,
    }


def parse_bool_query_param(value: str | None, param_name: str) -> bool | None:
    if value is None:
        return None
    value_lower = value.lower()
    if value_lower == "true":
        return True
    elif value_lower == "false":
        return False
    else:
        raise SystemValidationError(
            f"Only 'true' or 'false' are allowed for {param_name}."
        )


STATEMENT_HEADER_ALIASES = {
    "transaction_date": {
        "date",
        "transactiondate",
        "postingdate",
        "valuedate",
    },
    "description": {
        "description",
        "transactiondescription",
        "details",
        "narration",
        "particulars",
        "memo",
    },
    "deposit": {
        "deposit",
        "deposits",
        "credit",
        "credits",
        "inflow",
        "moneyin",
        "paidin",
    },
    "withdrawal": {
        "withdrawal",
        "withdrawals",
        "debit",
        "debits",
        "outflow",
        "moneyout",
        "paidout",
    },
    "balance": {
        "balance",
        "runningbalance",
        "closingbalance",
        "availablebalance",
    },
    "reference_code": {
        "reference",
        "transactionreference",
        "transactionref",
        "ref",
        "refno",
        "referenceno",
    },
}

STATEMENT_HEADER_WEIGHTS = {
    "transaction_date": 3,
    "description": 3,
    "deposit": 2,
    "withdrawal": 2,
    "balance": 2,
    "reference_code": 1,
}


def normalize_statement_header(value):
    if pd.isna(value):
        return ""

    value = re.sub(r"\([^)]*\)", "", str(value).strip().lower())
    return re.sub(r"[^a-z0-9]", "", value)


def detect_statement_header_row(df, scan_limit=50):
    best_row_index = None
    best_score = -1

    for row_index, row in df.head(scan_limit).iterrows():
        normalized_values = {
            normalize_statement_header(value)
            for value in row.values
            if normalize_statement_header(value)
        }

        matched_fields = {
            field
            for field, aliases in STATEMENT_HEADER_ALIASES.items()
            if normalized_values.intersection(aliases)
        }

        has_date = "transaction_date" in matched_fields
        has_description = "description" in matched_fields
        has_amount = bool(
            matched_fields.intersection({"deposit", "withdrawal", "balance"})
        )

        if not (has_date and has_description and has_amount):
            continue

        score = sum(STATEMENT_HEADER_WEIGHTS[field] for field in matched_fields)

        if score > best_score:
            best_row_index = row_index
            best_score = score

    return best_row_index


def extract_file_columns(file_obj):
    filename = file_obj.name.lower()

    try:
        # The serializer may already have read or saved the uploaded file.
        file_obj.seek(0)

        if filename.endswith(".csv"):
            df = pd.read_csv(file_obj, header=None)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_obj, header=None)
        else:
            raise validation_error(
                "Unsupported statement file type. Upload a CSV, XLSX, or XLS file."
            )

        header_row_index = detect_statement_header_row(df)

        if header_row_index is None:
            raise validation_error(
                "Could not detect the statement header row. The file must contain "
                "date, description/details, and amount or balance columns."
            )

        file_obj.seek(0)

        if filename.endswith(".csv"):
            df = pd.read_csv(file_obj, header=header_row_index)
        else:
            df = pd.read_excel(file_obj, header=header_row_index)

        return [
            str(col).strip()
            for col in df.columns
            if str(col).strip() and "unnamed" not in str(col).lower()
        ]
    except pd.errors.EmptyDataError:
        raise validation_error("The uploaded statement file is empty.")
    finally:
        # Leave the stream ready for any subsequent save or processing.
        file_obj.seek(0)


class AccountGroupTypes:
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"

    ALL = {ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE}

    BALANCE_SHEET_TYPES = {ASSET, LIABILITY, EQUITY}
    INCOME_STATEMENT_TYPES = {REVENUE, EXPENSE}


def get_or_raise(queryset, message=None, **filters):
    try:
        return queryset.get(**filters)
    except queryset.model.DoesNotExist:
        raise validation_error(
            message or f"{queryset.model._meta.verbose_name} not found."
        )


class DebugPrintService:
    SENSITIVE_KEY_PARTS = (
        "authorization",
        "api_key",
        "password",
        "secret",
        "token",
    )

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, Mapping):
            sanitized = {}

            for key, item in value.items():
                normalized_key = str(key).lower()

                if any(
                    sensitive_part in normalized_key
                    for sensitive_part in cls.SENSITIVE_KEY_PARTS
                ):
                    sanitized[str(key)] = "[REDACTED]"
                else:
                    sanitized[str(key)] = cls._sanitize(item)

            return sanitized

        if isinstance(value, (list, tuple)):
            return [cls._sanitize(item) for item in value]

        return value

    @classmethod
    def print(
        cls,
        title: str,
        data: Any = None,
        *,
        scope: str = "SYSTEM",
    ) -> None:
        if not settings.DEBUG:
            return

        separator = "=" * 80

        print(f"\n\n{separator}")
        print(f"{scope.upper()} DEBUG: {title}")
        print(separator)

        if data is not None:
            sanitized_data = cls._sanitize(data)

            if isinstance(sanitized_data, (dict, list, tuple)):
                print(
                    json.dumps(
                        sanitized_data,
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )
                )
            else:
                print(sanitized_data)

        print(f"{separator}\n\n")
