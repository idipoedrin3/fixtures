from django.contrib import admin
from approval.models import (
    Action,
    ApproverGroup,
    ApproverGroupRole,
    ApproverGroupUser,
    ApprovalDocument,
    ApprovalDocumentLevel,
    ApprovalDocumentLevelApprovers,
    ApprovalDocumentLevelOverriders,
    Approval,
    ApprovalTask,
    ApprovalDocumentCategory,
    AllowedUser,
)

admin.site.register(Action)
admin.site.register(ApproverGroup)
admin.site.register(ApproverGroupRole)
admin.site.register(ApproverGroupUser)
admin.site.register(ApprovalDocument)
admin.site.register(ApprovalDocumentLevel)
admin.site.register(ApprovalDocumentLevelApprovers)
admin.site.register(ApprovalDocumentLevelOverriders)
admin.site.register(Approval)
admin.site.register(ApprovalTask)
admin.site.register(ApprovalDocumentCategory)
admin.site.register(AllowedUser)
