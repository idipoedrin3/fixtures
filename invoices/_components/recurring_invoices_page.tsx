"use client";

import {useState} from "react";
import {Icon} from "@iconify/react";
import {useRouter} from "next/navigation";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import PageLayout from "#/_components/common/layouts/page-layout";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {RECURRING_INVOICES_API} from "#/_api/api.helpers";
import DateFilters, {DateFilterProps} from "#/_components/custom/data-filters";
import {showErrorToast} from "#/_lib/utils";
import {RecurringInvoicesTable} from "./recurring-invoice-table";
import ProtectedComponent from "#/_components/custom/protected-component";
import { PERMISSION_CODES } from "#/_constants/enums";

export default function RecurringInvoicesPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DateFilterProps>();

  return (
    <PageLayout title="Recurring Invoices">
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
          <div className="flex-grow flex justify-end">
          <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_CREATE_RECURRING_INVOICES}>
            <Button
              onClick={() => router.push("/invoices/recurring-invoices/create")}
              className="rounded-xl"
            >
              <Icon icon="hugeicons:add-01" className="w-4 h-4 mr-2" />
              New Recurring Invoice
            </Button>
          </ProtectedComponent>
          </div>
        </div>
      </div>

      {/* Use the modern table component */}
      <PaginatedTableWrapper
        query={{
          search,
          next_run_date_period: filters?.filter,
          next_run_date_from: filters?.from,
          next_run_date_to: filters?.to,
          ordering: filters?.ordering,
        }}
        deps={[search, filters]}
        fetchFirstPage={async (q) => await RECURRING_INVOICES_API.fetchRecurringInvoices(q)}
        fetchFromUrl={RECURRING_INVOICES_API.fetchRecurringInvoicesFromUrl}
        onError={(error) => {
          showErrorToast({
            error,
            defaultMessage: "Failed to load recurring templates",
          });
        }}
      >
        {({data, loading, refresh}) => (
          <div className="-mx-5">
            <RecurringInvoicesTable
              templates={data?.results || []}
              isLoading={loading}
              refresh={refresh}
            />
          </div>
        )}
      </PaginatedTableWrapper>
    </PageLayout>
  );
}
