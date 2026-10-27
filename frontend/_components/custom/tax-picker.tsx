import {TAXES_API} from "#/_api/api.helpers";
import {ITax} from "#/_types/api.types";
import {Button} from "@/components/ui/button";
import {Label} from "@/components/ui/label";
import {Switch} from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {PlusIcon, X} from "lucide-react";
import {useEffect, useState} from "react";
import GenericModal from "../common/modals/custom-modal";
import PaginatedSearchableSelect from "./paginated-searchable-select";

export type IInvoiceTax = {
  tax: string;
  is_inclusive: boolean;
  tax_name: string;
};

type Props = {
  initialData?: IInvoiceTax[];
  onChange(taxes: IInvoiceTax[]): void;
};

export default function TaxPicker({onChange, initialData}: Props) {
  const [formData, setFormData] = useState<IInvoiceTax[]>([]);

  const [taxModal, setTaxModal] = useState(false);

  const addTaxEntry = (tax: IInvoiceTax) => {
    if (!tax.tax) return;
    setFormData((prev) => [...prev, tax]);
  };

  const removeTaxEntry = (index: number) => {
    const updatedTaxes = [...formData];

    updatedTaxes.splice(index, 1);
    setFormData(() => updatedTaxes);
  };

  useEffect(() => {
    if (!initialData || !Array.isArray(initialData)) return;
    setFormData(() => initialData);
  }, [initialData]);

  useEffect(() => {
    onChange?.call(undefined, formData);
  }, [formData]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div>
          <Label>Applicable Taxes</Label>
          <p className="text-xs md:text-sm opacity-50">
            Select or enter the tax rates that should automatically apply.
          </p>
        </div>
      </div>

      <Table className="mt-3">
        <TableHeader>
          <TableRow>
            <TableHead>#</TableHead>
            <TableHead>Tax</TableHead>
            <TableHead>Inclusive</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {formData.length ? (
            formData.map((t, i) => (
              <TableRow key={i}>
                <TableCell>{i + 1}</TableCell>
                <TableCell>{t.tax_name}</TableCell>
                <TableCell>{t.is_inclusive ? "Yes" : "No"}</TableCell>
                <TableCell>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => removeTaxEntry(i)}
                    className="border-0 text-red-500 hover:text-red-500"
                  >
                    <X className="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4}>
                <div className="p-6 lg:py-10 text-center text-gray-500">
                  <p className="text-sm">No default invoice taxes added yet.</p>
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell colSpan={4}>
              <Button type="button" size="sm" variant="outline" onClick={() => setTaxModal(true)}>
                <PlusIcon className="mr-1" /> Add Tax
              </Button>
            </TableCell>
          </TableRow>
        </TableFooter>
      </Table>

      {/* Tax Modal */}
      <GenericModal<IInvoiceTax>
        initialData={{is_inclusive: true, tax: "", tax_name: ""}}
        isOpen={taxModal}
        onClose={() => setTaxModal(false)}
        onConfirm={addTaxEntry}
        title="Add Taxes to Apply"
        confirmText="Add Tax"
        cancelText="Cancel"
      >
        {({formData, setFormData}) => (
          <div className="grid grid-cols-1 gap-4">
            <div>
              <Label>Tax *</Label>
              <PaginatedSearchableSelect<ITax>
                fetchFirstPage={TAXES_API.fetchTaxes}
                fetchFromUrl={TAXES_API.fetchTaxesFromUrl}
                idKey="id"
                valueKey="id"
                labelKey="tax_name"
                labelDescKey="tax_description"
                placeholder="Select tax"
                onValueChange={(list) => setFormData((prev) => ({...prev, tax: list[0]}))}
                onItemSelected={(item) =>
                  setFormData((prev) => ({...prev, tax_name: item?.tax_name ?? "-"}))
                }
              />
            </div>

            <div className="flex items-center gap-4">
              <Label htmlFor="tax-inc">Is tax inclusive?</Label>
              <Switch
                id="tax-inc"
                checked={formData.is_inclusive}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({...prev, is_inclusive: checked}))
                }
              />
            </div>
          </div>
        )}
      </GenericModal>
    </div>
  );
}
