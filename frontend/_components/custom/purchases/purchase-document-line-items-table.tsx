import type {ReactNode} from "react";
import {useCallback, useEffect, useRef, useState} from "react";

import {VENDOR_BILLS_API, VENDOR_PURCHASE_ORDERS_API} from "#/_api/api.helpers";
import {formatCurrency} from "#/_lib/utils";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";

type PurchaseDocumentType = "vendor_purchase_order" | "vendor_bill";

interface TaxBreakdown {
  id?: number;
  base_uuid?: string;
  is_inclusive?: boolean;
  net_amount?: string | number;
  tax_amount?: string | number;
  gross_amount?: string | number;
  tax?: {
    base_uuid?: string;
    tax_name?: string;
  };
}

interface SourceItem {
  id?: number;
  base_uuid?: string;
  item_type?: string;
  inventory_item?: {item_name?: string; item_type?: "GOODS" | "SERVICES"};
  asset_category?: {category_name?: string};
  unit_of_measure?: {unit_name?: string; unit_abbreviation?: string};
  line_item_name?: string;
  other_asset_unit_of_measure?: string;
  other_unit_of_measure?: string;
  expense_name?: string;
  quantity?: string | number;
  unit_price?: string | number;
  line_total?: string | number;
  amount?: string | number;
  line_item_tax_breakdowns?: TaxBreakdown[];
  tax_breakdowns?: TaxBreakdown[];
}

interface PurchaseLineItem {
  key: string;
  itemName: string;
  itemType: "Inventory" | "Service" | "Other" | "Fixed Asset" | "Expense";
  unitOfMeasure: string;
  quantity: ReactNode;
  unitPrice: string | number;
  lineTotal: string | number;
  taxBreakdowns: TaxBreakdown[];
}

interface PurchaseDocumentLineItemsTableProps {
  documentType: PurchaseDocumentType;
  documentUuid: string;
  currency: string;
  netTotal: string | number;
  taxTotal: string | number;
  grossTotal: string | number;
  footerRows?: ReactNode;
  onTaxClick?: (taxUuid: string) => void;
}

const typeStyles: Record<PurchaseLineItem["itemType"], string> = {
  Inventory: "bg-blue-50 text-blue-700",
  Service: "bg-emerald-50 text-emerald-700",
  Other: "bg-gray-100 text-gray-600",
  "Fixed Asset": "bg-violet-50 text-violet-700",
  Expense: "bg-amber-50 text-amber-700",
};

export function PurchaseDocumentLineItemsTable({
  documentType,
  documentUuid,
  currency,
  netTotal,
  taxTotal,
  grossTotal,
  footerRows,
  onTaxClick,
}: PurchaseDocumentLineItemsTableProps) {
  const [items, setItems] = useState<PurchaseLineItem[]>([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const loadingRef = useRef(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const normalizeItem = useCallback((item: SourceItem, index: number): PurchaseLineItem => {
    const isExpense = item.item_type === "expense";
    const itemType = isExpense
      ? "Expense"
      : item.item_type === "inventory"
        ? item.inventory_item?.item_type === "SERVICES"
          ? "Service"
          : "Inventory"
        : item.item_type === "fixed_asset"
          ? "Fixed Asset"
          : "Other";

    return {
      key: String(item.base_uuid ?? item.id ?? `${itemType}-${index}`),
      itemName:
        item.inventory_item?.item_name ??
        item.line_item_name ??
        item.expense_name ??
        item.asset_category?.category_name ??
        "—",
      itemType,
      unitOfMeasure:
        item.unit_of_measure?.unit_abbreviation ??
        item.unit_of_measure?.unit_name ??
        item.other_asset_unit_of_measure ??
        item.other_unit_of_measure ??
        "—",
      quantity: isExpense ? "—" : (item.quantity ?? "—"),
      unitPrice: isExpense ? (item.amount ?? 0) : (item.unit_price ?? 0),
      lineTotal: isExpense ? (item.amount ?? 0) : (item.line_total ?? 0),
      taxBreakdowns: item.line_item_tax_breakdowns ?? item.tax_breakdowns ?? [],
    };
  }, []);

  const fetchPage = useCallback(
    async (pageNumber: number) => {
      if (!documentUuid || loadingRef.current) return;

      loadingRef.current = true;
      setIsLoading(true);
      setFailed(false);
      try {
        if (documentType === "vendor_purchase_order") {
          const response = await VENDOR_PURCHASE_ORDERS_API.fetchLineItems({
            purchaseOrderUuid: documentUuid,
            page: pageNumber,
          });
          const nextItems = (response.results as SourceItem[]).map(normalizeItem);
          setItems((current) =>
            pageNumber === 1
              ? nextItems
              : [
                  ...current,
                  ...nextItems.filter(
                    (nextItem) => !current.some((currentItem) => currentItem.key === nextItem.key),
                  ),
                ],
          );
          setPage(pageNumber);
          setHasMore(Boolean(response.next));
        } else {
          const response = await VENDOR_BILLS_API.fetchLineItems({billUuid: documentUuid});
          const sourceItems: SourceItem[] = [
            ...(response.line_items ?? []),
            ...(response.expenses ?? []).map((expense: SourceItem) => ({
              ...expense,
              item_type: "expense",
            })),
          ];
          setItems(sourceItems.map(normalizeItem));
          setPage(1);
          setHasMore(false);
        }
      } catch {
        setFailed(true);
      } finally {
        loadingRef.current = false;
        setIsLoading(false);
      }
    },
    [documentType, documentUuid, normalizeItem],
  );

  useEffect(() => {
    setItems([]);
    setPage(0);
    setHasMore(true);
    void fetchPage(1);
  }, [fetchPage]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (
      documentType !== "vendor_purchase_order" ||
      !container ||
      loadingRef.current ||
      !hasMore ||
      page === 0 ||
      container.scrollHeight > container.clientHeight
    ) {
      return;
    }
    void fetchPage(page + 1);
  }, [documentType, fetchPage, hasMore, items, page]);

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container || loadingRef.current || !hasMore) return;
    if (container.scrollHeight - container.scrollTop - container.clientHeight <= 80) {
      void fetchPage(page + 1);
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border">
      <div ref={scrollContainerRef} onScroll={handleScroll} className="max-h-[280px] overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-gray-800">
            <TableRow className="hover:bg-gray-800">
              <TableHead className="!text-white">#</TableHead>
              <TableHead className="!text-white">Item</TableHead>
              <TableHead className="!text-white">Type</TableHead>
              <TableHead className="!text-white">UOM</TableHead>
              <TableHead className="!text-white text-right">Qty</TableHead>
              <TableHead className="!text-white text-right">Unit Price</TableHead>
              <TableHead className="!text-white text-right">Net Amount</TableHead>
              <TableHead className="!text-white text-right">Taxes</TableHead>
              <TableHead className="!text-white text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {!isLoading && !failed && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="py-8 text-center text-muted-foreground">
                  No line items found
                </TableCell>
              </TableRow>
            )}
            {failed && (
              <TableRow>
                <TableCell colSpan={9} className="py-8 text-center text-destructive">
                  Failed to load line items
                </TableCell>
              </TableRow>
            )}
            {items.map((item, index) => {
              const taxAmount = item.taxBreakdowns.reduce(
                (total, breakdown) => total + Number(breakdown.tax_amount ?? 0),
                0,
              );
              const netAmount = item.taxBreakdowns[0]?.net_amount ?? item.lineTotal;
              const grossAmount = item.taxBreakdowns[0]?.gross_amount ?? item.lineTotal;

              return (
                <TableRow key={item.key}>
                  <TableCell>{index + 1}</TableCell>
                  <TableCell className="font-medium">{item.itemName}</TableCell>
                  <TableCell>
                    <span className={`rounded-full px-2 py-0.5 ${typeStyles[item.itemType]}`}>
                      {item.itemType}
                    </span>
                  </TableCell>
                  <TableCell>{item.unitOfMeasure}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {currency} {formatCurrency(item.unitPrice)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {currency} {formatCurrency(netAmount)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {item.taxBreakdowns.length ? (
                      <Popover>
                        <PopoverTrigger asChild>
                          <button
                            type="button"
                            aria-label={`View tax breakdown for ${item.itemName}`}
                            className="font-semibold text-primary underline decoration-dotted underline-offset-4 hover:text-primary/80"
                          >
                            {currency} {formatCurrency(taxAmount)}
                          </button>
                        </PopoverTrigger>
                        <PopoverContent align="center" className="w-auto p-3">
                          <div
                            className="max-h-64 w-80 space-y-2 overflow-y-auto overscroll-contain pr-2"
                            onWheel={(event) => event.stopPropagation()}
                          >
                            <p className="text-xs font-semibold text-muted-foreground">
                              Applied taxes
                            </p>
                            {item.taxBreakdowns.map((breakdown, taxIndex) => {
                              const taxUuid = breakdown.tax?.base_uuid;
                              const taxName =
                                breakdown.tax?.tax_name?.toUpperCase() || "Applied tax";

                              return (
                                <div
                                  key={breakdown.base_uuid ?? breakdown.id ?? taxIndex}
                                  className="rounded-lg border p-2 text-sm"
                                >
                                  {onTaxClick && taxUuid ? (
                                    <button
                                      type="button"
                                      className="font-medium text-primary hover:underline"
                                      onClick={() => onTaxClick(taxUuid)}
                                    >
                                      {taxName}
                                    </button>
                                  ) : (
                                    <span className="font-medium">{taxName}</span>
                                  )}
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {currency} {formatCurrency(breakdown.tax_amount ?? 0)}
                                  </p>
                                </div>
                              );
                            })}
                          </div>
                        </PopoverContent>
                      </Popover>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-right font-semibold tabular-nums">
                    {currency} {formatCurrency(grossAmount)}
                  </TableCell>
                </TableRow>
              );
            })}
            {isLoading && (
              <TableRow>
                <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                  {items.length ? "Loading more..." : "Loading line items..."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {items.length > 0 && (
        <div className="border-t bg-background">
          <Table className="w-full table-fixed">
            <colgroup>
              {Array.from({length: 9}, (_, index) => (
                <col key={index} className={index === 8 ? "w-44 sm:w-48" : undefined} />
              ))}
            </colgroup>
            <TableBody>
              <TableRow className="bg-muted/40">
                <TableCell colSpan={8} className="px-4 py-3 text-right">
                  Subtotal
                </TableCell>
                <TableCell className="px-4 py-3 text-right tabular-nums">
                  {currency} {formatCurrency(netTotal)}
                </TableCell>
              </TableRow>
              {Number(taxTotal || 0) > 0 && (
                <TableRow className="bg-muted/40">
                  <TableCell colSpan={8} className="px-4 py-3 text-right">
                    Tax
                  </TableCell>
                  <TableCell className="px-4 py-3 text-right tabular-nums">
                    {currency} {formatCurrency(taxTotal)}
                  </TableCell>
                </TableRow>
              )}
              <TableRow className="bg-gray-100 font-semibold">
                <TableCell colSpan={8} className="px-4 py-3 text-right">
                  Total
                </TableCell>
                <TableCell className="px-4 py-3 text-right tabular-nums">
                  {currency} {formatCurrency(grossTotal)}
                </TableCell>
              </TableRow>
              {footerRows}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
