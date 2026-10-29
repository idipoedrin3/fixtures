"use client";

import {Icon} from "@iconify/react";
import {useParams} from "next/navigation";
import {useCallback, useEffect, useMemo, useState} from "react";
import {PURCHASE_DEBIT_NOTES_API, VENDOR_BILLS_API} from "#/_api/api.helpers";
import {useToast} from "#/_hooks/use-toast";
import {capitalize, formatCurrency, formatDate} from "#/_lib/utils";
import {IVendorBill} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {CustomLink as Link} from "@/platform/v1/components/link";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {VENDOR_PAYMENTS_API} from "#/_api/api.helpers";
import {IVendorPayment, IDebitNote} from "#/_types/api.types";
import Approvals from "#/_components/common/approvals/approvals";
import {Tabs, TabsList, TabsTrigger, TabsContent} from "@/components/ui/tabs";
import JournalEntriesTable from "#/_components/common/tables/journal-entries-table";
import {EmptyState} from "#/_components/common/nodata";
import {Badge} from "#/_components/custom/badge";
import PageLayout from "#/_components/common/layouts/page-layout";
import {LinkPrepaymentsDialog} from "../../payments/_components/link_to _prepayments_dialog";
import {Checkbox} from "@/components/ui/checkbox";
import {useSelector} from "react-redux";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {PERMISSION_CODES} from "#/_constants/enums";
import {RecordSwitcher} from "#/_components/common/record-switcher";
import {DescriptionSection} from "#/_components/common/description";
import {PurchaseDocumentLineItemsTable} from "#/_components/custom/purchases/purchase-document-line-items-table";
import {ResponsiveActions} from "#/_components/common/responsive-actions";
import {ResponsiveAmountDisplay} from "#/_components/common/responsive-amount-display";

import ProtectedComponent from "#/_components/custom/protected-component";
import VendorPaymentCreateForm from "../../payments/_components/vendor-payment-create-form";

export default function VendorBillDetailPage() {
  const router = useRouter();
  const params = useParams();
  const {toast} = useToast();
  const [bill, setBill] = useState<IVendorBill | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [approvalToggleContainer, setApprovalToggleContainer] = useState<HTMLDivElement | null>(
    null,
  );
  const billId = params.id as string;
  const [activeTab, setActiveTab] = useState("line-items");
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [showPaymentRequisition, setShowPaymentRequisition] = useState(false);
  const [prepayments, setPrepayments] = useState<IVendorPayment[]>([]);
  const [selectedPrepayments, setSelectedPrepayments] = useState<Set<string>>(new Set());
  const [isLinkingPrepayments, setIsLinkingPrepayments] = useState(false);
  const currentInstitution = useSelector(selectSelectedInstitution);
  const routePaymentsThroughRequisitions =
    currentInstitution?.should_vendor_payments_go_through_requisitions === true;
  const canMakePaymentRequisition =
    routePaymentsThroughRequisitions &&
    !!bill &&
    bill.payment_status !== "paid" &&
    Number(bill.balance_due) > 0;

  const seeTaxDetails = (base_uuid: string) => {
    router.push(`/taxes/${base_uuid}`);
  };

  const vendor = useMemo(() => {
    if (!bill) return undefined;

    if (bill.vendor && bill.vendor.id) {
      return bill.vendor;
    }

    if (bill.purchase_order?.vendor && bill.purchase_order.vendor.id) {
      return bill.purchase_order.vendor;
    }

    return undefined;
  }, [bill]);

  const handleDuplicate = () => {
    if (!bill) return;
    router.push(`/vendor-bills/create?from=duplicate&dup=${bill.base_uuid}`);
  };

  // Fetch bill
  const fetchBill = async () => {
    if (!billId) return;

    setIsLoading(true);
    try {
      const response = await VENDOR_BILLS_API.fetchVendorBillById({billUuid: billId});

      setBill(response);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to fetch bill details",
        variant: "destructive",
      });
      router.push("/vendor-bills");
    } finally {
      setIsLoading(false);
    }
  };

  const seePurchaseOrderDetails = (base_uuid: string) => {
    router.push(`/vendor-purchase-orders/${base_uuid}`);
  };

  useEffect(() => {
    fetchBill();
  }, [billId]);

  const fetchVendorPrepayments = useCallback(async () => {
    if (!vendor?.base_uuid) return;
    try {
      const res = await VENDOR_PAYMENTS_API.fetchVendorPayments({
        has_bill: false,
        only_paid: true,
        vendor_base_uuid: vendor.base_uuid,
      });
      setPrepayments(res.results.filter((p) => !p.bill && Number(p.remaining_balance ?? 0) > 0));
    } catch (e) {
      console.error(e);
    }
  }, [vendor?.base_uuid, currentInstitution?.id]);

  useEffect(() => {
    fetchVendorPrepayments();
  }, [fetchVendorPrepayments, billId]);

  const handleLinkSelectedPrepayments = async () => {
    if (!selectedPrepayments.size) return;
    setIsLinkingPrepayments(true);
    try {
      await VENDOR_PAYMENTS_API.linkPrepaymentsToBills({
        prepayment_uuids: Array.from(selectedPrepayments),
        bill_uuids: [billId],
      });
      toast({title: "Success", description: "Prepayments linked successfully"});
      setSelectedPrepayments(new Set());
      fetchBill();
      fetchVendorPrepayments();
    } catch (error) {
      toast({title: "Error", description: "Failed to link prepayments", variant: "destructive"});
    } finally {
      setIsLinkingPrepayments(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const map: Record<string, string> = {
      draft: "bg-gray-100 text-gray-600",
      sent: "bg-blue-100 text-blue-600",
      paid: "bg-green-100 text-green-600",
      overdue: "bg-red-100 text-red-600",
      canceled: "bg-gray-200 text-gray-600",
      pending: "bg-yellow-100 text-yellow-600",
      approved: "bg-green-100 text-green-600",
    };
    return map[status?.toLowerCase()] ?? "bg-gray-100 text-gray-600";
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-gray-200 animate-pulse rounded w-1/4" />
        <div className="h-64 bg-gray-200 animate-pulse rounded" />
      </div>
    );
  }

  if (!bill) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Bill not found</p>
        <Button onClick={() => router.push("/vendor-bills")} className="mt-4">
          Back to Vendor Bills
        </Button>
      </div>
    );
  }

  const approvalStatus = bill.approval_status ?? bill.status ?? "draft";

  return (
    <PageLayout>
      <Approvals
        entity="VendorBill"
        toggleContainer={approvalToggleContainer}
        data={{
          base_uuid: bill.base_uuid,
          model_content_type_id: bill.model_content_type_id,
          approval_status: bill.approval_status,
        }}
        onRefresh={fetchBill}
      >
        {/* Header — matches Invoice style */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon"
              className="rounded-full"
              onClick={() => router.push("/vendor-bills")}
            >
              <Icon icon="hugeicons:arrow-left-02" className="size-5" />
            </Button>
            <div className="flex flex-col items-start gap-2">
              <RecordSwitcher<IVendorBill>
                currentId={bill.base_uuid}
                currentLabel={bill.reference_code}
                basePath="/vendor-bills"
                label="Vendor Bills"
                fetchFirstPage={(query) => VENDOR_BILLS_API.fetchVendorBills(query ?? {})}
                fetchFromUrl={VENDOR_BILLS_API.fetchVendorBillsFromUrl}
                idKey="base_uuid"
                labelKeyFn={(item) => formatCurrency(item.total_amount)}
                descriptionKeyFn={(item) =>
                  [
                    item.reference_code,
                    item.vendor?.vendor_name ?? item.purchase_order?.vendor?.vendor_name,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                }
                labelClassName="text-3xl sm:text-3xl"
              />

              <div className="flex items-center gap-2">
                <Badge
                  className={`rounded-full border-transparent ${getStatusBadge(approvalStatus)}`}
                >
                  {approvalStatus.charAt(0).toUpperCase() + approvalStatus.slice(1)}
                </Badge>
                <Badge status={bill.payment_status} className="rounded-full" />
              </div>
            </div>
          </div>

          <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2">
            <div ref={setApprovalToggleContainer} />
            <ResponsiveActions
              actions={[
                {
                  key: "make-payment",
                  label: routePaymentsThroughRequisitions ? "Make Requisition" : "Make Payment",
                  visible: !routePaymentsThroughRequisitions || canMakePaymentRequisition,
                  icon: "hugeicons:credit-card",
                  prominent: true,
                  disabled: bill.payment_status === "paid",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_VENDOR_PAYMENTS,
                  onSelect: () => {
                    if (routePaymentsThroughRequisitions) {
                      if (canMakePaymentRequisition) setShowPaymentRequisition(true);
                      return;
                    }
                    router.push(`/payments/create?billId=${billId}`);
                  },
                },
                {
                  key: "link-prepayment",
                  label: "Link Prepayment",
                  icon: "hugeicons:link-01",
                  disabled: bill.payment_status === "paid",
                  onSelect: () => setIsLinkModalOpen(true),
                },
                {
                  key: "create-grn",
                  label: "Create GRN",
                  icon: "hugeicons:package-receive",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_GOODS_RECEIVED_NOTES,
                  onSelect: () => router.push(`/goods-received-note/create?billId=${billId}`),
                },
                {
                  key: "create-purchase-order",
                  label: "Create Purchase Order",
                  icon: "hugeicons:shopping-cart-02",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_VENDOR_PURCHASE_ORDERS,
                  onSelect: () => router.push("/vendor-purchase-orders/create"),
                },
                {
                  key: "debit-note",
                  label: "Debit Note",
                  icon: "hugeicons:money-remove-02",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_CREDIT_DEBIT_NOTES,
                  onSelect: () => router.push(`/debit-notes/debit?billId=${billId}`),
                },
                {
                  key: "edit",
                  label: "Edit",
                  icon: "hugeicons:edit-01",
                  visible: bill.allow_changes === true,
                  permissionCode: PERMISSION_CODES.CAN_EDIT_VENDOR_BILLS,
                  onSelect: () => router.push(`/vendor-bills/${billId}/edit`),
                },
                {
                  key: "duplicate",
                  label: "Duplicate",
                  icon: "hugeicons:copy-01",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_VENDOR_BILLS,
                  onSelect: handleDuplicate,
                },
              ]}
            />
          </div>
        </div>

        {/* ── Bill + Vendor Info ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 pb-5 pt-2">
          {/* Left */}
          <div className="space-y-5">
            {vendor && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">FROM</p>
                <Link
                  href={`/vendors/${vendor.base_uuid}`}
                  className="text-base font-medium text-primary hover:underline"
                >
                  {capitalize(vendor.vendor_name)}
                </Link>
                {vendor.address && (
                  <p className="text-sm text-muted-foreground">{vendor.address}</p>
                )}
                {vendor.email && (
                  <p className="text-sm text-muted-foreground">
                    {vendor.email}
                    {vendor.phone_number && `, ${vendor.phone_number}`}
                  </p>
                )}
              </div>
            )}

            {bill.branch && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">BRANCH</p>
                <p className="font-normal text-base">{bill.branch.branch_name}</p>
                {bill.branch.reference_code && (
                  <p className="text-sm text-muted-foreground">{bill.branch.reference_code}</p>
                )}
              </div>
            )}
          </div>

          {/* Right */}
          <div className="flex flex-col items-end text-right">
            <p className="text-3xl font-black tracking-tight uppercase">Vendor Bill</p>
            <p className="text-sm text-muted-foreground mt-1">{bill.reference_code || "-"}</p>

            <div className="mt-4 ml-auto flex w-full max-w-xs flex-col gap-y-1.5 text-sm">
              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Issue Date</span>
                <span className="font-medium">{formatDate(bill.received_date)}</span>
              </div>

              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Due Date</span>
                <span className="font-medium text-red-600">
                  {bill.due_date ? formatDate(bill.due_date) : "—"}
                </span>
              </div>

              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Purchase Order</span>
                {bill?.purchase_order?.base_uuid ? (
                  <span
                    className="inline-flex cursor-pointer items-center gap-1.5 font-medium text-primary underline-offset-4 hover:underline"
                    onClick={() => seePurchaseOrderDetails(bill.purchase_order!.base_uuid)}
                  >
                    {bill.purchase_order.reference_code}
                    <Icon icon="hugeicons:arrow-right-02" className="h-3 w-3 opacity-60" />
                  </span>
                ) : (
                  <span className="font-medium">None</span>
                )}
              </div>

              <div className="mt-4 ml-auto w-full max-w-xs rounded-xl border bg-muted/50 p-4 shadow-sm">
                <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                  Outstanding Balance
                </p>
                <p className="mt-2 whitespace-nowrap text-3xl font-extrabold">
                  <ResponsiveAmountDisplay
                    value={bill?.balance_due ?? bill?.total_amount ?? 0}
                    currency={bill.currency?.code}
                  />
                </p>
              </div>
            </div>
          </div>
        </div>

        <DescriptionSection description={bill?.description} />

        {/* Tabbed Sections — unchanged */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-grow pt-4">
          <TabsList className="!bg-background !pl-0 !pb-4 gap-x-6 w-full justify-start rounded-none">
            <TabsTrigger
              value="line-items"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Line Items</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>

            <TabsTrigger
              value="payments"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Payments</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>

            <TabsTrigger
              value="debit-notes"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Debit Notes</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>

            <TabsTrigger
              value="tax-breakdowns"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Tax Breakdowns</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>

            <TabsTrigger
              value="related-documents"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Related Documents</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>

            <TabsTrigger
              value="journal-entries"
              className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
            >
              <span>Journal Entries</span>
              <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
            </TabsTrigger>
          </TabsList>

          {/* Line Items Tab */}
          <TabsContent value="line-items" className="mt-2">
            <PurchaseDocumentLineItemsTable
              documentType="vendor_bill"
              documentUuid={bill.base_uuid}
              currency={bill.currency?.code ?? ""}
              netTotal={bill.total_net_amount ?? 0}
              taxTotal={bill.total_tax_amount ?? 0}
              grossTotal={bill.adjusted_total ?? bill.total_amount}
              onTaxClick={seeTaxDetails}
              footerRows={
                <>
                  {parseFloat(bill.debit_note_total ?? "0") > 0 && (
                    <TableRow className="bg-gray-50">
                      <TableCell colSpan={8} className="text-right font-semibold">
                        Debit Note
                      </TableCell>
                      <TableCell className="text-right font-bold text-green-600">
                        - {bill.currency?.code} {formatCurrency(bill.debit_note_total ?? "0")}
                      </TableCell>
                    </TableRow>
                  )}
                  <TableRow className="bg-gray-200">
                    <TableCell colSpan={8} className="text-right font-bold">
                      Amount Due
                    </TableCell>
                    <TableCell className="text-right font-bold">
                      {bill.currency?.code} {formatCurrency(bill.balance_due ?? "0")}
                    </TableCell>
                  </TableRow>
                </>
              }
            />
            {prepayments.length > 0 && (
              <div className="mt-4 flex justify-end">
                <div className="w-[500px]">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-semibold text-base">Available Prepayments</h3>
                      <p className="text-base text-muted-foreground">
                        Select prepayments to apply to this bill
                      </p>
                    </div>
                    {selectedPrepayments.size > 0 && (
                      <Button
                        size="sm"
                        disabled={isLinkingPrepayments}
                        onClick={handleLinkSelectedPrepayments}
                      >
                        <Icon icon="hugeicons:link-01" className="w-4 h-4 mr-2" />
                        {isLinkingPrepayments
                          ? "Linking..."
                          : `Link ${selectedPrepayments.size} Prepayment(s)`}
                      </Button>
                    )}
                  </div>

                  <div className="border rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-8">
                            <Checkbox
                              checked={selectedPrepayments.size === prepayments.length}
                              onCheckedChange={(checked) => {
                                if (checked) {
                                  setSelectedPrepayments(
                                    new Set(prepayments.map((p) => p.base_uuid)),
                                  );
                                } else {
                                  setSelectedPrepayments(new Set());
                                }
                              }}
                            />
                          </TableHead>
                          <TableHead>Reference</TableHead>
                          <TableHead>Date</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {prepayments.map((p) => (
                          <TableRow
                            key={p.base_uuid}
                            className={`cursor-pointer ${selectedPrepayments.has(p.base_uuid) ? "bg-primary/5" : ""}`}
                            onClick={() => {
                              setSelectedPrepayments((prev) => {
                                const next = new Set(prev);
                                next.has(p.base_uuid)
                                  ? next.delete(p.base_uuid)
                                  : next.add(p.base_uuid);
                                return next;
                              });
                            }}
                          >
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <Checkbox
                                checked={selectedPrepayments.has(p.base_uuid)}
                                onCheckedChange={() => {
                                  setSelectedPrepayments((prev) => {
                                    const next = new Set(prev);
                                    next.has(p.base_uuid)
                                      ? next.delete(p.base_uuid)
                                      : next.add(p.base_uuid);
                                    return next;
                                  });
                                }}
                              />
                            </TableCell>
                            <TableCell className="font-medium">{p.reference_code || "-"}</TableCell>
                            <TableCell>{formatDate(p.created_at)}</TableCell>
                            <TableCell className="text-right font-semibold">
                              {formatCurrency(p.remaining_balance)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Payments Tab */}
          <TabsContent value="payments" className="mt-2">
            <PaginatedTableWrapper<IVendorPayment>
              fetchFirstPage={() =>
                VENDOR_PAYMENTS_API.fetchVendorPayments({bill_base_uuid: billId})
              }
              fetchFromUrl={VENDOR_PAYMENTS_API.fetchVendorPaymentsFromUrl}
              deps={[billId]}
              showFooter={true}
            >
              {({data, loading}) => (
                <div className="border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-800 hover:bg-gray-800">
                        <TableHead className="!text-white">Reference</TableHead>
                        <TableHead className="!text-white">Date</TableHead>
                        <TableHead className="!text-white">Cash Account</TableHead>
                        <TableHead className="!text-white">Status</TableHead>
                        <TableHead className="!text-white text-right">Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loading ? (
                        Array.from({length: 3}).map((_, i) => (
                          <TableRow key={i}>
                            <TableCell colSpan={5}>
                              <div className="h-4 bg-gray-200 animate-pulse rounded" />
                            </TableCell>
                          </TableRow>
                        ))
                      ) : !data?.results.length ? (
                        <TableRow className="hover:bg-transparent">
                          <TableCell colSpan={5}>
                            <EmptyState />
                          </TableCell>
                        </TableRow>
                      ) : (
                        data.results.map((payment) => (
                          <TableRow key={payment.base_uuid}>
                            <TableCell>{payment.reference_code || "-"}</TableCell>
                            <TableCell>{formatDate(payment.created_at)}</TableCell>
                            <TableCell>{payment.cash_account?.account_name || "-"}</TableCell>
                            <TableCell>{payment.payment_status || "-"}</TableCell>
                            <TableCell className="text-right">
                              {formatCurrency(payment.amount)}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </PaginatedTableWrapper>
          </TabsContent>

          {/* Debit Notes Tab */}
          <TabsContent value="debit-notes" className="mt-2">
            <PaginatedTableWrapper<IDebitNote>
              fetchFirstPage={() =>
                PURCHASE_DEBIT_NOTES_API.fetchDebitNotes({
                  bill_base_uuid: billId,
                  type: "DEBIT",
                  falls_under: "PURCHASE",
                })
              }
              fetchFromUrl={PURCHASE_DEBIT_NOTES_API.fetchFromUrl}
              deps={[billId]}
              showFooter={true}
            >
              {({data, loading}) => (
                <div className="border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-800 hover:bg-gray-800">
                        <TableHead className="!text-white">Reference</TableHead>
                        <TableHead className="!text-white">Date</TableHead>
                        <TableHead className="!text-white">Status</TableHead>
                        <TableHead className="!text-white text-right">Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {loading ? (
                        Array.from({length: 3}).map((_, i) => (
                          <TableRow key={i}>
                            <TableCell colSpan={4}>
                              <div className="h-4 bg-gray-200 animate-pulse rounded" />
                            </TableCell>
                          </TableRow>
                        ))
                      ) : !data?.results.length ? (
                        <TableRow className="hover:bg-transparent">
                          <TableCell colSpan={4}>
                            <EmptyState />
                          </TableCell>
                        </TableRow>
                      ) : (
                        data.results.map((note) => (
                          <TableRow key={note.base_uuid}>
                            <TableCell>{note.reference_code || "-"}</TableCell>
                            <TableCell>{formatDate(note.created_at)}</TableCell>
                            <TableCell>{note.status || "-"}</TableCell>
                            <TableCell className="text-right">
                              {formatCurrency(note.amount)}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </PaginatedTableWrapper>
          </TabsContent>

          {/* Tax Breakdowns Tab */}
          <TabsContent value="tax-breakdowns" className="mt-2">
            <div className="border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-800 hover:bg-gray-800">
                    <TableHead className="!text-white">Gross Amount</TableHead>
                    <TableHead className="!text-white">Net Amount</TableHead>
                    <TableHead className="!text-white">Tax Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!bill?.tax_breakdowns?.length ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={3}>
                        <EmptyState />
                      </TableCell>
                    </TableRow>
                  ) : (
                    bill.tax_breakdowns.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium">
                          {formatCurrency(item.gross_amount)}
                        </TableCell>
                        <TableCell className="font-medium">
                          {formatCurrency(item.net_amount)}
                        </TableCell>
                        <TableCell className="font-medium">
                          {formatCurrency(item.tax_amount)}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          {/* Related Documents Tab */}
          <TabsContent value="related-documents" className="mt-2">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 [&_div]:flex [&_div]:bg-gray-100 [&_div]: [&_div_span]:flex-grow [&_div]:p-2.5 [&_div]:flex-col [&_div]:gap-4">
              {bill.requisition ? (
                <div>
                  <span>
                    <b>Requisition:</b> {bill.requisition?.reference_code ?? "-"}
                  </span>
                  <span>
                    <b>Creation Date:</b>{" "}
                    {bill.requisition?.created_at ? formatDate(bill.requisition?.created_at) : "-"}
                  </span>
                  <span>
                    <b>Gross Amount:</b>{" "}
                    {bill.requisition?.gross_amount
                      ? formatCurrency(bill.requisition.gross_amount)
                      : "-"}
                  </span>
                  {bill.requisition?.base_uuid ? (
                    <Link
                      className="flex gap-2 hover:underline items-center text-primary"
                      href={`/vendor-bills/${bill.requisition?.base_uuid}`}
                    >
                      View <Icon icon="hugeicons:arrow-right-01" />
                    </Link>
                  ) : null}
                </div>
              ) : (
                <p className="p-4 opacity-50">
                  <span>No documents found.</span>
                </p>
              )}
            </div>
          </TabsContent>

          {/* Journal Entries Tab */}
          <TabsContent value="journal-entries" className="mt-2">
            <JournalEntriesTable
              modelContentTypeId={bill.model_content_type_id}
              objectBaseUuid={bill.base_uuid}
              loading={isLoading}
            />
          </TabsContent>
        </Tabs>
      </Approvals>
      {showPaymentRequisition && canMakePaymentRequisition && (
        <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_VENDOR_PAYMENTS}>
          <VendorPaymentCreateForm
            key={`${currentInstitution?.id}-${bill.base_uuid}`}
            context={{type: "payment", bill}}
            onClose={() => setShowPaymentRequisition(false)}
          />
        </ProtectedComponent>
      )}
      <LinkPrepaymentsDialog
        open={isLinkModalOpen}
        onClose={() => setIsLinkModalOpen(false)}
        onSuccess={fetchBill}
        mode="select_prepayments"
        billUuid={billId}
        vendorUuid={vendor?.base_uuid}
      />
    </PageLayout>
  );
}
