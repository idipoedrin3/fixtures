"use client";

import {Icon} from "@iconify/react";
import axios from "axios";
import {useEffect, useState} from "react";

import {ADMIN_REPORTS_API} from "#/_api/api.helpers";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import ReportFilterForm from "../../(dashboard)/reports/_components/report-center-filter-form";
import type {IReport} from "#/_types/api.types";
import {showErrorToast} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {SlideOverPanel} from "./slide-over-pannel";

type FeatureReportExportProps = {
  feature: string;
  buttonLabel?: string;
  title?: string;
  description?: string;
  disabled?: boolean;
  className?: string;
  fixedFilters?: Record<string, unknown>;
  defaultHeading?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  hideTrigger?: boolean;
};

function normalizeFeature(value: string) {
  return value.trim().replaceAll("_", "").replaceAll(" ", "").toLowerCase();
}

export function FeatureReportExport({
  feature,
  buttonLabel = "Export",
  title,
  description,
  disabled = false,
  className,
  fixedFilters,
  defaultHeading,
  open: controlledOpen,
  onOpenChange,
  hideTrigger = false,
}: FeatureReportExportProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [report, setReport] = useState<IReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const open = controlledOpen ?? internalOpen;
  const formId = `feature-report-export-${normalizeFeature(feature)}`;

  const setOpen = (nextOpen: boolean) => {
    if (controlledOpen === undefined) {
      setInternalOpen(nextOpen);
    }
    onOpenChange?.(nextOpen);
  };

  const submitExport = () => {
    document
      .getElementById(formId)
      ?.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
  };

  useEffect(() => {
    if (!open || report) return;

    const loadReport = async () => {
      setLoading(true);
      setLoadError(null);

      try {
        const matchingReport = await ADMIN_REPORTS_API.fetchReport(feature);
        setReport(matchingReport);
      } catch (error) {
        const message =
          axios.isAxiosError(error) && error.response?.status === 404
            ? `No export configuration was found for "${feature}".`
            : `Unable to load the export configuration for "${feature}".`;

        setLoadError(message);
        showErrorToast({
          error,
          defaultMessage: message,
        });
      } finally {
        setLoading(false);
      }
    };

    void loadReport();
  }, [feature, open, report]);

  return (
    <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_EXPORT_REPORTS}>
      {!hideTrigger && (
        <Button
          type="button"
          variant="outline"
          className={className}
          disabled={disabled}
          onClick={() => setOpen(true)}
        >
          <Icon icon="hugeicons:download-01" className="mr-2 size-4" />
          {buttonLabel}
        </Button>
      )}

      <SlideOverPanel
        open={open}
        onClose={() => setOpen(false)}
        title={title ?? `Export ${feature} List`}
        description={description ?? "Choose filters, columns, and a file format for the export."}
        width="md"
        submitLabel={exporting ? "Exporting..." : "Export"}
        isSubmitting={exporting}
        submitDisabled={loading || !report}
        onSubmit={submitExport}
      >
        {loading ? (
          <div className="flex min-h-48 items-center justify-center text-muted-foreground">
            <Icon icon="hugeicons:loading-03" className="mr-2 size-5 animate-spin" />
            Loading report options...
          </div>
        ) : loadError ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-2 px-6 text-center">
            <Icon icon="hugeicons:file-not-found" className="size-8 text-muted-foreground" />
            <p className="font-medium">Export configuration not found</p>
            <p className="text-sm text-muted-foreground">{loadError}</p>
          </div>
        ) : report ? (
          <ReportFilterForm
            report={report}
            formId={formId}
            hideHeading
            hideSubmitButton
            fixedFilters={fixedFilters}
            defaultHeading={defaultHeading}
            onDownloadingChange={setExporting}
            onDownloaded={() => setOpen(false)}
          />
        ) : null}
      </SlideOverPanel>
    </ProtectedComponent>
  );
}
