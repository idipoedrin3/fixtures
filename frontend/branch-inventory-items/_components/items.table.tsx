"use client";

import type {IBranchInventoryItem} from "#/_types/api.types";
import {useState} from "react";
import {useSelector} from "react-redux";
import {Icon} from "@iconify/react";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Badge} from "#/_components/custom/badge";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {BRANCH_INVENTORY_API} from "#/_api/api.helpers";
import {getBadgeStyle} from "#/_lib/utils";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PageLayout from "#/_components/common/layouts/page-layout";
import DateFilters from "#/_components/custom/data-filters";
import {EmptyState} from "#/_components/common/nodata";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {FeatureReportExport} from "#/_components/common/feature-report-export";
import {REPORT_FEATURES} from "#/_constants/report-features.enum";

type Props = {
  type: "item" | "service";
};

export default function InventoryItemsTable({type}: Props) {
  const router = useRouter();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState({filter: "", from: "", to: ""});

  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleViewDetails = (item: IBranchInventoryItem) => {
    router.push(`/branch-inventory-items/${item.base_uuid}/`);
  };

  if (!currentInstitution) {
    return (
      <PageLayout title="Branch Inventory Items">
        <div className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">No Institution found !</p>
        </div>
      </PageLayout>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-center gap-4 w-full">
        <div className="relative">
          <Icon
            icon="hugeicons:search-01"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 h-4 w-4"
          />
          <Input
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
            className="pl-10 rounded-xl"
          />
        </div>
        <div className="flex-grow flex items-center justify-center">
          <DateFilters onChange={setFilters} />
        </div>
        <div className="flex-grow flex justify-end">
          {/* Refresh Button */}
          <Button
            variant="outline"
            onClick={() => setRefreshTrigger((prev) => (prev + 1) % 10)}
            className="border-0 text-gray-500"
          >
            <Icon icon="hugeicons:refresh" width="24" height="24" />
          </Button>
          <FeatureReportExport
            feature={REPORT_FEATURES.BRANCH_INVENTORY_ITEM}
            title="Export Sales Orders List"
            className="shrink-0 rounded-xl"
          />
        </div>
      </div>

      {/* Table */}
      <PaginatedTableWrapper<IBranchInventoryItem>
        query={{
          search,
          item_type: type == "item" ? "GOODS" : type == "service" ? "SERVICES" : "GOODS",
          issue_date_period: filters.filter,
          issue_date_to: filters.to,
          issue_date_from: filters.from,
        }}
        deps={[type, search, filters, refreshTrigger]}
        fetchFirstPage={BRANCH_INVENTORY_API.fetchBranchInventory}
        fetchFromUrl={BRANCH_INVENTORY_API.fetchBranchInventoryFromUrl}
      >
        {({data, loading}) => {
          const items = data?.results || [];

          const showingGoods = type === "item";

          return (
            <>
              <Table className="w-full">
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-gray-800">Item Code</TableHead>
                    <TableHead className="text-gray-800">Branch</TableHead>
                    <TableHead className="text-gray-800">Item</TableHead>
                    <TableHead className="text-gray-800">Category</TableHead>
                    {showingGoods && <TableHead className="text-gray-800">Quantity</TableHead>}
                    <TableHead className="text-gray-800">Status</TableHead>
                    <TableHead className="w-[50px] text-gray-800">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    Array.from({length: 5}).map((_, i) => (
                      <TableRow key={i} className="border-none">
                        <TableCell colSpan={showingGoods ? 7 : 6}>
                          <div className="h-4 bg-muted animate-pulse rounded" />
                        </TableCell>
                      </TableRow>
                    ))
                  ) : items?.length === 0 ? (
                    <TableRow className="border-none">
                      <TableCell colSpan={showingGoods ? 7 : 6}>
                        <EmptyState />
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item?.inventory_item?.reference_code || "-"}</TableCell>
                        <TableCell>{item?.branch?.branch_name || "-"}</TableCell>
                        <TableCell>
                          <div>{item.inventory_item.item_name}</div>
                          <div className="opacity-50">{item.inventory_item.item_code}</div>
                        </TableCell>
                        <TableCell>{item?.inventory_item?.item_category?.name ?? "-"}</TableCell>
                        {showingGoods && <TableCell>{item.quantity}</TableCell>}
                        <TableCell>
                          <Badge className={getBadgeStyle(item.is_active ? "active" : "")}>
                            {item.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" className="h-8 w-8 rounded-full p-0">
                                <Icon
                                  icon="hugeicons:more-vertical-circle-01"
                                  className="h-4 w-4"
                                />
                                <span className="sr-only">Open actions</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleViewDetails(item)}>
                                <Icon icon="hugeicons:view" className="mr-2 h-4 w-4" />
                                Details
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </>
          );
        }}
      </PaginatedTableWrapper>
    </div>
  );
}
