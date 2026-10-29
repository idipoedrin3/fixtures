"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {useSelector} from "react-redux";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {CUSTOMERS_API, INVOICES_API} from "#/_api/api.helpers";
import type {ICustomer} from "#/_types/api.types";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {showErrorToast} from "#/_lib/utils";
import PageLayout from "#/_components/common/layouts/page-layout";
import DateFilters, {DateFilterProps} from "#/_components/custom/data-filters";
import {InvoicesTable} from "./invoices-table";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import {useSorting} from "#/_components/common/use-sorting";
import {FeatureReportExport} from "#/_components/common/feature-report-export";

export default function InvoicesPage() {
  const router = useRouter();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DateFilterProps>();
  const [paymentStatus, setPaymentStatus] = useState<"all" | "unpaid" | "partially_paid" | "paid">(
    "all",
  );
  const [ginStatus, setGinStatus] = useState<
    "all" | "full_issued" | "not_issued" | "partially_issued" | "not_required"
  >("all");
  const [customerFilter, setCustomerFilter] = useState("all");
  const [customerOptions, setCustomerOptions] = useState<ICustomer[]>([]);
  const [customerNext, setCustomerNext] = useState<string | null>(null);
  const [customerSearch, setCustomerSearch] = useState("");
  const [debouncedCustomerSearch, setDebouncedCustomerSearch] = useState("");
  const [customersLoading, setCustomersLoading] = useState(false);
  const [customerFilterOpened, setCustomerFilterOpened] = useState(false);
  const {ordering, handleSort, removeSort, isAsc, isDesc} = useSorting();

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedCustomerSearch(customerSearch.trim());
    }, 300);

    return () => window.clearTimeout(timeout);
  }, [customerSearch]);

  useEffect(() => {
    if (!customerFilterOpened) return;

    let cancelled = false;
    setCustomersLoading(true);

    CUSTOMERS_API.fetchCustomers({
      page: 1,
      search: debouncedCustomerSearch,
      has_invoices: true,
    })
      .then((response) => {
        if (!cancelled) {
          setCustomerOptions(response.results);
          setCustomerNext(response.next);
        }
      })
      .finally(() => {
        if (!cancelled) setCustomersLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [customerFilterOpened, debouncedCustomerSearch]);

  const handleCustomerSearchChange = (value: string) => {
    setCustomerSearch(value);
    setCustomerNext(null);
  };

  const handleLoadMoreCustomers = async () => {
    if (!customerNext || customersLoading) return;

    setCustomersLoading(true);

    try {
      const response = await CUSTOMERS_API.fetchCustomersFromUrl({
        url: customerNext,
      });

      setCustomerOptions((current) =>
        Array.from(
          new Map(
            [...current, ...response.results].map((customer) => [customer.base_uuid, customer]),
          ).values(),
        ),
      );
      setCustomerNext(response.next);
    } finally {
      setCustomersLoading(false);
    }
  };

  if (!currentInstitution) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Please select an institution to view invoices.</p>
      </div>
    );
  }

  return (
    <PageLayout>
      {/* Search and Filters */}
      <div className="-mx-5">
        <div className="flex flex-col md:flex-row md:justify-between">
          <div className="relative">
            <Icon
              icon="hugeicons:search-01"
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4"
            />
            <Input
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="flex-grow flex items-center justify-center">
            <DateFilters onChange={setFilters} />
          </div>
          <div className="flex-grow flex justify-end gap-2">
            <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_INVOICES}>
              <Button onClick={() => router.push("/invoices/create")} className="rounded-xl">
                <Icon icon="hugeicons:add-01" className="w-4 h-4 mr-2" />
                New Invoice
              </Button>
            </ProtectedComponent>

            <FeatureReportExport feature="Invoice" />
          </div>
        </div>
      </div>

      {/* Paginated Table Wrapper */}
      <PaginatedTableWrapper
        deps={[search, filters, ordering, paymentStatus, customerFilter, ginStatus]}
        fetchFirstPage={async (q) => {
          const params = {
            page: 1,
            ...q,
            ...(search.trim() && {search: search.trim()}),
            ...(filters || {}),
            ...(ordering && {ordering}),
            ...(paymentStatus !== "all" && {invoice_payment_status: paymentStatus}),
            ...(customerFilter !== "all" && {customer_base_uuid: customerFilter}),
            ...(ginStatus !== "all" && {goods_issued_note_status: ginStatus}),
          };
          return await INVOICES_API.fetchInvoices(params);
        }}
        fetchFromUrl={INVOICES_API.fetchInvoicesFromUrl}
        onError={(error) => {
          showErrorToast({error, defaultMessage: "Failed to load invoices"});
        }}
      >
        {({data, loading, refresh}) => (
          <div className="-mx-5">
            <InvoicesTable
              invoices={data?.results || []}
              isLoading={loading}
              onInvoiceUpdated={refresh}
              onInvoiceDeleted={refresh}
              ordering={ordering}
              onSort={handleSort}
              onRemoveSort={removeSort}
              isAsc={isAsc}
              isDesc={isDesc}
              paymentStatus={paymentStatus}
              onPaymentStatusChange={setPaymentStatus}
              ginStatus={ginStatus}
              onGinStatusChange={setGinStatus}
              customerFilter={customerFilter}
              onCustomerFilterChange={setCustomerFilter}
              customerOptions={customerOptions}
              customerSearch={customerSearch}
              onCustomerSearchChange={handleCustomerSearchChange}
              customersLoading={customersLoading}
              customerHasMore={Boolean(customerNext)}
              onLoadMoreCustomers={handleLoadMoreCustomers}
              onCustomerFilterOpen={() => setCustomerFilterOpened(true)}
            />
          </div>
        )}
      </PaginatedTableWrapper>
    </PageLayout>
  );
}
