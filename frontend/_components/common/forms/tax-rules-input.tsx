"use client";

import type {ITaxRuleFormDataNew} from "#/_types/api.types";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {FormattedNumberInput} from "#/_components/common/inputs/formatted-number-input";
import {Label} from "@/components/ui/label";

type Props = {
  rules: ITaxRuleFormDataNew[];
  onRulesChange: (rules: ITaxRuleFormDataNew[]) => void;
  onValidationChange?: (isValid: boolean) => void;
  taxType: "progressive" | "non_progressive";
  onTaxTypeChange: (value: "progressive" | "non_progressive") => void;
  rateType: "percentage" | "fixed";
  readonly?: boolean;
};

export default function TaxRulesInput({
  rules,
  onRulesChange,
  onValidationChange,
  taxType,
  onTaxTypeChange,
  rateType,
  readonly = false,
}: Props) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touchedFields, setTouchedFields] = useState<Set<string>>(new Set());
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
  }, [rules]);

  const validateRules = useCallback(() => {
    const newErrors: Record<string, string> = {};

    if (rules.length === 0) {
      newErrors.rules = "At least one rule is required";
    }

    rules.forEach((rule, index) => {
      if (touchedFields.has(`rate_value_${index}`)) {
        const val = parseFloat(rule.rate_value);
        if (isNaN(val) || val <= 0) {
          newErrors[`rate_value_${index}`] = "Required";
        }
        if (rule.rate_type === "percentage" && val > 100) {
          newErrors[`rate_value_${index}`] = "Cannot exceed 100%";
        }
      }

      if (
        touchedFields.has(`value_min_${index}`) &&
        touchedFields.has(`value_max_${index}`) &&
        rule.value_min &&
        rule.value_max
      ) {
        const min = parseFloat(rule.value_min);
        const max = parseFloat(rule.value_max);
        if (!isNaN(min) && !isNaN(max) && min >= max) {
          newErrors[`value_max_${index}`] = "Max must be greater than min";
        }
      }
    });

    // For progressive tax, check that ranges don't overlap
    if (taxType === "progressive" && rules.length > 1) {
      const sorted = [...rules]
        .map((r, i) => ({...r, origIndex: i}))
        .filter((r) => r.value_min !== "" && r.value_max !== "")
        .sort((a, b) => parseFloat(a.value_min || "0") - parseFloat(b.value_min || "0"));

      for (let i = 0; i < sorted.length - 1; i++) {
        const currMax = parseFloat(sorted[i].value_max || "0");
        const nextMin = parseFloat(sorted[i + 1].value_min || "0");
        if (currMax > nextMin) {
          newErrors[`value_max_${sorted[i].origIndex}`] = "Ranges overlap";
        }
      }
    }

    setErrors(newErrors);
    const isValid = Object.keys(newErrors).length === 0 && rules.length > 0;
    if (onValidationChange) onValidationChange(isValid);
    return isValid;
  }, [rules, onValidationChange, touchedFields, taxType]);

  useEffect(() => {
    if (touchedFields.size > 0) validateRules();
  }, [rules, validateRules, touchedFields]);

  const markFieldTouched = useCallback((fieldKey: string) => {
    setTouchedFields((prev) => new Set(prev).add(fieldKey));
  }, []);

  const addRule = useCallback(() => {
    onRulesChange([
      ...rules,
      {
        value_min: "",
        value_max: "",
        rate_type: rateType,
        rate_value: "0",
      },
    ]);
  }, [rules, onRulesChange, rateType]);

  const removeRule = useCallback(
    (index: number) => {
      if (rules.length === 1) return;
      onRulesChange(rules.filter((_, i) => i !== index));
      setTouchedFields((prev) => {
        const s = new Set(prev);
        s.delete(`rate_value_${index}`);
        s.delete(`value_min_${index}`);
        s.delete(`value_max_${index}`);
        return s;
      });
      setErrors((prev) => {
        const e = {...prev};
        delete e[`rate_value_${index}`];
        delete e[`value_min_${index}`];
        delete e[`value_max_${index}`];
        return e;
      });
    },
    [rules, onRulesChange],
  );

  const updateRule = useCallback(
    (index: number, field: keyof ITaxRuleFormDataNew, value: any) => {
      onRulesChange(rules.map((rule, i) => (i === index ? {...rule, [field]: value} : rule)));
    },
    [rules, onRulesChange],
  );

  // Always 5 columns (Rate Type, Rate Value, Min, Max, Remove) or 4 if readonly
  const totalCols = readonly ? 4 : 5;

  return (
    <div className="space-y-1">
      <div>
        <h4 className="text-lg font-semibold text-foreground">Calculation Rules</h4>
        <p className="text-sm text-muted-foreground py-2">
          {taxType === "progressive"
            ? "Define progressive calculation bands using minimum and maximum values."
            : "Define the calculation rule for each applicable value range."}
        </p>
      </div>

      <div className="max-w-xl pb-4">
        <Label htmlFor="rule_application_type">Rule Application Type</Label>
        <Select value={taxType} onValueChange={onTaxTypeChange} disabled={readonly}>
          <SelectTrigger id="rule_application_type">
            <SelectValue placeholder="Select rule application type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              value="progressive"
              description="Apply each band's rate to the portion of the amount within that band, then add the results."
            >
              Progressive
            </SelectItem>
            <SelectItem
              value="non_progressive"
              description="Apply only the matching rule to the amount above its minimum value."
            >
              Non-Progressive
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow className="text-base text-slate-800 hover:bg-background">
              <TableHead>Rate Type</TableHead>
              <TableHead>Rate Value</TableHead>
              <TableHead>Min Value</TableHead>
              <TableHead>Max Value</TableHead>
              {!readonly && <TableHead className="w-10" />}
            </TableRow>
          </TableHeader>

          <TableBody>
            {rules.length === 0 ? (
              <TableRow>
                <TableCell colSpan={totalCols} className="text-center text-muted-foreground py-8">
                  No calculation rules added.
                </TableCell>
              </TableRow>
            ) : (
              rules.map((rule, index) => (
                <TableRow key={index} className="hover:bg-muted/50 align-top">
                  {/* Rate Type */}
                  <TableCell className="py-1.5 align-middle">
                    <Select
                      value={rule.rate_type}
                      onValueChange={(value: "percentage" | "fixed") =>
                        updateRule(index, "rate_type", value)
                      }
                      disabled={readonly}
                    >
                      <SelectTrigger className="">
                        <SelectValue placeholder="Type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percentage">Percentage</SelectItem>
                        <SelectItem value="fixed">Fixed</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>

                  {/* Rate Value */}
                  <TableCell className="py-1.5 align-middle">
                    {/* Rate Value */}
                    <FormattedNumberInput
                      value={rule.rate_value}
                      onValueChange={(value) => {
                        markFieldTouched(`rate_value_${index}`);
                        updateRule(index, "rate_value", value != null ? value.toString() : "");
                      }}
                      placeholder="0.00"
                      disabled={readonly}
                      className="text-center"
                    />
                    {errors[`rate_value_${index}`] && (
                      <p className="text-[10px] text-destructive mt-0.5 text-right">
                        {errors[`rate_value_${index}`]}
                      </p>
                    )}
                  </TableCell>

                  {/* Min Value — always shown */}
                  <TableCell className="py-1.5 align-middle">
                    <FormattedNumberInput
                      value={rule.value_min || ""}
                      onValueChange={(value) => {
                        markFieldTouched(`value_min_${index}`);
                        updateRule(index, "value_min", value ? value.toString() : "");
                      }}
                      placeholder="0.00"
                      disabled={readonly}
                      className="text-right"
                    />
                    {errors[`value_min_${index}`] && (
                      <p className="text-[10px] text-destructive mt-0.5 text-right">
                        {errors[`value_min_${index}`]}
                      </p>
                    )}
                  </TableCell>

                  {/* Max Value — always shown */}
                  <TableCell className="py-1.5 align-middle">
                    <FormattedNumberInput
                      value={rule.value_max || ""}
                      onValueChange={(value) => {
                        markFieldTouched(`value_max_${index}`);
                        updateRule(index, "value_max", value ? value.toString() : "");
                      }}
                      placeholder="0.00"
                      disabled={readonly}
                      className="text-right"
                    />
                    {errors[`value_max_${index}`] && (
                      <p className="text-[10px] text-destructive mt-0.5 text-right">
                        {errors[`value_max_${index}`]}
                      </p>
                    )}
                  </TableCell>

                  {/* Remove */}
                  {!readonly && (
                    <TableCell className="py-1.5 align-middle px-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeRule(index)}
                        className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        disabled={rules.length === 1}
                      >
                        <Icon icon="mdi:close" className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>

          <TableFooter>
            <TableRow>
              <TableCell colSpan={totalCols}>
                {!readonly && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addRule}
                    className="flex items-center gap-2"
                  >
                    <Icon icon="hugeicons:plus-sign" className="h-4 w-4" />
                    Add Rule
                  </Button>
                )}
              </TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      </div>

      {errors.rules && <p className="text-xs text-destructive">{errors.rules}</p>}
    </div>
  );
}
