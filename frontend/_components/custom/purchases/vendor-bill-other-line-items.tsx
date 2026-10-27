"use client";

import FormattedNumberInput from "#/_components/common/inputs/formatted-number-input";
import {TAXES_API} from "#/_api/api.helpers";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Switch} from "@/components/ui/switch";
import {Icon} from "@iconify/react";
import React from "react";
import {formatCurrency} from "#/_lib/utils";

export type BillOtherLineItem = {
  line_item: string;
  unit_of_measure: string;
  quantity: number;
  unit_price: string;
  line_total?: string;
  applicable_taxes?: {tax: number; is_inclusive: boolean}[];
};

type Props = {
  value: BillOtherLineItem[];
  onChange: (items: BillOtherLineItem[]) => void;
  withTaxes?: boolean;
};

export default function VendorBillOtherLineItems({value, onChange, withTaxes = true}: Props) {
  const calculateLineTotal = (quantity: number, unitPrice: string) => {
    const clean = unitPrice.replace(/,/g, "");
    return (Number(quantity) * parseFloat(clean || "0")).toFixed(2);
  };

  const addRow = () => {
    onChange([
      ...value,
      {
        line_item: "",
        unit_of_measure: "",
        quantity: 1,
        unit_price: "0",
        line_total: "0",
        applicable_taxes: [],
      },
    ]);
  };

  const removeRow = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const updateRow = (index: number, fields: Partial<BillOtherLineItem>) => {
    const updated = [...value];
    updated[index] = {...updated[index], ...fields};
    if (fields.quantity !== undefined || fields.unit_price !== undefined) {
      updated[index].line_total = calculateLineTotal(
        updated[index].quantity,
        updated[index].unit_price,
      );
    }
    onChange(updated);
  };

  const addTax = (index: number) => {
    const updated = [...value];
    updated[index] = {
      ...updated[index],
      applicable_taxes: [...(updated[index].applicable_taxes ?? []), {tax: 0, is_inclusive: false}],
    };
    onChange(updated);
  };

  const removeTax = (rowIndex: number, taxIndex: number) => {
    const updated = [...value];
    updated[rowIndex] = {
      ...updated[rowIndex],
      applicable_taxes: (updated[rowIndex].applicable_taxes ?? []).filter(
        (_, ti) => ti !== taxIndex,
      ),
    };
    onChange(updated);
  };

  const updateTax = (rowIndex: number, taxIndex: number, field: string, val: any) => {
    const updated = [...value];
    const taxes = (updated[rowIndex].applicable_taxes ?? []).map((tax, ti) =>
      ti !== taxIndex ? tax : {...tax, [field]: val},
    );
    updated[rowIndex] = {...updated[rowIndex], applicable_taxes: taxes};
    onChange(updated);
  };

  const grandTotal = value
    .reduce((sum, item) => {
      const price = parseFloat((item.unit_price ?? "0").toString().replace(/,/g, "")) || 0;
      return sum + Number(item.quantity) * price;
    }, 0)
    .toFixed(2);
  return (
    <div className="border rounded-lg overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 w-8">#</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 min-w-[200px]">
              Item Description
            </th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 w-32">UOM</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 w-24">Qty</th>
            <th className="px-4 py-3 text-left text-sm font-medium text-gray-500 w-36">
              Unit Price
            </th>
            <th className="px-4 py-3 text-right text-sm font-medium text-gray-500 w-36">Total</th>
            <th className="px-4 py-3 w-24"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {value.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground text-sm">
                No items added yet. Click "Add Row" to get started.
              </td>
            </tr>
          ) : (
            value.map((row, index) => (
              <React.Fragment key={index}>
                <tr>
                  <td className="px-4 py-3 text-sm text-gray-500">{index + 1}</td>
                  <td className="px-4 py-3">
                    <Input
                      placeholder="Enter item description"
                      value={row.line_item}
                      onChange={(e) => updateRow(index, {line_item: e.target.value})}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Input
                      placeholder="e.g. pcs, kg"
                      value={row.unit_of_measure}
                      onChange={(e) => updateRow(index, {unit_of_measure: e.target.value})}
                    />
                  </td>
                  <td className="px-4 py-3">
                    <Input
                      type="number"
                      min="1"
                      value={row.quantity}
                      onChange={(e) => updateRow(index, {quantity: parseInt(e.target.value) || 1})}
                      className="text-right"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <FormattedNumberInput
                      value={row.unit_price}
                      onValueChange={(val) =>
                        updateRow(index, {unit_price: val.toString().replace(/,/g, "")})
                      }
                      className="text-right"
                    />
                  </td>
                  <td className="px-4 py-3 text-right text-sm font-medium">
                    {formatCurrency(
                      (
                        Number(row.quantity) *
                        parseFloat((row.unit_price ?? "0").toString().replace(/,/g, ""))
                      ).toFixed(2),
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {withTaxes && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => addTax(index)}
                          className="h-8 px-2 text-xs text-muted-foreground hover:text-primary hover:bg-muted gap-1"
                        >
                          <Icon icon="hugeicons:plus-sign" className="w-3 h-3" />
                          Tax
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeRow(index)}
                        className="text-red-500 hover:text-red-500 hover:bg-red-50"
                      >
                        <Icon icon="hugeicons:delete-02" className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>

                {/* Tax sub-rows */}
                {withTaxes &&
                  (row.applicable_taxes ?? []).map((tax, taxIndex) => (
                    <tr key={`tax-${index}-${taxIndex}`}>
                      <td />
                      <td colSpan={4} className="px-4 py-1">
                        <div className="ml-6 flex items-center gap-3 bg-muted/40 rounded-lg px-3 py-2 border-l-2 border-primary/30">
                          <div className="flex-1">
                            <PaginatedSearchableSelect
                              placeholder="Select tax"
                              searchPlaceholder="Search taxes..."
                              emptyMessage="No taxes found"
                              fetchFirstPage={TAXES_API.fetchTaxes}
                              fetchFromUrl={TAXES_API.fetchTaxesFromUrl}
                              idKey="base_uuid"
                              valueKey="base_uuid"
                              labelKey="tax_name"
                              onValueChange={(list) =>
                                updateTax(index, taxIndex, "tax", list[0] || 0)
                              }
                            />
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-xs text-muted-foreground whitespace-nowrap">
                              Inclusive
                            </span>
                            <Switch
                              checked={tax.is_inclusive}
                              onCheckedChange={(checked) =>
                                updateTax(index, taxIndex, "is_inclusive", checked)
                              }
                            />
                          </div>
                        </div>
                      </td>
                      <td />
                      <td className="px-4 py-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeTax(index, taxIndex)}
                          className="h-8 w-8 text-red-500 hover:text-red-500 hover:bg-red-50"
                        >
                          <Icon icon="hugeicons:delete-02" className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
              </React.Fragment>
            ))
          )}
        </tbody>
        <tfoot>
          <tr className="bg-gray-50">
            <td colSpan={4} className="px-4 py-3">
              <Button type="button" variant="outline" size="sm" onClick={addRow}>
                <Icon icon="hugeicons:plus-sign" className="w-4 h-4 mr-2" />
                Add Row
              </Button>
            </td>
            <td className="px-4 py-3 text-right text-sm font-semibold">Grand Total</td>
            <td className="px-4 py-3 text-right text-sm font-bold">{formatCurrency(grandTotal)}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
