"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {useSelector} from "react-redux";
import {toast} from "sonner";
import {VendorBillsTable} from "./_components/vendor-bills-table";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {VENDORS_API, VENDOR_BILLS_API} from "#/_api/api.helpers";
import type {IVendor} from "#/_types/api.types";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PageLayout from "#/_components/common/layouts/page-layout";
import DateFilters, {DateFilterProps} from "#/_components/custom/data-filters";
import {PERMISSION_CODES} from "#/_constants/enums";
import ProtectedComponent from "#/_components/custom/protected-component";
import {FeatureReportExport} from "#/_components/common/feature-report-export";
import {useSorting} from "#/_components/common/use-sorting";

export default function VendorBillsPage() {
  const router = useRouter();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DateFilterProps>();
  const [status, setStatus] = useState("all");
  const [paymentStatus, setPaymentStatus] = useState("all");
  const [grnStatus, setGrnStatus] = useState("all");
  const [vendorFilter, setVendorFilter] = useState("all");
  const [vendorOptions, setVendorOptions] = useState<IVendor[]>([]);
  const [vendorNext, setVendorNext] = useState<string | null>(null);
  const [vendorSearch, setVendorSearch] = useState("");
  const [debouncedVendorSearch, setDebouncedVendorSearch] = useState("");
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [vendorFilterOpened, setVendorFilterOpened] = useState(false);
  const {ordering, handleSort, removeSort, isAsc, isDesc} = useSorting();

  useEffect(() => {
    const timeout = window.setTimeout(
      () => setDebouncedVendorSearch(vendorSearch.trim()),
      300,
    );
    return () => window.clearTimeout(timeout);
  }, [vendorSearch]);

  useEffect(() => {
    if (!vendorFilterOpened) return;

    let cancelled = false;
    setVendorsLoading(true);

    VENDORS_API.fetchVendors({
      page: 1,
      search: debouncedVendorSearch,
      has_vendor_bills: true,
    })
      .then((response) => {
        if (!cancelled) {
          setVendorOptions(response.results);
          setVendorNext(response.next);
        }
      })
      .finally(() => {
        if (!cancelled) setVendorsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [vendorFilterOpened, debouncedVendorSearch]);

  const handleVendorSearchChange = (value: string) => {
    setVendorSearch(value);
    setVendorNext(null);
  };

  const handleLoadMoreVendors = async () => {
    if (!vendorNext || vendorsLoading) return;
    setVendorsLoading(true);

    try {
      const response = await VENDORS_API.fetchVendorsFromUrl({url: vendorNext});
      setVendorOptions((current) =>
        Array.from(
          new Map(
            [...current, ...response.results].map((vendor) => [vendor.base_uuid, vendor]),
          ).values(),
        ),
      );
      setVendorNext(response.next);
    } finally {
      setVendorsLoading(false);
    }
  };

  if (!currentInstitution) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Please select an institution to view vendor bills.</p>
      </div>
    );
  }

  return (
    <PageLayout title="Vendor Bills" permissions={PERMISSION_CODES.CAN_VIEW_VENDOR_BILLS}>
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Vendor Bills</h1>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="">
        <div className="flex flex-col gap-4 md:flex-row md:flex-wrap md:justify-between">
          <div className="relative w-full md:max-w-lg">
            <Icon
              icon="hugeicons:search-01"
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4"
            />

            <Input
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 rounded-xl w-full"
            />
          </div>
          <div className="flex-grow flex items-center justify-center">
            <DateFilters onChange={setFilters} />
          </div>
          <div className="flex-grow flex justify-end gap-2">
            <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_VENDOR_BILLS}>
              <Button onClick={() => router.push("/vendor-bills/create")} className="rounded-xl">
                <Icon icon="hugeicons:add-01" className="w-4 h-4 mr-2" />
                New Bill
              </Button>
            </ProtectedComponent>
            <FeatureReportExport feature="VendorBill" />
          </div>
        </div>
      </div>

      {/* Paginated Table Wrapper */}
      <PaginatedTableWrapper
        deps={[search, filters, ordering, status, paymentStatus, grnStatus, vendorFilter]}
        fetchFirstPage={async (q) => {
          return await VENDOR_BILLS_API.fetchVendorBills({
            page: 1,
            ...q,
            ...(search.trim() && {search: search.trim()}),
            issue_date_period: filters?.filter,
            issue_date_to: filters?.to,
            issue_date_from: filters?.from,
            ...(ordering && {ordering}),
            ...(status !== "all" && {status}),
            ...(paymentStatus !== "all" && {payment_status: paymentStatus}),
            ...(grnStatus !== "all" && {goods_received_note_status: grnStatus}),
            ...(vendorFilter !== "all" && {vendor: vendorFilter}),
          });
        }}
        fetchFromUrl={VENDOR_BILLS_API.fetchVendorBillsFromUrl}
        onError={(error) => {
          toast.error("Failed to load vendor bills.");
        }}
      >
        {({data, loading, refresh}) => (
          <VendorBillsTable
            bills={data?.results || []}
            isLoading={loading}
            onBillDeleted={refresh}
            onSort={handleSort}
            onRemoveSort={removeSort}
            isAsc={isAsc}
            isDesc={isDesc}
            status={status}
            onStatusChange={setStatus}
            paymentStatus={paymentStatus}
            onPaymentStatusChange={setPaymentStatus}
            grnStatus={grnStatus}
            onGrnStatusChange={setGrnStatus}
            vendorFilter={vendorFilter}
            onVendorFilterChange={setVendorFilter}
            vendorOptions={vendorOptions}
            vendorSearch={vendorSearch}
            onVendorSearchChange={handleVendorSearchChange}
            vendorsLoading={vendorsLoading}
            vendorHasMore={Boolean(vendorNext)}
            onLoadMoreVendors={handleLoadMoreVendors}
            onVendorFilterOpen={() => setVendorFilterOpened(true)}
          />
        )}
      </PaginatedTableWrapper>
    </PageLayout>
  );
}
