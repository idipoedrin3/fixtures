from customers.services import CustomerPaymentService


def reconcile_customer_prepayments(
    prepayment_uuids: list,
    invoice_uuids: list,
    institution,
):
    return CustomerPaymentService.reconcile_prepayments(
        prepayment_uuids=prepayment_uuids,
        invoice_uuids=invoice_uuids,
        institution=institution,
    )
