type ChipMultiSelectProps = {
  options: {label: string; value: number}[];
  selected: number[];
  onChange: (selected: number[]) => void;
  helperText?: string;
};

export function ChipMultiSelect({options, selected, onChange, helperText}: ChipMultiSelectProps) {
  const toggle = (value: number) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        {options.map((opt) => {
          const isSelected = selected.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => toggle(opt.value)}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors
                ${
                  isSelected
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background text-muted-foreground border-input hover:border-primary hover:text-primary"
                }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {helperText && <p className="text-sm text-muted-foreground">{helperText}</p>}
    </div>
  );
}
