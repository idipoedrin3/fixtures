"use client";

import {useEffect, useMemo, useState} from "react";
import {ChevronDown, Loader2, ShieldAlert} from "lucide-react";
import {toast} from "sonner";

import type {
  Approval,
  ApprovalRiskAnalysis as ApprovalRiskAnalysisData,
} from "#/_types/approvals.types";
import {APPROVALS_API} from "#/_api/approvals.helpers";
import {Badge} from "@/components/ui/badge";
import {Button} from "@/components/ui/button";

const RATING_STYLES = {
  low: "border-green-200 bg-green-50 text-green-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  critical: "border-red-200 bg-red-50 text-red-700",
};

type ApprovalRiskAnalysisProps = {
  approvals: Approval[];
  autoLoad?: boolean;
  hideWhenUnavailable?: boolean;
  onAvailabilityChange?: (available: boolean) => void;
};

export function ApprovalRiskAnalysis({
  approvals,
  autoLoad = false,
  hideWhenUnavailable = false,
  onAvailabilityChange,
}: ApprovalRiskAnalysisProps) {
  const [analyses, setAnalyses] = useState<Array<{
    approval: Approval;
    analysis: ApprovalRiskAnalysisData;
  }> | null>(null);
  const [expandedApproval, setExpandedApproval] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const completedRiskScore = useMemo(() => {
    const completedApproval = [...approvals]
      .reverse()
      .find(
        (approval) => approval.status === "completed" && approval.completion_risk_score !== null,
      );

    return completedApproval?.completion_risk_score ?? null;
  }, [approvals]);

  const approvalStateKey = useMemo(
    () =>
      approvals
        .map(
          (approval) =>
            `${approval.base_uuid}:${approval.status}:${approval.tasks
              .map((task) => `${task.base_uuid}:${task.status}:${task.updated_at}`)
              .join(",")}`,
        )
        .join("|"),
    [approvals],
  );

  useEffect(() => {
    setAnalyses(null);
    setExpandedApproval(null);
    setIsOpen(false);
  }, [approvalStateKey]);

  const loadAnalysis = async () => {
    if (isOpen) {
      setIsOpen(false);
      return;
    }

    if (analyses !== null) {
      setIsOpen(true);
      return;
    }

    setIsLoading(true);
    try {
      const results = await Promise.all(
        approvals.map(async (approval) => ({
          approval,
          analysis: await APPROVALS_API.fetchRiskAnalysis({
            baseUuid: approval.base_uuid,
          }),
        })),
      );

      const providedAnalyses = results.filter(
        ({analysis}) => analysis.is_snapshot || analysis.factors.length > 0,
      );

      setAnalyses(providedAnalyses);
      setIsOpen(providedAnalyses.length > 0);
      onAvailabilityChange?.(providedAnalyses.length > 0);
      if (providedAnalyses.length === 0) {
        if (!autoLoad) toast.info("No approval risk signals detected.");
      }
    } catch {
      setAnalyses([]);
      setIsOpen(false);
      onAvailabilityChange?.(false);
      if (!autoLoad) toast.error("Unable to load approval risk analysis.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (autoLoad && analyses === null && !isLoading) {
      void loadAnalysis();
    }
  }, [autoLoad, analyses, isLoading]);

  if (hideWhenUnavailable && analyses?.length === 0) return null;

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={loadAnalysis}
        disabled={isLoading}
        className="h-8 gap-2"
      >
        {isLoading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <ShieldAlert className="size-4" />
        )}
        {completedRiskScore === null ? "Risk Analysis" : `Recorded Risk · ${completedRiskScore}%`}
      </Button>

      {isOpen &&
        analyses?.map(({approval, analysis}) => {
          const expanded = expandedApproval === approval.base_uuid;

          return (
            <div
              key={approval.base_uuid}
              className="overflow-hidden rounded-lg border bg-background"
            >
              <div className="p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted">
                      <ShieldAlert className="size-4" />
                    </div>
                    <p className="text-sm font-semibold">Approval Risk</p>
                  </div>

                  <Badge variant="outline" className={RATING_STYLES[analysis.rating]}>
                    {analysis.rating.toUpperCase()} · {analysis.score}/100
                  </Badge>
                </div>

                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  {analysis.factors[0]?.message ??
                    "This approval completed with no detected risk signals."}
                </p>

                <div className="mt-3 grid grid-cols-3 divide-x rounded-md border bg-muted/20">
                  {[
                    ["Rejections", analysis.counts.rejections],
                    ["Send backs", analysis.counts.send_backs],
                    ["Risk factors", analysis.factors.length],
                  ].map(([label, value]) => (
                    <div key={label} className="px-2 py-2 text-center">
                      <p className="text-sm font-semibold text-foreground">{value}</p>
                      <p className="truncate text-[10px] text-muted-foreground">{label}</p>
                    </div>
                  ))}
                </div>
              </div>

              {analysis.factors.length > 0 && (
                <>
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-9 w-full justify-between rounded-none border-t px-3 text-xs"
                    onClick={() => setExpandedApproval(expanded ? null : approval.base_uuid)}
                  >
                    <span>{expanded ? "Hide details" : "View risk details"}</span>
                    <ChevronDown
                      className={`size-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
                    />
                  </Button>

                  {expanded && (
                    <div className="space-y-3 border-t bg-muted/10 p-3">
                      {analysis.factors.map((factor, index) => (
                        <div key={`${factor.code}-${index}`} className="text-xs">
                          <div className="flex justify-between gap-3">
                            <div>
                              <p className="font-medium">{factor.message}</p>
                              <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                                {factor.source} · {factor.category}
                              </p>
                            </div>
                            <Badge variant="secondary" className="h-5 shrink-0">
                              +{factor.points}
                            </Badge>
                          </div>
                          {factor.comment && (
                            <p className="mt-1 text-muted-foreground">“{factor.comment}”</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
    </div>
  );
}
