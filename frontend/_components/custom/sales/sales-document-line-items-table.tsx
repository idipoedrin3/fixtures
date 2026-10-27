import type {ReactNode} from "react";
import {useCallback, useEffect, useRef, useState} from "react";
import {Plus, Trash2} from "lucide-react";
import {INVOICES_API, PURCHASE_ORDERS_API, QUOTATIONS_API} from "#/_api/api.helpers";
import {formatCurrency} from "#/_lib/utils";
import {
  calculateSalesLineDiscounts,
  roundSalesDiscountAmount,
  validateSalesLineDiscounts,
} from "./sales-line-discount.utils";
import type {
  IInvoiceLineItem,
  IInvoiceLineItemTaxBreakdown,
  IPurchaseOrderLineItem,
  IQuotationLineItem,
  ISalesLineDiscount,
} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Textarea} from "#/_components/common/inputs/text-area";
import {DiscountItemSummary, DiscountValueInput} from "./sales-line-discount-input";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Table, TableBody, TableCell, TableHead, TableHeader, TableRow} from "@/components/ui/table";

type SalesDocumentType = "quotation" | "sales_order" | "invoice";
type SourceLineItem = IQuotationLineItem | IPurchaseOrderLineItem | IInvoiceLineItem;
type DiscountType = "percentage" | "fixed";
type SavedDiscount = ISalesLineDiscount & {
  id?: number | null;
  description?: string | null;
  discount_amount?: string | number;
};
interface DiscountDraft {
  id: number | null;
  discount_type: DiscountType;
  discount_value: string;
  description: string;
}

export interface DiscountPayload {
  id: number | null;
  discount_type: DiscountType;
  discount_value: string;
  description: string | null;
}

export interface SaveDiscountsArgs {
  lineUuid: string;
  discounts: DiscountPayload[];
}

interface SalesDocumentLineItem {
  key: string | number;
  itemName: string;
  unitOfMeasure?: string;
  quantity: ReactNode;
  quantityValue: number;
  unitPrice: string | number;
  lineTotal: string | number;
  quantityBilled?: ReactNode;
  quantityIssued?: ReactNode;
  quantityPending?: ReactNode;
  line_item_tax_breakdowns?: IInvoiceLineItemTaxBreakdown[];
  discounts?: SavedDiscount[];
}

interface SalesDocumentLineItemsTableProps {
  documentType: SalesDocumentType;
  documentUuid: string;
  currency: string;
  netTotal: string | number;
  taxTotal: string | number;
  grossTotal: string | number;
  totalDiscount: string | number;
  footerRows?: ReactNode;
  onTaxClick?: (taxUuid: string) => void;
  editable?: boolean;
  onSaveDiscounts?: (args: SaveDiscountsArgs) => Promise<void>;
}

const round2 = roundSalesDiscountAmount;

const emptyDraft = (): DiscountDraft => ({
  id: null,
  discount_type: "percentage",
  discount_value: "",
  description: "",
});

const toDrafts = (discounts?: SavedDiscount[]): DiscountDraft[] => {
  const sorted = [...(discounts ?? [])].sort((a, b) => (a.position || 0) - (b.position || 0));
  if (!sorted.length) return [emptyDraft()];

  return sorted.map((discount) => ({
    id: discount.id ?? null,
    discount_type: discount.discount_type as DiscountType,
    discount_value: String(Number(discount.discount_value)),
    description: discount.description ?? "",
  }));
};

interface DiscountCalculation {
  amounts: number[];
  errors: (string | null)[];
  total: number;
  remaining: number;
  hasBlank: boolean;
  isValid: boolean;
}

function calculateDiscounts(original: number, drafts: DiscountDraft[]): DiscountCalculation {
  const validationErrors = validateSalesLineDiscounts(drafts, original);
  const result = calculateSalesLineDiscounts(drafts, original);
  const errors = drafts.map((_, index) => validationErrors[index] ?? null);

  return {
    amounts: result.breakdown.map(({amount}) => amount),
    errors,
    total: result.totalDiscount,
    remaining: result.discountedTotal,
    hasBlank: drafts.some((draft) => draft.discount_value.trim() === ""),
    isValid: errors.every((error) => error === null),
  };
}

function buildLineView(item: SalesDocumentLineItem, drafts: DiscountDraft[] | null) {
  const breakdowns = item.line_item_tax_breakdowns ?? [];
  const original = round2(item.quantityValue * Number(item.unitPrice || 0));
  const savedLineTotal = Number(item.lineTotal || 0);

  let lineTotal = savedLineTotal;
  let discount = (item.discounts ?? []).reduce((sum, d) => sum + Number(d.discount_amount || 0), 0);
  let ratio = 1;

  if (drafts) {
    const calc = calculateDiscounts(original, drafts);
    lineTotal = calc.remaining;
    discount = calc.total;
    ratio = savedLineTotal > 0 ? lineTotal / savedLineTotal : 1;
  }

  const sumTax = (filter: (isInclusive: boolean) => boolean) =>
    breakdowns.reduce(
      (total, b) =>
        filter(Boolean(b.is_inclusive)) ? total + Number(b.tax_amount || 0) * ratio : total,
      0,
    );

  const taxAmount = sumTax(() => true);
  const inclusiveTax = sumTax((isInclusive) => isInclusive);
  const exclusiveTax = sumTax((isInclusive) => !isInclusive);

  return {
    original,
    discount,
    lineTotal,
    taxAmount,
    netAmount: lineTotal - inclusiveTax,
    grossAmount: lineTotal + exclusiveTax,
  };
}

interface DiscountEditorProps {
  currency: string;
  item: SalesDocumentLineItem;
  drafts: DiscountDraft[];
  calculation: DiscountCalculation;
  saving: boolean;
  saveError: string | null;
  onChange: (index: number, patch: Partial<DiscountDraft>) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onCancel: () => void;
  onApply: () => void;
}

function DiscountEditor({
  currency,
  item,
  drafts,
  calculation,
  saving,
  saveError,
  onChange,
  onAdd,
  onRemove,
  onCancel,
  onApply,
}: DiscountEditorProps) {
  return (
    <div className="space-y-3 text-left">
      <DialogHeader className="pr-8">
        <DialogTitle>Apply discounts</DialogTitle>
        <DialogDescription className="text-sm">
          Discounts apply in order, each to the amount remaining after the previous one.
        </DialogDescription>
      </DialogHeader>

      <DiscountItemSummary
        itemName={item.itemName}
        currency={currency}
        unitPrice={item.unitPrice}
        quantity={item.quantityValue}
        unitOfMeasure={item.unitOfMeasure}
        originalTotal={round2(item.quantityValue * Number(item.unitPrice || 0))}
        totalDiscount={calculation.total}
        discountedTotal={calculation.remaining}
        taxInclusive={
          item.line_item_tax_breakdowns?.length
            ? item.line_item_tax_breakdowns.some((tax) => tax.is_inclusive)
            : undefined
        }
      />

      <div className="max-h-[45vh] space-y-2.5 overflow-y-auto overscroll-contain">
        {drafts.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No discounts on this item. Add one below, or save to keep it without discounts.
          </p>
        )}

        {drafts.map((draft, index) => {
          const error = calculation.errors[index];
          const showError = Boolean(error);
          const amount = calculation.amounts[index] ?? 0;
          const showAmountHint = !showError && draft.discount_type === "percentage" && amount > 0;

          return (
            <div key={index}>
              <div className="flex flex-wrap items-center gap-2">
                <div
                  role="group"
                  aria-label={`Discount ${index + 1} type`}
                  className="inline-flex h-9 shrink-0 overflow-hidden rounded-md border text-xs font-semibold"
                >
                  {(["percentage", "fixed"] as const).map((type) => {
                    const active = draft.discount_type === type;
                    return (
                      <button
                        key={type}
                        type="button"
                        aria-pressed={active}
                        disabled={saving}
                        onClick={() => onChange(index, {discount_type: type})}
                        className={`min-w-10 px-2.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${
                          active
                            ? "bg-gray-800 text-white"
                            : "bg-background text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {type === "percentage" ? "%" : currency}
                      </button>
                    );
                  })}
                </div>

                <div className="w-36 shrink-0">
                  <DiscountValueInput
                    ariaLabel={`Discount ${index + 1} value`}
                    discountType={draft.discount_type}
                    suffix={draft.discount_type === "percentage" ? "%" : undefined}
                    autoFocus={index === 0 || draft.discount_value === ""}
                    value={draft.discount_value}
                    onChange={(value) => onChange(index, {discount_value: value})}
                    disabled={saving}
                    error={error ?? undefined}
                  />
                </div>

                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove discount ${index + 1}`}
                  disabled={saving}
                  onClick={() => onRemove(index)}
                  className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              <div className="mt-3">
                <Textarea
                  label="Description"
                  showOptional
                  collapsible
                  defaultExpanded={false}
                  aria-label={`Discount ${index + 1} description (optional)`}
                  placeholder="e.g. Promotional discount, bulk discount, loyalty discount…"
                  maxLength={255}
                  value={draft.description}
                  onChange={(event) => onChange(index, {description: event.target.value})}
                  disabled={saving}
                />
              </div>
              {showAmountHint && (
                <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                  Takes off {currency} {formatCurrency(amount)}
                </p>
              )}
            </div>
          );
        })}

        {drafts.length > 1 && (
          <p className="text-xs text-muted-foreground">
            Applied in order, each one on what is left after the one before.
          </p>
        )}
      </div>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onAdd}
        disabled={saving}
        className="-ml-2 h-8 px-2 text-primary hover:text-primary"
      >
        <Plus className="mr-1 h-4 w-4" />
        {drafts.length ? "Add another discount" : "Add discount"}
      </Button>

      <div className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm">
        <span className="text-muted-foreground">
          Discount{" "}
          <span className="tabular-nums text-foreground">
            {calculation.total > 0 ? "− " : ""}
            {currency} {formatCurrency(calculation.total)}
          </span>
        </span>
        <span className="font-semibold tabular-nums">
          {currency} {formatCurrency(calculation.remaining)}
        </span>
      </div>

      {saveError && <p className="text-sm text-destructive">{saveError}</p>}

      <DialogFooter className="gap-2 sm:gap-0">
        <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="button" onClick={onApply} disabled={saving || !calculation.isValid}>
          {saving ? "Saving..." : "Save discounts"}
        </Button>
      </DialogFooter>
    </div>
  );
}

export function SalesDocumentLineItemsTable({
  documentType,
  documentUuid,
  currency,
  onTaxClick,
  editable = false,
  onSaveDiscounts,
}: SalesDocumentLineItemsTableProps) {
  const [items, setItems] = useState<SalesDocumentLineItem[]>([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [editingKey, setEditingKey] = useState<string | null>(null);
  const editingItem = items.find((item) => String(item.key) === editingKey) ?? null;
  const [drafts, setDrafts] = useState<DiscountDraft[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const loadingRef = useRef(false);
  const generationRef = useRef(0);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const canEdit = Boolean(editable && onSaveDiscounts);
  const showFulfilmentColumns = documentType === "sales_order";
  const columnCount = showFulfilmentColumns ? 12 : 9;

  const editingOriginal = editingItem ? buildLineView(editingItem, null).original : 0;
  const editingCalculation = calculateDiscounts(editingOriginal, drafts);

  const normalizeItem = useCallback(
    (item: SourceLineItem): SalesDocumentLineItem => {
      if (documentType === "invoice") {
        const invoiceItem = item as IInvoiceLineItem;
        return {
          key: invoiceItem.base_uuid,
          itemName: invoiceItem.branch_item.item_name,
          unitOfMeasure:
            invoiceItem.unit_of_measure?.unit_abbreviation ||
            invoiceItem.unit_of_measure?.unit_name ||
            "-",
          quantity: invoiceItem.quantity,
          quantityValue: Number(invoiceItem.quantity || 0),
          unitPrice: invoiceItem.unit_price,
          lineTotal: invoiceItem.line_total,
          line_item_tax_breakdowns: invoiceItem.line_item_tax_breakdowns,
          discounts: invoiceItem.discounts as SavedDiscount[] | undefined,
        };
      }

      if (documentType === "sales_order") {
        const salesOrderItem = item as IPurchaseOrderLineItem;
        const isService = salesOrderItem.line_item?.inventory_item?.item_type === "SERVICES";
        return {
          key: salesOrderItem.base_uuid,
          itemName: salesOrderItem.line_item?.inventory_item?.item_name || "",
          unitOfMeasure:
            salesOrderItem.unit_of_measure?.unit_abbreviation ||
            salesOrderItem.unit_of_measure?.unit_name ||
            "-",
          quantity: salesOrderItem.quantity,
          quantityValue: Number(salesOrderItem.quantity || 0),
          quantityBilled: salesOrderItem.quantity_billed,
          quantityIssued: isService ? "N/A" : salesOrderItem.quantity_issued,
          quantityPending: isService ? "N/A" : salesOrderItem.quantity_pending,
          unitPrice: salesOrderItem.unit_price,
          lineTotal: salesOrderItem.line_total,
          line_item_tax_breakdowns: salesOrderItem.line_item_tax_breakdowns,
          discounts: salesOrderItem.discounts as SavedDiscount[] | undefined,
        };
      }

      const quotationItem = item as IQuotationLineItem;
      return {
        key: quotationItem.base_uuid,
        itemName: quotationItem.line_item?.inventory_item?.item_name || "",
        unitOfMeasure:
          quotationItem.unit_of_measure?.unit_abbreviation ||
          quotationItem.unit_of_measure?.unit_name ||
          "-",
        quantity: quotationItem.quantity,
        quantityValue: Number(quotationItem.quantity || 0),
        unitPrice: quotationItem.unit_price,
        lineTotal: quotationItem.line_total,
        line_item_tax_breakdowns: quotationItem.line_item_tax_breakdowns,
        discounts: quotationItem.discounts as SavedDiscount[] | undefined,
      };
    },
    [documentType],
  );

  const fetchPage = useCallback(
    async (pageNumber: number) => {
      if (!documentUuid || loadingRef.current) return;

      const generation = generationRef.current;
      loadingRef.current = true;
      setIsLoading(true);

      try {
        const response =
          documentType === "quotation"
            ? await QUOTATIONS_API.fetchQuotationLineItems({
                quotationBaseUuid: documentUuid,
                page: pageNumber,
              })
            : documentType === "sales_order"
              ? await PURCHASE_ORDERS_API.fetchPurchaseOrderLineItemsPage({
                  purchaseOrderUuid: documentUuid,
                  page: pageNumber,
                })
              : await INVOICES_API.fetchInvoiceLineItemsPage({
                  invoiceUuid: documentUuid,
                  page: pageNumber,
                });

        if (generation !== generationRef.current) return;

        const nextItems = response.results.map((item) => normalizeItem(item));
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
      } catch (error) {
        if (generation !== generationRef.current) return;
        setHasMore(false);
        setLoadError(error instanceof Error ? error.message : "Could not load the line items.");
      } finally {
        if (generation === generationRef.current) {
          loadingRef.current = false;
          setIsLoading(false);
        }
      }
    },
    [documentType, documentUuid, normalizeItem],
  );

  const resetAndLoad = useCallback(() => {
    generationRef.current += 1;
    loadingRef.current = false;
    setItems([]);
    setPage(0);
    setHasMore(true);
    setLoadError(null);
    setEditingKey(null);
    setDrafts([]);
    void fetchPage(1);
  }, [fetchPage]);

  useEffect(() => {
    resetAndLoad();
  }, [resetAndLoad]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (
      !container ||
      loadingRef.current ||
      !hasMore ||
      page === 0 ||
      container.scrollHeight > container.clientHeight
    ) {
      return;
    }

    void fetchPage(page + 1);
  }, [fetchPage, hasMore, items, page]);

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container || loadingRef.current || !hasMore) return;

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom <= 80) void fetchPage(page + 1);
  };

  const openEditor = (item: SalesDocumentLineItem) => {
    setDrafts(toDrafts(item.discounts));
    setSaveError(null);
    setEditingKey(String(item.key));
  };

  const closeEditor = () => {
    setEditingKey(null);
    setDrafts([]);
    setSaveError(null);
  };

  const updateDraft = (index: number, patch: Partial<DiscountDraft>) =>
    setDrafts((current) =>
      current.map((draft, draftIndex) => (draftIndex === index ? {...draft, ...patch} : draft)),
    );

  const applyDiscounts = async (item: SalesDocumentLineItem) => {
    if (!onSaveDiscounts) return;

    setSaving(true);
    setSaveError(null);

    try {
      await onSaveDiscounts({
        lineUuid: String(item.key),
        discounts: drafts.map((draft) => ({
          id: draft.id,
          discount_type: draft.discount_type,
          discount_value: draft.discount_value.trim(),
          description: draft.description.trim() || null,
        })),
      });
      closeEditor();
      resetAndLoad();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Could not save the discounts.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border">
      <div ref={scrollContainerRef} onScroll={handleScroll} className="max-h-[280px] overflow-auto">
        <Table className="w-full border-collapse">
          <TableHeader className="sticky top-0 z-10 bg-gray-800">
            <TableRow className="hover:bg-gray-800">
              <TableHead className="!text-white">#</TableHead>
              <TableHead className="!text-white">Item</TableHead>
              <TableHead className="!text-white">UOM</TableHead>
              <TableHead className="!text-white text-right">Qty</TableHead>
              {showFulfilmentColumns && (
                <>
                  <TableHead className="!text-white text-right">Billed</TableHead>
                  <TableHead className="!text-white text-right">Issued</TableHead>
                  <TableHead className="!text-white text-right">Pending</TableHead>
                </>
              )}
              <TableHead className="!text-white text-right">Unit Price</TableHead>
              <TableHead className="!text-white text-right">Net Amount</TableHead>
              <TableHead className="!text-white text-right">Discount</TableHead>
              <TableHead className="!text-white text-right">Taxes</TableHead>
              <TableHead className="!text-white text-right">Total</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {loadError && (
              <TableRow>
                <TableCell colSpan={columnCount} className="py-6 text-center text-destructive">
                  {loadError}
                </TableCell>
              </TableRow>
            )}

            {!isLoading && !loadError && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={columnCount} className="py-8 text-center text-muted-foreground">
                  No line items found
                </TableCell>
              </TableRow>
            )}

            {items.map((item, index) => {
              const breakdowns = item.line_item_tax_breakdowns ?? [];
              const isEditing = String(item.key) === editingKey;
              const view = buildLineView(item, isEditing ? drafts : null);
              const discountLabel =
                view.discount > 0 ? `${currency} ${formatCurrency(view.discount)}` : null;

              return (
                <TableRow key={item.key}>
                  <TableCell>{index + 1}</TableCell>
                  <TableCell>{item.itemName}</TableCell>
                  <TableCell>{item.unitOfMeasure || "-"}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  {showFulfilmentColumns && (
                    <>
                      <TableCell className="text-right">{item.quantityBilled ?? "-"}</TableCell>
                      <TableCell className="text-right">{item.quantityIssued ?? "-"}</TableCell>
                      <TableCell className="text-right">{item.quantityPending ?? "-"}</TableCell>
                    </>
                  )}
                  <TableCell className="text-right tabular-nums">
                    {currency} {formatCurrency(item.unitPrice)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {currency} {formatCurrency(view.netAmount)}
                  </TableCell>

                  <TableCell className="text-right tabular-nums">
                    {canEdit ? (
                      <button
                        type="button"
                        aria-label={
                          discountLabel
                            ? `Edit discounts for ${item.itemName}`
                            : `Add a discount to ${item.itemName}`
                        }
                        onClick={() => openEditor(item)}
                        className={
                          discountLabel
                            ? "font-semibold text-primary underline decoration-dotted underline-offset-4 hover:text-primary/80"
                            : "text-sm text-muted-foreground hover:text-primary"
                        }
                      >
                        {discountLabel ?? "+ Add"}
                      </button>
                    ) : (
                      (discountLabel ?? "-")
                    )}
                    {isEditing && (
                      <span className="block text-[10px] font-normal text-muted-foreground">
                        not saved yet
                      </span>
                    )}
                  </TableCell>

                  <TableCell className="text-right tabular-nums">
                    {breakdowns.length ? (
                      <Popover>
                        <PopoverTrigger asChild>
                          <button
                            type="button"
                            aria-label={`View tax breakdown for ${item.itemName}`}
                            className="font-semibold text-primary underline decoration-dotted underline-offset-4 hover:text-primary/80"
                          >
                            {currency} {formatCurrency(view.taxAmount)}
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
                            {breakdowns.map((breakdown) => (
                              <div
                                key={breakdown.base_uuid}
                                className="rounded-lg border p-2 text-sm"
                              >
                                {onTaxClick && breakdown.tax?.base_uuid ? (
                                  <button
                                    type="button"
                                    className="font-medium text-primary hover:underline"
                                    onClick={() => onTaxClick(breakdown.tax.base_uuid)}
                                  >
                                    {breakdown.tax.tax_name?.toUpperCase()}
                                  </button>
                                ) : (
                                  <span className="font-medium">
                                    {breakdown.tax?.tax_name?.toUpperCase() || "Applied tax"}
                                  </span>
                                )}
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {currency} {formatCurrency(breakdown.tax_amount)}
                                </p>
                              </div>
                            ))}
                          </div>
                        </PopoverContent>
                      </Popover>
                    ) : (
                      "-"
                    )}
                  </TableCell>

                  <TableCell className="text-right font-semibold tabular-nums">
                    {currency} {formatCurrency(view.grossAmount)}
                  </TableCell>
                </TableRow>
              );
            })}

            {isLoading && (
              <TableRow>
                <TableCell colSpan={columnCount} className="py-6 text-center text-muted-foreground">
                  {items.length ? "Loading more..." : "Loading line items..."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {canEdit && (
        <Dialog
          open={Boolean(editingItem)}
          onOpenChange={(open) => {
            if (!open && !saving) closeEditor();
          }}
        >
          <DialogContent
            className="max-h-[90vh] overflow-y-auto p-5 sm:max-w-3xl"
            onInteractOutside={(event) => event.preventDefault()}
          >
            {editingItem && (
              <DiscountEditor
                currency={currency}
                item={editingItem}
                drafts={drafts}
                calculation={editingCalculation}
                saving={saving}
                saveError={saveError}
                onChange={updateDraft}
                onAdd={() => setDrafts((current) => [...current, emptyDraft()])}
                onRemove={(removeIndex) =>
                  setDrafts((current) => current.filter((_, i) => i !== removeIndex))
                }
                onCancel={closeEditor}
                onApply={() => void applyDiscounts(editingItem)}
              />
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
