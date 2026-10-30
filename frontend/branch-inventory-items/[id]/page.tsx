"use client";

import type {IBranchInventoryItem, IBranchInventoryItemUnitOfMeasure} from "#/_types/api.types";
import {Icon} from "@iconify/react";
import {AlertTriangle} from "lucide-react";
import {useParams, useSearchParams} from "next/navigation";
import {useEffect, useState} from "react";
import {useSelector} from "react-redux";
import EditSellingPriceModal, {
  BranchInventoryItemEditData,
  UOMEntry,
} from "../../branch-inventory-items/_components/edit-branch-inventory-item-modal";
import {BRANCH_INVENTORY_API, ITEM_UNIT_OF_MEASURE_API} from "#/_api/api.helpers";
import {capitalizeEachWord, showSuccessToast} from "#/_api/helpers";
import Approvals from "#/_components/common/approvals/approvals";
import PageLayout from "#/_components/common/layouts/page-layout";
import TabbedContent from "#/_components/custom/tabbed-content";
import {formatCurrency, showErrorToast} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {Badge} from "#/_components/custom/badge";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PriceHistory from "../../inventory-items/_components/price-history";
import PurchaseHistory from "../../inventory-items/_components/purchases.table";
import SaleHistory from "../../inventory-items/_components/sales.table";
import StockLogsHistory from "../../inventory-items/_components/stock-logs";
import BranchStockLayersHistory from "../_components/stock-layers";
import ProtectedComponent from "#/_components/custom/protected-component";
import {PERMISSION_CODES} from "#/_constants/enums";
import {RecordSwitcher} from "#/_components/common/record-switcher";

function Detail({label, value}: {label: string; value: string | number}) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium">{value}</p>
    </div>
  );
}

export default function InventoryItemDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const currentInstitution = useSelector(selectSelectedInstitution);

  const [item, setItem] = useState<IBranchInventoryItem | null>(null);
  const [units, setUnits] = useState<IBranchInventoryItemUnitOfMeasure[]>([]);
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<IBranchInventoryItem | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);

  const searchParams = useSearchParams();

  useEffect(() => {
    if (searchParams.get("edit")) {
      setEditModalOpen(searchParams.get("edit")?.toString() == "true");
    }
  }, [searchParams]);

  const itemId = params.id as string;

  useEffect(() => {
    fetchItem();
    fetchUnitsOfMeasure();
  }, [itemId, currentInstitution, router]);

  const getConversionDisplay = (uom: IBranchInventoryItemUnitOfMeasure) => {
    if (uom.is_base_unit_of_measure) {
      return "Base unit";
    }

    const otherUnit = units.find(
      (unit) => unit.unit_of_measure.id === uom.other_uom,
    )?.unit_of_measure;
    const quantity = Number(uom.other_quantity);

    if (!otherUnit || !quantity) {
      return "Not configured";
    }

    const fromUnit = uom.unit_of_measure.unit_abbreviation || uom.unit_of_measure.unit_name;
    const toUnit = otherUnit.unit_abbreviation || otherUnit.unit_name;

    return `1 ${fromUnit} = ${quantity} ${toUnit}`;
  };

  const fetchUnitsOfMeasure = async () => {
    if (!itemId || !currentInstitution) return;

    setUnitsLoading(true);
    try {
      const response = await ITEM_UNIT_OF_MEASURE_API.fetchBranchInventoryItemUoms({
        branch_inventory_item_uuid: itemId,
      });

      setUnits(
        response.results.sort(
          (a, b) => Number(b.is_base_unit_of_measure) - Number(a.is_base_unit_of_measure),
        ),
      );
    } catch (error) {
      setUnits([]);
      showErrorToast({
        error,
        defaultMessage: "Failed to load branch units of measure",
      });
    } finally {
      setUnitsLoading(false);
    }
  };

  const fetchItem = async () => {
    if (!itemId || !currentInstitution) return;

    setLoading(true);
    try {
      const response = await BRANCH_INVENTORY_API.fetchBranchInventoryItemById({
        item_uuid: itemId,
      });

      setItem(response);
    } catch (error) {
      showErrorToast({
        error,
        defaultMessage: "Failed to load inventory item/service",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item: IBranchInventoryItem) => {
    setEditModalOpen(true);
    setSelectedItem(item);
  };

  const handleConfirmEdit = async (data: BranchInventoryItemEditData) => {
    try {
      await BRANCH_INVENTORY_API.updateBranchInventoryItem({
        item_uuid: selectedItem?.base_uuid ?? "",
        data: {
          can_be_returned: data.can_be_returned,
          price_changes: data.units
            .filter((u) => u.selling_price_num !== Number(u.selling_price))
            .map((u) => ({
              unit_of_measure: u.base_uuid,
              selling_price: u.selling_price_num.toString(),
            })),
        },
      });

      showSuccessToast("Inventory updated successfully");
      await fetchItem();
      await fetchUnitsOfMeasure();
      setSelectedItem(null);
      setEditModalOpen(false);
    } catch (error) {
      showErrorToast({error, defaultMessage: "Failed to update inventory record"});
    }
  };
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-current border-t-transparent mx-auto mb-4" />
          <p className="text-gray-600">Loading inventory...</p>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Item Not Found</h3>
          <p className="text-gray-600 mb-4">
            The inventory item/service you're looking for doesn't exist.
          </p>
          <Button onClick={() => router.push("/branch-inventory-items")} className="rounded-xl">
            Back to Branch Inventory Items/Services
          </Button>
        </div>
      </div>
    );
  }

  const isService = item?.inventory_item?.item_type === "SERVICES";
  const isLowStock = item.quantity <= 1;

  return (
    <PageLayout title="">
      <Approvals
        entity="BranchInventoryItem"
        data={{
          approvals: item.approvals,
          approval_status: item.approval_status,
        }}
        onRefresh={fetchItem}
      >
        {/* Header */}
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="flex gap-4 items-center flex-grow">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.back()}
              className="rounded-full"
            >
              <Icon icon="hugeicons:arrow-left-02" className="h-4 w-4" />
            </Button>
            <RecordSwitcher<IBranchInventoryItem>
              currentId={item.base_uuid}
              currentLabel={item.inventory_item.item_name}
              currentDescription={`${item.branch.branch_name} · ${
                item.inventory_item.reference_code || item.inventory_item.item_code
              }`}
              basePath="/branch-inventory-items"
              label="Branch Inventory Item"
              fetchFirstPage={(query) => BRANCH_INVENTORY_API.fetchBranchInventory(query ?? {})}
              fetchFromUrl={BRANCH_INVENTORY_API.fetchBranchInventoryFromUrl}
              idKey="base_uuid"
              labelKeyFn={(record) => record.inventory_item.item_name}
              descriptionKeyFn={(record) =>
                `${record.branch.branch_name} · ${
                  record.inventory_item.reference_code || record.inventory_item.item_code
                }`
              }
              query={{item_type: item.inventory_item.item_type}}
            />
          </div>
          <div className="flex gap-2">
            <ProtectedComponent permissionCode={PERMISSION_CODES.CAN_EDIT_BRANCH_INVENTORY_ITEMS}>
              <Button variant="outline" onClick={() => handleEdit(item)} className="rounded-xl">
                <Icon icon="hugeicons:edit-01" className="h-4 w-4 mr-2" />
                Update Seling Price
              </Button>
            </ProtectedComponent>
          </div>
        </div>

        {/* Status Alert */}
        {isLowStock && !isService && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              <p className="text-red-800 font-medium">Low Stock Alert</p>
            </div>
            <p className="text-red-700 text-sm mt-1">
              Current quantity ({item.quantity}) is at or below reorder point
              {/* {item.reorder_point} */}
            </p>
          </div>
        )}

        <div className="space-y-8">
          <section>
            <h2 className="text-lg font-semibold">Stock Configuration</h2>
            <div className="mt-3 overflow-x-auto">
              <div className="grid min-w-[1200px] grid-cols-6 gap-3">
                <Detail
                  label="Valuation method"
                  value={capitalizeEachWord(
                    item.inventory_item.product_stock_valuation_method?.name ?? "—",
                  )}
                />
                <Detail
                  label="Movement strategy"
                  value={capitalizeEachWord(
                    item.inventory_item.product_stock_movement_strategy?.name ?? "—",
                  )}
                />
                <Detail
                  label="Inventory account"
                  value={item.inventory_item.inventory_account?.account_name ?? "—"}
                />
                <Detail
                  label="Revenue account"
                  value={item.inventory_item.revenue_account?.account_name ?? "—"}
                />
                <Detail
                  label="Purchase Tax"
                  value={item.inventory_item.purchase_tax?.tax_name ?? "—"}
                />
                <Detail label="Sales Tax" value={item.inventory_item.sales_tax?.tax_name ?? "—"} />
              </div>
            </div>
          </section>

          <section>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Units & Prices</h2>
                <p className="text-sm text-muted-foreground">
                  Conversion rates and selling prices configured for this branch.
                </p>
              </div>
              {!unitsLoading && (
                <Badge className="shrink-0 bg-muted text-foreground">
                  {units.length} {units.length === 1 ? "unit" : "units"}
                </Badge>
              )}
            </div>

            <div className="mt-3 overflow-hidden rounded-xl border bg-card">
              <Table className="text-sm">
                <TableHeader className="bg-muted/50">
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Unit of Measure</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Conversion</TableHead>
                    <TableHead className="text-right">Selling Price</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {unitsLoading ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={4} className="h-28 text-center">
                        <Icon
                          icon="hugeicons:loading-03"
                          className="mx-auto size-5 animate-spin text-muted-foreground"
                        />
                        <p className="mt-2 text-sm text-muted-foreground">
                          Loading units of measure...
                        </p>
                      </TableCell>
                    </TableRow>
                  ) : units.length ? (
                    units.map((uom) => (
                      <TableRow key={uom.base_uuid}>
                        <TableCell>
                          <div className="font-medium">{uom.unit_of_measure.unit_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {uom.unit_of_measure.unit_abbreviation || "No abbreviation"}
                          </div>
                        </TableCell>
                        <TableCell>
                          {uom.is_base_unit_of_measure ? (
                            <Badge className="bg-emerald-50 text-emerald-700">Base unit</Badge>
                          ) : (
                            <span className="text-muted-foreground">Alternative</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              uom.is_base_unit_of_measure
                                ? "text-muted-foreground"
                                : "font-medium tabular-nums"
                            }
                          >
                            {getConversionDisplay(uom)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right font-semibold tabular-nums">
                          {Number(uom.selling_price) === 0
                            ? "—"
                            : formatCurrency(uom.selling_price ?? 0)}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={4} className="h-28 text-center text-muted-foreground">
                        No units of measure have been configured for this branch.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </section>

          <TabbedContent
            tabs={{
              ...(!isService && {
                "Stock Movement Logs": (
                  <StockLogsHistory
                    item={item.inventory_item.base_uuid}
                    branchUuid={item.branch.base_uuid}
                  />
                ),
              }),
              "Stock Layers": <BranchStockLayersHistory item={item} />,
              "Sales History": <SaleHistory item={item.base_uuid} />,
              "Purchases History": <PurchaseHistory item={item.base_uuid} />,
              "Price History": <PriceHistory item={item.id?.toString() ?? ""} />,
            }}
            defaultTab={isService ? "Stock Layers" : "Stock Movement Logs"}
          />

          <EditSellingPriceModal
            isOpen={editModalOpen}
            onClose={() => setEditModalOpen(false)}
            onConfirm={handleConfirmEdit}
            initialUnits={
              selectedItem?.branch_inventory_item_units_of_measure?.map((u) => ({
                ...u,
                selling_price_num: Number(u.selling_price),
              })) ?? []
            }
            initialCanBeReturned={selectedItem?.can_be_returned ?? false}
          />
        </div>
      </Approvals>
    </PageLayout>
  );
}
