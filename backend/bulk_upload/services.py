import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal

import openpyxl
from django.db.models import Exists, OuterRef
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from accounts.models import Account
from fixed_assets.models import AssetCategory, AssetClass
from institution.models import InstitutionSupportedCurrency
from system.models import SystemAccountRole
from utilities.helpers import normalize_url, serialize_value, validation_error


class BulkUploadService:
    @classmethod
    def queue(cls, template_type, definition, rows, request, institution):
        if template_type == "expenses":
            from .expenses import prepare_expenses

            groups = prepare_expenses(rows, request)
            result = definition.task.delay(
                institution_id=institution.pk,
                rows=groups,
                requested_by_id=request.user.pk,
                profile_institution_id=getattr(
                    getattr(request, "profile_institution", None), "pk", None
                ),
                external_identity_id=getattr(
                    getattr(request, "external_identity", None), "pk", None
                ),
            )
            return {
                "detail": f"{len(groups)} expenses queued from {len(rows)} data rows.",
                "task_id": result.id,
                "total_rows": len(rows),
                "total_expenses": len(groups),
            }

        if template_type == "vendor_bill":
            from .vendor_bills import prepare_vendor_bills

            groups = prepare_vendor_bills(rows, request)
            result = definition.task.delay(
                institution_id=institution.pk,
                groups=groups,
                requested_by_id=request.user.pk,
                profile_institution_id=getattr(
                    getattr(request, "profile_institution", None), "pk", None
                ),
                external_identity_id=getattr(
                    getattr(request, "external_identity", None), "pk", None
                ),
            )
            return {
                "detail": (
                    f"{len(groups)} vendor bill(s) queued from {len(rows)} data rows."
                ),
                "task_id": result.id,
                "total_rows": len(rows),
                "total_bills": len(groups),
            }

        validated_rows, errors = cls._validate_rows(
            rows,
            definition.serializer,
            {
                "request": request,
                "institution": institution,
            },
        )

        if errors:
            raise validation_error(
                {
                    "detail": "Row validation failed.",
                    "errors": errors,
                }
            )

        task_kwargs = {
            "institution_id": institution.pk,
            "rows": cls._make_json_serialisable(validated_rows),
            "requested_by_id": request.user.pk,
        }

        if template_type == "fixed_asset_items":
            task_kwargs.update(
                {
                    "should_notify": getattr(request, "should_notify", False),
                    "profile_institution_id": getattr(
                        getattr(request, "profile_institution", None),
                        "id",
                        None,
                    ),
                }
            )

        result = definition.task.delay(**task_kwargs)

        return {
            "detail": (
                f"{len(validated_rows)} {template_type}(s) queued for creation."
            ),
            "task_id": result.id,
            "total_rows": len(validated_rows),
        }

    @staticmethod
    def _validate_rows(rows, serializer_class, context):
        validated_rows = []
        errors = []

        for row_number, row in enumerate(rows, start=2):
            serializer = serializer_class(
                data=row,
                context=context,
            )

            if serializer.is_valid():
                validated_rows.append(serializer.validated_data)
            else:
                errors.append(
                    {
                        "row": row_number,
                        "errors": serializer.errors,
                    }
                )

        return validated_rows, errors

    @staticmethod
    def _make_json_serialisable(rows):
        return [
            {key: serialize_value(value) for key, value in row.items()} for row in rows
        ]


class BulkUploadParser:
    HEADER_ALIASES = {
        "code": "reference_code",
        "asset_category": "category",
        "unit_price_ugx": "unit_price",
        "amount_paid_ugx": "amount_paid",
        "payment_term": "payment_terms",
        "payment_terms": "payment_terms",
    }

    NUMERIC_COLUMNS = {
        "qty",
        "unit_price",
        "amount_paid",
    }
    @classmethod
    def parse(cls, file_obj, file_format, columns):
        if file_format == "excel":
            return cls._parse_excel(file_obj, columns)
        if file_format == "csv":
            return cls._parse_csv(file_obj, columns)
        raise validation_error(f"Unsupported file format: {file_format}")

    @classmethod
    def _normalize_header(cls, value):
        key = str(value or "").strip().lower().replace("*", "")
        key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
        return cls.HEADER_ALIASES.get(key, key)

    @classmethod
    def _parse_excel(cls, file_obj, columns):
        workbook = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        if not rows:
            return []

        header = [cls._normalize_header(value) for value in rows[0]]
        subheader_markers = {"* required", "optional"}
        has_subheader = len(rows) > 1 and any(
            str(value).strip().lower() in subheader_markers
            for value in rows[1]
            if value is not None
        )
        data_rows = rows[2:] if has_subheader else rows[1:]
        result = []

        for row in data_rows:
            if all(value is None or str(value).strip() == "" for value in row):
                continue

            obj = {}
            for col_idx, col_name in enumerate(header):
                if col_name not in columns:
                    continue
                raw = row[col_idx] if col_idx < len(row) else None

                if col_name == "opening_balance":
                    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                        value = Decimal("0.00")
                    else:
                        try:
                            value = Decimal(str(raw).strip())
                        except Exception:
                            raise validation_error(
                                f"Invalid opening_balance value: {raw}"
                            )
                    obj[col_name] = value
                    continue

                if col_name == "salvage_value":
                    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                        value = Decimal("0.00")
                    else:
                        try:
                            value = Decimal(str(raw).strip())
                        except Exception:
                            raise validation_error(f"Invalid {col_name} value: {raw}")
                    obj[col_name] = value
                    continue

                if col_name == "useful_life":
                    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                        value = None
                    else:
                        try:
                            value = Decimal(str(raw))
                        except Exception:
                            raise validation_error(f"Invalid {col_name} value: {raw}")
                    obj[col_name] = value
                    continue

                if col_name in cls.NUMERIC_COLUMNS:
                    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                        value = None
                    else:
                        value = str(raw).strip().replace(",", "")
                    obj[col_name] = value
                    continue

                if "date" in col_name:
                    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                        value = None
                    elif isinstance(raw, datetime):
                        value = raw.date().isoformat()
                    elif isinstance(raw, date):
                        value = raw.isoformat()
                    else:
                        value = str(raw).strip()
                    obj[col_name] = value
                    continue

                if col_name in {"is_capitalizable", "is_depreciable"}:
                    if raw is None or str(raw).strip() == "":
                        value = None
                    else:
                        normalized = str(raw).strip().lower()
                        if normalized in {"true", "1"}:
                            value = True
                        elif normalized in {"false", "0"}:
                            value = False
                        else:
                            raise validation_error(f"Invalid {col_name} value: {raw}")
                    obj[col_name] = value
                    continue

                if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                    value = None
                elif col_name == "website":
                    value = normalize_url(str(raw).strip())
                else:
                    value = str(raw).strip()
                obj[col_name] = value

            result.append(obj)
        return result

    @classmethod
    def _parse_csv(cls, file_obj, columns):
        text = file_obj.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        result = []

        for row in reader:
            if all(value is None or str(value).strip() == "" for value in row.values()):
                continue

            obj = {}
            for header, raw_value in row.items():
                key = cls._normalize_header(header)
                if key not in columns:
                    continue
                raw = raw_value.strip() if raw_value is not None else ""

                if key == "salvage_value":
                    if raw == "":
                        value = Decimal("0.00")
                    else:
                        try:
                            value = Decimal(raw)
                        except Exception:
                            raise validation_error(f"Invalid {key} value: {raw}")
                elif key == "useful_life":
                    if raw == "":
                        value = None
                    else:
                        try:
                            value = Decimal(str(raw))
                        except Exception:
                            raise validation_error(f"Invalid {key} value: {raw}")
                elif key in {"is_capitalizable", "is_depreciable"}:
                    if raw == "":
                        value = None
                    else:
                        normalized = raw.lower()
                        if normalized in {"true", "1"}:
                            value = True
                        elif normalized in {"false", "0"}:
                            value = False
                        else:
                            raise validation_error(f"Invalid {key} value: {raw}")
                elif key in cls.NUMERIC_COLUMNS:
                    value = raw.replace(",", "") if raw != "" else None
                elif key == "website" and raw:
                    value = normalize_url(raw)
                else:
                    value = raw if raw != "" else None
                obj[key] = value

            result.append(obj)
        return result


class TemplateFileService:
    DROPDOWN_ROW_COUNT = 500
    REQUIRED_HEADER_FILL = PatternFill("solid", fgColor="C0392B")
    OPTIONAL_HEADER_FILL = PatternFill("solid", fgColor="2C3E50")
    HEADER_FONT = Font(color="FFFFFF", bold=True, name="Calibri", size=11)
    SUBHEADER_REQ_FILL = PatternFill("solid", fgColor="FADBD8")
    SUBHEADER_OPT_FILL = PatternFill("solid", fgColor="EAF0F6")
    SUBHEADER_FONT = Font(color="555555", italic=True, name="Calibri", size=9)
    DATA_FONT = Font(name="Calibri", size=10)
    THIN_BORDER_SIDE = Side(style="thin", color="CCCCCC")
    CELL_BORDER = Border(
        left=THIN_BORDER_SIDE,
        right=THIN_BORDER_SIDE,
        top=THIN_BORDER_SIDE,
        bottom=THIN_BORDER_SIDE,
    )

    @classmethod
    def build_excel(
        cls,
        col_defs: list[dict],
        sheet_title: str,
        dynamic_dropdowns: dict | None = None,
    ) -> bytes:
        dynamic_dropdowns = dynamic_dropdowns or {}
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_title
        dropdown_worksheet = workbook.create_sheet("Dropdown Options")
        dropdown_worksheet.sheet_state = "veryHidden"

        cls._add_headers(worksheet, col_defs)
        cls._add_data_rows(
            worksheet,
            dropdown_worksheet,
            col_defs,
            dynamic_dropdowns,
        )
        cls._add_legend(workbook)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def build_csv(columns: list[str]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        return buffer.getvalue()

    @classmethod
    def _add_headers(cls, worksheet, col_defs):
        for col_idx, col_def in enumerate(col_defs, start=1):
            cell = worksheet.cell(
                row=1,
                column=col_idx,
                value=col_def.get("label", col_def["name"]),
            )
            cell.fill = (
                cls.REQUIRED_HEADER_FILL
                if col_def["required"]
                else cls.OPTIONAL_HEADER_FILL
            )
            cell.font = cls.HEADER_FONT
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )
            cell.border = cls.CELL_BORDER

        for col_idx, col_def in enumerate(col_defs, start=1):
            label = "* Required" if col_def["required"] else "Optional"
            cell = worksheet.cell(row=2, column=col_idx, value=label)
            cell.fill = (
                cls.SUBHEADER_REQ_FILL
                if col_def["required"]
                else cls.SUBHEADER_OPT_FILL
            )
            cell.font = cls.SUBHEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cls.CELL_BORDER

        worksheet.row_dimensions[1].height = 30
        worksheet.row_dimensions[2].height = 18

    @classmethod
    def _add_data_rows(
        cls,
        worksheet,
        dropdown_worksheet,
        col_defs,
        dynamic_dropdowns,
    ):
        last_data_row = cls.DROPDOWN_ROW_COUNT + 2

        for col_idx, col_def in enumerate(col_defs, start=1):
            col_letter = get_column_letter(col_idx)

            for row_idx in range(3, last_data_row + 1):
                cell = worksheet.cell(row=row_idx, column=col_idx)
                cell.font = cls.DATA_FONT
                cell.border = cls.CELL_BORDER
                cell.alignment = Alignment(vertical="center")

            options = dynamic_dropdowns.get(col_def["name"]) or col_def["dropdown"]

            if options:
                cls._add_dropdown(
                    worksheet,
                    dropdown_worksheet,
                    col_idx,
                    col_letter,
                    col_def,
                    options,
                    last_data_row,
                )

            if "date" in col_def["name"]:
                for row_idx in range(3, last_data_row + 1):
                    worksheet.cell(
                        row=row_idx,
                        column=col_idx,
                    ).number_format = "YYYY-MM-DD"

            max_length = max(
                len(col_def.get("label", col_def["name"])),
                max((len(str(value)) for value in (options or [])), default=0),
                18,
            )
            worksheet.column_dimensions[col_letter].width = max_length + 4

        worksheet.freeze_panes = "A3"

    @staticmethod
    def _add_dropdown(
        worksheet,
        dropdown_worksheet,
        col_idx,
        col_letter,
        col_def,
        options,
        last_data_row,
    ):
        option_col_letter = get_column_letter(col_idx)
        for row_idx, option in enumerate(options, start=1):
            dropdown_worksheet.cell(
                row=row_idx,
                column=col_idx,
                value=str(option),
            )

        formula = (
            f"'Dropdown Options'!${option_col_letter}$1:"
            f"${option_col_letter}${len(options)}"
        )

        strict = col_def.get("strict", True)
        validation = DataValidation(
            type="list",
            formula1=formula,
            allow_blank=not col_def["required"],
            showDropDown=False,
            showErrorMessage=True,
            errorStyle="stop" if strict else "warning",
            errorTitle="Invalid value" if strict else "Value not in list",
            error=(
                "Please choose a value from the dropdown list."
                if strict
                else "This value is not in the list. Continue only if it is intentional."
            ),
        )
        worksheet.add_data_validation(validation)
        validation.sqref = f"{col_letter}3:{col_letter}{last_data_row}"

    @classmethod
    def _add_legend(cls, workbook):
        legend = workbook.create_sheet("Legend")
        legend.sheet_state = "veryHidden"
        legend.column_dimensions["A"].width = 22
        legend.column_dimensions["B"].width = 40

        legend.cell(row=1, column=1, value="Colour").font = Font(bold=True)
        legend.cell(row=1, column=2, value="Meaning").font = Font(bold=True)

        required_cell = legend.cell(row=2, column=1, value="Red header")
        required_cell.fill = cls.REQUIRED_HEADER_FILL
        required_cell.font = Font(color="FFFFFF", bold=True)
        legend.cell(
            row=2,
            column=2,
            value="Column is REQUIRED — must not be left blank.",
        )

        optional_cell = legend.cell(row=3, column=1, value="Dark header")
        optional_cell.fill = cls.OPTIONAL_HEADER_FILL
        optional_cell.font = Font(color="FFFFFF")
        legend.cell(
            row=3,
            column=2,
            value="Column is OPTIONAL — can be left blank.",
        )
        legend.cell(
            row=4,
            column=2,
            value="Columns with a dropdown arrow only accept listed values.",
        )
        legend.cell(
            row=5,
            column=2,
            value="Date columns must be in YYYY-MM-DD format.",
        )


class TemplateDropdownService:
    _BUILDERS = {
        "fixed_asset_category": "_fixed_asset_category_dropdowns",
        "fixed_asset_items": "_fixed_asset_item_dropdowns",
        "charts_of_accounts": "_chart_of_accounts_dropdowns",
        "inventory_item_categories": "_inventory_category_dropdowns",
        "vendor_bill": "_vendor_bill_dropdowns",
    }

    @staticmethod
    def _requested_columns(col_defs):
        return {column["name"] for column in col_defs}

    @staticmethod
    def _leaf_accounts(institution, *, active_only):
        active_children = Account.objects.active().filter(
            parent_id=OuterRef("pk"),
        )

        accounts = Account.objects.active() if active_only else Account.objects

        return (
            accounts.filter(institution=institution, deleted_at__isnull=True)
            .select_related("account_role__role_group")
            .annotate(has_children=Exists(active_children))
            .filter(has_children=False)
            .order_by("account_name")
        )

    @staticmethod
    def _account_names(accounts, **filters):
        return list(
            accounts.filter(**filters).values_list("account_name", flat=True).distinct()
        )

    @classmethod
    def _select_requested(cls, options, col_defs):
        requested = cls._requested_columns(col_defs)
        return {name: values for name, values in options.items() if name in requested}

    @classmethod
    def _inventory_category_dropdowns(cls, institution, col_defs):
        accounts = cls._leaf_accounts(institution, active_only=True)

        return cls._select_requested(
            {
                "expense_account": cls._account_names(
                    accounts,
                    account_role__role_group__group_type_name="expense",
                ),
                "inventory_account": cls._account_names(
                    accounts,
                    account_role__role_group__group_type_name="asset",
                ),
                "revenue_account": cls._account_names(
                    accounts,
                    account_role__role_group__group_type_name="revenue",
                ),
            },
            col_defs,
        )

    @classmethod
    def _fixed_asset_category_dropdowns(cls, institution, col_defs):
        accounts = cls._leaf_accounts(institution, active_only=False)

        return cls._select_requested(
            {
                "fixed_asset_account": cls._account_names(
                    accounts,
                    account_role__role_code="fixed_asset_account",
                ),
                "depreciation_expense_account": cls._account_names(
                    accounts,
                    account_role__role_group__group_type_name="expense",
                ),
                "accumulated_depreciation_account": cls._account_names(
                    accounts,
                    account_role__role_code="contra_asset_account",
                ),
                "asset_class": list(
                    AssetClass.objects.filter(
                        institution=institution,
                        deleted_at__isnull=True,
                    )
                    .order_by("asset_class_name")
                    .values_list("asset_class_name", flat=True)
                ),
            },
            col_defs,
        )

    @classmethod
    def _fixed_asset_item_dropdowns(cls, institution, col_defs):
        categories = list(
            AssetCategory.objects.filter(
                institution=institution,
                is_active=True,
                deleted_at__isnull=True,
            )
            .order_by("category_name")
            .values_list("category_name", flat=True)
            .distinct()
        )

        return cls._select_requested(
            {"category": categories},
            col_defs,
        )

    @classmethod
    def _vendor_bill_dropdowns(cls, institution, col_defs):
        from customers.models import PaymentTerm
        from institution.models import Branch
        from items.models import InventoryItem, ItemUnitOfMeasure
        from taxation.models import Tax
        from vendors.models import Vendor
        from .vendor_bills import cash_account_options

        accounts = cls._leaf_accounts(institution, active_only=True)

        return cls._select_requested(
            {
                "vendor": list(
                    Vendor.objects.active()
                    .filter(institution=institution)
                    .order_by("vendor_name")
                    .values_list("vendor_name", flat=True)
                    .distinct()
                ),
                "branch": list(
                    Branch.objects.active()
                    .filter(institution=institution)
                    .order_by("branch_name")
                    .values_list("branch_name", flat=True)
                    .distinct()
                ),
                "payment_terms": list(
                    PaymentTerm.objects.active()
                    .filter(institution=institution)
                    .order_by("term_name")
                    .values_list("term_name", flat=True)
                    .distinct()
                ),
                "item": list(
                    InventoryItem.objects.active()
                    .filter(institution=institution)
                    .order_by("item_name")
                    .values_list("item_name", flat=True)
                    .distinct()
                ),
                "uom": list(
                    ItemUnitOfMeasure.objects.active()
                    .filter(institution=institution)
                    .order_by("unit_name")
                    .values_list("unit_name", flat=True)
                    .distinct()
                ),
                "expense_account": cls._account_names(
                    accounts,
                    account_role__role_group__group_type_name="expense",
                ),
                "tax": list(
                    Tax.objects.active()
                    .filter(institution=institution)
                    .order_by("tax_name")
                    .values_list("tax_name", flat=True)
                    .distinct()
                ),
                "cash_account": cash_account_options(institution),
            },
            col_defs,
        )

    @classmethod
    def _chart_of_accounts_dropdowns(cls, institution, col_defs):
        account_roles = list(
            SystemAccountRole.objects.order_by("role_name").values_list(
                "role_name",
                flat=True,
            )
        )
        parent_accounts = list(
            Account.objects.filter(
                institution=institution,
                deleted_at__isnull=True,
            )
            .order_by("account_name")
            .values_list("account_name", flat=True)
        )
        currencies = list(
            InstitutionSupportedCurrency.objects.filter(
                institution=institution,
                currency__isnull=False,
            )
            .order_by("currency__code")
            .values_list("currency__code", flat=True)
        )

        return cls._select_requested(
            {
                "account_role": account_roles,
                "parent_account": parent_accounts or ["(none)"],
                "currency_code": currencies or ["(none)"],
            },
            col_defs,
        )

    @classmethod
    def build(cls, template_type, institution, col_defs):
        builder_name = cls._BUILDERS.get(template_type)
        builder = getattr(cls, builder_name) if builder_name else None
        return builder(institution, col_defs) if builder else {}
