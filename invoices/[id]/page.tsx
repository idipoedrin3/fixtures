"use client";

import {Icon} from "@iconify/react";
import {X} from "lucide-react";
import {useParams} from "next/navigation";
import {useEffect, useState} from "react";
import {useSelector} from "react-redux";
import InvoiceCreditDebitNotes from "../_components/invoice-credit-debit";
import PaymentModal from "../_components/make-invoice-payment-modal";
import {
  ACCOUNTS_API,
  CUSTOMER_PAYMENTS_API,
  INVOICES_API,
  triggerDownload,
} from "#/_api/api.helpers";
import PageLayout from "#/_components/common/layouts/page-layout";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {Badge} from "#/_components/custom/badge";
import {useToast} from "#/_hooks/use-toast";
import {formatCurrency, formatDate, formatText, getBadgeStyle} from "#/_lib/utils";
import {ICustomerPaymentRecord, ICustomerPaymentRecordFormData, IInvoice} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {TableCell, TableRow} from "@/components/ui/table";
import {CustomLink as Link} from "@/platform/v1/components/link";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import Approvals from "#/_components/common/approvals/approvals";
import {DescriptionSection} from "#/_components/common/description";
import {Tabs, TabsList, TabsTrigger, TabsContent} from "@/components/ui/tabs";
import JournalEntriesTable from "#/_components/common/tables/journal-entries-table";
import {LinkDepositsDialog} from "../../customer-transactions/_components/link-deposits-dialog";
import {PERMISSION_CODES} from "#/_constants/enums";
import {ResponsiveActions} from "#/_components/common/responsive-actions";
import {RecordSwitcher} from "#/_components/common/record-switcher";
import EntityAuditLogs from "#/_components/common/entity-audit-logs";
import {AUDIT_CONTENT_TYPES} from "#/_constants/audit.enum";
import {PlaceOrderPanel} from "../_components/place-order-panel";
import {AvailablePrepaymentsPanel} from "../_components/customer-deposits";
import {RelatedReferences} from "#/_components/common/related-references";
import {SalesDocumentLineItemsTable} from "#/_components/custom/sales/sales-document-line-items-table";
import {CustomerPaymentsTable} from "../../customer-payments/_components/customer-payments-table";

export default function InvoiceDetailPage() {
  const router = useRouter();
  const params = useParams();
  const {toast} = useToast();
  const [invoice, setInvoice] = useState<IInvoice | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [isPaymentLoading, setIsPaymentLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [approvalToggleContainer, setApprovalToggleContainer] = useState<HTMLDivElement | null>(
    null,
  );
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [activeTab, setActiveTab] = useState("line-items");
  const invoiceId = params.id as string;
  const seeTaxDetails = (base_uuid: string) => {
    router.push(`/taxes/${base_uuid}`);
  };
  const [isDepositLinkModalOpen, setIsDepositLinkModalOpen] = useState(false);
  const [isPlaceOrderOpen, setIsPlaceOrderOpen] = useState(false);
  const [hasAvailablePrepayments, setHasAvailablePrepayments] = useState(false);
  const [paymentsRefreshTrigger, setPaymentsRefreshTrigger] = useState(0);

  const fetchInvoice = async () => {
    if (!invoiceId) return;
    setIsLoading(true);
    try {
      const response = await INVOICES_API.fetchInvoiceById({invoiceUuid: invoiceId});
      setInvoice(response);
    } catch {
      toast({
        title: "Error",
        description: "Failed to fetch invoice details",
        variant: "destructive",
      });
      router.push("/invoices");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoice();
  }, [invoiceId]);

  const handlePayment = async (data: ICustomerPaymentRecordFormData) => {
    if (!invoice) return;

    if (!data.coa_cash_account) {
      toast({
        title: "Receiving account required",
        description: "Select the cash or bank account receiving the payment.",
        variant: "destructive",
      });
      return;
    }
    setIsPaymentLoading(true);
    try {
      await CUSTOMER_PAYMENTS_API.createCustomerPayment({
        paymentData: data,
      });

      toast({title: "Success", description: "Payment submitted successfully"});
      await fetchInvoice();
      setIsPaymentModalOpen(false);
    } catch {
      toast({
        title: "Error",
        description: "Failed to submit payment",
        variant: "destructive",
      });
    } finally {
      setIsPaymentLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const map = {
      draft: "bg-gray-100 text-gray-600",
      sent: "bg-blue-100 text-blue-600",
      paid: "bg-green-100 text-green-600",
      overdue: "bg-red-100 text-red-600",
      canceled: "bg-gray-200 text-gray-600",
    };

    return map[status as keyof typeof map] ?? "bg-gray-100 text-gray-600";
  };

  const handleDuplicate = async () => {
    if (!invoice) return;
    const lineItems = await INVOICES_API.fetchInvoiceLineItems({invoiceUuid: invoice.base_uuid});
    sessionStorage.setItem(
      "duplicate_invoice",
      JSON.stringify({
        customerData: invoice.customer ?? null,
        line_items: lineItems.map((item) => ({
          item_base_uuid: item.branch_item?.base_uuid,
          unit_of_measure_base_uuid: item.unit_of_measure?.base_uuid,
          quantity: item.quantity,
        })),
      }),
    );
    router.push("/invoices/create");
  };

  const handleInvoiceDownload = async () => {
    if (!invoice) return;
    setIsDownloading(true);

    try {
      const blob = await INVOICES_API.downloadInvoicePDF({invoiceUuid: invoice.base_uuid});
      triggerDownload(blob, `Invoice-${invoice.reference_code}.pdf`);
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to download invoice PDF",
        variant: "destructive",
      });
    } finally {
      setIsDownloading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-gray-200 animate-pulse rounded w-1/4" />
        <div className="h-64 bg-gray-200 animate-pulse rounded" />
      </div>
    );
  }
  if (!invoice) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Invoice not found</p>
        <Button onClick={() => router.push("/invoices?tab=list")} className="mt-4">
          Back to Invoices
        </Button>
      </div>
    );
  }

  return (
    <PageLayout>
      <Approvals
        entity="Invoice"
        toggleContainer={approvalToggleContainer}
        data={{
          base_uuid: invoice.base_uuid,
          model_content_type_id: invoice.model_content_type_id,
          approval_status: invoice.approval_status,
        }}
        onRefresh={fetchInvoice}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon"
              className="rounded-full "
              onClick={() => router.push("/invoices?tab=list")}
            >
              <Icon icon="hugeicons:arrow-left-02" className="size-5" />
            </Button>
            <div className="flex gap-4 items-center">
              <RecordSwitcher<IInvoice>
                currentId={invoice.base_uuid}
                currentLabel={invoice.reference_code}
                currentDescription={invoice.customer?.customer_name}
                basePath="/invoices"
                label="Invoices"
                fetchFirstPage={(query) => INVOICES_API.fetchInvoices(query ?? {})}
                fetchFromUrl={INVOICES_API.fetchInvoicesFromUrl}
                idKey="base_uuid"
                labelKey="reference_code"
                descriptionKeyFn={(item) =>
                  `Amount due: ${item.currency?.code ? `${item.currency.code} ` : ""}${formatCurrency(
                    item.amount_due,
                  )}`
                }
              />
              <Badge
                className={`rounded-full border-transparent ${getStatusBadge(invoice.invoice_status)}`}
              >
                {invoice.invoice_status.charAt(0).toUpperCase() + invoice.invoice_status.slice(1)}
              </Badge>
            </div>
          </div>

          <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2">
            <div ref={setApprovalToggleContainer} />
            <ResponsiveActions
              actions={[
                {
                  key: "make-payment",
                  label: "Receive Payment",
                  icon: "hugeicons:payment-02",
                  prominent: true,
                  disabled: invoice.invoice_payment_status === "paid",
                  onSelect: () => setIsPaymentModalOpen(true),
                },
                {
                  key: "download",
                  label: isDownloading ? "Downloading..." : "Download",
                  icon: "hugeicons:download-01",
                  prominent: true,
                  disabled: isDownloading,
                  onSelect: handleInvoiceDownload,
                },
                {
                  key: "goods-issued-note",
                  label: "Goods Issued Note",
                  icon: "hugeicons:note-edit",
                  onSelect: () => router.push(`/goods-issued-note/create?invoiceId=${invoiceId}`),
                },
                {
                  key: "place-order",
                  label: "Place Order",
                  icon: "hugeicons:factory-01",
                  onSelect: () => setIsPlaceOrderOpen(true),
                },
                {
                  key: "apply-deposit",
                  label: "Apply Deposit",
                  icon: "hugeicons:link-01",
                  disabled: Number(invoice.amount_due || 0) <= 0,
                  onSelect: () => setIsDepositLinkModalOpen(true),
                },
                {
                  key: "credit-note",
                  label: "Credit Note",
                  icon: "hugeicons:money-send-02",
                  permissionCode: PERMISSION_CODES.CAN_CREATE_CREDIT_DEBIT_NOTES,
                  onSelect: () => router.push(`/credit-notes/credit?invoiceId=${invoiceId}`),
                },
                {
                  key: "duplicate",
                  label: "Duplicate",
                  icon: "hugeicons:copy-01",
                  onSelect: handleDuplicate,
                },
              ]}
            />
          </div>
        </div>

        {/* Invoice + Customer Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 py-6">
          {/* Left Column - Company and Customer Details */}
          <div>
            {/* Company Details */}
            <div className="mb-8">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-muted-foreground">FROM</p>
                <p className="font-semibold text-base">
                  {invoice.branch?.branch_name ?? currentInstitution?.institution_name}
                </p>
                <p className="text-sm text-muted-foreground">
                  {invoice.branch?.branch_location ?? currentInstitution?.location}
                </p>
                {(invoice.branch?.branch_email || currentInstitution?.institution_email) && (
                  <p className="text-sm text-muted-foreground">
                    {invoice.branch?.branch_email ?? currentInstitution?.institution_email}
                    {invoice.branch?.branch_phone_number &&
                      `, ${invoice.branch.branch_phone_number}`}
                  </p>
                )}
              </div>
            </div>

            {/* Customer Details */}
            <div>
              <p className="text-sm font-semibold text-muted-foreground mb-2">BILL TO</p>
              <div className="space-y-1">
                {invoice.customer ? (
                  <Link
                    href={`/customers/${invoice.customer.base_uuid}`}
                    className="inline-flex items-center gap-1.5 font-semibold text-base text-primary"
                  >
                    {invoice.customer.customer_name}
                    <Icon icon="hugeicons:arrow-right-02" className="size-3 opacity-60" />
                  </Link>
                ) : (
                  <p className="font-semibold text-base">Customer name not available</p>
                )}
                <p className="text-sm text-muted-foreground">{invoice.customer?.address}</p>
                <p className="text-sm text-muted-foreground">
                  {invoice.customer?.email}
                  {invoice.customer?.phone_number && `, ${invoice.customer.phone_number}`}
                </p>
              </div>
            </div>
          </div>

          {/* Right Column - Invoice Details */}
          <div className="flex flex-col items-end text-right">
            <p className="text-3xl font-black tracking-tight uppercase">Invoice</p>
            <p className="text-sm text-muted-foreground mt-1">#{invoice.reference_code}</p>

            <div className="mt-4 text-sm w-full max-w-xs ml-auto flex flex-col gap-y-1.5">
              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Issue Date</span>
                <span className="font-medium">{formatDate(invoice.issue_date)}</span>
              </div>
              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Due Date</span>
                <span className="font-medium text-red-600">{formatDate(invoice.due_date)}</span>
              </div>
              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Linked SO</span>
                {invoice.purchase_order ? (
                  <Link
                    className="inline-flex items-center gap-1.5 text-primary hover:underline underline-offset-4 font-medium"
                    href={`/sales-orders/${invoice.purchase_order.base_uuid}`}
                  >
                    {invoice.purchase_order.reference_code}
                    <Icon icon="hugeicons:arrow-right-02" className="w-3 h-3 opacity-60" />
                  </Link>
                ) : (
                  <span className="font-medium">None</span>
                )}
              </div>

              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">Linked GINs</span>
                {invoice.related_goods_issued_notes?.length ? (
                  <RelatedReferences
                    items={invoice.related_goods_issued_notes.map((gin) => ({
                      id: gin.base_uuid,
                      reference: gin.reference_code,
                      href: `/goods-issued-note/${gin.base_uuid}`,
                    }))}
                  />
                ) : (
                  <span className="font-medium">None</span>
                )}
              </div>

              <div className="flex justify-end gap-1.5">
                <span className="text-muted-foreground">GIN Status</span>
                <Badge className={getBadgeStyle(invoice.goods_issued_note_status)}>
                  {formatText(invoice.goods_issued_note_status)}
                </Badge>
              </div>

              <div className="mt-4 ml-auto w-full max-w-xs rounded-xl border bg-muted/50 p-4 shadow-sm">
                <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                  Outstanding Balance
                </p>
                <p className="mt-2 text-3xl font-extrabold">
                  {invoice.amount_due
                    ? `${invoice.currency?.code ? `${invoice.currency.code} ` : ""}${formatCurrency(
                        invoice.amount_due,
                      )}`
                    : "Pending balance not available"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div
          className={`grid grid-cols-1 gap-4 ${
            hasAvailablePrepayments && Number(invoice.amount_due || 0) > 0
              ? "xl:grid-cols-[minmax(0,1fr)_380px]"
              : ""
          }`}
        >
          <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0">
            <TabsList className="h-auto w-full justify-start gap-x-6 rounded-xl border bg-muted/30 px-4 py-2">
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
                value="credit-notes"
                className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
              >
                <span>Credit</span>
                <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
              </TabsTrigger>
              <TabsTrigger
                value="journal-entries"
                className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
              >
                <span>Journal Entries</span>
                <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
              </TabsTrigger>

              <TabsTrigger
                value="audit-logs"
                className="grid !pl-0 relative group data-[state=active]:shadow-none data-[state=active]:font-medium"
              >
                <span>Audit Logs</span>
                <div className="mt-1.5 w-full rounded-full border-b-4 group-data-[state=active]:border-primary group-data-[state=inactive]:border-transparent" />
              </TabsTrigger>
            </TabsList>

            {/* Line Items Tab */}
            <TabsContent value="line-items" className="mt-2">
              <SalesDocumentLineItemsTable
                documentType="invoice"
                documentUuid={invoice.base_uuid}
                currency={invoice.currency?.code ?? ""}
                netTotal={invoice.net_total}
                taxTotal={invoice.tax_total}
                grossTotal={invoice.gross_total}
                onTaxClick={seeTaxDetails}
                footerRows={
                  <>
                    {parseFloat(invoice.credit_note_total) > 0 && (
                      <TableRow className="bg-gray-50">
                        <TableCell colSpan={7} className="text-right text-muted-foreground">
                          Credit Note
                        </TableCell>
                        <TableCell className="text-right text-green-600">
                          - {invoice.currency?.code} {formatCurrency(invoice.credit_note_total)}
                        </TableCell>
                      </TableRow>
                    )}
                    <TableRow className="bg-gray-100 font-semibold">
                      <TableCell colSpan={7} className="text-right">
                        Amount Due
                      </TableCell>
                      <TableCell className="text-right">
                        {invoice.currency?.code} {formatCurrency(invoice.amount_due)}
                      </TableCell>
                    </TableRow>
                  </>
                }
              />
            </TabsContent>

            {/* Payments Tab */}
            <TabsContent value="payments" className="mt-2">
              <PaginatedTableWrapper<ICustomerPaymentRecord>
                fetchFirstPage={() =>
                  CUSTOMER_PAYMENTS_API.fetchCustomerPayments({
                    invoice_base_uuid: invoiceId,
                    payment_type: "invoice_payment",
                  })
                }
                fetchFromUrl={CUSTOMER_PAYMENTS_API.fetchCustomerPaymentsFromUrl}
                deps={[invoiceId, paymentsRefreshTrigger]}
                showFooter={true}
              >
                {({data, loading}) => (
                  <CustomerPaymentsTable
                    payments={data?.results ?? []}
                    isLoading={loading}
                    invoiceContext
                    onRefresh={() => setPaymentsRefreshTrigger((current) => current + 1)}
                    onSelectionCountChange={() => undefined}
                    applyTrigger={0}
                  />
                )}
              </PaginatedTableWrapper>
            </TabsContent>

            {/* Credit / Debit Notes Tab */}
            <TabsContent value="credit-notes" className="mt-2">
              <InvoiceCreditDebitNotes invoiceUuid={invoice?.base_uuid} />
            </TabsContent>

            <TabsContent value="journal-entries" className="mt-2">
              <JournalEntriesTable
                modelContentTypeId={invoice.model_content_type_id}
                objectBaseUuid={invoice.base_uuid}
              />
            </TabsContent>

            <TabsContent value="audit-logs" className="mt-2">
              <EntityAuditLogs objectId={invoice.id} contentType={AUDIT_CONTENT_TYPES.INVOICE} />
            </TabsContent>
          </Tabs>

          {Number(invoice.amount_due || 0) > 0 && (
            <AvailablePrepaymentsPanel
              customerUuid={invoice.customer?.base_uuid}
              invoiceUuid={invoice.base_uuid}
              outstandingBalance={invoice.amount_due}
              currencyCode={invoice.currency?.code}
              onApplied={fetchInvoice}
              onAvailabilityChange={setHasAvailablePrepayments}
            />
          )}
        </div>

        <DescriptionSection description={invoice.description} />

        <PaymentModal
          isOpen={isPaymentModalOpen}
          onClose={() => {
            setIsPaymentModalOpen(false);
          }}
          onConfirm={handlePayment}
          isLoading={isPaymentLoading}
          invoice={invoice}
          institutionCurrency={currentInstitution?.currency}
          fetchAccounts={ACCOUNTS_API.fetchAccounts}
          fetchAccountsFromUrl={ACCOUNTS_API.fetchAccountsFromUrl}
        />
      </Approvals>

      <LinkDepositsDialog
        open={isDepositLinkModalOpen}
        onClose={() => setIsDepositLinkModalOpen(false)}
        onSuccess={fetchInvoice}
        mode="select_deposits"
        invoiceUuid={invoiceId}
        customerUuid={invoice?.customer?.base_uuid}
      />

      <PlaceOrderPanel
        open={isPlaceOrderOpen}
        onClose={() => setIsPlaceOrderOpen(false)}
        invoice={invoice}
        onCreated={() => {
          /* stay on the invoice; optionally refresh: fetchInvoice(); */
        }}
      />
    </PageLayout>
  );
}
