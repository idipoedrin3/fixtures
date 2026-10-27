from django.urls import path

from .views import (
    LenderDetailView,
    LenderListCreateView,
    LoanDetailView,
    LoanListCreateView,
    LoanRepaymentAllocationPreviewView,
    LoanRepaymentDetailView,
    LoanRepaymentListCreateView,
    LoanSchedulePreviewView,
    LoanScheduleView,
)

urlpatterns = [
    path("lenders/", LenderListCreateView.as_view(), name="lender-list-create"),
    path(
        "lenders/<uuid:base_uuid>/",
        LenderDetailView.as_view(),
        name="lender-detail",
    ),
    path("loans/", LoanListCreateView.as_view(), name="loan-list-create"),
    path(
        "loans/<uuid:base_uuid>/",
        LoanDetailView.as_view(),
        name="loan-detail",
    ),
    path(
        "loans/<uuid:base_uuid>/schedule/",
        LoanScheduleView.as_view(),
        name="loan-schedule",
    ),
    path(
        "loans/<uuid:base_uuid>/repayments/",
        LoanRepaymentListCreateView.as_view(),
        name="loan-repayment-list-create",
    ),
    path(
        "loans/<uuid:base_uuid>/repayments/allocation-preview/",
        LoanRepaymentAllocationPreviewView.as_view(),
        name="loan-repayment-allocation-preview",
    ),
    path(
        "loans/<uuid:base_uuid>/repayments/<uuid:repayment_uuid>/",
        LoanRepaymentDetailView.as_view(),
        name="loan-repayment-detail",
    ),
    path(
        "loans/schedule-preview/",
        LoanSchedulePreviewView.as_view(),
        name="loan-schedule-preview",
    ),
]