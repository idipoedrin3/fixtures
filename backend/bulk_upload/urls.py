from django.urls import path
from .views import BulkUploadView

urlpatterns = [
    path("", BulkUploadView.as_view(), name="bulk-upload-template"),
]
