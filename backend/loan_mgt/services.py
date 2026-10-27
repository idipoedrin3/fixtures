from calendar import isleap
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.models import AuditLog
from transactions.models import Transaction
from transactions.models import TransactionEntry
from transactions.services import JournalLine, JournalPostingService, LEDGER_PRECISION
from utilities.helpers import AccountGroupTypes, get_fiscal_year, validation_error

from .models import (
    Lender,
    Loan,
    LoanPaymentAllocation,
    LoanRepayment,
    LoanRepaymentSchedule,
)


class LenderService:
    @staticmethod
    def validate_delete(lender):
        persisted = Lender._base_manager.select_for_update().get(pk=lender.pk)
        if Loan._base_manager.filter(
            party_content_type=ContentType.objects.get_for_model(Lender),
            party_object_uuid=persisted.base_uuid,
        ).exists():
            raise validation_error(
                "This lender is referenced by a loan and cannot be deleted."
            )


class LoanService:
    @staticmethod
    def validate_party(loan):
        from customers.models import Customer

        if loan.direction == Loan.Direction.OUTFLOW:
            party_model = Customer
        elif loan.direction == Loan.Direction.INFLOW:
            party_model = Lender
        else:
            raise validation_error("Select a valid loan direction.")

        expected_type = ContentType.objects.get_for_model(party_model)
        if loan.party_content_type_id != expected_type.pk:
            raise validation_error(
                "Outgoing loans require a customer; incoming loans require a lender."
            )

        parties = party_model._base_manager.filter(
            base_uuid=loan.party_object_uuid,
            deleted_at__isnull=True,
            is_active=True,
        )
        if party_model in (Customer, Lender):
            parties = parties.filter(institution_id=loan.institution_id)

        if not parties.exists():
            raise validation_error(
                "Select an existing active party appropriate for this loan."
            )

    SCHEDULE_FIELDS = (
        "principal",
        "annual_interest_rate",
        "interest_method",
        "interest_type",
        "day_count_convention",
        "repayment_structure",
        "repayment_frequency",
        "repayment_method",
        "repayment_timing",
        "disbursement_date",
        "first_repayment_date",
        "maturity_date",
    )
    ACCOUNTING_FIELDS = (
        "institution_id",
        "branch_id",
        "direction",
        "party_content_type_id",
        "party_object_uuid",
        "currency_id",
        "cash_account_id",
        "liability_receivable_account_id",
        "initial_accounting_treatment",
        "initial_accounting_date",
        "opening_principal",
        "opening_balance_account_id",
        "initial_journal_id",
        "initial_accounting_reference",
    )

    @classmethod
    def validate_update(cls, loan):
        if loan._state.adding:
            return
        persisted = Loan._base_manager.select_for_update().get(pk=loan.pk)
        has_schedule = LoanRepaymentSchedule._base_manager.filter(
            loan_id=loan.pk
        ).exists()
        has_accounting = (
            persisted.initial_journal_id is not None
            or persisted.are_initial_journal_entries_processed
            or Transaction._base_manager.filter(
                content_type=ContentType.objects.get_for_model(Loan),
                object_id=loan.pk,
            ).exists()
        )
        protected = set()
        if has_schedule or has_accounting:
            protected.update(cls.SCHEDULE_FIELDS)
            protected.update(
                {
                    "institution_id",
                    "direction",
                    "currency_id",
                    "party_content_type_id",
                    "party_object_uuid",
                }
            )
        if has_accounting:
            protected.update(cls.ACCOUNTING_FIELDS)
        changed = sorted(
            field
            for field in protected
            if getattr(persisted, field) != getattr(loan, field)
        )
        if changed:
            raise validation_error(
                "Recorded loan terms cannot be overwritten. "
                "Use an explicit correction or rescheduling workflow. "
                f"Changed fields: {', '.join(changed)}."
            )

    @classmethod
    def validate_delete(cls, loan):
        persisted = Loan._base_manager.select_for_update().get(pk=loan.pk)
        if (
            persisted.initial_journal_id is not None
            or persisted.are_initial_journal_entries_processed
            or Transaction._base_manager.filter(
                content_type=ContentType.objects.get_for_model(Loan),
                object_id=loan.pk,
            ).exists()
            or LoanRepayment._base_manager.filter(loan_id=loan.pk).exists()
        ):
            raise validation_error(
                "A loan with accounting history or repayments cannot be deleted. "
                "Use the accounting correction workflow."
            )

    @staticmethod
    def validate_account(loan, account, *, group_types, role_codes=None):
        if account.institution_id != loan.institution_id:
            raise validation_error(
                f"Account '{account.account_name}' belongs to another institution."
            )
        if account.deleted_at is not None or not account.is_active:
            raise validation_error(f"Account '{account.account_name}' must be active.")
        if not account.is_postable:
            raise validation_error(
                f"Account '{account.account_name}' cannot accept postings."
            )
        if (
            account.currency_id is not None
            and account.currency_id != loan.currency.currency_id
        ):
            raise validation_error(
                f"Account '{account.account_name}' has a different currency."
            )
        account.validate_account(
            expected_group_types=group_types,
            expected_role_codes=role_codes,
        )

    @classmethod
    def validate_configuration(cls, loan):
        cls.validate_party(loan)
        if loan.direction not in Loan.Direction.values:
            raise validation_error("Select a valid loan direction.")
        if loan.currency.institution_id != loan.institution_id:
            raise validation_error("Loan currency belongs to another institution.")
        if loan.currency.deleted_at is not None or not loan.currency.is_active:
            raise validation_error("Select an active institution currency.")
        if loan.branch_id and (
            loan.branch.institution_id != loan.institution_id
            or loan.branch.deleted_at is not None
            or not loan.branch.is_active
        ):
            raise validation_error(
                "Select an active branch belonging to the loan institution."
            )
        if loan.cash_account_id == loan.liability_receivable_account_id:
            raise validation_error("Cash and loan balance accounts must be different.")

        cls.validate_account(
            loan,
            loan.cash_account,
            group_types={AccountGroupTypes.ASSET},
            role_codes={"cash_account"},
        )
        balance_type = (
            AccountGroupTypes.ASSET
            if loan.direction == Loan.Direction.OUTFLOW
            else AccountGroupTypes.LIABILITY
        )
        cls.validate_account(
            loan,
            loan.liability_receivable_account,
            group_types={balance_type},
        )


class LoanInitialAccountingService:
    @classmethod
    @transaction.atomic
    def record_opening_balance(
        cls,
        loan,
        *,
        balance_confirmed,
        exchange_rate,
        existing_journal=None,
        created_by=None,
    ):
        loan = (
            Loan._base_manager.select_for_update(of=("self",))
            .select_related(
                "institution",
                "currency__currency",
                "liability_receivable_account",
                "opening_balance_account",
                "branch",
            )
            .get(pk=loan.pk)
        )
        treatment = loan.initial_accounting_treatment
        linking = treatment == Loan.InitialAccountingTreatment.ALREADY_RECORDED
        if treatment not in {
            Loan.InitialAccountingTreatment.OPENING_BALANCE,
            Loan.InitialAccountingTreatment.ALREADY_RECORDED,
        }:
            raise validation_error("Select an opening-balance accounting treatment.")
        if balance_confirmed is not True:
            raise validation_error(
                "Confirm the outstanding principal and its ledger treatment."
            )
        LoanService.validate_party(loan)
        if (
            loan.status != Loan.Status.APPROVED
            or loan.approval_status != "active"
            or not loan.is_active
            or loan.deleted_at is not None
        ):
            raise validation_error("The loan must have completed approval.")
        if not loan.initial_accounting_reference.strip():
            raise validation_error("Provide the supporting conversion reference.")

        opening_date = loan.initial_accounting_date
        today = LoanRepaymentScheduleService.institution_local_date(loan.institution)
        if opening_date is None or not loan.disbursement_date <= opening_date <= today:
            raise validation_error(
                "The opening date must be between disbursement and today."
            )
        amount = loan.opening_principal
        if amount is None or not Decimal("0") < amount <= loan.principal:
            raise validation_error(
                "Opening principal must be positive and cannot exceed original principal."
            )
        with localcontext() as context:
            context.prec = 80
            if amount != amount.quantize(LEDGER_PRECISION):
                raise validation_error(
                    "Opening principal exceeds the supported journal precision."
                )
        if (
            not isinstance(exchange_rate, Decimal)
            or not exchange_rate.is_finite()
            or exchange_rate <= 0
        ):
            raise validation_error(
                "Provide a positive decimal conversion exchange rate."
            )
        if (
            loan.currency.currency_id == loan.institution.currency_id
            and exchange_rate != Decimal("1")
        ):
            raise validation_error("Base-currency conversions require a rate of one.")

        if loan.currency.institution_id != loan.institution_id:
            raise validation_error("Loan currency belongs to another institution.")
        if loan.direction not in Loan.Direction.values:
            raise validation_error("Select a valid loan direction.")
        if loan.branch_id and loan.branch.institution_id != loan.institution_id:
            raise validation_error("Loan branch belongs to another institution.")
        if not loan.opening_balance_account_id:
            raise validation_error("Select the non-cash conversion offset account.")
        if loan.opening_balance_account_id in {
            loan.cash_account_id,
            loan.liability_receivable_account_id,
        }:
            raise validation_error(
                "The conversion offset must differ from the cash and loan accounts."
            )
        if (
            getattr(loan.opening_balance_account.account_role, "role_code", None)
            == "cash_account"
        ):
            raise validation_error("A conversion cannot use a cash offset account.")

        lending = loan.direction == Loan.Direction.OUTFLOW
        LoanService.validate_account(
            loan,
            loan.liability_receivable_account,
            group_types={
                AccountGroupTypes.ASSET if lending else AccountGroupTypes.LIABILITY
            },
        )
        LoanService.validate_account(
            loan,
            loan.opening_balance_account,
            group_types=AccountGroupTypes.BALANCE_SHEET_TYPES,
        )
        lines = [
            JournalLine(
                account=loan.liability_receivable_account,
                entry_type="debit" if lending else "credit",
                transaction_amount=amount,
                transaction_currency=loan.currency.currency,
                exchange_rate=exchange_rate,
            ),
            JournalLine(
                account=loan.opening_balance_account,
                entry_type="credit" if lending else "debit",
                transaction_amount=amount,
                transaction_currency=loan.currency.currency,
                exchange_rate=exchange_rate,
            ),
        ]
        content_type = ContentType.objects.get_for_model(Loan)
        supplied_id = existing_journal.pk if existing_journal is not None else None
        if supplied_id and not linking:
            raise validation_error(
                "Use already-recorded treatment when linking an existing journal."
            )
        if loan.initial_journal_id and supplied_id not in {
            None,
            loan.initial_journal_id,
        }:
            raise validation_error("The loan already references another journal.")
        journal_id = loan.initial_journal_id or supplied_id
        if linking and journal_id is None:
            raise validation_error("Select the existing conversion journal.")

        if journal_id:
            journal = Transaction._base_manager.select_for_update().get(pk=journal_id)
            prepared = JournalPostingService.prepare_lines(
                institution=loan.institution, lines=lines, source=loan
            )
            cls._validate_conversion_journal(
                loan, journal, prepared, require_posted=linking
            )
            if loan.initial_journal_id:
                return journal

        if loan.are_initial_journal_entries_processed:
            raise validation_error(
                "Reconcile the processed flag with its missing journal reference."
            )
        if LoanRepayment._base_manager.filter(loan_id=loan.pk).exists():
            raise validation_error(
                "Reconcile existing repayments before establishing the opening balance."
            )
        source_journals = Transaction._base_manager.filter(
            content_type=content_type, object_id=loan.pk
        )
        if journal_id:
            source_journals = source_journals.exclude(pk=journal_id)
        if source_journals.exists():
            raise validation_error(
                "Existing loan journals require reconciliation before conversion."
            )

        if not journal_id:
            journal, _ = JournalPostingService.post(
                fiscal_year=get_fiscal_year(loan.institution, opening_date),
                title=f"Loan opening balance — {loan.reference_code}",
                description=loan.initial_accounting_reference,
                transaction_date=opening_date,
                branch=loan.branch,
                content_type=content_type,
                object_id=loan.pk,
                source=loan,
                created_by=created_by,
                lines=lines,
            )
            journal.refresh_from_db()

        Loan._base_manager.filter(pk=loan.pk).update(
            initial_journal_id=journal.pk,
            are_initial_journal_entries_processed=(
                journal.transaction_status == "posted"
                and journal.is_active
                and journal.deleted_at is None
            ),
        )
        AuditLog.objects.create(
            content_type=content_type,
            object_id=loan.pk,
            action="UPDATE",
            user=created_by,
            description=f"Recorded opening balance for loan {loan.reference_code}.",
            changes={
                "treatment": treatment,
                "opening_date": opening_date.isoformat(),
                "opening_principal": str(amount),
                "exchange_rate": str(exchange_rate),
                "journal": str(journal.base_uuid),
                "reference": loan.initial_accounting_reference,
            },
        )
        return journal

    @staticmethod
    def _validate_conversion_journal(loan, journal, prepared, *, require_posted):
        content_type = ContentType.objects.get_for_model(Loan)
        if (
            journal.get_institution() != loan.institution
            or journal.branch_id != loan.branch_id
            or journal.transaction_currency_id != loan.currency.currency_id
            or journal.base_currency_id != loan.institution.currency_id
            or timezone.localdate(journal.transaction_date)
            != loan.initial_accounting_date
        ):
            raise validation_error(
                "The conversion journal has a different institution, branch, "
                "currency or accounting date."
            )
        if (
            journal.deleted_at is not None
            or journal.transaction_status in {"reversed", "cancelled"}
            or journal.reversal_records.exists()
            or (
                require_posted
                and (journal.transaction_status != "posted" or not journal.is_active)
            )
        ):
            raise validation_error(
                "The conversion journal is not eligible for linking."
            )
        if (journal.content_type_id, journal.object_id) not in {
            (None, None),
            (content_type.pk, loan.pk),
        }:
            raise validation_error("The journal belongs to another source record.")
        if (
            Loan._base_manager.filter(initial_journal_id=journal.pk)
            .exclude(pk=loan.pk)
            .exists()
            or LoanRepayment._base_manager.filter(journal_id=journal.pk).exists()
        ):
            raise validation_error("The journal is already used by another loan event.")

        entries = list(
            TransactionEntry._base_manager.select_for_update().filter(
                transaction_id=journal.pk
            )
        )
        if len(entries) != 2 or any(entry.deleted_at is not None for entry in entries):
            raise validation_error("Select a dedicated two-line conversion journal.")
        if require_posted and any(not entry.is_active for entry in entries):
            raise validation_error("Conversion journal entries must be active.")
        expected = sorted(
            (
                line.account.pk,
                line.entry_type,
                line.transaction_currency.pk,
                line.transaction_amount,
                line.base_amount,
                line.exchange_rate,
            )
            for line in prepared.lines
        )
        actual = sorted(
            (
                entry.account_id,
                entry.entry_type,
                entry.transaction_currency_id,
                entry.entry_amount_in_foreign_currency,
                entry.entry_amount,
                entry.foreign_exchange_rate,
            )
            for entry in entries
        )
        if actual != expected:
            raise validation_error(
                "The journal does not match the declared opening principal, "
                "conversion accounts and exchange rate."
            )

    @classmethod
    @transaction.atomic
    def post_cash_transaction(
        cls, loan, *, funds_confirmed, exchange_rate, created_by=None
    ):
        loan = (
            Loan._base_manager.select_for_update(of=("self",))
            .select_related(
                "institution",
                "currency__currency",
                "cash_account",
                "liability_receivable_account",
                "branch",
            )
            .get(pk=loan.pk)
        )
        treatment = loan.initial_accounting_treatment
        if treatment not in {
            Loan.InitialAccountingTreatment.NEW_CASH,
            Loan.InitialAccountingTreatment.HISTORICAL_CASH,
        }:
            raise validation_error(
                "This operation requires a new or historical cash transaction. "
                "Opening balances and already-recorded transactions must not "
                "be processed as new cash movements."
            )
        if funds_confirmed is not True:
            raise validation_error("Confirm the actual movement of funds.")
        if (
            loan.status != Loan.Status.APPROVED
            or loan.approval_status != "active"
            or not loan.is_active
            or loan.deleted_at is not None
        ):
            raise validation_error("The loan must have completed approval.")

        accounting_date = loan.initial_accounting_date
        if accounting_date is None:
            raise validation_error("Provide the actual accounting date.")
        if accounting_date != loan.disbursement_date:
            raise validation_error(
                "A principal cash transaction must use the actual disbursement date."
            )
        if accounting_date > LoanRepaymentScheduleService.institution_local_date(
            loan.institution
        ):
            raise validation_error(
                "A confirmed cash transaction cannot be future-dated."
            )
        if loan.principal <= 0:
            raise validation_error("The disbursed principal must be positive.")
        with localcontext() as context:
            context.prec = 80
            if loan.principal != loan.principal.quantize(LEDGER_PRECISION):
                raise validation_error(
                    "Principal exceeds the precision supported by the journal service."
                )

        content_type = ContentType.objects.get_for_model(Loan)
        if loan.initial_journal_id:
            journal = Transaction._base_manager.select_for_update().get(
                pk=loan.initial_journal_id
            )
            if (
                journal.content_type_id != content_type.pk
                or journal.object_id != loan.pk
                or journal.get_institution() != loan.institution
            ):
                raise validation_error(
                    "The linked journal does not belong to this loan's cash event."
                )
            if (
                journal.deleted_at is not None
                or journal.transaction_status in {"reversed", "cancelled"}
                or journal.reversal_records.exists()
            ):
                raise validation_error(
                    "The initial journal was deleted, reversed or cancelled. "
                    "Use the accounting correction workflow."
                )
            return journal

        if loan.are_initial_journal_entries_processed:
            raise validation_error(
                "The loan is marked processed but has no journal reference. "
                "Reconcile the existing accounting before posting."
            )
        if Transaction._base_manager.filter(
            content_type=content_type,
            object_id=loan.pk,
        ).exists():
            raise validation_error(
                "Existing journals reference this loan. Reconcile them before "
                "creating an initial cash transaction."
            )

        LoanService.validate_configuration(loan)
        LoanService.validate_update(loan)
        if not isinstance(exchange_rate, Decimal) or not exchange_rate.is_finite():
            raise validation_error("Provide a finite decimal exchange rate.")
        if exchange_rate <= 0:
            raise validation_error("Exchange rate must be positive.")
        if (
            loan.currency.currency_id == loan.institution.currency_id
            and exchange_rate != Decimal("1")
        ):
            raise validation_error("Base-currency transactions require a rate of one.")

        lending = loan.direction == Loan.Direction.OUTFLOW
        lines = [
            JournalLine(
                account=loan.liability_receivable_account,
                entry_type="debit" if lending else "credit",
                transaction_amount=loan.principal,
                transaction_currency=loan.currency.currency,
                exchange_rate=exchange_rate,
                description=f"Loan principal — {loan.reference_code}",
            ),
            JournalLine(
                account=loan.cash_account,
                entry_type="credit" if lending else "debit",
                transaction_amount=loan.principal,
                transaction_currency=loan.currency.currency,
                exchange_rate=exchange_rate,
                description=f"Loan cash movement — {loan.reference_code}",
            ),
        ]
        journal, _ = JournalPostingService.post(
            fiscal_year=get_fiscal_year(loan.institution, accounting_date),
            title=f"Loan principal — {loan.reference_code}",
            description=(
                f"Confirmed {treatment} for loan {loan.reference_code}. "
                f"{loan.initial_accounting_reference}"
            ),
            transaction_date=accounting_date,
            branch=loan.branch,
            content_type=content_type,
            object_id=loan.pk,
            source=loan,
            created_by=created_by,
            lines=lines,
        )
        journal.refresh_from_db()
        loan.initial_journal = journal
        loan.are_initial_journal_entries_processed = (
            journal.transaction_status == "posted"
            and journal.is_active
            and journal.deleted_at is None
        )
        Loan._base_manager.filter(pk=loan.pk).update(
            initial_journal_id=journal.pk,
            are_initial_journal_entries_processed=(
                loan.are_initial_journal_entries_processed
            ),
        )
        return journal


class LoanRepaymentScheduleService:
    AMOUNT_QUANTUM = Decimal("0.00000000000000000001")
    MAX_INSTALLMENTS = 10000
    SCHEDULE_FIELDS = (
        "installation_number",
        "due_date",
        "opening_principal",
        "principal_due",
        "interest_due",
        "fees_due",
    )

    @staticmethod
    def institution_local_date(institution):
        try:
            tz = ZoneInfo(institution.timezone or "Africa/Kampala")
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            tz = ZoneInfo("Africa/Kampala")
        return timezone.now().astimezone(tz).date()

    @classmethod
    def _amount(cls, value):
        with localcontext() as context:
            context.prec = 80
            return value.quantize(cls.AMOUNT_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def _year_fraction(start, end, convention):
        if end < start:
            raise validation_error("The interest period cannot end before it starts.")
        with localcontext() as context:
            context.prec = 80
            days = Decimal((end - start).days)
            if convention == Loan.DayCountConvention.ACTUAL_365:
                return days / Decimal("365")
            if convention == Loan.DayCountConvention.ACTUAL_360:
                return days / Decimal("360")
            if convention != Loan.DayCountConvention.ACTUAL_ACTUAL_ISDA:
                raise validation_error("Select the loan's day-count convention.")

            fraction = Decimal("0")
            current = start
            while current < end:
                boundary = (
                    end if current.year == end.year else date(current.year + 1, 1, 1)
                )
                denominator = Decimal("366" if isleap(current.year) else "365")
                fraction += Decimal((boundary - current).days) / denominator
                current = boundary
            return fraction

    @classmethod
    def _due_dates(cls, loan):
        if loan.principal <= 0 or loan.annual_interest_rate < 0:
            raise validation_error(
                "Principal must be positive and interest cannot be negative."
            )
        if not (
            loan.disbursement_date <= loan.first_repayment_date <= loan.maturity_date
        ):
            raise validation_error(
                "Repayment dates must fall between disbursement and maturity."
            )
        if loan.repayment_structure == Loan.RepaymentStructure.SINGLE:
            if loan.first_repayment_date != loan.maturity_date:
                raise validation_error(
                    "A single repayment must fall on the maturity date."
                )
            return [loan.maturity_date]
        if loan.repayment_structure != Loan.RepaymentStructure.PERIODIC:
            raise validation_error("Unsupported repayment structure.")
        if loan.repayment_method not in Loan.RepaymentMethod.values:
            raise validation_error("Select a periodic repayment method.")
        if loan.repayment_timing not in Loan.RepaymentTiming.values:
            raise validation_error("Select the repayment timing.")
        if (
            loan.repayment_timing == Loan.RepaymentTiming.BEGINNING
            and loan.first_repayment_date != loan.disbursement_date
        ):
            raise validation_error(
                "Beginning-of-period repayments must start on disbursement."
            )
        if (
            loan.repayment_timing == Loan.RepaymentTiming.END
            and loan.first_repayment_date <= loan.disbursement_date
        ):
            raise validation_error(
                "End-of-period repayments must start after disbursement."
            )

        day_steps = {"daily": 1, "weekly": 7, "biweekly": 14}
        month_steps = {
            "monthly": 1,
            "quarterly": 3,
            "semiannually": 6,
            "annually": 12,
        }
        frequency = loan.repayment_frequency
        if frequency not in day_steps and frequency not in month_steps:
            raise validation_error("Select a supported repayment frequency.")

        dates = []
        for index in range(cls.MAX_INSTALLMENTS):
            if frequency in day_steps:
                due_date = loan.first_repayment_date + timedelta(
                    days=day_steps[frequency] * index
                )
            else:
                due_date = loan.first_repayment_date + relativedelta(
                    months=month_steps[frequency] * index
                )
            if due_date > loan.maturity_date:
                break
            dates.append(due_date)
            if due_date == loan.maturity_date:
                return dates
        else:
            raise validation_error("The schedule exceeds 10,000 instalments.")

        if loan.repayment_timing == Loan.RepaymentTiming.END:
            raise validation_error(
                "Maturity does not match a repayment date. "
                "An irregular final period requires an explicit contract schedule."
            )
        return dates

    @classmethod
    def _build_schedule(cls, loan):
        if loan.day_count_convention not in Loan.DayCountConvention.values:
            raise validation_error(
                "Select the loan's day-count convention before generating schedules."
            )
        if loan.interest_method not in Loan.InterestMethod.values:
            raise validation_error("Select a supported interest method.")
        if loan.interest_type not in Loan.InterestType.values:
            raise validation_error("Select a supported interest type.")

        dates = cls._due_dates(loan)
        count = len(dates)

        with localcontext() as context:
            context.prec = 80
            annual_rate = loan.annual_interest_rate / Decimal("100")
            rates = []
            previous_date = loan.disbursement_date
            for due_date in dates:
                fraction = cls._year_fraction(
                    previous_date, due_date, loan.day_count_convention
                )
                if loan.interest_type == Loan.InterestType.SIMPLE:
                    rate = annual_rate * fraction
                else:
                    rate = (Decimal("1") + annual_rate) ** fraction - Decimal("1")
                rates.append(rate)
                previous_date = due_date

            equal_installments = (
                loan.repayment_structure == Loan.RepaymentStructure.PERIODIC
                and loan.repayment_method == Loan.RepaymentMethod.EQUAL_INSTALLMENTS
            )
            flat = loan.interest_method == Loan.InterestMethod.FLAT
            if equal_installments and flat:
                payment = (
                    loan.principal * (Decimal("1") + sum(rates, Decimal("0"))) / count
                )
            elif equal_installments:
                discount = Decimal("1")
                discount_sum = Decimal("0")
                for rate in rates:
                    discount /= Decimal("1") + rate
                    discount_sum += discount
                payment = loan.principal / discount_sum
            else:
                payment = None

            outstanding = loan.principal
            rows = []
            for number, (due_date, rate) in enumerate(zip(dates, rates), start=1):
                interest_base = loan.principal if flat else outstanding
                interest = cls._amount(interest_base * rate)
                if number == count:
                    principal = outstanding
                elif payment is not None:
                    principal = cls._amount(payment - interest)
                else:
                    principal = cls._amount(loan.principal / count)
                if principal < 0 or principal > outstanding:
                    raise validation_error(
                        "These terms require an explicit contract schedule; "
                        "automatic generation would produce invalid principal."
                    )
                rows.append(
                    {
                        "installation_number": number,
                        "due_date": due_date,
                        "opening_principal": outstanding,
                        "principal_due": principal,
                        "interest_due": interest,
                        "fees_due": Decimal("0"),
                    }
                )
                outstanding = cls._amount(outstanding - principal)
            return rows

    @classmethod
    def get_loan_schedule(cls, loan):
        proposed = cls._build_schedule(loan)
        recorded = list(
            LoanRepaymentSchedule._base_manager.filter(loan=loan).order_by(
                "installation_number", "created_at"
            )
        )
        proposed_by_number = {row["installation_number"]: row for row in proposed}
        notice = ""
        if loan.deleted_at is not None or not loan.is_active:
            notice = "The loan must be active."
        elif loan.status != Loan.Status.APPROVED:
            notice = "Approve the loan before creating its repayment schedule."

        rows = {}
        for entry in recorded:
            number = entry.installation_number
            expected = proposed_by_number.get(number)
            if entry.deleted_at is not None:
                notice = (
                    "The schedule contains deleted instalments. "
                    "Resolve their history before creating further instalments."
                )
            elif expected is None or any(
                getattr(entry, field) != expected[field]
                for field in cls.SCHEDULE_FIELDS
            ):
                notice = (
                    "Recorded instalments differ from the proposed terms. "
                    "An explicit schedule revision is required."
                )
            rows[number] = {
                field: getattr(entry, field) for field in cls.SCHEDULE_FIELDS
            }
            rows[number].update(
                {
                    "base_uuid": str(entry.base_uuid),
                    "status": entry.status,
                    "record_state": "deleted" if entry.deleted_at else "recorded",
                    "can_create": False,
                }
            )

        for proposed_row in proposed:
            number = proposed_row["installation_number"]
            if number in rows:
                continue
            rows[number] = {
                **proposed_row,
                "base_uuid": None,
                "status": None,
                "record_state": "proposed",
                "can_create": not notice,
            }
        return [rows[number] for number in sorted(rows)], notice

    @classmethod
    @transaction.atomic
    def create_missing_installments(cls, loan):
        loan = (
            Loan._base_manager.select_for_update()
            .select_related("institution")
            .get(pk=loan.pk)
        )
        rows, notice = cls.get_loan_schedule(loan)
        if notice:
            raise validation_error(notice)

        created = []
        for row in rows:
            if row["record_state"] == "recorded":
                continue
            created.append(
                LoanRepaymentSchedule.objects.create(
                    loan=loan,
                    **{field: row[field] for field in cls.SCHEDULE_FIELDS},
                )
            )
        return created


class LoanRepaymentService:
    TOLERANCE = Decimal("0.000001")
    COMPONENTS = ("fees", "interest", "principal")
    ALLOCATION_FIELDS = {
        "principal": "principal_amount",
        "interest": "interest_amount",
        "fees": "fee_amount",
    }

    @staticmethod
    def validate_loan_ready(loan):
        if (
            loan.status != Loan.Status.APPROVED
            or loan.approval_status != "active"
            or not loan.is_active
            or loan.deleted_at is not None
        ):
            raise validation_error(
                "Repayments can only be recorded against an approved, active loan."
            )

    @classmethod
    def _allocated(cls, schedule_ids, statuses, exclude_payment_id=None):
        queryset = LoanPaymentAllocation._base_manager.filter(
            repayment_schedule_id__in=schedule_ids,
            deleted_at__isnull=True,
            payment__deleted_at__isnull=True,
            payment__status__in=statuses,
        )
        if exclude_payment_id is not None:
            queryset = queryset.exclude(payment_id=exclude_payment_id)
        rows = (
            queryset.values("repayment_schedule_id")
            .order_by()
            .annotate(
                principal=Sum("principal_amount"),
                interest=Sum("interest_amount"),
                fees=Sum("fee_amount"),
            )
        )
        return {row["repayment_schedule_id"]: row for row in rows}

    @classmethod
    def schedule_balances(
        cls, loan, *, statuses=None, lock=False, exclude_payment_id=None
    ):
        statuses = statuses or (
            LoanRepayment.Status.PENDING,
            LoanRepayment.Status.COMPLETED,
        )
        queryset = (
            LoanRepaymentSchedule._base_manager.filter(
                loan=loan, deleted_at__isnull=True
            )
            .exclude(status=LoanRepaymentSchedule.Status.WAIVED)
            .order_by("installation_number")
        )
        if lock:
            queryset = queryset.select_for_update()
        schedules = list(queryset)
        allocated = cls._allocated(
            [item.pk for item in schedules], statuses, exclude_payment_id
        )
        zero = Decimal("0")
        balances = []
        for schedule in schedules:
            paid_row = allocated.get(schedule.pk, {})
            row = {"schedule": schedule}
            for key, due in (
                ("principal", schedule.principal_due),
                ("interest", schedule.interest_due),
                ("fees", schedule.fees_due),
            ):
                paid = paid_row.get(key) or zero
                row[f"{key}_paid"] = paid
                row[f"{key}_outstanding"] = max(due - paid, zero)
            balances.append(row)
        return balances

    @classmethod
    def suggest_allocations(
        cls, loan, amount, *, first_schedule=None, exclude_payment_id=None
    ):
        balances = cls.schedule_balances(loan, exclude_payment_id=exclude_payment_id)
        if first_schedule is not None:
            if not any(item["schedule"].pk == first_schedule.pk for item in balances):
                raise validation_error(
                    f"Installment {first_schedule.installation_number} cannot receive payments."
                )
            balances.sort(key=lambda item: item["schedule"].pk != first_schedule.pk)
        remaining = amount
        suggestions = []
        for balance in balances:
            if remaining <= 0:
                break
            parts = {}
            for key in cls.COMPONENTS:
                part = min(remaining, balance[f"{key}_outstanding"])
                parts[key] = part
                remaining -= part
            if any(part > 0 for part in parts.values()):
                suggestions.append({"balance": balance, "parts": parts})
        return suggestions, remaining

    @classmethod
    def payment_lines(cls, loan, payment):
        balances = {
            item["schedule"].pk: item
            for item in cls.schedule_balances(loan, exclude_payment_id=payment.pk)
        }
        lines = []
        allocations = payment.allocations.all().order_by(
            "repayment_schedule__installation_number"
        )
        for allocation in allocations:
            balance = balances.get(allocation.repayment_schedule_id)
            if balance is None:
                continue
            lines.append(
                {
                    "balance": balance,
                    "parts": {
                        "principal": allocation.principal_amount,
                        "interest": allocation.interest_amount,
                        "fees": allocation.fee_amount,
                    },
                }
            )
        return lines

    @classmethod
    def validate_header(cls, loan, *, date, treatment, reference):
        cls.validate_loan_ready(loan)
        today = LoanRepaymentScheduleService.institution_local_date(loan.institution)
        if date < loan.disbursement_date:
            raise validation_error("A repayment cannot precede the disbursement date.")
        if date > today:
            raise validation_error("A repayment cannot be future-dated.")
        if treatment == LoanRepayment.AccountingTreatment.ALREADY_RECORDED and not (
            reference or ""
        ).strip():
            raise validation_error(
                "Provide the supporting reference for a repayment already in the ledger."
            )

    @classmethod
    def validate_allocations(cls, loan, allocations, *, exclude_payment_id=None):
        if not allocations:
            raise validation_error("Allocate the repayment to at least one installment.")
        balances = {
            item["schedule"].pk: item
            for item in cls.schedule_balances(
                loan, lock=True, exclude_payment_id=exclude_payment_id
            )
        }
        seen = set()
        total = Decimal("0")
        for line in allocations:
            schedule = line["repayment_schedule"]
            balance = balances.get(schedule.pk)
            if schedule.loan_id != loan.pk or balance is None:
                raise validation_error(
                    f"Installment {schedule.installation_number} cannot receive payments."
                )
            if schedule.pk in seen:
                raise validation_error(
                    f"Installment {schedule.installation_number} is allocated more than once."
                )
            seen.add(schedule.pk)
            line_total = Decimal("0")
            for key, field in cls.ALLOCATION_FIELDS.items():
                value = line.get(field) or Decimal("0")
                outstanding = balance[f"{key}_outstanding"]
                if value > outstanding:
                    raise validation_error(
                        f"Installment {schedule.installation_number}: {key} allocation "
                        f"exceeds the outstanding {outstanding.normalize():f}."
                    )
                line_total += value
            if line_total <= 0:
                raise validation_error(
                    f"Installment {schedule.installation_number} has no allocated amount."
                )
            total += line_total
        return total

    @staticmethod
    def validate_edit(payment):
        if payment.journal_id is not None:
            raise validation_error(
                "A repayment with a posted journal cannot be edited. "
                "Use the accounting correction workflow."
            )
        if payment.status == LoanRepayment.Status.REJECTED:
            raise validation_error("A rejected repayment cannot be edited.")

    @classmethod
    def create_allocations(cls, payment, allocations):
        for line in allocations:
            LoanPaymentAllocation.objects.create(
                payment=payment,
                repayment_schedule=line["repayment_schedule"],
                principal_amount=line.get("principal_amount") or Decimal("0"),
                interest_amount=line.get("interest_amount") or Decimal("0"),
                fee_amount=line.get("fee_amount") or Decimal("0"),
            )

    @staticmethod
    def snapshot_allocations(payment):
        return [
            {
                "repayment_schedule": allocation.repayment_schedule_id,
                "principal_amount": str(allocation.principal_amount),
                "interest_amount": str(allocation.interest_amount),
                "fee_amount": str(allocation.fee_amount),
            }
            for allocation in payment.allocations.all()
        ]

    @classmethod
    def replace_allocations(cls, payment, allocations):
        LoanPaymentAllocation._base_manager.filter(payment_id=payment.pk).delete()
        cls.create_allocations(payment, allocations)

    @classmethod
    def restore_allocations(cls, payment):
        snapshot = (
            LoanRepayment._base_manager.filter(pk=payment.pk)
            .values_list("allocations_snapshot", flat=True)
            .first()
        )
        if snapshot is None:
            return
        LoanPaymentAllocation._base_manager.filter(payment_id=payment.pk).delete()
        total = Decimal("0")
        for line in snapshot:
            principal = Decimal(line["principal_amount"])
            interest = Decimal(line["interest_amount"])
            fee = Decimal(line["fee_amount"])
            LoanPaymentAllocation.objects.create(
                payment_id=payment.pk,
                repayment_schedule_id=line["repayment_schedule"],
                principal_amount=principal,
                interest_amount=interest,
                fee_amount=fee,
            )
            total += principal + interest + fee
        LoanRepayment._base_manager.filter(pk=payment.pk).update(
            allocations_snapshot=None, amount=total
        )

    @staticmethod
    def validate_delete(payment):
        persisted = LoanRepayment._base_manager.select_for_update().get(pk=payment.pk)
        if persisted.journal_id is not None:
            raise validation_error(
                "A repayment with a posted journal cannot be deleted. "
                "Use the accounting correction workflow."
            )

    @classmethod
    def refresh_schedule_statuses(cls, loan):
        balances = cls.schedule_balances(
            loan, statuses=(LoanRepayment.Status.COMPLETED,), lock=True
        )
        for balance in balances:
            schedule = balance["schedule"]
            paid = (
                balance["principal_paid"]
                + balance["interest_paid"]
                + balance["fees_paid"]
            )
            due = schedule.principal_due + schedule.interest_due + schedule.fees_due
            if due > 0 and paid >= due:
                new_status = LoanRepaymentSchedule.Status.PAID
            elif paid > 0:
                new_status = LoanRepaymentSchedule.Status.PARTIALLY_PAID
            elif schedule.status in (
                LoanRepaymentSchedule.Status.PAID,
                LoanRepaymentSchedule.Status.PARTIALLY_PAID,
            ):
                new_status = LoanRepaymentSchedule.Status.PENDING
            else:
                continue
            if new_status != schedule.status:
                LoanRepaymentSchedule._base_manager.filter(pk=schedule.pk).update(
                    status=new_status
                )

    @classmethod
    def schedule_overview(cls, loan, rows, page):
        zero = Decimal("0")
        completed = {
            str(item["schedule"].base_uuid): item
            for item in cls.schedule_balances(
                loan, statuses=(LoanRepayment.Status.COMPLETED,)
            )
        }
        committed = {
            str(item["schedule"].base_uuid): item for item in cls.schedule_balances(loan)
        }

        def paid_total(item):
            if item is None:
                return zero
            return item["principal_paid"] + item["interest_paid"] + item["fees_paid"]

        total_principal = sum((row["principal_due"] for row in rows), zero)
        total_interest = sum((row["interest_due"] for row in rows), zero)
        total_fees = sum((row["fees_due"] for row in rows), zero)
        total_due = total_principal + total_interest + total_fees
        total_paid = sum((paid_total(item) for item in completed.values()), zero)
        totals = {
            "principal": str(total_principal),
            "interest": str(total_interest),
            "fees": str(total_fees),
            "total_due": str(total_due),
            "paid": str(total_paid),
            "outstanding": str(max(total_due - total_paid, zero)),
        }

        keys = [row["base_uuid"] for row in page if row["base_uuid"]]
        payments = {}
        if keys:
            allocations = (
                LoanPaymentAllocation._base_manager.filter(
                    repayment_schedule__base_uuid__in=keys,
                    deleted_at__isnull=True,
                    payment__deleted_at__isnull=True,
                )
                .exclude(payment__status=LoanRepayment.Status.REJECTED)
                .select_related("payment", "repayment_schedule")
                .order_by("payment__date", "payment__created_at")
            )
            for allocation in allocations:
                payments.setdefault(
                    str(allocation.repayment_schedule.base_uuid), []
                ).append(
                    {
                        "base_uuid": str(allocation.payment.base_uuid),
                        "reference_code": allocation.payment.reference_code,
                        "date": allocation.payment.date.isoformat(),
                        "status": allocation.payment.status,
                        "principal_amount": str(allocation.principal_amount),
                        "interest_amount": str(allocation.interest_amount),
                        "fee_amount": str(allocation.fee_amount),
                        "amount": str(allocation.amount),
                    }
                )

        described = []
        for row in page:
            key = row["base_uuid"]
            due = row["principal_due"] + row["interest_due"] + row["fees_due"]
            paid = paid_total(completed.get(key))
            open_item = committed.get(key)
            payable = (
                zero
                if open_item is None
                else open_item["principal_outstanding"]
                + open_item["interest_outstanding"]
                + open_item["fees_outstanding"]
            )
            described.append(
                {
                    "base_uuid": key,
                    "installation_number": row["installation_number"],
                    "due_date": row["due_date"].isoformat(),
                    "status": row["status"],
                    "record_state": row["record_state"],
                    "opening_principal": str(row["opening_principal"]),
                    "principal_due": str(row["principal_due"]),
                    "interest_due": str(row["interest_due"]),
                    "fees_due": str(row["fees_due"]),
                    "total_due": str(due),
                    "total_paid": str(paid),
                    "outstanding": str(max(due - paid, zero)),
                    "payable": str(payable),
                    "can_pay": row["record_state"] == "recorded" and payable > 0,
                    "payments": payments.get(key, []),
                }
            )
        return totals, described