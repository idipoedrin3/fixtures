from django.contrib import admin
from .dummy_data_admin import DummyDataAdminMixin
from transactions.admin_mixins import JournalBalanceAdminMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST
import json

from accounts.utils import create_industry_specific_coa_for_institution
from system.exceptions import SystemValidationError

from .models import (
    Institution,
    Branch,
    InstitutionFeatureStatus,
    InstitutionSupportedCurrency,
    InstitutionSupportedPaymentOption,
    RecycleBin,
    InstitutionReferenceSequence,
    RecycleBinItem,
    InstitutionSupportedBankingInstitution,
)


# ---------------------------------------------------------------------------
# Existing admins
# ---------------------------------------------------------------------------
class InstitutionAdmin(DummyDataAdminMixin, JournalBalanceAdminMixin, admin.ModelAdmin):
    balance_rebuild_scope = "institution"
    change_form_template = "admin/institution/institution/change_form.html"
    list_display = ("institution_name", "institution_owner")
    search_fields = ("institution_name",)
    ordering = ("institution_name",)
    list_per_page = 20

    def get_urls(self):
        return [
            path(
                "<path:object_id>/create-industry-coa/",
                self.admin_site.admin_view(require_POST(self.create_industry_coa)),
                name="institution_institution_create_industry_coa",
            ),
        ] + super().get_urls()

    def create_industry_coa(self, request, object_id):
        institution = self.get_object(request, object_id)
        if institution is None:
            raise Http404("Institution not found.")
        if not self.has_change_permission(request, institution):
            raise PermissionDenied

        try:
            with transaction.atomic():
                create_industry_specific_coa_for_institution(institution)
                self.log_change(
                    request, institution, "Ran industry-specific COA creation."
                )
        except (ValidationError, SystemValidationError) as exc:
            self.message_user(request, f"COA creation failed: {exc}", level="error")
        else:
            self.message_user(
                request,
                f"COA creation completed for {institution.institution_name}.",
                level="success",
            )

        return HttpResponseRedirect(
            reverse(
                f"{self.admin_site.name}:institution_institution_change",
                args=[institution.pk],
            )
        )


class BranchAdmin(admin.ModelAdmin):
    list_display = ("branch_name", "institution", "branch_location")
    search_fields = ("branch_name", "institution_name")
    ordering = ("branch_name",)
    list_per_page = 20


class InstitutionSupportedBankingInstitutionAdmin(admin.ModelAdmin):
    list_display = (
        "bank_name",
        "institution",
        "reference_code",
        "is_active",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "bank_name",
        "institution__institution_name",
        "reference_code",
    )
    list_filter = (
        "institution",
        "is_active",
        "is_deleted",
        "created_at",
    )
    ordering = ("institution__institution_name", "bank_name")
    list_select_related = ("institution",)
    autocomplete_fields = ("institution",)
    readonly_fields = (
        "base_uuid",
        "reference_code",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    fieldsets = (
        (
            "Banking Institution",
            {
                "fields": (
                    "institution",
                    "bank_name",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "System Information",
            {
                "classes": ("collapse",),
                "fields": (
                    "reference_code",
                    "base_uuid",
                    "is_deleted",
                    "deleted_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )
    date_hierarchy = "created_at"
    list_per_page = 25


# ---------------------------------------------------------------------------
# RecycleBinItem inline — shown inside RecycleBin
# ---------------------------------------------------------------------------


class RecycleBinItemInline(admin.TabularInline):
    model = RecycleBinItem
    extra = 0
    readonly_fields = (
        "object_uuid",
        "content_type",
        "model_label",
        "deleted_by",
        "deleted_at",
        "restore_action",
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True

    def model_label(self, obj):
        return obj.content_type.app_labeled_name

    model_label.short_description = "Model"

    def restore_action(self, obj):
        url = f"/admin/institution/recyclebinitem/{obj.pk}/change/"
        return format_html('<a href="{}">View / Restore</a>', url)

    restore_action.short_description = "Actions"


@admin.register(RecycleBin)
class RecycleBinAdmin(admin.ModelAdmin):
    list_display = ("institution", "item_count", "created_at")
    search_fields = ("institution__institution_name",)
    readonly_fields = ("institution", "created_at", "item_count")
    inlines = [RecycleBinItemInline]
    list_per_page = 20

    def item_count(self, obj):
        count = obj.items.count()
        return format_html(
            '<span style="font-weight:600">{}</span> item{}',
            count,
            "s" if count != 1 else "",
        )

    item_count.short_description = "Items in Bin"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RecycleBinItem)
class RecycleBinItemAdmin(admin.ModelAdmin):
    list_display = (
        "model_label",
        "object_uuid",
        "institution_name",
        "deleted_by",
        "deleted_at",
    )
    list_filter = ("content_type", "deleted_at")
    search_fields = (
        "object_uuid",
        "deleted_by__email",
        "recycle_bin__institution__institution_name",
    )
    readonly_fields = (
        "recycle_bin",
        "content_type",
        "object_uuid",
        "deleted_by",
        "deleted_at",
        "institution_name",
        "model_label",
        "pretty_data",
    )
    fields = (
        "recycle_bin",
        "institution_name",
        "model_label",
        "object_uuid",
        "deleted_by",
        "deleted_at",
        "pretty_data",
    )
    actions = ["restore_selected", "permanently_delete_selected"]
    list_per_page = 25

    def model_label(self, obj):
        return obj.content_type.app_labeled_name

    model_label.short_description = "Model"

    def institution_name(self, obj):
        return str(obj.recycle_bin.institution)

    institution_name.short_description = "Institution"

    def pretty_data(self, obj):
        if not obj.data:
            return "—"
        try:
            parsed = json.loads(f"[{obj.data}]")
            formatted = json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            formatted = str(obj.data)
        return format_html(
            '<pre style="background:#f5f5f5;padding:12px;border-radius:4px;'
            'font-size:12px;max-height:400px;overflow:auto;white-space:pre-wrap">{}</pre>',
            formatted,
        )

    pretty_data.short_description = "Snapshot Data"

    @admin.action(description="Restore selected items")
    def restore_selected(self, request, queryset):
        restored, failed = 0, 0
        for item in queryset:
            try:
                item.restore(user=request.user)
                restored += 1
            except Exception:
                failed += 1
        if restored:
            self.message_user(request, f"{restored} item(s) restored successfully.")
        if failed:
            self.message_user(
                request, f"{failed} item(s) could not be restored.", level="warning"
            )

    @admin.action(description="Permanently delete selected items")
    def permanently_delete_selected(self, request, queryset):
        count = queryset.count()
        for item in queryset:
            item.hard_delete(user=request.user)
        self.message_user(request, f"{count} item(s) permanently deleted.")

    def has_add_permission(self, request):
        return False


admin.site.register(Branch, BranchAdmin)
admin.site.register(Institution, InstitutionAdmin)
admin.site.register(InstitutionFeatureStatus)
admin.site.register(InstitutionSupportedCurrency)
admin.site.register(
    InstitutionSupportedBankingInstitution,
    InstitutionSupportedBankingInstitutionAdmin,
)
admin.site.register(InstitutionSupportedPaymentOption)
admin.site.register(InstitutionReferenceSequence)
