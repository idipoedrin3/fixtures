"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {toast} from "sonner";

import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type ReportExportOptions = {
  file_type: "excel" | "pdf";
  delivery_method: "download" | "email";
  recipient_email?: string;
};

type ReportExportResult = {
  message?: string;
};

type ReportExportDialogProps = {
  onExport: (options: ReportExportOptions) => Promise<ReportExportResult | void>;
  disabled?: boolean;
};

export function ReportExportDialog({onExport, disabled = false}: ReportExportDialogProps) {
  const [open, setOpen] = useState(false);
  const [fileType, setFileType] = useState<"excel" | "pdf">("excel");
  const [deliveryMethod, setDeliveryMethod] = useState<"download" | "email">("download");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [exporting, setExporting] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!exporting) return;

    const startedAt = Date.now();
    setElapsedSeconds(0);

    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [exporting]);

  const formattedElapsedTime = `${String(Math.floor(elapsedSeconds / 60)).padStart(
    2,
    "0",
  )}:${String(elapsedSeconds % 60).padStart(2, "0")}`;

  const handleExport = async () => {
    setExporting(true);

    try {
      const result = await onExport({
        file_type: fileType,
        delivery_method: deliveryMethod,
        recipient_email: deliveryMethod === "email" ? recipientEmail.trim() : "",
      });

      toast.success(
        result?.message ??
          (deliveryMethod === "download"
            ? "Report downloaded successfully."
            : "Report will be emailed shortly."),
      );

      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to export report.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={disabled || exporting}
          className="h-8 gap-1.5 border-gray-300 text-gray-600"
        >
          <Icon icon="hugeicons:download-01" className="h-3.5 w-3.5" />
          Export
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export report</DialogTitle>
          <DialogDescription>
            Download the report now or have it delivered by email.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 py-2">
          <div className="grid gap-2">
            <Label htmlFor="report-file-type">File format</Label>
            <Select value={fileType} onValueChange={(value: "excel" | "pdf") => setFileType(value)}>
              <SelectTrigger id="report-file-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="excel">Excel (.xlsx)</SelectItem>
                <SelectItem value="pdf">PDF (.pdf)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="report-delivery-method">Delivery method</Label>
            <Select
              value={deliveryMethod}
              onValueChange={(value: "download" | "email") => setDeliveryMethod(value)}
            >
              <SelectTrigger id="report-delivery-method">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="download">Download now</SelectItem>
                <SelectItem value="email">Send by email</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {deliveryMethod === "email" && (
            <div className="grid gap-2">
              <Label htmlFor="report-recipient-email">Recipient email (optional)</Label>
              <Input
                id="report-recipient-email"
                type="email"
                value={recipientEmail}
                onChange={(event) => setRecipientEmail(event.target.value)}
                placeholder="Leave blank to use your account email"
              />
              <p className="text-xs text-muted-foreground">
                If left blank, the backend sends the report to the email address on your logged-in
                account.
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={exporting}
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button type="button" disabled={exporting} onClick={handleExport}>
            {exporting && <Icon icon="hugeicons:loading-03" className="mr-2 size-4 animate-spin" />}
            {exporting
              ? `${
                  deliveryMethod === "download" ? "Downloading" : "Preparing email"
                }… ${formattedElapsedTime}`
              : deliveryMethod === "download"
                ? "Download report"
                : "Email report"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
