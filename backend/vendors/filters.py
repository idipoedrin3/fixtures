from utilities.helpers import BaseReportFilterSerializer


class VendorBillFilterSerializer(BaseReportFilterSerializer):
    date_fields = {
        "created_at": ("Created date", "created_at__date"),
        "issue_date": ("Issue date", "issue_date"),
        "due_date": ("Due date", "due_date"),
    }
