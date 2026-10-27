"use client";

import {useState} from "react";
import {Icon} from "@iconify/react";

import {STATEMENTS_API} from "#/_api/services/statements.service";
import {triggerDownload} from "#/_api/api.helpers";
import {showSuccessToast} from "#/_api/helpers";
import {showErrorToast} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type StatementExportMenuProps = {
  entityType: "customer" | "vendor";
  baseUuid: string;
  referenceCode?: string;
  startDate?: string;
  endDate?: string;
};

export function StatementExportMenu({
  entityType,
  baseUuid,
  referenceCode,
  startDate,
  endDate,
}: StatementExportMenuProps) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async (format: "pdf" | "excel") => {
    setIsExporting(true);

    try {
      const blob = await STATEMENTS_API.downloadStatement({
        entityType,
        baseUuid,
        format,
        startDate,
        endDate,
      });
      const extension = format === "excel" ? "xlsx" : "pdf";
      const filename = referenceCode || entityType;

      triggerDownload(blob, `${filename}-statement.${extension}`);
      showSuccessToast(
        `${entityType === "customer" ? "Customer" : "Vendor"} statement downloaded successfully`,
      );
    } catch (error) {
      showErrorToast({
        error,
        defaultMessage: "Failed to download statement",
      });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={isExporting} className="h-9 gap-2 rounded-xl">
          <Icon
            icon={isExporting ? "hugeicons:loading-03" : "hugeicons:download-01"}
            className={`size-4 ${isExporting ? "animate-spin" : ""}`}
          />
          {isExporting ? "Exporting..." : "Export"}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Download as</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={isExporting}
          className="cursor-pointer gap-2"
          onClick={() => void handleExport("excel")}
        >
          <Icon icon="hugeicons:file-02" className="size-5 text-green-600" />
          Excel (.xlsx)
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={isExporting}
          className="cursor-pointer gap-2"
          onClick={() => void handleExport("pdf")}
        >
          <Icon icon="hugeicons:pdf-02" className="size-5 text-red-600" />
          PDF (.pdf)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
