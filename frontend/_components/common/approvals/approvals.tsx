import type {Approval, ApprovableEntityStatus} from "#/_types/approvals.types";
import {APPROVALS_API} from "#/_api/approvals.helpers";
import React, {useCallback, useEffect, useState} from "react";
import {createPortal} from "react-dom";
import {ChevronRight} from "lucide-react";
import {ApprovalWorkflow, type ApprovalWorkflowAction} from "./approval-workflow";
import {Button} from "@/components/ui/button";

type ApprovalsData =
  | {
      base_uuid: string;
      model_content_type_id: number;
      approvals?: Approval[];
      approval_status?: ApprovableEntityStatus;
    }
  | {
      base_uuid?: never;
      model_content_type_id?: never;
      approvals?: Approval[];
      approval_status?: ApprovableEntityStatus;
    };

interface ApprovalsProps {
  entity: string;
  externalTrigger?: boolean;
  data: ApprovalsData;
  onRefresh?: () => void;
  onActionComplete?: (action: ApprovalWorkflowAction) => void;
  onExpandedChange?: (expanded: boolean) => void;
  children: React.ReactNode;
  collapsedToggleClassName?: string;
  collapsedToggleStyle?: React.CSSProperties;
  expandedToggleClassName?: string;
  expandedPanelClassName?: string;
  expandedPanelOuterClassName?: string;
  expandedContentClassName?: string;
  toggleContainer?: HTMLElement | null;
}

const Approvals: React.FC<ApprovalsProps> = ({
  entity,
  externalTrigger = false,
  data,
  onRefresh,
  onActionComplete,
  onExpandedChange,
  children,
  collapsedToggleClassName,
  collapsedToggleStyle,
  expandedToggleClassName,
  expandedPanelClassName,
  expandedPanelOuterClassName,
  expandedContentClassName,
  toggleContainer,
}) => {
  const {
    approvals: embeddedApprovals,
    approval_status,
    base_uuid,
    model_content_type_id,
  } = data || {};
  const [fetchedApprovals, setFetchedApprovals] = useState<Approval[]>([]);
  const usesApprovalEndpoint = Boolean(base_uuid && model_content_type_id);

  const fetchObjectApprovals = useCallback(async () => {
    if (!base_uuid || !model_content_type_id) {
      setFetchedApprovals([]);
      return;
    }

    const response = await APPROVALS_API.fetchAll({
      content_type_id: model_content_type_id,
      object_base_uuid: base_uuid,
      page_size: 100,
    });

    setFetchedApprovals(response.results);
  }, [base_uuid, model_content_type_id]);

  useEffect(() => {
    let cancelled = false;

    if (!usesApprovalEndpoint) {
      setFetchedApprovals([]);
      return;
    }

    void fetchObjectApprovals().catch((error) => {
      if (!cancelled) {
        setFetchedApprovals([]);
        console.error(`Failed to load approvals for ${entity}:`, error);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [entity, fetchObjectApprovals, usesApprovalEndpoint]);

  const approvals = usesApprovalEndpoint ? fetchedApprovals : (embeddedApprovals ?? []);

  const approvalsWithTasks = approvals.filter(
    (approval) => Array.isArray(approval.tasks) && approval.tasks.length > 0,
  );
  const isWorkflowDone =
    approvalsWithTasks.length > 0 &&
    approvalsWithTasks.every(
      (approval) => approval.status === "completed" || approval.status === "rejected",
    );
  const [collapsedOverride, setIsCollapsed] = useState<boolean | null>(null);
  const isCollapsed = collapsedOverride ?? isWorkflowDone;

  const showWorkflow = approvalsWithTasks.length > 0;
  const collapsedButtonClass = `border-primary bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary ${
    isWorkflowDone ? "" : "animate-pulse"
  }`;

  useEffect(() => {
    if (isWorkflowDone && !externalTrigger) setIsCollapsed(true);
  }, [isWorkflowDone, externalTrigger]);

  useEffect(() => {
    onExpandedChange?.(showWorkflow && !isCollapsed);
  }, [isCollapsed, onExpandedChange, showWorkflow]);

  const handleRefresh = useCallback(async () => {
    await Promise.all([
      usesApprovalEndpoint ? fetchObjectApprovals() : Promise.resolve(),
      Promise.resolve(onRefresh?.()),
    ]);
  }, [fetchObjectApprovals, onRefresh, usesApprovalEndpoint]);

  if (!showWorkflow) {
    return <div className="space-y-8">{children}</div>;
  }

  const desktopToggle = (
    <div
      style={!toggleContainer && isCollapsed ? collapsedToggleStyle : undefined}
      className={
        toggleContainer
          ? "flex items-center"
          : `hidden lg:flex z-30 items-center ${
              isCollapsed
                ? (collapsedToggleClassName ?? "absolute right-0 top-10")
                : `order-2 sticky top-6 self-start flex-shrink-0 mx-2 ${
                    expandedToggleClassName ?? ""
                  }`
            }`
      }
    >
      <Button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className={`relative flex items-center justify-center border shadow-sm transition-all duration-300
          ${
            isCollapsed
              ? `${collapsedButtonClass} h-8 rounded-md px-3 text-sm font-medium`
              : "size-8 rounded-full p-0 border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}
        aria-expanded={!isCollapsed}
      >
        {isCollapsed && !isWorkflowDone && (
          <>
            <span className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-primary/30" />
            <span className="pointer-events-none absolute inset-0 animate-ping rounded-full bg-primary/20 [animation-delay:0.4s]" />
          </>
        )}
        {isCollapsed ? (
          <span className="relative">Show Approvals</span>
        ) : (
          <ChevronRight className="size-5" />
        )}
      </Button>
    </div>
  );

  return (
    <div className="flex flex-col lg:flex-row gap-0 items-start min-h-0">
      {/* Main content */}
      <div
        className={`order-3 min-w-0 w-full flex-1 space-y-8 lg:order-1 lg:w-auto ${
          !isCollapsed ? (expandedContentClassName ?? "") : ""
        }`}
      >
        {children}
      </div>

      {/* Desktop/header toggle button */}
      {!(externalTrigger && isCollapsed) &&
        (toggleContainer
          ? isCollapsed
            ? createPortal(desktopToggle, toggleContainer)
            : null
          : desktopToggle)}

      {/* Mobile toggle button */}
      {!toggleContainer && !(externalTrigger && isCollapsed) && (
        <div className="order-1 flex w-full justify-end lg:hidden">
          <Button
            onClick={() => setIsCollapsed(!isCollapsed)}
            aria-expanded={!isCollapsed}
            className={`relative flex items-center justify-center border shadow-sm transition-all duration-300
              ${
                isCollapsed
                  ? `${collapsedButtonClass} h-8 rounded-md px-3 text-sm font-medium`
                  : "size-8 rounded-full p-0 border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground"
              }`}
          >
            {isCollapsed && !isWorkflowDone && (
              <>
                <span className="absolute inset-0 rounded-md animate-ping bg-primary/30 pointer-events-none" />
                <span className="absolute inset-0 rounded-md animate-ping bg-primary/20 pointer-events-none [animation-delay:0.4s]" />
              </>
            )}
            {isCollapsed ? (
              <span className="relative">Approvals</span>
            ) : (
              <ChevronRight className="size-5" />
            )}
          </Button>
        </div>
      )}

      {/* Approval workflow panel */}
      <div
        className={`order-2 lg:order-3 relative flex-shrink-0 w-full transition-all duration-300 ease-in-out
        ${
          isCollapsed
            ? "hidden lg:block lg:w-0 lg:overflow-hidden lg:opacity-0 lg:pointer-events-none"
            : toggleContainer
              ? `lg:w-[calc(24rem+2.5rem)] xl:w-[calc(26rem+2.5rem)]
                lg:self-stretch opacity-100`
              : "lg:w-[24rem] xl:w-[26rem] lg:self-stretch opacity-100"
        }
        ${!isCollapsed ? (expandedPanelOuterClassName ?? "") : ""}
      `}
      >
        <div
          className={`flex items-start gap-2 pb-6 lg:sticky lg:top-0 lg:max-h-[calc(94svh-3rem)] lg:overflow-y-auto lg:pl-2 ${
            expandedPanelClassName ?? ""
          }`}
        >
          {toggleContainer && !isCollapsed ? desktopToggle : null}
          <div className="min-w-0 flex-1">
            <ApprovalWorkflow
              approvals={approvalsWithTasks}
              instance_approval_status={approval_status}
              onRefresh={() => {
                void handleRefresh();
              }}
              onActionComplete={onActionComplete}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Approvals;
