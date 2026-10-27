import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";

interface ReferenceCodeInputProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
  prefix?: string;
  description?: string;
  label?: string;
  disabled?: boolean;
  required?: boolean;
}

export default function ReferenceCodeInput({
  value,
  onChange,
  error,
  prefix = "REF",
  description = "Enter the unique reference code",
  label = "Code",
  disabled = false,
  required = false,
}: ReferenceCodeInputProps) {
  const placeholder = `e.g. ${prefix}-001`;

  return (
    <div className="space-y-2">
      <Label required={required} showOptional={!required} htmlFor="reference_code">
        {label}
      </Label>
      <Input
        id="reference_code"
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`rounded-xl disabled:opacity-100 ${error ? "border-red-500" : ""}`}
        description={description}
        disabled={disabled}
      />
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
