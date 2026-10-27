from decimal import Decimal
from statistics import median

from requisitions.utils import ATTACHMENT_LEVEL_AT_REQUEST


def _empty_result():
    return {
        "score": 0,
        "factors": [],
        "counts": {
            "evidence_issues": 0,
            "amount_outliers": 0,
        },
    }


class RequisitionRiskAnalyzer:
    model_labels = {"requisitions.requisition"}

    @staticmethod
    def _amount(requisition):
        return (
            requisition.total_payable_amount or requisition.gross_amount or Decimal("0")
        )

    @staticmethod
    def _amount_label(requisition, amount):
        currency = getattr(requisition.currency, "currency", None)
        currency_code = getattr(currency, "code", None)
        if not currency_code:
            currency_code = getattr(requisition.currency, "code", None)

        return f"{currency_code} {amount:,.2f}" if currency_code else f"{amount:,.2f}"

    def _is_amount_outlier(self, requisition, amount):
        peer_amounts = list(
            requisition.__class__.objects.filter(
                requisition_type=requisition.requisition_type,
                total_payable_amount__gt=0,
                deleted_at__isnull=True,
            )
            .exclude(pk=requisition.pk)
            .order_by("-created_at")
            .values_list("total_payable_amount", flat=True)[:100]
        )

        if len(peer_amounts) < 5:
            return False, None

        peer_median = median(peer_amounts)
        if peer_median <= 0:
            return False, peer_median

        return amount >= peer_median * 3, peer_median

    def analyse(self, approval, actions):
        result = _empty_result()
        requisition = approval.content_object

        amount = self._amount(requisition)
        has_request_attachment = requisition.has_attachment_at_level(
            ATTACHMENT_LEVEL_AT_REQUEST
        )
        requires_request_attachment = (
            requisition.requisition_type.requires_attachment_at_level(
                ATTACHMENT_LEVEL_AT_REQUEST
            )
        )

        if requires_request_attachment and not has_request_attachment:
            result["score"] += 25
            result["counts"]["evidence_issues"] += 1
            result["factors"].append(
                {
                    "code": "required_evidence_missing",
                    "source": "requisition",
                    "severity": "high",
                    "points": 25,
                    "message": (
                        "This requisition requires a supporting attachment "
                        "at the request stage, but none was supplied."
                    ),
                    "level": None,
                    "category": "Evidence",
                    "comment": "Required request-stage attachment missing.",
                    "acted_by": None,
                    "occurred_at": requisition.created_at,
                }
            )

        if amount > 0 and not has_request_attachment:
            result["score"] += 15
            result["counts"]["evidence_issues"] += 1
            result["factors"].append(
                {
                    "code": "value_without_evidence",
                    "source": "requisition",
                    "severity": "medium",
                    "points": 15,
                    "message": (
                        f"A requisition worth {self._amount_label(requisition, amount)} "
                        "has no supporting attachment."
                    ),
                    "level": None,
                    "category": "Evidence",
                    "comment": None,
                    "acted_by": None,
                    "occurred_at": requisition.created_at,
                }
            )

        is_outlier, peer_median = self._is_amount_outlier(requisition, amount)
        if is_outlier:
            result["score"] += 15
            result["counts"]["amount_outliers"] += 1
            result["factors"].append(
                {
                    "code": "amount_outlier",
                    "source": "requisition",
                    "severity": "medium",
                    "points": 15,
                    "message": (
                        "The requisition amount is at least three times the recent "
                        f"median of {self._amount_label(requisition, peer_median)} "
                        "for this template."
                    ),
                    "level": None,
                    "category": "Amount",
                    "comment": None,
                    "acted_by": None,
                    "occurred_at": requisition.created_at,
                }
            )

        return result


SCOPED_ANALYZERS = (RequisitionRiskAnalyzer(),)


def analyse_scoped_risk(approval, actions):
    content_object = approval.content_object
    if content_object is None:
        return _empty_result()

    model_label = content_object._meta.label_lower
    for analyzer in SCOPED_ANALYZERS:
        if model_label in analyzer.model_labels:
            return analyzer.analyse(approval, actions)

    return _empty_result()
