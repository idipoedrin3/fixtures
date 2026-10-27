"use client";

import {useState, useRef} from "react";
import {Upload, ChevronsDown} from "lucide-react";
import {Icon} from "@iconify/react";
import {toast} from "sonner";
import {useSelector} from "react-redux";

import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {selectAccessToken} from "@/store/auth/selectors";
import apiRequest from "#/_api/api-request";
import {showErrorToast} from "#/_lib/utils";

interface Props {
  templateName?: string;
  templateURL: string;
  templateType?: string;
  isOpen: boolean;
  title: string;
  description?: string;
  onOpenChange: (open?: boolean) => void;
  bulkUploader?: (data: FormData) => Promise<any>;
  onSuccess?: () => void;
}

export default function BulkUploadDialog({
  templateURL,
  templateName,
  isOpen,
  onOpenChange,
  onSuccess,
  title,
  description,
  templateType,
  bulkUploader,
}: Props) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  const accessToken = useSelector(selectAccessToken);

  const handleDownloadTemplate = async (format: "csv" | "excel") => {
    setDropdownOpen(false);
    try {
      setLoading(true);

      const separator = templateURL.includes("?") ? "&" : "?";
      const typeParam = templateType ? `&template_type=${templateType}` : "";

      const endpoint = `${templateURL}${separator}file_format=${format}${typeParam}`;

      const response = await apiRequest.get(endpoint, null, {}, {responseType: "blob"});

      const fileData = response.data as Blob;

      if (!fileData || fileData.size === 0) {
        throw new Error("Empty file received from server");
      }

      // Use the original blob (already correct type from server in most cases)
      const blob = fileData;

      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = downloadUrl;
      link.setAttribute(
        "download",
        `${templateName || window.location.pathname.replaceAll("/", "-")}-template.${format === "excel" ? "xlsx" : "csv"}`,
      );

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setTimeout(() => URL.revokeObjectURL(downloadUrl), 5000);
    } catch (err: any) {
      console.error("Template download error:", err);

      let errorMsg = "Failed to download template. Please try again.";
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          errorMsg = json.detail || json.message || errorMsg;
        } catch {}
      }

      showErrorToast({defaultMessage: errorMsg});
    } finally {
      setLoading(false);
    }
  };

  /** Submit parsed data */
  const handleSubmit = async () => {
    if (!uploadedFile || !uploadedFile?.size) return;
    setSubmitting(true);
    try {
      const data = new FormData();
      data.append("file", uploadedFile);
      if (templateType) data.append("template_type", templateType);

      if (bulkUploader) {
        await bulkUploader(data);
      } else {
        await apiRequest.post("/bulk_upload/", data);
      }

      toast(`Uploaded ${uploadedFile.name} successfully.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (onSuccess) onSuccess();
    } catch (err) {
      // toast("Error uploading data. Please try again.");
    } finally {
      setSubmitting(false);
      onOpenChange(false);
      setUploadedFile(null);
    }
  };
  /** Remove parsed data */
  const handleRemoveData = () => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /** Close dropdown if clicked outside */
  const handleClickOutside = (e: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
      setDropdownOpen(false);
    }
  };

  if (dropdownOpen) {
    document.addEventListener("mousedown", handleClickOutside);
  } else {
    document.removeEventListener("mousedown", handleClickOutside);
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[90vw] max-w-[600px] mx-auto rounded-2xl"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {description ||
              "Upload a CSV or Excel file containing the items. Use the provided template to ensure column accuracy."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="rounded-md bg-muted/40 p-4 text-sm text-gray-700">
            <p className="mb-2">
              You can upload <strong>.csv</strong>, <strong>.xlsx</strong>, or <strong>.xls</strong>{" "}
              files.
            </p>
            <p>Download the template below to see the required column structure.</p>
          </div>

          <div className="flex flex-col md:flex-row justify-between gap-4 relative">
            {/* Dropdown for CSV/Excel */}
            <div className="relative w-full" ref={dropdownRef}>
              <Button
                className="w-full rounded-full h-[48px] flex justify-between items-center"
                disabled={loading}
                onClick={() => setDropdownOpen((prev) => !prev)}
              >
                Download Template
                <ChevronsDown className="h-4 w-4" />
              </Button>

              {dropdownOpen && (
                <div className="absolute mt-1 w-full bg-white border rounded shadow-md z-10">
                  <button
                    className="w-full px-4 py-2 text-left hover:bg-gray-100"
                    onClick={() => handleDownloadTemplate("csv")}
                  >
                    CSV
                  </button>
                  <button
                    className="w-full px-4 py-2 text-left hover:bg-gray-100"
                    onClick={() => handleDownloadTemplate("excel")}
                  >
                    Excel
                  </button>
                </div>
              )}
            </div>

            {/* Upload button */}
            <Button
              variant="secondary"
              className="w-full rounded-full h-[48px] flex items-center gap-2"
              type="button"
              disabled={loading}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-4 w-4" />
              {loading ? "Processing..." : "Upload File"}
            </Button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];

                if (file) setUploadedFile(file);
              }}
            />
          </div>

          {uploadedFile && (
            <div className="rounded-md bg-green-50 p-3 text-sm flex justify-between items-center">
              <span className="text-green-700">
                File: {uploadedFile.name} - added and ready to submit.
              </span>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleRemoveData}
                className="flex items-center gap-1"
              >
                <Icon icon="hugeicons:delete-02" className="h-4 w-4" />
                Remove
              </Button>
            </div>
          )}
        </div>

        <DialogFooter className="pt-4 grid md:grid-cols-2 gap-4">
          <DialogClose asChild>
            <Button variant="outline" className="rounded-full">
              Cancel
            </Button>
          </DialogClose>
          <Button
            onClick={handleSubmit}
            className="rounded-full"
            disabled={!uploadedFile || submitting}
          >
            {submitting ? "Submitting..." : "Submit Data"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
