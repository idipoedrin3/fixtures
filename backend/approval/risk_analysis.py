from django.utils import timezone

from approval.models import ApprovalTaskAction
from approval.risk_scopes import analyse_scoped_risk


class ApprovalRiskAnalysisService:
    def __init__(self, approval):
        self.approval = approval

    @staticmethod
    def _rating(score):
        if score >= 70:
            return "critical"
        if score >= 40:
            return "high"
        if score >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _task_level(task):
        return task.level.name or f"Level {task.effective_sequence}"

    @staticmethod
    def _task_category(task):
        category = getattr(task.level, "category", None)
        return category.name if category else None

    def analyse(self):
        tasks = list(
            self.approval.tasks.filter(deleted_at__isnull=True).select_related(
                "level", "level__category"
            )
        )
        tasks.sort(key=lambda task: (task.effective_sequence, task.pk))

        actions = list(
            ApprovalTaskAction.objects.filter(
                approval=self.approval,
                deleted_at__isnull=True,
            )
            .select_related("task", "task__level", "acted_by")
            .order_by("created_at", "pk")
        )

        rejection_actions = [
            action for action in actions if action.action == "rejected"
        ]
        approval_actions = [action for action in actions if action.action == "approved"]
        send_back_actions = [
            action for action in actions if action.action == "sent_back"
        ]
        override_actions = [
            action for action in actions if action.action == "overridden"
        ]
        reset_actions = [action for action in actions if action.action == "reset"]
        recall_actions = [action for action in actions if action.action == "recalled"]

        factors = []
        score = 0
        continued_rejections = 0

        if rejection_actions:
            points = min(len(rejection_actions) * 10, 20)
            score += points
            factors.append(
                {
                    "code": "rejection_recorded",
                    "source": "general",
                    "severity": "medium",
                    "points": points,
                    "message": (
                        f"The workflow contains {len(rejection_actions)} "
                        "rejection decision(s)."
                    ),
                    "level": None,
                    "category": "Decision",
                    "comment": None,
                    "acted_by": None,
                    "occurred_at": rejection_actions[-1].created_at,
                }
            )

        unexplained_rejections = [
            action for action in rejection_actions if not (action.comment or "").strip()
        ]
        if unexplained_rejections:
            points = min(len(unexplained_rejections) * 20, 40)
            score += points
            factors.append(
                {
                    "code": "rejection_without_reason",
                    "source": "general",
                    "severity": "high",
                    "points": points,
                    "message": (
                        f"{len(unexplained_rejections)} rejection decision(s) "
                        "were submitted without a reason."
                    ),
                    "level": self._task_level(unexplained_rejections[-1].task),
                    "category": "Decision quality",
                    "comment": None,
                    "acted_by": (
                        unexplained_rejections[-1].acted_by.fullname
                        if unexplained_rejections[-1].acted_by
                        else None
                    ),
                    "occurred_at": unexplained_rejections[-1].created_at,
                }
            )

        unexplained_approvals = [
            action for action in approval_actions if not (action.comment or "").strip()
        ]
        if unexplained_approvals:
            points = min(len(unexplained_approvals) * 5, 15)
            score += points
            factors.append(
                {
                    "code": "approval_without_reason",
                    "source": "general",
                    "severity": "low",
                    "points": points,
                    "message": (
                        f"{len(unexplained_approvals)} approval decision(s) "
                        "were submitted without supporting comments."
                    ),
                    "level": self._task_level(unexplained_approvals[-1].task),
                    "category": "Decision quality",
                    "comment": None,
                    "acted_by": (
                        unexplained_approvals[-1].acted_by.fullname
                        if unexplained_approvals[-1].acted_by
                        else None
                    ),
                    "occurred_at": unexplained_approvals[-1].created_at,
                }
            )

        decision_actions = [
            action
            for action in actions
            if action.action in {"approved", "rejected", "overridden"}
        ]

        levels_by_user = {}
        for action in decision_actions:
            if action.acted_by_id:
                levels_by_user.setdefault(action.acted_by_id, set()).add(
                    action.task.effective_sequence
                )

        concentrated_user_id = max(
            levels_by_user,
            key=lambda user_id: len(levels_by_user[user_id]),
            default=None,
        )
        concentrated_levels = (
            len(levels_by_user[concentrated_user_id])
            if concentrated_user_id is not None
            else 0
        )

        if concentrated_levels >= 2:
            concentrated_action = next(
                action
                for action in reversed(decision_actions)
                if action.acted_by_id == concentrated_user_id
            )
            points = min(concentrated_levels * 5, 20)
            score += points
            factors.append(
                {
                    "code": "approver_concentration",
                    "source": "general",
                    "severity": "high" if concentrated_levels >= 3 else "medium",
                    "points": points,
                    "message": (
                        f"{concentrated_action.acted_by.fullname} acted across "
                        f"{concentrated_levels} approval levels."
                    ),
                    "level": None,
                    "category": "Segregation of duties",
                    "comment": None,
                    "acted_by": concentrated_action.acted_by.fullname,
                    "occurred_at": concentrated_action.created_at,
                }
            )

        previous_event_at = self.approval.created_at
        fast_decisions = []
        slow_decisions = []

        for action in actions:
            response_seconds = max(
                0,
                int((action.created_at - previous_event_at).total_seconds()),
            )
            if action in decision_actions:
                if response_seconds < 60:
                    fast_decisions.append(action)
                elif response_seconds > 72 * 60 * 60:
                    slow_decisions.append(action)
            previous_event_at = action.created_at

        if fast_decisions:
            points = min(len(fast_decisions) * 5, 15)
            score += points
            factors.append(
                {
                    "code": "rapid_decisions",
                    "source": "general",
                    "severity": "medium",
                    "points": points,
                    "message": (
                        f"{len(fast_decisions)} decision(s) were completed "
                        "in under one minute."
                    ),
                    "level": self._task_level(fast_decisions[-1].task),
                    "category": "Response time",
                    "comment": None,
                    "acted_by": (
                        fast_decisions[-1].acted_by.fullname
                        if fast_decisions[-1].acted_by
                        else None
                    ),
                    "occurred_at": fast_decisions[-1].created_at,
                }
            )

        if slow_decisions:
            points = min(len(slow_decisions) * 5, 15)
            score += points
            factors.append(
                {
                    "code": "delayed_decisions",
                    "source": "general",
                    "severity": "low",
                    "points": points,
                    "message": (
                        f"{len(slow_decisions)} decision(s) took longer "
                        "than 72 hours."
                    ),
                    "level": self._task_level(slow_decisions[-1].task),
                    "category": "Response time",
                    "comment": None,
                    "acted_by": (
                        slow_decisions[-1].acted_by.fullname
                        if slow_decisions[-1].acted_by
                        else None
                    ),
                    "occurred_at": slow_decisions[-1].created_at,
                }
            )

        for rejected_task in [task for task in tasks if task.status == "rejected"]:
            later_task = next(
                (
                    task
                    for task in tasks
                    if task.effective_sequence > rejected_task.effective_sequence
                    and task.status in {"pending", "approved", "rejected", "overridden"}
                ),
                None,
            )

            if not later_task:
                continue

            continued_rejections += 1
            points = 40
            score += points

            rejection_action = next(
                (
                    action
                    for action in reversed(rejection_actions)
                    if action.task_id == rejected_task.pk
                ),
                None,
            )

            level_name = self._task_level(rejected_task)
            factors.append(
                {
                    "code": "rejection_continued",
                    "severity": "high",
                    "points": points,
                    "message": (
                        f"{level_name} rejected this approval, "
                        f"but the workflow continued to "
                        f"{self._task_level(later_task)}."
                    ),
                    "level": level_name,
                    "category": self._task_category(rejected_task),
                    "comment": (
                        rejection_action.comment
                        if rejection_action
                        else rejected_task.comment
                    ),
                    "acted_by": (
                        rejection_action.acted_by.fullname
                        if rejection_action and rejection_action.acted_by
                        else (
                            rejected_task.approved_by_fullname
                            if hasattr(rejected_task, "approved_by_fullname")
                            else None
                        )
                    ),
                    "occurred_at": (
                        rejection_action.created_at
                        if rejection_action
                        else rejected_task.updated_at
                    ),
                }
            )

        if self.approval.status == "rejected":
            points = 50
            score += points
            factors.append(
                {
                    "code": "workflow_rejected",
                    "severity": "critical",
                    "points": points,
                    "message": "The overall approval workflow was rejected.",
                    "level": None,
                    "category": None,
                    "comment": None,
                    "acted_by": None,
                    "occurred_at": self.approval.updated_at,
                }
            )

        if send_back_actions:
            points = min(len(send_back_actions) * 10, 20)
            score += points
            latest = send_back_actions[-1]
            factors.append(
                {
                    "code": "sent_back",
                    "severity": "medium",
                    "points": points,
                    "message": (
                        f"The approval was sent back "
                        f"{len(send_back_actions)} time(s) for correction."
                    ),
                    "level": self._task_level(latest.task),
                    "category": self._task_category(latest.task),
                    "comment": latest.comment,
                    "acted_by": (latest.acted_by.fullname if latest.acted_by else None),
                    "occurred_at": latest.created_at,
                }
            )

        if override_actions:
            points = min(len(override_actions) * 20, 40)
            score += points
            latest = override_actions[-1]
            factors.append(
                {
                    "code": "overridden",
                    "severity": "high",
                    "points": points,
                    "message": (
                        f"{len(override_actions)} approval action(s) "
                        "were overridden."
                    ),
                    "level": self._task_level(latest.task),
                    "category": self._task_category(latest.task),
                    "comment": latest.comment,
                    "acted_by": (latest.acted_by.fullname if latest.acted_by else None),
                    "occurred_at": latest.created_at,
                }
            )

        if reset_actions:
            points = min(len(reset_actions) * 10, 20)
            score += points
            latest = reset_actions[-1]
            factors.append(
                {
                    "code": "reopened",
                    "severity": "medium",
                    "points": points,
                    "message": (
                        f"The approval was reopened " f"{len(reset_actions)} time(s)."
                    ),
                    "level": self._task_level(latest.task),
                    "category": self._task_category(latest.task),
                    "comment": latest.comment,
                    "acted_by": (latest.acted_by.fullname if latest.acted_by else None),
                    "occurred_at": latest.created_at,
                }
            )

        if recall_actions:
            points = min(len(recall_actions) * 15, 30)
            score += points
            latest = recall_actions[-1]
            factors.append(
                {
                    "code": "approval_recalled",
                    "source": "general",
                    "severity": "medium",
                    "points": points,
                    "message": (
                        f"The approval was recalled {len(recall_actions)} time(s)."
                    ),
                    "level": self._task_level(latest.task),
                    "category": "Workflow stability",
                    "comment": latest.comment,
                    "acted_by": (latest.acted_by.fullname if latest.acted_by else None),
                    "occurred_at": latest.created_at,
                }
            )

        if len(rejection_actions) > 1:
            points = 15
            score += points
            factors.append(
                {
                    "code": "multiple_rejections",
                    "severity": "high",
                    "points": points,
                    "message": (
                        f"The workflow contains "
                        f"{len(rejection_actions)} rejection events."
                    ),
                    "level": None,
                    "category": None,
                    "comment": None,
                    "acted_by": None,
                    "occurred_at": rejection_actions[-1].created_at,
                }
            )

        scoped_analysis = analyse_scoped_risk(self.approval, actions)
        score += scoped_analysis["score"]
        factors.extend(scoped_analysis["factors"])

        for factor in factors:
            factor.setdefault("source", "general")

        score = min(score, 100)

        return {
            "score": score,
            "rating": self._rating(score),
            "has_dissent": continued_rejections > 0,
            "counts": {
                "rejections": len(rejection_actions),
                "continued_rejections": continued_rejections,
                "send_backs": len(send_back_actions),
                "overrides": len(override_actions),
                "reopens": len(reset_actions),
                "recalls": len(recall_actions),
                "decisions_without_reason": (
                    len(unexplained_rejections) + len(unexplained_approvals)
                ),
                "repeated_approver_levels": concentrated_levels,
                "fast_decisions": len(fast_decisions),
                "slow_decisions": len(slow_decisions),
                **scoped_analysis["counts"],
            },
            "factors": factors,
            "generated_at": timezone.now(),
        }
