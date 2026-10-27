"use client";

import {useEffect, useState} from "react";
import {Icon} from "@iconify/react";
import {toast} from "sonner";

import InventoryItemSelect, {InventorySelectableItem} from "./inventory-item-select";

import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {IInventoryItem} from "#/_types/api.types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface AllocatedProduct {
  id?: string | number;
  item_name?: string;
  quantity_on_hand?: number;
  allocatedQuantity: number;
  base_uuid?: string;
  unit_of_measure_options?: Array<{
    uuid: string;
    name: string;
    abbreviation?: string;
    is_base?: boolean;
    selling_price?: number;
  }>;
  selected_uom_uuid?: string;
  selected_uom_name?: string;
}

interface ProductsAllocationInputProps {
  initialProducts: AllocatedProduct[];
  onProductsChange(products: AllocatedProduct[]): void;
  title?: string;
  description?: string;
  disabled?: boolean;
  branchFilter?: string;
  mapItemToProduct?: (item: any) => AllocatedProduct;
}

export default function ProductsAllocationInput({
  initialProducts,
  onProductsChange,
  title = "Products",
  description = "Select products to allocate and specify quantities.",
  disabled,
  branchFilter,
  mapItemToProduct,
}: ProductsAllocationInputProps) {
  const [products, setProducts] = useState<AllocatedProduct[]>(initialProducts || []);

  useEffect(() => {
    onProductsChange(products);
  }, [products, onProductsChange]);

  useEffect(() => {
    if (branchFilter && !initialProducts?.length) {
      setProducts([]);
    }
  }, [branchFilter]);

  const handleAddRow = () => {
    setProducts((prev) => [
      ...prev,
      {id: undefined, item_name: "", quantity_on_hand: 0, allocatedQuantity: 0},
    ]);
  };

  const handleSelectProduct = (index: number, item: any) => {
    if (!item) return;

    if (mapItemToProduct) {
      const mapped = mapItemToProduct(item);
      const exists = products.some((p, i) => i !== index && p.base_uuid === mapped.base_uuid);
      if (exists) {
        toast.warning("This product is already added.");
        return;
      }
      if (!mapped.unit_of_measure_options?.length) {
        toast.error("This product has no unit of measure configured.");
        return;
      }
      setProducts((prev) => prev.map((p, i) => (i === index ? mapped : p)));
      return;
    }

    const product = item as IInventoryItem;
    const exists = products.some((p, i) => i !== index && p.base_uuid === product.base_uuid);
    if (exists) {
      toast.warning("This product with the selected UOM is already added.");
      return;
    }

    const uomOptions = (product.inventory_item_units_of_measure || []).map((uom) => ({
      uuid: uom?.base_uuid || "",
      name: uom.unit_of_measure?.unit_name || "Unknown",
      abbreviation: uom.unit_of_measure?.unit_abbreviation || "",
      is_base: uom.is_base_unit_of_measure ?? false,
      selling_price: Number(uom.selling_price) || 0,
    }));

    const defaultUom = uomOptions.find((u) => u.is_base === true) || uomOptions[0];
    if (!defaultUom) {
      toast.error("This product has no unit of measure configured.");
      return;
    }

    setProducts((prev) =>
      prev.map((p, i) =>
        i === index
          ? {
              id: product.id,
              base_uuid: product.base_uuid,
              item_name: product.item_name,
              quantity_on_hand: product.quantity_on_hand,
              allocatedQuantity: 1,
              unit_of_measure_options: uomOptions,
              selected_uom_uuid: defaultUom.uuid,
              selected_uom_name: defaultUom.name,
            }
          : p,
      ),
    );
  };

  const handleQuantityChange = (index: number, value: string) => {
    const num = Number(value);

    setProducts((prev) =>
      prev.map((p, i) => {
        if (i !== index) return p;

        // Prevent non-numeric or negative input
        if (isNaN(num) || num < 0) {
          return {...p, allocatedQuantity: 0};
        }

        // Constrain to available quantity if product selected
        const constrained = Math.min(num, p.quantity_on_hand ?? 0);

        return {...p, allocatedQuantity: constrained};
      }),
    );
  };

  /** Increment/decrement helpers */
  const increment = (index: number) => {
    setProducts((prev) =>
      prev.map((p, i) =>
        i === index && p.allocatedQuantity < (p.quantity_on_hand || 0)
          ? {...p, allocatedQuantity: p.allocatedQuantity + 1}
          : p,
      ),
    );
  };

  const decrement = (index: number) => {
    setProducts((prev) =>
      prev.map((p, i) =>
        i === index && p.allocatedQuantity > 0
          ? {...p, allocatedQuantity: p.allocatedQuantity - 1}
          : p,
      ),
    );
  };

  /** Remove a row */
  const removeRow = (index: number) => {
    setProducts((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div title={title} className="overflow-x-auto mb-4">
      <div className="w-full">
        {/* Products Table */}
        <Table className="w-full">
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead>#</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>UOM</TableHead>
              <TableHead className="text-center">Available Stock</TableHead>
              <TableHead className="text-right">Allocated Quantity</TableHead>
              <TableHead className="text-right">&nbsp;</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {products.map((product, index) => (
              <TableRow
                key={product.base_uuid || index}
                className="hover:bg-background hover:shadow-sm"
              >
                <TableCell>{index + 1}</TableCell>
                {/* Product Selector inside cell */}
                <TableCell className="min-w-[250px]">
                  <InventoryItemSelect
                    key={branchFilter}
                    level={branchFilter ? "branch" : "institution"}
                    branchBaseUuid={branchFilter}
                    itemType="GOODS"
                    placeholder={product.item_name || "Search product"}
                    searchPlaceholder="Search inventory items..."
                    emptyMessage="No products found"
                    disabled={disabled}
                    onItemSelected={(item: InventorySelectableItem | null) =>
                      handleSelectProduct(index, item)
                    }
                    onValueChange={() => {}}
                  />
                </TableCell>

                {/* UOM cell */}
                <TableCell className="min-w-[180px]">
                  {product.unit_of_measure_options && product.unit_of_measure_options.length > 0 ? (
                    <Select
                      key={`${product.base_uuid}-${product.selected_uom_uuid}`}
                      value={product.selected_uom_uuid || ""}
                      onValueChange={(uomUuid) => {
                        const selected = product.unit_of_measure_options?.find(
                          (u) => u.uuid === uomUuid,
                        );
                        setProducts((prev) =>
                          prev.map((p, i) =>
                            i === index
                              ? {
                                  ...p,
                                  selected_uom_uuid: uomUuid,
                                  selected_uom_name: selected?.name || "",
                                }
                              : p,
                          ),
                        );
                      }}
                      disabled={!product.item_name}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue>{product.selected_uom_name || "Select UOM"}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {product.unit_of_measure_options.map((uom) => (
                          <SelectItem key={uom.uuid} value={uom.uuid}>
                            {uom.name} {uom.abbreviation && `(${uom.abbreviation})`}
                            {uom.is_base && " (Base)"}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-sm text-muted-foreground pl-3">-</span>
                  )}
                </TableCell>
                <TableCell className="text-center">{product.quantity_on_hand ?? "-"}</TableCell>
                <TableCell className="text-right">
                  <Input
                    className="align-middle text-center "
                    type="number"
                    value={product.allocatedQuantity || ""}
                    placeholder="0"
                    min="0"
                    max={product.quantity_on_hand || 0}
                    onChange={(e) => handleQuantityChange(index, e.target.value)}
                    disabled={!product.item_name}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    type="button"
                    className="text-red-500 hover:text-red-600 size-7 rounded-full bg-transparent hover:bg-red-200"
                    onClick={() => removeRow(index)}
                  >
                    <Icon icon="hugeicons:cancel-01" className="text-red-500 size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}

            {/* Add new row button */}
            <TableRow>
              <TableCell colSpan={6}>
                <div className="flex justify-start mt-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleAddRow}
                    className="flex items-center gap-2"
                    disabled={disabled}
                  >
                    <Icon icon="hugeicons:add-01" className="h-4 w-4" />
                    Add Product
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>

          {products.length > 0 && (
            <TableFooter>
              <TableRow>
                <TableCell colSpan={6}>
                  <div className="flex justify-end text-sm text-gray-600">
                    Total Products: {products.length}
                  </div>
                </TableCell>
              </TableRow>
            </TableFooter>
          )}
        </Table>
      </div>
    </div>
  );
}
