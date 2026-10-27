"use client";

import type React from "react";
import type {IItemUnitOfMeasure, IItemUnitOfMeasureFormData} from "#/_types/api.types";

import {useState, useEffect} from "react";
import {useSelector} from "react-redux";
import {toast} from "sonner";

import {Dialog, DialogContent, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";
import {Label} from "@/components/ui/label";
import {showErrorToast} from "#/_lib/utils";
import {ITEM_UNIT_OF_MEASURE_API} from "#/_api/api.helpers";
import {selectSelectedInstitution} from "@/store/auth/selectors";

interface ItemUnitFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  unit?: IItemUnitOfMeasure;
}

export function ItemUnitFormDialog({isOpen, onClose, onSuccess, unit}: ItemUnitFormDialogProps) {
  const [formData, setFormData] = useState<IItemUnitOfMeasureFormData>({
    unit_name: unit?.unit_name || "",
    unit_abbreviation: unit?.unit_abbreviation || "",
    description: unit?.description || "",
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const currentInstitution = useSelector(selectSelectedInstitution);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.unit_name.trim()) {
      newErrors.unit_name = "Unit name is required";
    }
    if (!formData.unit_abbreviation.trim()) {
      newErrors.unit_abbreviation = "Unit abbreviation is required";
    }
    if (!formData.description?.trim()) {
      newErrors.description = "Unit description is required";
    }

    setErrors(newErrors);

    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (field: keyof IItemUnitOfMeasureFormData, value: string | number) => {
    setFormData((prev) => ({...prev, [field]: value}));
    if (errors[field]) {
      setErrors((prev) => ({...prev, [field]: ""}));
    }
  };

  useEffect(() => {
    if (unit) {
      setFormData({
        unit_name: unit.unit_name,
        unit_abbreviation: unit.unit_abbreviation,
        description: unit.description || "",
      });
    } else {
      setFormData({
        unit_name: "",
        unit_abbreviation: "",
        description: "",
      });
    }
    setErrors({});
  }, [unit, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm() || !currentInstitution) {
      return;
    }

    setIsLoading(true);
    try {
      if (unit) {
        await ITEM_UNIT_OF_MEASURE_API.updateUnitOfMeasure({
          base_uuid: unit.base_uuid,
          unitData: formData,
        });
      } else {
        await ITEM_UNIT_OF_MEASURE_API.createUnitOfMeasure({
          unitData: formData,
        });
      }
      toast.success(`Unit of measure ${unit ? "updated" : "created"} successfully`);
      onSuccess?.();
    } catch (error) {
      showErrorToast({error, defaultMessage: "An unexpected error occurred"});
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-sm w-[94svw] mx-auto md:max-w-2xl md:w-full lg:max-w-3xl rounded-xl">
        <DialogHeader>
          <DialogTitle>{unit ? "Edit Unit of Measure" : "Create Unit of Measure"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="px-2 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="unit_name">Unit Name</Label>
              <Input
                id="unit_name"
                placeholder="e.g. Kilogram, Liter, Piece"
                className="rounded-xl"
                value={formData.unit_name}
                onChange={(e) => handleInputChange("unit_name", e.target.value)}
              />
              {errors.unit_name && <p className="text-sm text-red-500 mt-1">{errors.unit_name}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="unit_abbreviation">Unit Abbreviation</Label>
              <Input
                id="unit_abbreviation"
                placeholder="e.g. kg, L, pcs"
                className="rounded-xl"
                value={formData.unit_abbreviation}
                onChange={(e) => handleInputChange("unit_abbreviation", e.target.value)}
              />
              {errors.unit_abbreviation && (
                <p className="text-sm text-red-500 mt-1">{errors.unit_abbreviation}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Enter unit description"
                className="resize-none rounded-xl"
                rows={3}
                value={formData.description}
                onChange={(e) => handleInputChange("description", e.target.value)}
              />
              {errors.description && (
                <p className="text-sm text-red-500 mt-1">{errors.description}</p>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end ">
            <Button type="submit" disabled={isLoading} className="w-full rounded-xl mt-8">
              {isLoading ? "Saving..." : unit ? "Update Unit" : "Create Unit"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
