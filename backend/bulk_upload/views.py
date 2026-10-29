from utilities.helpers import get_institution, validation_error
from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from .registry import BULK_UPLOAD_REGISTRY
from .services import (
    BulkUploadParser,
    BulkUploadService,
    TemplateDropdownService,
    TemplateFileService,
)
from .serializers import BulkUploadRequestSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter


class BulkUploadView(APIView):

    parser_classes = [FormParser, MultiPartParser]

    def check_permissions(self, request):
        super().check_permissions(request)
        template_type = (
            request.query_params.get("template_type")
            if request.method == "GET"
            else request.data.get("template_type")
        )
        if str(template_type or "").lower() == "expenses":
            from types import SimpleNamespace
            from users.permissions import HasInstitutionPermission

            HasInstitutionPermission().has_permission(
                request,
                SimpleNamespace(
                    required_permissions={
                        "get": "can_create_expenses",
                        "post": "can_create_expenses",
                    },
                    required_features={"expenses_management"},
                ),
            )

        if str(template_type or "").lower() == "vendor_bill":
            from types import SimpleNamespace
            from users.permissions import HasInstitutionPermission

            HasInstitutionPermission().has_permission(
                request,
                SimpleNamespace(
                    required_permissions={
                        "get": "can_create_vendor_bills",
                        "post": "can_create_vendor_bills",
                    },
                    required_features=set(),
                ),
            )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="template_type",
                description="Type of template to download (customer or vendor).",
                required=True,
                enum=[
                    "customer",
                    "vendor",
                    "fixed_asset_category",
                    "fixed_asset_items",
                    "salesperson",
                    "charts_of_accounts",
                    "requisition_item",
                    "inventory_units_of_measure",
                    "inventory_item_categories",
                    "expenses",
                    "vendor_bill",
                ],
            ),
            OpenApiParameter(
                name="file_format",
                description="Format of the template file (excel or csv). Defaults to excel.",
                required=False,
                enum=["excel", "csv"],
            ),
        ],
        tags=["Bulk Upload"],
        description=(
            "Download a blank bulk-upload template. "
            "Excel templates include dropdown validation for choice fields "
            "and colour-coded headers indicating required vs optional columns."
        ),
    )
    def get(self, request):
        template_type = request.query_params.get("template_type", "").lower()
        file_format = request.query_params.get("file_format", "excel").lower()

        definition = BULK_UPLOAD_REGISTRY.get(template_type)
        if definition is None:
            raise validation_error(
                "Invalid template_type. Expected one of: "
                f"{', '.join(BULK_UPLOAD_REGISTRY)}"
            )
        if file_format not in ["excel", "csv"]:
            raise validation_error("Invalid file_format. Expected 'excel' or 'csv'.")

        col_defs = definition.columns
        columns = definition.column_names
        filename = f"{template_type}_bulk_upload_template"

        content = None
        response = None

        institution = get_institution(request)

        if file_format == "excel":
            dynamic_dropdowns = TemplateDropdownService.build(
                template_type,
                institution,
                col_defs,
            )

            content = TemplateFileService.build_excel(
                col_defs,
                sheet_title=template_type.capitalize(),
                dynamic_dropdowns=dynamic_dropdowns,
            )
            response = HttpResponse(
                content,
                content_type=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        else:
            content = TemplateFileService.build_csv(columns)
            response = HttpResponse(content, content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'

        return response

    @extend_schema(
        request=BulkUploadRequestSerializer,
        tags=["Bulk Upload"],
        description=(
            "Upload a filled bulk-upload template (Excel or CSV). "
            "All rows are validated first — any row errors are returned immediately "
            "and nothing is queued. On success the task is dispatched to Celery."
        ),
    )
    def post(self, request):
        institution = get_institution(request)

        outer = BulkUploadRequestSerializer(data=request.data)
        if not outer.is_valid():
            raise validation_error(outer.errors)

        template_type = outer.validated_data["template_type"]
        file_obj = outer.validated_data["file"]
        definition = BULK_UPLOAD_REGISTRY[template_type]
        columns = definition.column_names

        filename = file_obj.name.lower()
        if filename.endswith(".xlsx"):
            file_format = "excel"
        elif filename.endswith(".csv"):
            file_format = "csv"
        else:
            raise validation_error(
                "File must be an Excel file (.xlsx) or a CSV file (.csv)."
            )

        try:
            raw_rows = BulkUploadParser.parse(
                file_obj,
                file_format,
                columns,
            )
        except Exception as exc:
            raise validation_error(f"Could not parse the uploaded file: {exc}")

        if not raw_rows:
            raise validation_error("The uploaded file contains no data rows.")

        response_data = BulkUploadService.queue(
            template_type,
            definition,
            raw_rows,
            request,
            institution,
        )

        return Response(
            response_data,
            status=status.HTTP_202_ACCEPTED,
        )
