import {useState} from "react";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {formatCurrency, formatDate} from "#/_lib/utils";
import {PaginatedTableWrapper} from "#/_components/common/tables/paginated-table-wrapper";
import {EmptyState} from "#/_components/common/nodata";
import DateFilters, {DateFilterProps} from "#/_components/custom/data-filters";
import {BRANCH_INVENTORY_API} from "#/_api/api.helpers";
import {IBranchInventoryItem} from "#/_types/api.types";

type Props = {
  item: IBranchInventoryItem;
};

export default function BranchStockLayersHistory({item}: Props) {
  const [filters, setFilters] = useState<DateFilterProps>();

  console.log("BranchInventoryItemUUID:", item?.base_uuid);

  return (
    <>
      <div className="flex items-center justify-center gap-4 w-full my-4">
        <h3 className="font-bold text-xl flex-grow">Stock Layers</h3>
        <div className="flex items-center justify-center">
          <DateFilters onChange={setFilters} dateRange={false} />
        </div>
      </div>
      {!item.base_uuid ? (
        <Table className="w-full">
          <TableHeader>
            <TableRow>
              <TableHead className="text-gray-800">Ref Code</TableHead>
              <TableHead className="text-gray-800">Unit of Measure</TableHead>
              <TableHead className="text-gray-800">Quantity</TableHead>
              <TableHead className="text-gray-800">Unit Cost</TableHead>
              <TableHead className="text-gray-800">Recieved Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell colSpan={4}>
                <EmptyState />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      ) : (
        <PaginatedTableWrapper
          query={{
            issue_date_period: filters?.filter,
            issue_date_to: filters?.to,
            issue_date_from: filters?.from,
            ordering: filters?.ordering,
            branch_inventory_item_uuid: item?.base_uuid,
          }}
          deps={[filters, item.base_uuid]}
          fetchFirstPage={BRANCH_INVENTORY_API.fetchItemStockLayers as any}
          fetchFromUrl={BRANCH_INVENTORY_API.fetchItemStockLayersFromUrl}
        >
          {({data, loading}) => {
            const entries = data?.results ?? [];

            return (
              <div className="overflow-x-auto w-full max-w-full">
                <Table className="w-full">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-gray-800">Ref Code</TableHead>
                      <TableHead className="text-gray-800">Unit of Measure</TableHead>
                      <TableHead className="text-gray-800">Quantity</TableHead>
                      <TableHead className="text-gray-800">Unit Cost</TableHead>
                      <TableHead className="text-gray-800">Recieved Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      <TableRow>
                        <TableCell colSpan={4}>
                          <div className="text-center p-8 opacity-50">Loading entries...</div>
                        </TableCell>
                      </TableRow>
                    ) : !entries.length ? (
                      <TableRow>
                        <TableCell colSpan={4}>
                          <EmptyState />
                        </TableCell>
                      </TableRow>
                    ) : (
                      entries.map((x, i) => (
                        <TableRow key={i}>
                          <TableCell className="">{x.reference_code}</TableCell>
                          <TableCell className="">{x.unit_of_measure?.unit_name}</TableCell>
                          <TableCell className="">{formatCurrency(x.quantity_remaining)}</TableCell>
                          <TableCell className="">{formatCurrency(x.unit_cost)}</TableCell>
                          <TableCell className="">{formatDate(x.received_date)}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            );
          }}
        </PaginatedTableWrapper>
      )}
    </>
  );
}
