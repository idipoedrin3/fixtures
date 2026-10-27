"use client";

import {useRef} from "react";
import {Printer} from "lucide-react";
import {spaceMono} from "@/platform/v1/utils/fonts";
import {useSelector} from "react-redux";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogTitle} from "@/components/ui/dialog";
import {selectSelectedBranches, selectSelectedInstitution} from "@/store/auth/selectors";
import {formatCurrency, formatDate} from "#/_lib/utils";
import { generateReceiptPDF, ReceiptSection } from "../common/receipt-pdf";

export interface ReceiptData {
  total: number | string;
  paymentMethod: string;
  date: string;
  receiptNumber: string;
  transaction_code?: string;
  customerName?: string;
  accountName?: string;
  depositDate?: string;
  description?: string;
  currency?: string;
  servedBy?: string;
}

interface ReceiptProps {
  showReceipt: boolean;
  setShowReceipt: (show: boolean) => void;
  receiptData: ReceiptData | undefined;
  onClose?: () => void;
}

export default function ReceiptCard({
  showReceipt,
  setShowReceipt,
  receiptData,
  onClose,
}: ReceiptProps) {
  const branches = useSelector(selectSelectedBranches);
  const branch = branches?.length === 1 ? branches[0] : undefined;
  const institution = useSelector(selectSelectedInstitution);

const handlePrint = () => {
  if (!receiptData) return;

  const sections: ReceiptSection[] = [
    {type: "text", text: "CUSTOMER DEPOSIT RECEIPT", bold: true},
    {type: "text", text: receiptData.receiptNumber, bold: true, size: 8},
    {type: "divider"},
    {type: "row", label: "Date", value: formatDate(receiptData.date)},
  ];
  if (receiptData.depositDate)
    sections.push({type: "row", label: "Deposit Date", value: receiptData.depositDate});
  if (receiptData.customerName)
    sections.push({type: "row", label: "Customer", value: receiptData.customerName});
  if (receiptData.accountName)
    sections.push({type: "row", label: "Account", value: receiptData.accountName});
  sections.push(
    {type: "row", label: "Payment Method", value: receiptData.paymentMethod},
    {
      type: "row",
      label: "Amount",
      value: `${receiptData.currency ?? ""} ${formatCurrency(receiptData.total)}`.trim(),
      bold: true,
    },
  );
  if (receiptData.description) {
    sections.push(
      {type: "divider"},
      {type: "text", text: `Note: ${receiptData.description}`, align: "left"},
    );
  }

  const url = generateReceiptPDF({
    header: {
      businessName: branch?.branch_name || institution?.institution_name,
      lines: [
        branch?.branch_location,
        branch?.branch_phone_number ? `Tel: ${branch.branch_phone_number}` : undefined,
        branch?.branch_email,
      ].filter(Boolean) as string[],
    },
    sections,
    footerLines: [
      ...(receiptData.servedBy ? [`Served by: ${receiptData.servedBy}`] : []),
      "Thank you!",
    ],
  });
  window.open(url, "_blank");
};

  return (
    <Dialog aria-label="Receipt Details" open={showReceipt} onOpenChange={setShowReceipt}>
      <DialogContent className="sm:max-w-md bg-white z-[150]">
        <DialogTitle className="sr-only">Receipt Details</DialogTitle>
        {receiptData ? (
          <>
            <div className="max-h-[80vh] overflow-y-auto">
              <div className={`receipt bg-white p-4 text-black ${spaceMono.className}`}>
                {/* Header */}
                <div className="text-center border-b border-dashed border-gray-400 pb-3">
                  <h2 className="text-sm font-bold uppercase">
                    {branch?.branch_name || institution?.institution_name || "-"}
                  </h2>
                  {branch?.branch_location && <p className="text-xs">{branch.branch_location}</p>}
                  {branch?.branch_phone_number && <p className="text-xs">Tel: {branch.branch_phone_number}</p>}
                  {branch?.branch_email && <p className="text-xs">{branch.branch_email}</p>}
                </div>

                {/* Title + reference */}
                <div className="text-center py-3 border-b border-dashed border-gray-400">
                  <p className="text-xs font-bold uppercase">Customer Deposit Receipt</p>
                  <p className="text-sm font-bold mt-1">{receiptData.receiptNumber}</p>
                  <p className="text-xs mt-0.5">{formatDate(receiptData.date)}</p>
                </div>

                {/* Details */}
                <div className="py-3 space-y-1.5 text-xs border-b border-dashed border-gray-400">
                  {receiptData.customerName && (
                    <div className="flex justify-between gap-4">
                      <span>Customer</span>
                      <span className="font-bold text-right">{receiptData.customerName}</span>
                    </div>
                  )}
                  {receiptData.accountName && (
                    <div className="flex justify-between gap-4">
                      <span>Account</span>
                      <span className="font-bold text-right">{receiptData.accountName}</span>
                    </div>
                  )}
                  {receiptData.depositDate && (
                    <div className="flex justify-between gap-4">
                      <span>Deposit Date</span>
                      <span className="font-bold">{receiptData.depositDate}</span>
                    </div>
                  )}
                  <div className="flex justify-between gap-4">
                    <span>Payment Method</span>
                    <span className="font-bold capitalize">{receiptData.paymentMethod}</span>
                  </div>
                  <div className="flex justify-between gap-4 pt-1">
                    <span className="font-bold">AMOUNT</span>
                    <span className="font-bold text-sm">
                      {`${receiptData.currency ?? ""} ${formatCurrency(receiptData.total)}`.trim()}
                    </span>
                  </div>
                </div>

                {/* Note */}
                {receiptData.description && (
                  <div className="py-3 text-xs border-b border-dashed border-gray-400">
                    <span className="font-bold">Note: </span>
                    {receiptData.description}
                  </div>
                )}

                {/* Footer */}
                <div className="text-center pt-3 text-xs">
                  {receiptData.servedBy && <p>Served by: {receiptData.servedBy}</p>}
                  <p className="mt-1">Thank you!</p>
                </div>
              </div>
            </div>

            <div className="flex justify-between gap-3 mt-4">
              <Button
                className="w-1/2"
                variant="outline"
                onClick={() => {
                  setShowReceipt(false);
                  onClose?.call(undefined);
                }}
              >
                Close
              </Button>
              <Button data-receipt-print-button className="w-1/2" onClick={handlePrint}>
                <Printer className="mr-2 h-4 w-4" />
                Print
              </Button>
            </div>
          </>
        ) : (
          <div className="p-8 text-center">
            <p className="text-gray-500">Receipt data not available</p>
            <Button className="mt-4" onClick={() => setShowReceipt(false)}>
              Close
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
