from pathlib import Path

import requests
from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.authentication import JWTAuthentication

DATASETS = {
    "supporting": [
        (
            "units-of-measure-data.xlsx",
            "bulk-upload-template",
            "inventory_units_of_measure",
        ),
        (
            "item-categories-data.xlsx",
            "bulk-upload-template",
            "inventory_item_categories",
        ),
        ("customers-data.xlsx", "bulk-upload-template", "customer"),
        ("vendors-data.xlsx", "bulk-upload-template", "vendor"),
    ],
    "inventory": [
        ("inventory-items-data.xlsx", "inventory-item-bulk-upload", None),
        ("another-inventory-items-data.xlsx", "inventory-item-bulk-upload", None),
    ],
}


class DummyDataForm(forms.Form):
    access_token = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        strip=True,
    )
    stage = forms.ChoiceField(
        choices=[
            ("supporting", "Import supporting data"),
            ("inventory", "Import inventory"),
        ]
    )


class DummyDataAdminMixin:
    def render_change_form(self, request, context, *args, **kwargs):
        context["show_dummy_data_import"] = settings.DEBUG
        return super().render_change_form(request, context, *args, **kwargs)

    def get_urls(self):
        return [
            path(
                "<path:object_id>/import-dummy-data/",
                self.admin_site.admin_view(self.import_dummy_data),
                name="institution_institution_import_dummy_data",
            ),
        ] + super().get_urls()

    @method_decorator(sensitive_post_parameters("access_token"))
    def import_dummy_data(self, request, object_id):
        if not settings.DEBUG:
            raise Http404
        institution = self.get_object(request, object_id)
        if institution is None:
            raise Http404("Institution not found.")
        if not self.has_change_permission(request, institution):
            raise PermissionDenied

        form = DummyDataForm(request.POST if request.method == "POST" else None)
        results = []
        if request.method == "POST" and form.is_valid():
            token = form.cleaned_data["access_token"]
            if token.lower().startswith("bearer "):
                token = token[7:].strip()
            try:
                authentication = JWTAuthentication()
                validated = authentication.get_validated_token(token)
                authentication.get_user(validated)
                current = validated.get("current_institution") or {}
                if str(current.get("id")) != str(institution.pk):
                    form.add_error(
                        "access_token",
                        "Use an access token for this institution.",
                    )
            except APIException:
                form.add_error("access_token", "Invalid or expired access token.")

            if not form.errors:
                stage = form.cleaned_data["stage"]
                datasets = DATASETS[stage]
                folder = Path(settings.BASE_DIR) / "dummy_data"
                missing = [
                    name for name, _, _ in datasets if not (folder / name).is_file()
                ]
                if missing:
                    form.add_error(None, "Missing files: " + ", ".join(missing))
                else:
                    with requests.Session() as session:
                        session.headers["Authorization"] = f"Bearer {token}"
                        for filename, route, template_type in datasets:
                            data = (
                                {"template_type": template_type}
                                if template_type
                                else {}
                            )
                            try:
                                with (folder / filename).open("rb") as file:
                                    response = session.post(
                                        request.build_absolute_uri(reverse(route)),
                                        data=data,
                                        files={
                                            "file": (
                                                filename,
                                                file,
                                                "application/vnd.openxmlformats-officedocument."
                                                "spreadsheetml.sheet",
                                            )
                                        },
                                        timeout=(10, 120),
                                        allow_redirects=False,
                                    )
                            except requests.RequestException:
                                results.append(
                                    f"{filename}: request failed or timed out. "
                                    "Check the import status before retrying; "
                                    "the server may already have accepted it."
                                )
                                break

                            if response.status_code not in (200, 201, 202):
                                detail = response.text.replace(token, "[redacted]")
                                results.append(
                                    f"{filename}: HTTP {response.status_code}. "
                                    f"{detail[:2000]}"
                                )
                                break

                            results.append(
                                f"{filename}: accepted for background processing."
                            )
                            self.log_change(
                                request,
                                institution,
                                f"Submitted dummy-data file: {filename}.",
                            )

            # Never send the submitted token back to the template.
            errors = form.errors.copy()
            stage = form.cleaned_data.get("stage", "supporting")
            form = DummyDataForm(initial={"stage": stage})
            if errors:
                form._errors = errors

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Import dummy data",
            "institution": institution,
            "form": form,
            "results": results,
        }
        return TemplateResponse(
            request,
            "admin/institution/institution/import_dummy_data.html",
            context,
        )
