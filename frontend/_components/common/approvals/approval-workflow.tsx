"use client";

import type {
  ApprovableEntityStatus,
  Approval,
  ApprovalTask,
  ApprovalDocumentCategory,
} from "#/_types/approvals.types";
import {useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState} from "react";
import {format} from "date-fns";
import {useSelector} from "react-redux";
import {Icon} from "@iconify/react";

import {Button} from "@/components/ui/button";
import {Badge} from "@/components/ui/badge";
import {Label} from "@/components/ui/label";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {APPROVAL_TASKS_API} from "#/_api/approvals.helpers";
import {formatTransactionDate} from "#/_api/helpers";
import {selectSelectedInstitution, selectUser} from "@/store/auth/selectors";
import {Textarea} from "../inputs/text-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import SwitchSetting from "../inputs/switch-setting";
import {ApprovalRiskAnalysis} from "./approval-risk-analysis";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const HISTORY_ACTION_LABELS: Record<string, string> = {
  approved: "Approved",
  rejected: "Declined",
  sent_back: "Sent back",
  reset: "Reopened",
  overridden: "Overridden",
  recalled: "Recalled",
};

const ACTION_COLORS: Record<string, string> = {
  approved: "bg-green-500",
  rejected: "bg-red-500",
  sent_back: "bg-amber-500",
  reset: "bg-blue-500",
  overridden: "bg-violet-500",
  recalled: "bg-orange-500",
};

const WORKFLOW_ACTION_LABELS: Record<string, string> = {
  create: "Creation",
  update: "Update",
  delete: "Deletion",
};

function getPositiveActionCopy(category: ApprovalDocumentCategory | null) {
  const categoryName = category?.name?.trim().toLowerCase() ?? "";
  const isAuthorisation = /authoris|authoriz/.test(categoryName);

  if (isAuthorisation) {
    return {
      label: "Authorise",
      completed: "Authorised",
      title: "Authorise this request?",
      description:
        "This confirms your authorisation and advances the request to the next workflow step.",
      processing: "Authorising...",
      confirm: "Authorise",
    };
  }

  return {
    label: "Approve",
    completed: "Approved",
    title: "Approve this request?",
    description: "This confirms your approval and advances the request to the next workflow step.",
    processing: "Approving...",
    confirm: "Approve",
  };
}

const formatStatus = (status?: string | null) => {
  if (status === "rejected") return "declined";
  return status ? status.replaceAll("_", " ") : null;
};

function formatElapsed(seconds: number) {
  const total = Math.max(Math.floor(seconds), 0);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${total}s`;
}

function formatElapsedPrecise(seconds: number) {
  const total = Math.max(Math.floor(seconds), 0);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const parts: string[] = [];

  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  parts.push(`${secs}s`);

  return parts.join(" ");
}

function formatTimestampWithSeconds(dateString?: string | null) {
  if (!dateString) return null;

  try {
    return format(new Date(dateString), "MMM dd, yyyy h:mm:ss a");
  } catch {
    return dateString;
  }
}

const useIsomorphicLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

export type ApprovalWorkflowAction = "approve" | "reject" | "override" | "send_back" | "recall";

interface ApprovalWorkflowProps {
  approvals: Approval[];
  instance_approval_status?: ApprovableEntityStatus;
  onRefresh?: () => void;
  onActionComplete?: (action: ApprovalWorkflowAction) => void;
  className?: string;
}

export function ApprovalWorkflow({
  approvals,
  instance_approval_status,
  onRefresh,
  onActionComplete,
  className = "",
}: ApprovalWorkflowProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [showCommentFor, setShowCommentFor] = useState<{
    taskId: number;
    taskBaseUuid: string;
    action: ApprovalWorkflowAction;
  } | null>(null);
  const [targetLevel, setTargetLevel] = useState<string>("previous");
  const [returnToSender, setReturnToSender] = useState(false);
  const [expandedHistory, setExpandedHistory] = useState<number | null>(null);
  const [expandedRoundId, setExpandedRoundId] = useState<number | null>(null);
  const [isProcessActivityExpanded, setIsProcessActivityExpanded] = useState(false);
  const currentUser = useSelector(selectUser);
  const [comment, setComment] = useState("");
  const [hasRiskAnalysis, setHasRiskAnalysis] = useState<boolean | null>(null);
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const rootRef = useRef<HTMLDivElement>(null);
  const stepNodeRefs = useRef(new Map<string, HTMLDivElement>());
  const taskContainerRefs = useRef(new Map<number, HTMLDivElement>());
  const [elapsedBadgeTops, setElapsedBadgeTops] = useState<Record<number, number>>({});
  const [, remeasure] = useReducer((tick: number) => tick + 1, 0);

  useIsomorphicLayoutEffect(() => {
    const centers = [...stepNodeRefs.current.entries()]
      .map(([key, element]) => {
        const rect = element.getBoundingClientRect();
        return {
          key,
          center: rect.top + rect.height / 2,
          round: element.closest("[data-approval-round]"),
        };
      })
      .sort((a, b) => a.center - b.center);

    const tops: Record<number, number> = {};

    centers.forEach((node, index) => {
      if (index === 0 || !node.key.startsWith("task-")) return;
      if (node.round !== centers[index - 1].round) return;

      const taskId = Number(node.key.slice("task-".length));
      const container = taskContainerRefs.current.get(taskId);

      if (!container) return;

      const midpoint = (centers[index - 1].center + node.center) / 2;
      tops[taskId] = midpoint - container.getBoundingClientRect().top;
    });

    setElapsedBadgeTops((current) => {
      const keys = Object.keys(tops);
      const unchanged =
        keys.length === Object.keys(current).length &&
        keys.every((key) => Math.abs((current[Number(key)] ?? NaN) - tops[Number(key)]) < 0.5);

      return unchanged ? current : tops;
    });
  });

  // The panel animates its width while staying mounted, so a render-time
  // measurement can land mid-transition.
  useEffect(() => {
    const root = rootRef.current;

    if (!root) return;

    const observer = new ResizeObserver(remeasure);

    observer.observe(root);

    return () => observer.disconnect();
  }, []);

  const handleActionClick = (task: ApprovalTask, action: ApprovalWorkflowAction) => {
    setHasRiskAnalysis(null);
    setShowCommentFor({taskId: task.id, taskBaseUuid: task.base_uuid, action});
    setComment("");
    setTargetLevel("previous");
    setReturnToSender(false);
  };

  const ACTION_LABELS = {
    approve: {
      title: "Approve this request?",
      description:
        "This confirms your approval and advances the request to the next workflow step.",
      ing: "Approving...",
      confirm: "Approve",
    },
    reject: {
      title: "Decline this request?",
      description: "This declines the request at the current workflow step.",
      ing: "Declining...",
      confirm: "Decline",
    },
    override: {
      title: "Override this approval?",
      description:
        "This approves the current level as an override and advances the workflow to the next step.",
      ing: "Overriding...",
      confirm: "Override",
    },
    send_back: {
      title: "Send this request back?",
      description: "The request will return to the selected workflow step for correction.",
      ing: "Sending Back...",
      confirm: "Send back",
    },
    recall: {
      title: "Recall this decision?",
      description: "This reopens your completed decision and returns it for review.",
      ing: "Recalling...",
      confirm: "Recall",
    },
  };

  const handleSubmitAction = async () => {
    if (!showCommentFor || !comment.trim()) return;

    setIsProcessing(true);
    try {
      if (showCommentFor.action === "approve") {
        await APPROVAL_TASKS_API.approve({
          baseUuid: showCommentFor.taskBaseUuid,
          comment: comment,
        });
      } else if (showCommentFor.action === "override") {
        await APPROVAL_TASKS_API.override({id: showCommentFor.taskId, comment});
      } else if (showCommentFor.action === "send_back") {
        await APPROVAL_TASKS_API.sendBack({
          baseUuid: showCommentFor.taskBaseUuid,
          payload: {
            ...(targetLevel !== "previous" && {target_level: Number(targetLevel)}),
            ...(comment && {comment}),
            return_to_sender: returnToSender,
          },
        });
      } else if (showCommentFor.action === "recall") {
        await APPROVAL_TASKS_API.recall({
          baseUuid: showCommentFor.taskBaseUuid,
          comment,
        });
      } else {
        await APPROVAL_TASKS_API.reject({
          baseUuid: showCommentFor.taskBaseUuid,
          comment,
        });
      }
      onRefresh?.();
      onActionComplete?.(showCommentFor.action);
      setShowCommentFor(null);
      setComment("");
      setReturnToSender(false);
    } catch (error) {
      console.error(`Failed to ${showCommentFor.action} task:`, error);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancelAction = () => {
    setShowCommentFor(null);
    setComment("");
    setReturnToSender(false);
  };

  const toggleHistory = (taskId: number) => {
    setExpandedHistory((current) => (current === taskId ? null : taskId));
  };

  const canUserActOnLevel = useCallback(
    (task: ApprovalTask, type: "approve" | "override"): boolean => {
      const currentUserId = currentUser?.id;

      if (!currentUserId) return false;

      if (type === "override" && selectedInstitution?.institution_owner_id === currentUserId) {
        return true;
      }

      const currentUserRoleIds = new Set((currentUser?.roles ?? []).map((role: any) => role.id));

      if (type === "approve") {
        const isDirectApprover = (task.level.approver_users ?? []).some(
          (pi: any) => pi.profile?.user?.id === currentUserId,
        );

        if (isDirectApprover) return true;

        return (task.level.approvers_detail ?? []).some(
          (entry: any) =>
            entry.approver_group?.users_display?.some(
              (user: any) => user.user?.id === currentUserId,
            ) ||
            entry.approver_group?.roles_display?.some((role: any) =>
              currentUserRoleIds.has(role.id),
            ),
        );
      }

      if (type === "override") {
        const isDirectOverrider = (task.level.overrider_users ?? []).some(
          (pi: any) => pi.profile?.user?.id === currentUserId,
        );

        if (isDirectOverrider) return true;

        return (task.level.overriders_detail ?? []).some(
          (entry: any) =>
            entry.approver_group?.users_display?.some(
              (user: any) => user.user?.id === currentUserId,
            ) ||
            entry.approver_group?.roles_display?.some((role: any) =>
              currentUserRoleIds.has(role.id),
            ),
        );
      }

      return false;
    },
    [currentUser?.id, currentUser?.roles, selectedInstitution?.institution_owner_id],
  );

  const getActionIcon = (actionName: string) => {
    switch (actionName.toLowerCase()) {
      case "create":
        return <Icon icon="hugeicons:add-01" className="!size-3 shrink-0" />;
      case "update":
        return <Icon icon="hugeicons:edit-02" className="!size-3 shrink-0" />;
      case "delete":
        return <Icon icon="hugeicons:delete-02" className="!size-3 shrink-0" />;
      default:
        return <Icon icon="hugeicons:file-validation" className="!size-3 shrink-0" />;
    }
  };

  const getActionColor = (actionName: string) => {
    switch (actionName.toLowerCase()) {
      case "create":
        return "bg-green-100 text-green-800 border-green-200";
      case "update":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "delete":
        return "bg-red-100 text-red-800 border-red-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "approved":
        return "bg-green-100 text-green-800 border-green-200";
      case "overridden":
        return "bg-violet-100 text-violet-800 border-violet-200";
      case "rejected":
        return "bg-red-100 text-red-800 border-red-200";
      case "pending":
        return "bg-blue-100 text-blue-800 border-blue-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "approved":
        return "Approved";
      case "overridden":
        return "Overridden";
      case "rejected":
        return "Declined";
      case "pending":
        return "Pending";
      default:
        return "Not Started";
    }
  };

  const buildCategoryGroups = (tasks: ApprovalTask[]) => {
    const groups: Array<{
      category: ApprovalDocumentCategory | null;
      tasks: ApprovalTask[];
    }> = [];

    const seenCategoryIds = new Set<number | "uncategorized">();

    for (const task of tasks) {
      const cat = task.level.category;
      const key = cat ? cat.id : "uncategorized";

      if (!seenCategoryIds.has(key)) {
        seenCategoryIds.add(key);
        groups.push({category: cat, tasks: []});
      }

      const targetGroup = groups.find(
        (g) => (g.category ? g.category.id : "uncategorized") === key,
      );
      targetGroup?.tasks.push(task);
    }

    return groups;
  };

  const orderedApprovals = [...approvals].sort((a, b) => b.id - a.id);
  const currentApproval =
    orderedApprovals.find((approval) => approval.status === "ongoing") ?? orderedApprovals[0];
  const displayedApprovals = currentApproval
    ? [
        currentApproval,
        ...orderedApprovals.filter((approval) => approval.id !== currentApproval.id),
      ]
    : [];
  const initiation = approvals.find((approval) => approval.initiation)?.initiation;
  const processActions = approvals
    .flatMap((approval) =>
      approval.tasks.flatMap((task) =>
        (task.actions ?? []).map((action) => ({
          ...action,
          levelName: task.level?.name,
          categoryName: task.level?.category?.name,
        })),
      ),
    )
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  const actionApproval = showCommentFor
    ? approvals.find((approval) => approval.tasks.some((task) => task.id === showCommentFor.taskId))
    : undefined;
  const actionTaskIndex =
    actionApproval && showCommentFor
      ? actionApproval.tasks.findIndex((task) => task.id === showCommentFor.taskId)
      : -1;
  const actionTask =
    actionApproval && actionTaskIndex >= 0 ? actionApproval.tasks[actionTaskIndex] : undefined;
  const selectedPositiveAction = getPositiveActionCopy(actionTask?.level?.category ?? null);
  const priorActionTasks =
    actionApproval && actionTaskIndex > 0
      ? actionApproval.tasks
          .slice(0, actionTaskIndex)
          .filter((task) => task.status === "approved" || task.status === "overridden")
      : [];

  if (approvals.length === 0) {
    return null;
  }

  return (
    <div ref={rootRef} className={`space-y-2 ${className}`}>
      <h3 className="text-base font-semibold">Approval Workflow</h3>

      {displayedApprovals.map((approval, index) => {
        const categoryGroups = buildCategoryGroups(approval.tasks);
        const isCurrentRound = approval.id === currentApproval.id;
        const isExpanded = isCurrentRound || expandedRoundId === approval.id;
        const roundNumber = orderedApprovals.length - orderedApprovals.indexOf(approval);
        const actionLabel =
          WORKFLOW_ACTION_LABELS[approval.action.name.toLowerCase()] ?? approval.action.name;
        const statusLabel =
          approval.status === "ongoing"
            ? "In progress"
            : approval.status === "completed"
              ? "Completed"
              : "Declined";
        const roundTitle = (
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className={`${getActionColor(approval.action.name)} gap-1`}>
                {getActionIcon(approval.action.name)}
                {actionLabel}
              </Badge>
              <span className="text-xs font-medium text-muted-foreground">Round {roundNumber}</span>
              <span className="text-xs font-medium">{statusLabel}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Started {formatTransactionDate(approval.created_at)}
            </p>
          </div>
        );

        return (
          <div key={approval.id} data-approval-round={approval.id} className="space-y-2">
            {index === 0 && (
              <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {approval.status === "ongoing" ? "Current round" : "Latest round"}
              </p>
            )}
            {index === 1 && (
              <div className="flex items-center gap-2 border-t pt-4">
                <Icon icon="hugeicons:time-04" className="h-4 w-4 text-muted-foreground" />
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Approval history ({displayedApprovals.length - 1})
                </p>
              </div>
            )}
            <div className="overflow-hidden rounded-lg border">
              {isCurrentRound ? (
                <div className="bg-muted/30 p-3">{roundTitle}</div>
              ) : (
                <button
                  type="button"
                  aria-expanded={isExpanded}
                  aria-controls={`approval-round-${approval.id}`}
                  onClick={() => {
                    setExpandedRoundId(isExpanded ? null : approval.id);
                    setExpandedHistory(null);
                  }}
                  className="approval-history-toggle flex w-full items-center justify-between gap-3 p-3 text-left hover:bg-muted/40"
                >
                  {roundTitle}
                  <Icon
                    icon="hugeicons:arrow-down-01"
                    className={`h-4 w-4 shrink-0 transition-transform ${
                      isExpanded ? "rotate-180" : ""
                    }`}
                  />
                </button>
              )}
              <div id={`approval-round-${approval.id}`} hidden={!isExpanded}>
                {isExpanded && (
                  <div className="border-t p-3">
                    {/* Category groups */}
                    <div className="space-y-4">
                      {isCurrentRound && initiation && (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 px-1">
                            <div className="h-px flex-1 bg-gray-200" />
                            <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-gray-500">
                              Initiation Information
                            </span>
                            <div className="h-px flex-1 bg-gray-200" />
                          </div>

                          <div className="grid w-full grid-cols-[1.5rem_minmax(0,1fr)] items-center gap-3">
                            <div className="relative flex self-stretch items-center justify-center">
                              <span className="absolute bottom-[-1rem] left-1/2 top-1/2 w-px -translate-x-1/2 bg-gray-300" />
                              <div
                                ref={(element) => {
                                  if (element) stepNodeRefs.current.set("initiation", element);
                                  else stepNodeRefs.current.delete("initiation");
                                }}
                                className="relative z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 border-green-500 bg-green-100"
                              >
                                <span className="text-sm font-semibold text-green-700">1</span>
                              </div>
                            </div>

                            <div className="min-w-0 rounded-xl bg-gray-100 p-2.5">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-semibold text-gray-900">
                                    {initiation.created_by_fullname}
                                  </p>
                                  <time className="mt-1 block text-xs text-gray-500">
                                    {formatTransactionDate(initiation.created_at)}
                                  </time>
                                </div>

                                <button
                                  type="button"
                                  onClick={() =>
                                    setIsProcessActivityExpanded((expanded) => !expanded)
                                  }
                                  aria-expanded={isProcessActivityExpanded}
                                  className="flex shrink-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-[11px] font-medium text-gray-600 hover:bg-gray-200/70"
                                >
                                  <Icon icon="hugeicons:time-04" className="h-3.5 w-3.5" />
                                  <span>Overall activity</span>
                                  <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px]">
                                    {processActions.length + 1}
                                  </span>
                                  <Icon
                                    icon="hugeicons:arrow-down-01"
                                    className={`h-3.5 w-3.5 transition-transform ${
                                      isProcessActivityExpanded ? "rotate-180" : ""
                                    }`}
                                  />
                                </button>
                              </div>
                            </div>
                          </div>

                          {isProcessActivityExpanded && (
                            <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200 bg-white px-3">
                              <div className="border-b border-gray-100 py-3">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <p className="text-xs font-semibold text-gray-900">
                                      {initiation.created_by_fullname}{" "}
                                      <span className="font-normal text-gray-600">initiated</span>
                                    </p>
                                    <p className="mt-0.5 text-[11px] text-gray-500">
                                      Initiation Information
                                    </p>
                                  </div>

                                  <time className="shrink-0 text-[10px] text-gray-400">
                                    {formatTransactionDate(initiation.created_at)}
                                  </time>
                                </div>
                              </div>

                              {processActions.map((action) => (
                                <div
                                  key={action.id}
                                  className="border-b border-gray-100 py-3 last:border-b-0"
                                >
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <p className="text-xs font-semibold text-gray-900">
                                        {action.acted_by_fullname ?? "System"}{" "}
                                        <span className="font-normal text-gray-600">
                                          {HISTORY_ACTION_LABELS[action.action]?.toLowerCase() ??
                                            action.action.replaceAll("_", " ")}
                                        </span>
                                      </p>
                                      <p className="mt-0.5 text-[11px] text-gray-500">
                                        {[action.levelName, action.categoryName]
                                          .filter(Boolean)
                                          .join(" · ")}
                                      </p>
                                    </div>
                                    <time className="shrink-0 text-[10px] text-gray-400">
                                      {formatTransactionDate(action.created_at)}
                                    </time>
                                  </div>

                                  {action.comment?.trim() && (
                                    <p className="mt-2 rounded-md bg-gray-50 px-2.5 py-2 text-xs text-gray-700">
                                      {action.comment}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {categoryGroups.map((group) => (
                        <div key={group.category?.id ?? "uncategorized"} className="space-y-2">
                          {/* Keep category metadata out of the timeline rail. */}
                          <div className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-3">
                            <div className="relative flex justify-center">
                              <span className="absolute bottom-[-0.5rem] left-1/2 top-[-0.5rem] w-px -translate-x-1/2 bg-gray-300" />
                            </div>

                            <div className="min-w-0 space-y-1">
                              <div className="flex items-center gap-2">
                                <div className="h-px flex-1 bg-gray-200" />
                                <span className="whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-gray-500">
                                  {group.category ? group.category.name : "General"}
                                </span>
                                <div className="h-px flex-1 bg-gray-200" />
                              </div>

                              {group.category?.description && (
                                <p className="text-xs text-muted-foreground">
                                  {group.category.description}
                                </p>
                              )}
                            </div>
                          </div>

                          {/* Tasks within this category */}
                          {group.tasks.map((task, taskIndex) => {
                            const canApprove = canUserActOnLevel(task, "approve");
                            const canOverride = !canApprove && canUserActOnLevel(task, "override");
                            const positiveAction = getPositiveActionCopy(task.level.category);
                            // Global step number across all tasks in the approval
                            const globalIndex = approval.tasks.indexOf(task);
                            const priorApprovedTasks = approval.tasks
                              .slice(0, globalIndex)
                              .filter((t) => t.status === "approved" || t.status === "overridden");
                            const canSendBack =
                              (canApprove ||
                                selectedInstitution?.institution_owner_id === currentUser?.id) &&
                              priorApprovedTasks.length > 0;
                            const taskActions = [...(task.actions ?? [])]
                              .sort(
                                (a, b) =>
                                  new Date(a.created_at).getTime() -
                                  new Date(b.created_at).getTime(),
                              )
                              .filter(
                                (action, _index, actions) =>
                                  !(
                                    action.action === "reset" &&
                                    actions.some(
                                      (candidate) =>
                                        candidate.action === "sent_back" &&
                                        candidate.acted_by === action.acted_by &&
                                        candidate.comment === action.comment &&
                                        candidate.from_level === action.from_level &&
                                        Math.abs(
                                          new Date(candidate.created_at).getTime() -
                                            new Date(action.created_at).getTime(),
                                        ) < 5000,
                                    )
                                  ),
                              );
                            const isHistoryExpanded = expandedHistory === task.id;
                            const elapsedSeconds = task.timing?.elapsed_seconds ?? 0;

                            return (
                              <div
                                key={task.id}
                                ref={(element) => {
                                  if (element) taskContainerRefs.current.set(task.id, element);
                                  else taskContainerRefs.current.delete(task.id);
                                }}
                                className="relative"
                              >
                                {task.timing?.state === "completed" && (
                                  <div
                                    className="absolute left-3 z-20 -translate-x-1/2 -translate-y-1/2"
                                    style={{top: elapsedBadgeTops[task.id] ?? 0}}
                                  >
                                    <Popover>
                                      <PopoverTrigger asChild>
                                        <button
                                          type="button"
                                          aria-label={`Explain elapsed time: ${formatElapsed(elapsedSeconds)}`}
                                          className="block whitespace-nowrap rounded-full border border-gray-200 bg-white px-1.5 py-0.5 text-[9px] font-semibold text-gray-600 hover:bg-gray-50"
                                        >
                                          {formatElapsed(elapsedSeconds)}
                                        </button>
                                      </PopoverTrigger>
                                      <PopoverContent
                                        side="right"
                                        align="center"
                                        sideOffset={8}
                                        className="w-72 space-y-2 p-2.5 text-xs text-gray-700"
                                      >
                                        <div className="text-sm font-semibold text-gray-900">
                                          {formatElapsedPrecise(elapsedSeconds)}
                                        </div>
                                        <div className="space-y-1">
                                          <div className="flex items-start justify-between gap-2">
                                            <span className="text-gray-500">From</span>
                                            <span className="text-right font-medium text-gray-800">
                                              {formatTimestampWithSeconds(task.timing.started_at) ??
                                                "—"}
                                            </span>
                                          </div>
                                          <div className="flex items-start justify-between gap-2">
                                            <span className="text-gray-500">To</span>
                                            <span className="text-right font-medium text-gray-800">
                                              {formatTimestampWithSeconds(task.timing.ended_at) ??
                                                "—"}
                                            </span>
                                          </div>
                                        </div>
                                        <p className="border-t border-gray-100 pt-2 text-gray-600">
                                          {task.timing.started_by === "workflow_initiated"
                                            ? "Time from requisition initiation until this approval action"
                                            : "Time from the preceding approval action until this action"}
                                        </p>
                                      </PopoverContent>
                                    </Popover>
                                  </div>
                                )}

                                <div className="flex flex-col items-start gap-2">
                                  <div className="grid w-full grid-cols-[1.5rem_minmax(0,1fr)] items-center gap-3">
                                    {/* Shared vertical timeline rail */}
                                    <div className="relative flex self-stretch items-center justify-center">
                                      <span
                                        className={`absolute left-1/2 top-[-0.5rem] w-px -translate-x-1/2 bg-gray-300 ${
                                          globalIndex < approval.tasks.length - 1
                                            ? "bottom-[-1rem]"
                                            : "bottom-1/2"
                                        }`}
                                      />

                                      <div
                                        ref={(element) => {
                                          if (element)
                                            stepNodeRefs.current.set(`task-${task.id}`, element);
                                          else stepNodeRefs.current.delete(`task-${task.id}`);
                                        }}
                                        className={`relative z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 ${
                                          task.status === "approved"
                                            ? "border-green-500 bg-green-100"
                                            : task.status === "overridden"
                                              ? "border-violet-500 bg-violet-100"
                                              : task.status === "rejected"
                                                ? "border-red-500 bg-red-100"
                                                : "border-blue-400 bg-blue-100"
                                        }`}
                                      >
                                        <span
                                          className={`text-xs font-semibold md:text-sm ${
                                            task.status === "approved"
                                              ? "text-green-700"
                                              : task.status === "overridden"
                                                ? "text-violet-700"
                                                : task.status === "rejected"
                                                  ? "text-red-700"
                                                  : "text-blue-700"
                                          }`}
                                        >
                                          {globalIndex + 2}
                                        </span>
                                      </div>
                                    </div>

                                    <div className="flex w-full flex-col rounded-xl border border-transparent bg-gray-100 p-2.5 transition-colors duration-150 hover:border-gray-200 hover:bg-gray-50">
                                      {/* Task name + status badge */}
                                      <div className="grid min-h-7 grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
                                        <div className="min-w-0 space-y-1">
                                          <div className="flex min-w-0 flex-wrap items-center gap-2">
                                            <h4 className="text-sm font-medium text-gray-900">
                                              {task.level?.name ||
                                                `Approval Step ${globalIndex + 1}`}
                                            </h4>
                                            <Badge
                                              variant="outline"
                                              className={`text-xs ${getStatusColor(task.status)}`}
                                            >
                                              <span>{getStatusText(task.status)}</span>
                                            </Badge>
                                          </div>
                                        </div>

                                        {taskActions.length > 0 && (
                                          <button
                                            type="button"
                                            onClick={() => toggleHistory(task.id)}
                                            aria-expanded={isHistoryExpanded}
                                            className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-transparent px-1.5 py-1 text-[11px] font-medium text-gray-600 transition-colors duration-150 hover:border-gray-200 hover:bg-gray-200/70 hover:text-gray-900"
                                          >
                                            <Icon
                                              icon="hugeicons:time-04"
                                              className="h-3.5 w-3.5"
                                            />
                                            <span>Level activity</span>
                                            <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px]">
                                              {taskActions.length}
                                            </span>
                                            <Icon
                                              icon="hugeicons:arrow-down-01"
                                              className={`h-3.5 w-3.5 transition-transform ${
                                                isHistoryExpanded ? "rotate-180" : ""
                                              }`}
                                            />
                                          </button>
                                        )}
                                      </div>

                                      {(task.status === "approved" ||
                                        task.status === "overridden" ||
                                        task.status === "rejected") && (
                                        <div className="mt-1 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-xs text-gray-500">
                                          {task.approved_by_fullname && (
                                            <span className="truncate font-medium text-gray-600">
                                              {task.approved_by_fullname}
                                            </span>
                                          )}
                                          <time className="shrink-0 text-right">
                                            {formatTransactionDate(task.updated_at)}
                                          </time>
                                        </div>
                                      )}

                                      {/* Timestamp / actor — only useful after an action */}
                                      {task.active_return_route && (
                                        <div className="mt-2 rounded-lg border border-gray-200 bg-white p-3 text-xs text-gray-700 shadow-sm">
                                          <div className="flex items-center gap-2">
                                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber-50 text-amber-700">
                                              <Icon
                                                icon="hugeicons:reload"
                                                className="h-3.5 w-3.5"
                                              />
                                            </span>
                                            <p className="font-semibold text-gray-900">
                                              Correction requested
                                            </p>
                                          </div>
                                          {task.active_return_route.description && (
                                            <p className="mt-2 leading-relaxed text-gray-700">
                                              {task.active_return_route.description}
                                            </p>
                                          )}
                                          <p className="mt-2 border-t border-gray-100 pt-2 text-[11px] leading-relaxed text-gray-500">
                                            Sent by{" "}
                                            <span className="font-medium text-gray-700">
                                              {task.active_return_route.sent_by_fullname ??
                                                `level ${task.active_return_route.source_level}`}
                                            </span>
                                            . After completion, it returns directly to level{" "}
                                            <span className="font-medium text-gray-700">
                                              {task.active_return_route.source_level}
                                            </span>
                                            .
                                          </p>
                                        </div>
                                      )}

                                      {taskActions.length > 0 && isHistoryExpanded && (
                                        <div className="mt-2 max-h-72 space-y-0 overflow-y-auto rounded-lg border border-gray-200 bg-white px-3">
                                          {taskActions.map((action, actionIndex) => {
                                            const fromStatus = formatStatus(action.from_status);
                                            const toStatus = formatStatus(action.to_status);

                                            return (
                                              <div
                                                key={action.id}
                                                className="relative flex gap-3 border-b border-gray-100 py-3 last:border-b-0"
                                              >
                                                <div className="relative flex w-5 shrink-0 justify-center">
                                                  <span
                                                    className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold text-white ring-4 ring-white ${
                                                      ACTION_COLORS[action.action] ?? "bg-gray-400"
                                                    }`}
                                                  >
                                                    {actionIndex + 1}
                                                  </span>
                                                  {actionIndex < taskActions.length - 1 && (
                                                    <span className="absolute bottom-[-12px] top-6 w-px bg-gray-200" />
                                                  )}
                                                </div>

                                                <div className="min-w-0 flex-1">
                                                  <div className="flex flex-wrap items-start justify-between gap-1">
                                                    <p className="text-xs font-semibold text-gray-900">
                                                      {HISTORY_ACTION_LABELS[action.action] ??
                                                        action.action.replaceAll("_", " ")}
                                                    </p>
                                                    <time className="text-[10px] text-gray-400">
                                                      {formatTransactionDate(action.created_at)}
                                                    </time>
                                                  </div>

                                                  <p className="mt-0.5 text-[11px] text-gray-500">
                                                    {action.acted_by_fullname ?? "System"}
                                                  </p>

                                                  {fromStatus &&
                                                    toStatus &&
                                                    fromStatus !== toStatus && (
                                                      <div className="mt-1.5 flex items-center gap-1.5 text-[10px] capitalize text-gray-600">
                                                        <span className="rounded-full bg-gray-100 px-2 py-0.5">
                                                          {fromStatus}
                                                        </span>
                                                        <Icon
                                                          icon="hugeicons:arrow-right-01"
                                                          className="h-3 w-3 text-gray-400"
                                                        />
                                                        <span className="rounded-full bg-gray-100 px-2 py-0.5">
                                                          {toStatus}
                                                        </span>
                                                      </div>
                                                    )}

                                                  {action.comment?.trim() && (
                                                    <div className="mt-2 rounded-md border border-gray-100 bg-gray-50 px-2.5 py-2 text-xs leading-relaxed text-gray-700">
                                                      <Icon
                                                        icon="hugeicons:message-01"
                                                        className="mr-1.5 inline h-3 w-3 text-gray-400"
                                                      />
                                                      {action.comment}
                                                    </div>
                                                  )}
                                                </div>
                                              </div>
                                            );
                                          })}
                                        </div>
                                      )}

                                      {/* Action buttons (approve / reject / override) */}
                                      {task.status === "pending" && (canApprove || canOverride) && (
                                        <div className="mt-3 grid w-full grid-cols-1 gap-2">
                                          <p className="text-[11px] font-medium text-gray-500">
                                            Your action is required
                                          </p>
                                          {(canApprove ||
                                            selectedInstitution?.institution_owner_id ===
                                              currentUser?.id) && (
                                            <>
                                              {canApprove && (
                                                <Button
                                                  size="sm"
                                                  className="h-8 w-full bg-green-600 text-xs text-white hover:bg-green-700"
                                                  onClick={() => handleActionClick(task, "approve")}
                                                  disabled={isProcessing}
                                                >
                                                  <Icon
                                                    icon="hugeicons:tick-02"
                                                    className="mr-1.5 size-4"
                                                  />
                                                  {positiveAction.label}
                                                </Button>
                                              )}
                                              <Button
                                                size="sm"
                                                className="h-8 w-full bg-red-600 text-xs text-white hover:bg-red-700"
                                                onClick={() => handleActionClick(task, "reject")}
                                                disabled={isProcessing}
                                              >
                                                <Icon
                                                  icon="hugeicons:cancel-01"
                                                  className="mr-1.5 size-4"
                                                />
                                                Decline
                                              </Button>
                                            </>
                                          )}
                                          {canOverride && (
                                            <Button
                                              size="sm"
                                              className="h-8 w-full bg-blue-600 text-xs text-white hover:bg-blue-700"
                                              onClick={() => handleActionClick(task, "override")}
                                              disabled={isProcessing}
                                            >
                                              <Icon
                                                icon="hugeicons:file-validation"
                                                className="mr-1.5 size-4"
                                              />
                                              Override
                                            </Button>
                                          )}
                                          {canSendBack && (
                                            <Button
                                              size="sm"
                                              className="h-8 w-full bg-amber-500 text-xs text-white hover:bg-amber-600"
                                              onClick={() => handleActionClick(task, "send_back")}
                                              disabled={isProcessing}
                                            >
                                              <Icon
                                                icon="hugeicons:arrow-turn-backward"
                                                className="mr-1.5 size-4"
                                              />
                                              Send Back
                                            </Button>
                                          )}
                                        </div>
                                      )}

                                      {task.can_recall && (
                                        <Button
                                          size="sm"
                                          className="mt-3 h-8 w-full bg-orange-600 text-xs text-white hover:bg-orange-700"
                                          onClick={() => handleActionClick(task, "recall")}
                                          disabled={isProcessing}
                                        >
                                          <Icon
                                            icon="hugeicons:undo-02"
                                            className="mr-1.5 size-4"
                                          />
                                          Recall Decision
                                        </Button>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* Dotted connector between tasks within the same category */}
                                {taskIndex < group.tasks.length - 1 && (
                                  <div
                                    className="absolute left-1/2 -translate-x-1/2 w-0.5 h-12 ml-1"
                                    style={{
                                      backgroundImage:
                                        "repeating-linear-gradient(0deg, transparent, transparent 2px, #d1d5db 2px, #d1d5db 4px)",
                                    }}
                                  />
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <Dialog
        open={showCommentFor !== null}
        onOpenChange={(open) => {
          if (!open && !isProcessing) handleCancelAction();
        }}
      >
        <DialogContent
          className="h-[720px] max-h-[90vh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-xl"
          onPointerDownOutside={(event) => {
            if (isProcessing) event.preventDefault();
          }}
        >
          {showCommentFor && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {showCommentFor.action === "approve"
                    ? selectedPositiveAction.title
                    : ACTION_LABELS[showCommentFor.action].title}
                </DialogTitle>
                <DialogDescription>
                  {showCommentFor.action === "approve"
                    ? selectedPositiveAction.description
                    : ACTION_LABELS[showCommentFor.action].description}
                </DialogDescription>
              </DialogHeader>

              <div className="min-h-0 space-y-5 overflow-y-auto p-1 pr-3">
                <div
                  className={
                    hasRiskAnalysis === true ? "rounded-xl border bg-muted/20 p-4" : "hidden"
                  }
                >
                  <p className="text-sm font-semibold">Review risk before confirming</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Risk Analysis is optional, but can help you review unusual approval activity
                    before taking this action.
                  </p>
                  <div className="mt-3">
                    <ApprovalRiskAnalysis
                      approvals={approvals}
                      autoLoad
                      hideWhenUnavailable
                      onAvailabilityChange={setHasRiskAnalysis}
                    />
                  </div>
                </div>

                {showCommentFor.action === "send_back" && (
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor="target-level" showOptional className="text-xs font-medium">
                        Send back to
                      </Label>
                      <Select value={targetLevel} onValueChange={setTargetLevel}>
                        <SelectTrigger id="target-level" className="h-9 rounded-xl text-sm">
                          <SelectValue placeholder="Previous level" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="previous">Previous level</SelectItem>
                          {priorActionTasks.map((task) => {
                            const stepNumber =
                              (actionApproval?.tasks.findIndex(
                                (candidate) => candidate.id === task.id,
                              ) ?? 0) + 1;

                            return (
                              <SelectItem key={task.id} value={String(stepNumber)}>
                                Level {stepNumber} — {task.level?.name || `Step ${stepNumber}`}
                              </SelectItem>
                            );
                          })}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-start gap-2 rounded-lg border p-3">
                      <SwitchSetting
                        id={`return-to-sender-${showCommentFor.taskId}`}
                        label="Return directly to this level"
                        description="After the correction is completed, the approval returns directly to this step."
                        checked={returnToSender}
                        onCheckedChange={(checked) => setReturnToSender(checked === true)}
                        labelClassName="text-xs font-medium"
                      />
                    </div>
                  </div>
                )}

                <Textarea
                  id="approval-action-comment"
                  label={
                    showCommentFor.action === "recall"
                      ? "Recall reason"
                      : showCommentFor.action === "reject"
                        ? "Decline reason"
                        : showCommentFor.action === "override"
                          ? "Override reason"
                          : "Comment"
                  }
                  required
                  labelClassName="text-xs font-medium"
                  placeholder={
                    showCommentFor.action === "reject"
                      ? "Add a comment explaining why this request is being declined..."
                      : showCommentFor.action === "override"
                        ? "Add a comment explaining why this approval is being overridden..."
                        : showCommentFor.action === "recall"
                          ? "Explain why this decision is being recalled..."
                          : showCommentFor.action === "send_back"
                            ? "Describe what needs to be corrected..."
                            : "Add a comment to continue..."
                  }
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  className="mt-1 resize-none text-sm"
                  rows={5}
                  showCount
                  maxLength={150}
                />
              </div>

              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  type="button"
                  onClick={handleSubmitAction}
                  disabled={isProcessing || !comment.trim()}
                  className={`w-full ${
                    showCommentFor.action === "approve"
                      ? "bg-green-600 hover:bg-green-700"
                      : showCommentFor.action === "override"
                        ? "bg-blue-600 hover:bg-blue-700"
                        : showCommentFor.action === "send_back"
                          ? "bg-amber-500 hover:bg-amber-600"
                          : showCommentFor.action === "recall"
                            ? "bg-orange-600 hover:bg-orange-700"
                            : "bg-red-600 hover:bg-red-700"
                  }`}
                >
                  {isProcessing && (
                    <Icon icon="hugeicons:loading-03" className="mr-2 size-4 animate-spin" />
                  )}
                  {isProcessing
                    ? showCommentFor.action === "approve"
                      ? selectedPositiveAction.processing
                      : ACTION_LABELS[showCommentFor.action].ing
                    : showCommentFor.action === "approve"
                      ? selectedPositiveAction.confirm
                      : ACTION_LABELS[showCommentFor.action].confirm}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
