"use client";

import {Fragment, useEffect, useMemo, useRef, useState} from "react";
import {Icon} from "@iconify/react";
import {useSelector} from "react-redux";
import {LOANS_API, LOAN_REPAYMENTS_API} from "#/_api/loans.helpers";
import {triggerDownload} from "#/_api/api.helpers";
import type {
  ILoan,
  ILoanDetail,
  ILoanRepayment,
  ILoanScheduleResponse,
  ILoanScheduleRow,
} from "#/_types/loans.types";
import {formatCurrency, formatDate, showErrorToast} from "#/_lib/utils";
import {PERMISSION_CODES} from "#/_constants/enums";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import Approvals from "#/_components/common/approvals/approvals";
import {RecordSwitcher} from "#/_components/common/record-switcher";
import {ResponsiveActions} from "#/_components/common/responsive-actions";
import {DescriptionSection} from "#/_components/common/description";
import {EmptyState} from "#/_components/common/nodata";
import JournalEntriesTable from "#/_components/common/tables/journal-entries-table";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {Badge} from "#/_components/custom/badge";
import ProtectedComponent from "#/_components/custom/protected-component";
import {CustomLink as Link} from "@/platform/v1/components/link";
import {Button} from "@/components/ui/button";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {Dialog, DialogContent, DialogDescription, DialogTitle} from "@/components/ui/dialog";
import {loanFormData} from "./loan-create-dialog";
import {LoanPaymentFormDialog} from "./loan-payment-form-dialog";
import {LoanPaymentDetailDialog} from "./loan-payment-detail-dialog";
import {LoanInstallmentDetailDialog} from "./loan-installment-detail-dialog";

const TABS = [
  ["terms", "Terms & Accounts"],
  ["schedule", "Repayment Schedule"],
  ["payments", "Payments"],
  ["journal-entries", "Journal Entries"],
] as const;

const DAY_COUNT_LABELS: Record<string, string> = {
  actual_365: "Actual / 365",
  actual_360: "Actual / 360",
  actual_actual_isda: "Actual / Actual (ISDA)",
};

type PaymentForm = {payment?: ILoanRepayment; schedule?: ILoanScheduleRow};

function displayChoice(value: string | null | undefined) {
  return value
    ? value.replaceAll("_", " ").replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
    : "—";
}

function money(amount: number | string) {
  return formatCurrency(amount, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function LoanDetailDialog({
  uuid,
  onClose,
  onEdit,
  onRefresh,
}: {
  uuid: string;
  onClose: () => void;
  onEdit: () => void;
  onRefresh?: () => void;
}) {
  const currentInstitution = useSelector(selectSelectedInstitution);

  const [loan, setLoan] = useState<ILoanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [version, setVersion] = useState(0);
  const [dataVersion, setDataVersion] = useState(0);
  const [activeTab, setActiveTab] = useState<string>("terms");
  const [downloading, setDownloading] = useState(false);
  const [paymentForm, setPaymentForm] = useState<PaymentForm | null>(null);
  const [viewPayment, setViewPayment] = useState<ILoanRepayment | null>(null);
  const [viewInstallment, setViewInstallment] = useState<ILoanScheduleRow | null>(null);
  // A nested dialog is currently open. Ignore parent dismiss events while it is open.
  const nestedDialogOpen = useRef(false);

  const openPaymentForm = (form: PaymentForm) => {
    nestedDialogOpen.current = true;
    setPaymentForm(form);
  };

  const openPaymentDetails = (payment: ILoanRepayment) => {
    nestedDialogOpen.current = true;
    setViewPayment(payment);
  };

  const openInstallmentDetails = (row: ILoanScheduleRow) => {
    nestedDialogOpen.current = true;
    setViewInstallment(row);
  };

  // Keep the parent loan dialog protected while ANY child dialog remains open.
  // In particular, closing the payment form must not dismiss the details dialog beneath it.
  useEffect(() => {
    nestedDialogOpen.current = Boolean(paymentForm || viewPayment || viewInstallment);
  }, [paymentForm, viewPayment, viewInstallment]);

  const closeNestedDialog = (close: () => void) => {
    close();
  };
  const [scheduleSummary, setScheduleSummary] = useState<Pick<
    ILoanScheduleResponse,
    "currency" | "totals"
  > | null>(null);
  const [panel, setPanel] = useState<HTMLDivElement | null>(null);
  const [toggle, setToggle] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    setLoan(null);
    void LOANS_API.detail(uuid)
      .then((record) => {
        if (active) setLoan(record);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [uuid, version]);

  const scheduleData = useMemo(
    () => (loan ? {...loanFormData(loan), reference_code: undefined} : null),
    [loan],
  );

  const refreshLoan = () => {
    setVersion((value) => value + 1);
    onRefresh?.();
  };

  const downloadSchedule = async () => {
    if (!scheduleData || downloading) return;
    setDownloading(true);
    try {
      const file = await LOANS_API.downloadSchedule(scheduleData);
      triggerDownload(file, `Loan-Schedule-${loan?.reference_code ?? "loan"}.csv`);
    } catch (error) {
      showErrorToast({error, defaultMessage: "Unable to download repayment schedule"});
    } finally {
      setDownloading(false);
    }
  };

  const lending = loan?.direction === "outflow";
  const canRecord = loan?.status === "approved" && loan?.approval_status === "active";
  const currencyCode = loan?.currency_code ?? "";
  const canEditPayment = (payment: ILoanRepayment) =>
    Boolean(payment.allow_changes) &&
    payment.approval_status === "active" &&
    payment.status !== "rejected";

  const institutionBlock = (
    <div className="space-y-0.5">
      <p className="font-semibold text-base">
        {loan?.branch_name ?? currentInstitution?.institution_name}
      </p>
      <p className="text-sm text-muted-foreground">{currentInstitution?.location}</p>
      {currentInstitution?.institution_email && (
        <p className="text-sm text-muted-foreground">{currentInstitution.institution_email}</p>
      )}
    </div>
  );

  const partyBlock = loan?.party_name ? (
    <Link
      href={
        lending
          ? `/customers/${loan.party_object_uuid}`
          : `/loan-mgt?tab=lenders&dialog=lender-details&lender=${loan.party_object_uuid}`
      }
      className="inline-flex items-center gap-1.5 font-semibold text-base text-primary"
    >
      {loan.party_name}
      <Icon icon="hugeicons:arrow-right-02" className="size-3 opacity-60" />
    </Link>
  ) : (
    <p className="font-semibold text-base">Party not available</p>
  );

  const parties = [
    {label: "LENDER", node: lending ? institutionBlock : partyBlock},
    {label: "BORROWER", node: lending ? partyBlock : institutionBlock},
  ];

  const detailRows: [string, string | null | undefined, string?][] = loan
    ? [
        [lending ? "Disbursement Date" : "Funds Receipt Date", formatDate(loan.disbursement_date)],
        [
          "First Repayment",
          loan.first_repayment_date ? formatDate(loan.first_repayment_date) : "—",
        ],
        ["Maturity Date", formatDate(loan.maturity_date), "text-red-600"],
        [
          "Interest",
          `${formatCurrency(loan.annual_interest_rate)}% · ${displayChoice(loan.interest_method)}`,
        ],
      ]
    : [];

  const amountBlocks: [string, string, string?][] = loan
    ? [
        ["Principal", `${loan.currency_code} ${formatCurrency(loan.principal)}`],
        [
          "Total Interest",
          scheduleSummary
            ? `${scheduleSummary.currency} ${money(scheduleSummary.totals.interest)}`
            : "—",
          "text-orange-600",
        ],
        [
          "Total Repayment",
          scheduleSummary
            ? `${scheduleSummary.currency} ${money(scheduleSummary.totals.total_due)}`
            : "—",
        ],
      ]
    : [];

  const termRows: [string, string | null | undefined][] = loan
    ? [
        ["Direction", lending ? "Outflow (Lent)" : "Inflow (Borrowed)"],
        ["Currency", loan.currency_code],
        ["Branch", loan.branch_name || "—"],
        ["Interest Method", displayChoice(loan.interest_method)],
        ["Interest Type", displayChoice(loan.interest_type)],
        ["Day Count Convention", DAY_COUNT_LABELS[loan.day_count_convention] ?? "—"],
        [
          "Repayment Structure",
          loan.repayment_structure === "single" ? "Single Repayment" : "Periodic Installments",
        ],
        ["Repayment Frequency", displayChoice(loan.repayment_frequency)],
        ["Repayment Method", displayChoice(loan.repayment_method)],
        ["Repayment Timing", displayChoice(loan.repayment_timing)],
        ["Cash Account", loan.cash_account_name],
        [lending ? "Loan Receivable Account" : "Loan Liability Account", loan.loan_account_name],
      ]
    : [];

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !nestedDialogOpen.current) onClose();
      }}
    >
      <DialogContent
        className="z-[50] flex h-[88vh] max-h-[88vh] w-[88vw] max-w-[88vw] flex-col gap-0 overflow-hidden p-0"
        onPointerDownOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => {
          if (nestedDialogOpen.current) event.preventDefault();
        }}
      >
        <DialogTitle className="sr-only">Loan Details</DialogTitle>
        <DialogDescription className="sr-only">
          View loan terms, repayment schedule, payments and journal entries.
        </DialogDescription>

        {loading ? (
          <div className="p-5" role="status">
            Loading loan...
          </div>
        ) : failed || !loan || !scheduleData ? (
          <div role="alert" className="space-y-3 p-5">
            <p>Unable to load this loan.</p>
            <Button variant="outline" onClick={() => setVersion((value) => value + 1)}>
              Retry
            </Button>
          </div>
        ) : (
          <div ref={setPanel} className="relative min-h-0 flex-1 overflow-y-auto p-5">
            <Approvals
              entity="loan"
              data={loan}
              toggleContainer={toggle}
              onRefresh={refreshLoan}
              onActionComplete={(action) => {
                if (action === "reject") onClose();
              }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4 lg:pr-9">
                <div className="flex min-w-0 flex-col items-start gap-1">
                  <RecordSwitcher<ILoan>
                    portalContainer={panel}
                    currentId={loan.base_uuid}
                    currentLabel={`${loan.party_name || loan.reference_code || "Loan"}`}
                    currentDescription={loan.reference_code || undefined}
                    basePath="/loan-mgt"
                    getRecordPath={(record) =>
                      `/loan-mgt?tab=loans&dialog=loan-details&loan=${record.base_uuid}`
                    }
                    fetchFirstPage={(query) => LOANS_API.list(query ?? {})}
                    fetchFromUrl={LOANS_API.fromUrl}
                    idKey="base_uuid"
                    labelKey="reference_code"
                    label="Loans"
                    className="max-w-full"
                  />
                  <span className="pl-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {lending ? "Lent" : "Borrowed"}
                  </span>
                </div>

                <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2">
                  <div ref={setToggle} />
                  <ResponsiveActions
                    actions={[
                      {
                        key: "edit",
                        label: "Edit",
                        icon: "hugeicons:edit-01",
                        prominent: true,
                        visible: loan.allow_changes,
                        permissionCode: PERMISSION_CODES.CAN_EDIT_LOANS,
                        onSelect: onEdit,
                      },
                      {
                        key: "record-payment",
                        label: "Record Payment",
                        icon: "hugeicons:payment-02",
                        prominent: true,
                        visible: canRecord,
                        permissionCode: PERMISSION_CODES.CAN_EDIT_LOANS,
                        onSelect: () => openPaymentForm({}),
                      },
                      {
                        key: "download-schedule",
                        label: downloading ? "Downloading..." : "Download Schedule",
                        icon: "hugeicons:download-01",
                        prominent: true,
                        disabled: downloading,
                        onSelect: downloadSchedule,
                      },
                    ]}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 py-3 md:grid-cols-2">
                <div className="space-y-3">
                  {parties.map((party) => (
                    <div key={party.label}>
                      <p className="mb-1 text-sm font-semibold text-muted-foreground">
                        {party.label}
                      </p>
                      {party.node}
                    </div>
                  ))}
                </div>

                <div className="flex flex-col items-end text-right">
                  <p className="text-2xl font-black uppercase tracking-tight">LOANS</p>
                  <div className="mt-2 ml-auto flex w-full max-w-md flex-col gap-y-1 text-sm">
                    {detailRows.map(([label, value, tone]) => (
                      <div key={label} className="flex justify-end gap-1.5">
                        <span className="text-muted-foreground">{label}</span>
                        <span className={`font-medium ${tone ?? ""}`}>{value || "—"}</span>
                      </div>
                    ))}

                    <div className="mt-2 grid w-full grid-cols-1 items-center gap-2 rounded-xl border bg-muted/40 px-3 py-2 shadow-sm sm:grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)_1px_minmax(0,1fr)] sm:gap-1.5">
                      {amountBlocks.map(([label, value, tone], index) => (
                        <Fragment key={label}>
                          {index > 0 && (
                            <div
                              aria-hidden="true"
                              className="h-px w-full bg-border sm:h-8 sm:w-px sm:justify-self-center"
                            />
                          )}
                          <div className="min-w-0 text-left sm:text-right">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                              {label}
                            </p>
                            <p
                              className={`mt-0.5 break-words text-base font-bold tabular-nums sm:text-base ${tone ?? ""}`}
                            >
                              {value}
                            </p>
                          </div>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="min-w-0">
                <div
                  role="tablist"
                  aria-label="Loan details"
                  className="flex h-auto w-full flex-wrap justify-start gap-x-6 bg-transparent py-1"
                >
                  {TABS.map(([value, label]) => (
                    <button
                      key={value}
                      id={`loan-tab-${value}`}
                      type="button"
                      role="tab"
                      aria-selected={activeTab === value}
                      aria-controls={`loan-panel-${value}`}
                      onClick={() => setActiveTab(value)}
                      className={`group grid relative !pl-0 text-sm ${activeTab === value ? "font-medium" : "text-muted-foreground"}`}
                    >
                      <span>{label}</span>
                      <div
                        className={`mt-1.5 w-full rounded-full border-b-4 ${activeTab === value ? "border-primary" : "border-transparent"}`}
                      />
                    </button>
                  ))}
                </div>

                <section
                  id="loan-panel-terms"
                  role="tabpanel"
                  aria-labelledby="loan-tab-terms"
                  hidden={activeTab !== "terms"}
                  className="mt-2"
                >
                  <dl className="grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-3">
                    {termRows.map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-sm text-muted-foreground">{label}</dt>
                        <dd className="mt-1 break-words font-medium">{value || "—"}</dd>
                      </div>
                    ))}
                  </dl>
                </section>

                <section
                  id="loan-panel-schedule"
                  role="tabpanel"
                  aria-labelledby="loan-tab-schedule"
                  hidden={activeTab !== "schedule"}
                  className="mt-2"
                >
                  <PaginatedTableWrapper
                    fetchFirstPage={async () => {
                      const result = await LOANS_API.schedule(loan.base_uuid);
                      setScheduleSummary({currency: result.currency, totals: result.totals});
                      return result;
                    }}
                    fetchFromUrl={async (query) => {
                      const result = await LOANS_API.scheduleFromUrl(query);
                      setScheduleSummary({currency: result.currency, totals: result.totals});
                      return result;
                    }}
                    deps={[loan.base_uuid, dataVersion]}
                    showFooter={true}
                    onError={(error) =>
                      showErrorToast({error, defaultMessage: "Unable to load repayment schedule"})
                    }
                  >
                    {({data: page, loading: scheduleLoading}) => {
                      const rows = page?.results ?? [];

                      return (
                        <div className="w-full max-w-full overflow-x-auto bg-white shadow-sm">
                          <div className="min-w-[48rem] lg:min-w-full">
                            <Table className="w-full border-collapse">
                              <TableHeader className="bg-gray-800">
                                <TableRow className="border-none">
                                  <TableHead className="!text-white">Installment</TableHead>
                                  <TableHead className="!text-white">Due Date</TableHead>
                                  {[
                                    "Principal",
                                    "Interest",
                                    "Total Due",
                                    "Paid",
                                    "Outstanding",
                                  ].map((label) => (
                                    <TableHead key={label} className="!text-white text-right">
                                      {label}
                                    </TableHead>
                                  ))}
                                  <TableHead className="!text-white">Status</TableHead>
                                  <TableHead className="!text-white w-[50px]">Actions</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {scheduleLoading ? (
                                  Array.from({length: 3}).map((_, index) => (
                                    <TableRow key={index} className="border-none">
                                      <TableCell colSpan={9}>
                                        <div className="h-4 animate-pulse rounded bg-muted" />
                                      </TableCell>
                                    </TableRow>
                                  ))
                                ) : rows.length === 0 ? (
                                  <TableRow className="border-none hover:bg-transparent">
                                    <TableCell colSpan={9}>
                                      <EmptyState />
                                    </TableCell>
                                  </TableRow>
                                ) : (
                                  <>
                                    {rows.map((row) => (
                                      <TableRow key={row.installation_number}>
                                        <TableCell className="font-medium">
                                          {row.installation_number}
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">
                                          {formatDate(row.due_date)}
                                        </TableCell>
                                        {[
                                          [row.principal_due, ""],
                                          [row.interest_due, ""],
                                          [row.total_due, "font-medium"],
                                          [row.total_paid, "text-green-600"],
                                          [row.outstanding, "font-semibold"],
                                        ].map(([amount, tone], index) => (
                                          <TableCell
                                            key={index}
                                            className={`whitespace-nowrap text-right tabular-nums ${tone}`}
                                          >
                                            {money(amount)}
                                          </TableCell>
                                        ))}
                                        <TableCell>
                                          <Badge status={row.status ?? "pending"} />
                                        </TableCell>
                                        <TableCell>
                                          <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                              <Button
                                                variant="ghost"
                                                size="icon"
                                                aria-label={`Actions for installment ${row.installation_number}`}
                                              >
                                                <Icon
                                                  icon="hugeicons:more-vertical-circle-01"
                                                  className="size-4"
                                                />
                                              </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                              <DropdownMenuItem
                                                onSelect={() => openInstallmentDetails(row)}
                                              >
                                                <Icon
                                                  icon="hugeicons:view"
                                                  className="mr-2 size-4"
                                                />
                                                Details
                                              </DropdownMenuItem>
                                              {canRecord && row.can_pay && (
                                                <ProtectedComponent
                                                  permissionCode={PERMISSION_CODES.CAN_EDIT_LOANS}
                                                >
                                                  <DropdownMenuItem
                                                    onSelect={() =>
                                                      openPaymentForm({schedule: row})
                                                    }
                                                  >
                                                    <Icon
                                                      icon="hugeicons:payment-02"
                                                      className="mr-2 size-4"
                                                    />
                                                    Record Payment
                                                  </DropdownMenuItem>
                                                </ProtectedComponent>
                                              )}
                                            </DropdownMenuContent>
                                          </DropdownMenu>
                                        </TableCell>
                                      </TableRow>
                                    ))}
                                    {scheduleSummary && (
                                      <TableRow className="bg-gray-100 font-semibold">
                                        <TableCell colSpan={2} className="text-right">
                                          Total ({scheduleSummary.currency})
                                        </TableCell>
                                        {[
                                          scheduleSummary.totals.principal,
                                          scheduleSummary.totals.interest,
                                          scheduleSummary.totals.total_due,
                                          scheduleSummary.totals.paid,
                                          scheduleSummary.totals.outstanding,
                                        ].map((amount, index) => (
                                          <TableCell
                                            key={index}
                                            className="whitespace-nowrap text-right tabular-nums"
                                          >
                                            {money(amount)}
                                          </TableCell>
                                        ))}
                                        <TableCell colSpan={2} />
                                      </TableRow>
                                    )}
                                  </>
                                )}
                              </TableBody>
                            </Table>
                          </div>
                        </div>
                      );
                    }}
                  </PaginatedTableWrapper>
                </section>

                <section
                  id="loan-panel-payments"
                  role="tabpanel"
                  aria-labelledby="loan-tab-payments"
                  hidden={activeTab !== "payments"}
                  className="mt-2"
                >
                  <PaginatedTableWrapper<ILoanRepayment>
                    fetchFirstPage={() => LOAN_REPAYMENTS_API.list(loan.base_uuid)}
                    fetchFromUrl={LOAN_REPAYMENTS_API.fromUrl}
                    deps={[loan.base_uuid, dataVersion]}
                    showFooter={true}
                    onError={(error) =>
                      showErrorToast({error, defaultMessage: "Unable to load repayments"})
                    }
                  >
                    {({data: page, loading: paymentsLoading}) => {
                      const payments = page?.results ?? [];

                      return (
                        <div className="w-full max-w-full overflow-x-auto bg-white shadow-sm">
                          <div className="min-w-[40rem] md:min-w-[50rem] lg:min-w-full">
                            <Table className="w-full border-collapse">
                              <TableHeader className="bg-gray-800">
                                <TableRow className="border-none">
                                  <TableHead className="!text-white">Reference</TableHead>
                                  <TableHead className="!text-white">Date</TableHead>
                                  <TableHead className="!text-white">Installments Paid</TableHead>
                                  <TableHead className="!text-white text-right">Amount</TableHead>
                                  <TableHead className="!text-white">Status</TableHead>
                                  <TableHead className="!text-white w-[50px]">Actions</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {paymentsLoading ? (
                                  Array.from({length: 3}).map((_, index) => (
                                    <TableRow key={index} className="border-none">
                                      <TableCell colSpan={6}>
                                        <div className="h-4 animate-pulse rounded bg-muted" />
                                      </TableCell>
                                    </TableRow>
                                  ))
                                ) : payments.length === 0 ? (
                                  <TableRow className="border-none hover:bg-transparent">
                                    <TableCell colSpan={6}>
                                      <EmptyState />
                                    </TableCell>
                                  </TableRow>
                                ) : (
                                  payments.map((payment) => (
                                    <TableRow key={payment.base_uuid}>
                                      <TableCell className="font-medium">
                                        {payment.reference_code || "—"}
                                      </TableCell>
                                      <TableCell className="whitespace-nowrap">
                                        {formatDate(payment.date)}
                                      </TableCell>
                                      <TableCell>
                                        <div className="space-y-1">
                                          {payment.allocations.map((allocation) => (
                                            <div
                                              key={allocation.repayment_schedule}
                                              className="text-xs"
                                            >
                                              <span className="font-medium">
                                                Installment {allocation.installation_number}
                                              </span>
                                              <span className="text-muted-foreground">
                                                {[
                                                  ["Principal", allocation.principal_amount],
                                                  ["Interest", allocation.interest_amount],
                                                  ["Fees", allocation.fee_amount],
                                                ]
                                                  .filter(([, value]) => Number(value) > 0)
                                                  .map(
                                                    ([label, value]) =>
                                                      ` · ${label} ${money(value)}`,
                                                  )
                                                  .join("")}
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      </TableCell>
                                      <TableCell className="whitespace-nowrap text-right font-semibold tabular-nums text-green-600">
                                        {loan.currency_code} {money(payment.amount)}
                                      </TableCell>
                                      <TableCell>
                                        <Badge status={payment.status} />
                                      </TableCell>
                                      <TableCell>
                                        <DropdownMenu>
                                          <DropdownMenuTrigger asChild>
                                            <Button
                                              variant="ghost"
                                              size="icon"
                                              aria-label={`Actions for repayment ${payment.reference_code ?? ""}`}
                                            >
                                              <Icon
                                                icon="hugeicons:more-vertical-circle-01"
                                                className="size-4"
                                              />
                                            </Button>
                                          </DropdownMenuTrigger>
                                          <DropdownMenuContent align="end">
                                            <DropdownMenuItem
                                              onSelect={() => openPaymentDetails(payment)}
                                            >
                                              <Icon icon="hugeicons:view" className="mr-2 size-4" />
                                              Details
                                            </DropdownMenuItem>
                                            {canEditPayment(payment) && (
                                              <ProtectedComponent
                                                permissionCode={PERMISSION_CODES.CAN_EDIT_LOANS}
                                              >
                                                <DropdownMenuItem
                                                  onSelect={() => openPaymentForm({payment})}
                                                >
                                                  <Icon
                                                    icon="hugeicons:edit-01"
                                                    className="mr-2 size-4"
                                                  />
                                                  Edit
                                                </DropdownMenuItem>
                                              </ProtectedComponent>
                                            )}
                                          </DropdownMenuContent>
                                        </DropdownMenu>
                                      </TableCell>
                                    </TableRow>
                                  ))
                                )}
                              </TableBody>
                            </Table>
                          </div>
                        </div>
                      );
                    }}
                  </PaginatedTableWrapper>
                </section>

                {activeTab === "journal-entries" && (
                  <section
                    id="loan-panel-journal-entries"
                    role="tabpanel"
                    aria-labelledby="loan-tab-journal-entries"
                    className="mt-2 min-w-0"
                  >
                    {loan.model_content_type_id ? (
                      <JournalEntriesTable
                        modelContentTypeId={loan.model_content_type_id}
                        objectBaseUuid={loan.base_uuid}
                      />
                    ) : (
                      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                        Journal entries are unavailable because this loan has no model content type
                        ID.
                      </div>
                    )}
                  </section>
                )}
              </div>

              <DescriptionSection description={loan.description ?? undefined} />
            </Approvals>

            {viewPayment && (
              <LoanPaymentDetailDialog
                payment={viewPayment}
                currencyCode={currencyCode}
                onClose={() => closeNestedDialog(() => setViewPayment(null))}
                onEdit={
                  canEditPayment(viewPayment)
                    ? () => {
                        setPaymentForm({payment: viewPayment});
                      }
                    : undefined
                }
              />
            )}
            {viewInstallment && (
              <LoanInstallmentDetailDialog
                row={viewInstallment}
                currencyCode={currencyCode}
                onClose={() => closeNestedDialog(() => setViewInstallment(null))}
                onRecord={
                  canRecord && viewInstallment.can_pay
                    ? () => {
                        setPaymentForm({schedule: viewInstallment});
                      }
                    : undefined
                }
              />
            )}
            {paymentForm && (
              <LoanPaymentFormDialog
                key={paymentForm.payment?.base_uuid ?? paymentForm.schedule?.base_uuid ?? "new"}
                loanUuid={loan.base_uuid}
                currencyCode={currencyCode}
                payment={paymentForm.payment}
                schedule={paymentForm.schedule}
                onClose={() => closeNestedDialog(() => setPaymentForm(null))}
                onSaved={() => {
                  setPaymentForm(null);
                  setDataVersion((value) => value + 1);
                  setActiveTab("payments");
                }}
              />
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
