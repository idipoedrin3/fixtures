import {forwardRef, InputHTMLAttributes, useEffect, useRef, useState} from "react";

import {Input} from "@/components/ui/input";
import {formatCurrency} from "#/_lib/utils";

interface FormattedNumberInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "onChange"
> {
  value: string | number;
  onValueChange: (val: number | null) => void;
  className?: string;
  description?: string;
  onLimitExceeded?: (limit: {type: "min" | "max"; value: number}) => void;
}

export const FormattedNumberInput = forwardRef<HTMLInputElement, FormattedNumberInputProps>(
  function FormattedNumberInput(
    {value, onValueChange, className = "", type, inputMode, description, onLimitExceeded, ...props},
    ref,
  ) {
    const [inputValue, setInputValue] = useState<string>(() =>
      value == null || value === "" ? "" : formatCurrency(value),
    );
    const tidRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isFocusedRef = useRef(false);

    useEffect(() => {
      if (tidRef.current) clearTimeout(tidRef.current);

      if (isFocusedRef.current) return;

      tidRef.current = setTimeout(() => {
        setInputValue(value == null || value === "" ? "" : formatCurrency(value));
      }, 10);
      return () => {
        if (tidRef.current) clearTimeout(tidRef.current);
      };
    }, [value]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const input = e.currentTarget;
      const valueBeforeFormatting = input.value;
      const caretBeforeFormatting = input.selectionStart ?? valueBeforeFormatting.length;
      const logicalCaretPosition = valueBeforeFormatting
        .slice(0, caretBeforeFormatting)
        .replace(/,/g, "").length;

      const formattedValue = formatEditableNumber(valueBeforeFormatting);
      setInputValue(formattedValue);

      window.requestAnimationFrame(() => {
        let logicalCharactersSeen = 0;
        let restoredCaretPosition = formattedValue.length;

        for (let index = 0; index < formattedValue.length; index += 1) {
          if (formattedValue[index] !== ",") {
            logicalCharactersSeen += 1;
          }

          if (logicalCharactersSeen >= logicalCaretPosition) {
            restoredCaretPosition = index + 1;
            break;
          }
        }

        input.setSelectionRange(restoredCaretPosition, restoredCaretPosition);
      });

      // Remove commas and spaces
      let raw = formattedValue.replace(/,/g, "").trim();

      const sign = raw.charAt(0) == "-" ? "-" : raw.charAt(0) == "+" ? "+" : undefined;

      if (sign) raw = raw.slice(1);

      // If the user cleared the input, allow that and send 0 to parent so the model can reset
      if (raw === "") {
        onValueChange(null);

        return;
      }

      // Remove non-digit characters to ensure whole numbers only
      const digits = extractNumber(raw);

      if (digits === "") {
        onValueChange(null);

        return;
      }

      const parsed = Number.parseFloat(digits);

      if (!Number.isNaN(parsed)) {
        let nextValue = sign == "-" ? 0 - parsed : parsed;
        const originalValue = nextValue;
        const minValue = props.min != null ? Number(props.min) : null;
        const maxValue = props.max != null ? Number(props.max) : null;
        let exceededLimit: {type: "min" | "max"; value: number} | null = null;

        if (minValue != null && !Number.isNaN(minValue) && nextValue < minValue) {
          nextValue = minValue;
          exceededLimit = {type: "min", value: minValue};
        }

        if (maxValue != null && !Number.isNaN(maxValue) && nextValue > maxValue) {
          nextValue = maxValue;
          exceededLimit = {type: "max", value: maxValue};
        }

        if (nextValue !== originalValue) {
          setInputValue(formatCurrency(nextValue));
        }

        onValueChange(nextValue);
        if (exceededLimit) {
          onLimitExceeded?.(exceededLimit);
        }
      } else {
        onValueChange(0);
      }
    };

    function extractNumber(str: string) {
      // Remove everything except digits and decimal points
      const cleaned = str.replace(/[^0-9.]/g, "");
      // Keep only the first decimal point (if multiple exist)
      const parts = cleaned.split(".");

      return parts.length > 1 ? parts[0] + "." + parts.slice(1).join("") : parts[0];
    }

    function formatEditableNumber(input: string) {
      let raw = input.replace(/,/g, "").replace(/[^0-9.+-]/g, "");

      const sign = raw.startsWith("-") ? "-" : raw.startsWith("+") ? "+" : "";
      if (sign) raw = raw.slice(1);

      const hasDecimalPoint = raw.includes(".");
      const [integerPart = "", ...fractionParts] = raw.split(".");
      const fractionPart = fractionParts.join("");
      const normalizedInteger = integerPart.replace(/^0+(?=\d)/, "");
      const groupedInteger = normalizedInteger.replace(/\B(?=(\d{3})+(?!\d))/g, ",");

      if (!groupedInteger && !hasDecimalPoint) return sign;

      return `${sign}${groupedInteger || "0"}${hasDecimalPoint ? `.${fractionPart}` : ""}`;
    }

    const handleFocus = (event: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = true;
      props.onFocus?.(event);
    };

    const handleBlur = (event: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = false;
      const formatted = value == null || value === "" ? "" : formatCurrency(value);
      setInputValue(formatted);
      props.onBlur?.(event);
    };

    return (
      <Input
        {...props}
        ref={ref}
        type="text"
        inputMode="numeric"
        className={className}
        value={inputValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        description={description}
      />
    );
  },
);

export default FormattedNumberInput;
