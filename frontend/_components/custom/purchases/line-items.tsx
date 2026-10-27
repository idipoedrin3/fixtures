"use client";

import {Icon} from "@iconify/react";
import {useCallback, useEffect, useRef, useState} from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {VENDORS_API, ITEM_UNIT_OF_MEASURE_API} from "#/_api/api.helpers";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {IVendor, IItemUnitOfMeasure} from "#/_types/api.types";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import {toast} from "sonner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type UnitPrice = {
  unit_of_measure: string;
  price: string;
  minimum_order_qty: number;
};

export type PreferredVendorRow = {
  vendor: string;
  unit_prices: UnitPrice[];
};

type FlatRow = {
  id: string;
  parent_id: string | null;
  vendor: string;
  vendorData?: IVendor;
  vendor_name?: string;
  vendor_type?: string;
  unit_of_measure: string;
  unit_of_measure_name?: string;
  price: string;
  minimum_order_qty: number;
};

type Props = {
  onVendorsChange?: (vendors: PreferredVendorRow[]) => void;
  onValidationChange?: (isValid: boolean) => void;
  initialVendors?: PreferredVendorRow[];
  readonly?: boolean;
  availableUnits?: {unit_of_measure: string; unit_name?: string}[];
  singleVendorMode?: boolean;
};

export default function PreferredVendorsInput({
  onVendorsChange,
  onValidationChange,
  initialVendors = [],
  readonly = false,
  availableUnits,
  singleVendorMode = false,
}: Props) {
  const [rows, setRows] = useState<FlatRow[]>(() =>
    singleVendorMode
      ? [
          {
            id: `row-${Date.now()}-${Math.random()}`,
            parent_id: null,
            vendor: "",
            unit_of_measure: "",
            price: "",
            minimum_order_qty: 0,
          },
        ]
      : [],
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const touchedFields = useRef(new Set<string>());
  const hasSeeded = useRef(false);

  useEffect(() => {
    if (hasSeeded.current) return;
    if (initialVendors.length === 0) return;
    if (!availableUnits || availableUnits.length === 0) return;

    hasSeeded.current = true;

    const seeded: FlatRow[] = (initialVendors as any[]).flatMap((v) => {
      const ups = v.unit_prices && v.unit_prices.length > 0 ? v.unit_prices : [null];
      const parentId = `row-${Date.now()}-${Math.random()}`;
      return ups.map((up: any, i: number) => ({
        id: i === 0 ? parentId : `row-${Date.now()}-${Math.random()}-${i}`,
        parent_id: i === 0 ? null : parentId,
        vendor: v.vendor,
        vendor_name: v.vendorData?.vendor_name ?? "",
        vendor_type: v.vendorData?.vendor_type ?? "",
        vendorData: v.vendorData,
        unit_of_measure: up?.unit_of_measure ?? "",
        price: up?.price ?? "",
        minimum_order_qty: up?.minimum_order_qty ?? 0,
      }));
    });
    setRows(seeded);
  }, [availableUnits]);

  useEffect(() => {
    if (!onVendorsChange) return;

    const vendorMap = new Map<string, UnitPrice[]>();
    rows.forEach((row) => {
      if (row.vendor) {
        if (!vendorMap.has(row.vendor)) vendorMap.set(row.vendor, []);
        if (row.unit_of_measure) {
          vendorMap.get(row.vendor)!.push({
            unit_of_measure: row.unit_of_measure,
            price: row.price,
            minimum_order_qty: row.minimum_order_qty,
          });
        }
      }
    });

    const grouped: PreferredVendorRow[] = Array.from(vendorMap.entries()).map(
      ([vendor, unit_prices]) => ({vendor, unit_prices}),
    );

    onVendorsChange(grouped);
  }, [rows, onVendorsChange]);

  const validateRows = useCallback(() => {
    const allErrors: Record<string, string> = {};
    const submittedUnits = new Set<string>();

    rows.forEach((row, index) => {
      if (singleVendorMode) {
        if (index === 0 && !row.vendor) allErrors["vendor_0"] = "Vendor is required";
      } else if (row.parent_id === null && !row.vendor) {
        allErrors[`${row.id}:vendor`] = "Vendor is required";
      }

      if (!row.unit_of_measure) {
        allErrors[`${row.id}:unit_of_measure`] = "Unit of measure is required";
      }
      if (!row.price || parseFloat(row.price) <= 0) {
        allErrors[`${row.id}:price`] = "Price must be greater than 0";
      }
      if (row.minimum_order_qty < 0) {
        allErrors[`${row.id}:min_qty`] = "Minimum order quantity cannot be negative";
      }

      const unitKey = `${row.vendor}__${row.unit_of_measure}`;
      if (row.unit_of_measure && submittedUnits.has(unitKey)) {
        allErrors[`${row.id}:unit_of_measure`] = "This unit has already been added for the vendor";
      }
      submittedUnits.add(unitKey);
    });

    const visibleErrors = Object.fromEntries(
      Object.entries(allErrors).filter(([field]) => touchedFields.current.has(field)),
    );

    setErrors(visibleErrors);
    const isValid = rows.length > 0 && Object.keys(allErrors).length === 0;
    onValidationChange?.(isValid);
    return isValid;
  }, [rows, onValidationChange, singleVendorMode]);

  const updateVendor = useCallback((vendor: IVendor) => {
    touchedFields.current.add("vendor_0");
    setRows((prev) =>
      prev.map((row) => ({
        ...row,
        vendor: vendor.base_uuid,
        vendor_name: vendor.vendor_name,
        vendor_type: vendor.vendor_type || "",
        vendorData: vendor,
      })),
    );
    setErrors({});
  }, []);

  useEffect(() => {
    validateRows();
  }, [rows, validateRows]);

  const updateRow = useCallback((id: string, fields: Partial<FlatRow>) => {
    setRows((prev) => {
      const current = prev.find((r) => r.id === id);
      if (!current) return prev;

      if ("unit_of_measure" in fields && fields.unit_of_measure !== current.unit_of_measure) {
        touchedFields.current.add(`${id}:unit_of_measure`);
      }
      if ("price" in fields && fields.price !== current.price) {
        touchedFields.current.add(`${id}:price`);
      }
      if ("minimum_order_qty" in fields && fields.minimum_order_qty !== current.minimum_order_qty) {
        touchedFields.current.add(`${id}:min_qty`);
      }
      if ("vendor" in fields && fields.vendor !== current.vendor) {
        touchedFields.current.add(`${id}:vendor`);
      }

      const updated = prev.map((r) => (r.id === id ? {...r, ...fields} : r));

      if ("vendor" in fields) {
        const target = updated.find((r) => r.id === id);
        if (target) {
          for (let i = 0; i < updated.length; i++) {
            if (updated[i].parent_id === id) {
              updated[i] = {
                ...updated[i],
                vendor: target.vendor,
                vendor_name: target.vendor_name,
                vendor_type: target.vendor_type,
                vendorData: target.vendorData,
              };
            }
          }
        }
      }
      return updated;
    });
    setErrors({});
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => {
      const selectedVendor = singleVendorMode ? prev[0] : undefined;
      return [
        ...prev,
        {
          id: `row-${Date.now()}-${Math.random()}`,
          parent_id: null,
          vendor: selectedVendor?.vendor ?? "",
          vendor_name: selectedVendor?.vendor_name,
          vendor_type: selectedVendor?.vendor_type,
          vendorData: selectedVendor?.vendorData,
          unit_of_measure: "",
          price: "",
          minimum_order_qty: 0,
        },
      ];
    });
  }, [singleVendorMode]);

  const addChildRow = useCallback((parentId: string) => {
    setRows((prev) => {
      const parent = prev.find((r) => r.id === parentId);
      if (!parent?.vendor) {
        toast.error("Please select a vendor first before adding more units");
        return prev;
      }
      const child: FlatRow = {
        id: `row-${Date.now()}-${Math.random()}`,
        parent_id: parentId,
        vendor: parent.vendor,
        vendor_name: parent.vendor_name,
        vendor_type: parent.vendor_type,
        vendorData: parent.vendorData,
        unit_of_measure: "",
        price: "",
        minimum_order_qty: 0,
      };
      const lastIdx = prev.reduce(
        (acc, r, i) => (r.id === parentId || r.parent_id === parentId ? i : acc),
        -1,
      );
      const updated = [...prev];
      updated.splice(lastIdx + 1, 0, child);
      return updated;
    });
  }, []);

  const removeRow = useCallback(
    (id: string) => {
      setRows((prev) => {
        if (singleVendorMode && prev.length === 1) {
          const only = prev[0];
          touchedFields.current.delete(`${only.id}:unit_of_measure`);
          touchedFields.current.delete(`${only.id}:price`);
          touchedFields.current.delete(`${only.id}:min_qty`);
          return [{...only, unit_of_measure: "", price: "", minimum_order_qty: 0}];
        }

        const target = prev.find((r) => r.id === id);
        const toRemove =
          !singleVendorMode && target?.parent_id === null
            ? prev.filter((r) => r.id === id || r.parent_id === id)
            : prev.filter((r) => r.id === id);

        toRemove.forEach((r) => {
          touchedFields.current.delete(`${r.id}:vendor`);
          touchedFields.current.delete(`${r.id}:unit_of_measure`);
          touchedFields.current.delete(`${r.id}:price`);
          touchedFields.current.delete(`${r.id}:min_qty`);
        });

        const removeIds = new Set(toRemove.map((r) => r.id));
        return prev.filter((r) => !removeIds.has(r.id));
      });
      setErrors({});
    },
    [singleVendorMode],
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h4 className="text-lg font-semibold text-gray-900">
          {singleVendorMode ? "Vendor Pricing" : "Preferred Vendors"}
        </h4>
        <p className="text-sm text-gray-600 leading-relaxed">
          {singleVendorMode
            ? "Select a vendor, then add the prices offered for each unit of measure."
            : "Add vendors you prefer to purchase this item from, along with unit pricing details."}
        </p>
      </div>

      {singleVendorMode && (
        <div className="rounded-lg border bg-muted/20 p-4">
          <div className="max-w-xl space-y-2">
            <label className="text-sm font-medium">
              Vendor <span className="text-destructive">*</span>
            </label>
            <PaginatedSearchableSelect<IVendor>
              fetchFirstPage={VENDORS_API.fetchVendors}
              fetchFromUrl={VENDORS_API.fetchVendorsFromUrl}
              idKey="base_uuid"
              valueKey="base_uuid"
              labelKey="vendor_name"
              labelDescKey="vendor_type"
              placeholder="Select vendor"
              searchPlaceholder="Search vendors..."
              emptyMessage="No vendors found"
              value={rows[0]?.vendor || undefined}
              initialData={rows[0]?.vendorData ? [rows[0].vendorData] : []}
              onValueChange={() => {}}
              onItemSelected={(vendor) => vendor && updateVendor(vendor)}
              disabled={readonly}
            />
            {rows[0]?.vendor_type && (
              <p className="text-xs capitalize text-muted-foreground">
                Vendor type: {rows[0].vendor_type}
              </p>
            )}
            {errors.vendor_0 && <p className="text-xs text-red-600">{errors.vendor_0}</p>}
          </div>
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead className="w-12">#</TableHead>
              {!singleVendorMode && (
                <>
                  <TableHead className="min-w-[200px]">Vendor *</TableHead>
                  <TableHead className="w-32">Vendor Type</TableHead>
                </>
              )}
              <TableHead className="min-w-[180px]">Unit of Measure *</TableHead>
              <TableHead className="w-36">Price *</TableHead>
              <TableHead className="w-36">Min Order Qty</TableHead>
              {!readonly && <TableHead className="w-12" />}
            </TableRow>
          </TableHeader>

          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No vendors added. Click &quot;Add Row&quot; to get started.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row, index) => (
                <TableRow key={row.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-muted-foreground">{index + 1}</TableCell>

                  {/* Vendor */}
                  {!singleVendorMode && (
                    <TableCell>
                      {row.parent_id === null ? (
                        <div className="space-y-1">
                          <PaginatedSearchableSelect<IVendor>
                            fetchFirstPage={VENDORS_API.fetchVendors}
                            fetchFromUrl={VENDORS_API.fetchVendorsFromUrl}
                            idKey="base_uuid"
                            valueKey="base_uuid"
                            labelKey="vendor_name"
                            labelDescKey="vendor_type"
                            placeholder="Select vendor"
                            searchPlaceholder="Search vendors..."
                            emptyMessage="No vendors found"
                            value={row.vendor || undefined}
                            initialData={row.vendorData ? [row.vendorData] : []}
                            onValueChange={() => {}}
                            onItemSelected={(vendor) => {
                              if (vendor) {
                                updateRow(row.id, {
                                  vendor: vendor.base_uuid,
                                  vendor_name: vendor.vendor_name,
                                  vendor_type: vendor.vendor_type || "",
                                  vendorData: vendor,
                                });
                              }
                            }}
                            disabled={readonly}
                          />
                          {errors[`${row.id}:vendor`] && (
                            <p className="text-xs text-red-600">{errors[`${row.id}:vendor`]}</p>
                          )}
                        </div>
                      ) : (
                        <div className="flex h-9 items-center pl-2 text-sm text-muted-foreground" />
                      )}
                    </TableCell>
                  )}

                  {/* Vendor Type */}
                  {!singleVendorMode && (
                    <TableCell>
                      {row.parent_id === null && (
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm text-muted-foreground capitalize">
                            {row.vendor_type || "-"}
                          </span>
                          {!readonly && (
                            <Button
                              type="button"
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 flex-shrink-0 pl-6"
                              onClick={() => addChildRow(row.id)}
                              title="Add another unit for this vendor"
                            >
                              <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      )}
                    </TableCell>
                  )}

                  {/* Unit of Measure */}
                  <TableCell>
                    <div className="space-y-1">
                      {availableUnits && availableUnits.length > 0 ? (
                        <Select
                          value={row.unit_of_measure || undefined}
                          onValueChange={(value) => updateRow(row.id, {unit_of_measure: value})}
                          disabled={readonly}
                        >
                          <SelectTrigger
                            className={`h-9 rounded-md ${
                              errors[`${row.id}:unit_of_measure`]
                                ? "border-red-500"
                                : "border-input"
                            }`}
                          >
                            <SelectValue placeholder="Select unit..." />
                          </SelectTrigger>
                          <SelectContent position="popper" className="z-[1000]">
                            {availableUnits.map((u) => (
                              <SelectItem key={u.unit_of_measure} value={u.unit_of_measure}>
                                {u.unit_name || u.unit_of_measure}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <PaginatedSearchableSelect<IItemUnitOfMeasure>
                          fetchFirstPage={({search}: {search: string}) =>
                            ITEM_UNIT_OF_MEASURE_API.fetchUnitsOfMeasure({search})
                          }
                          fetchFromUrl={({url}: {url: string}) =>
                            ITEM_UNIT_OF_MEASURE_API.fetchUnitsOfMeasureFromUrl({url})
                          }
                          idKey="base_uuid"
                          valueKey="base_uuid"
                          labelKey="unit_name"
                          labelDescKey="unit_abbreviation"
                          placeholder="Select unit"
                          searchPlaceholder="Search units..."
                          emptyMessage="No units found"
                          value={row.unit_of_measure || undefined}
                          onValueChange={(values) =>
                            updateRow(row.id, {unit_of_measure: values[0] || ""})
                          }
                          disabled={readonly}
                        />
                      )}
                      {errors[`${row.id}:unit_of_measure`] && (
                        <p className="text-xs text-red-600">
                          {errors[`${row.id}:unit_of_measure`]}
                        </p>
                      )}
                    </div>
                  </TableCell>

                  {/* Price */}
                  <TableCell>
                    <div className="space-y-1">
                      <FormattedNumberInput
                        value={row.price}
                        onValueChange={(val) => updateRow(row.id, {price: val?.toString() ?? ""})}
                        placeholder="0.00"
                        disabled={readonly}
                        className={errors[`${row.id}:price`] ? "border-red-500" : ""}
                      />
                      {errors[`${row.id}:price`] && (
                        <p className="text-xs text-red-600">{errors[`${row.id}:price`]}</p>
                      )}
                    </div>
                  </TableCell>

                  {/* Min Order Qty */}
                  <TableCell>
                    <div className="space-y-1">
                      <Input
                        type="number"
                        min="0"
                        step="1"
                        placeholder="0"
                        value={row.minimum_order_qty}
                        onChange={(e) =>
                          updateRow(row.id, {minimum_order_qty: parseInt(e.target.value) || 0})
                        }
                        disabled={readonly}
                        className={errors[`${row.id}:min_qty`] ? "border-red-500" : ""}
                      />
                      {errors[`${row.id}:min_qty`] && (
                        <p className="text-xs text-red-600">{errors[`${row.id}:min_qty`]}</p>
                      )}
                    </div>
                  </TableCell>

                  {/* Remove */}
                  {!readonly && (
                    <TableCell>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeRow(row.id)}
                        className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                        title="Remove row"
                      >
                        <Icon icon="mdi:delete-outline" className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>

          <TableFooter>
            <TableRow>
              <TableCell colSpan={7}>
                {!readonly && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addRow}
                    className="flex items-center gap-2"
                  >
                    <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
                    {singleVendorMode ? "Add Unit Price" : "Add Row"}
                  </Button>
                )}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>
    </div>
  );
}
