"use client";

import {Input} from "@/components/ui/input";
import {useRef, useState} from "react";
import {createPortal} from "react-dom";

export interface ComboboxOption {
  label: string;
  description?: string;
  value: string;
}

interface SearchableComboboxInputProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: (search: string) => Promise<ComboboxOption[]>;
  placeholder?: string;
  disabled?: boolean;
}

export default function SearchableComboboxInput({
  value,
  onChange,
  onSearch,
  placeholder = "Search or type a value...",
  disabled,
}: SearchableComboboxInputProps) {
  const [inputValue, setInputValue] = useState(value ?? "");
  const [displayed, setDisplayed] = useState<ComboboxOption[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const positionDropdown = () => {
    if (!inputRef.current) return;
    const rect = inputRef.current.getBoundingClientRect();
    setDropdownStyle({
      position: "fixed",
      top: rect.bottom + 4,
      left: rect.left,
      width: rect.width,
      zIndex: 9999,
    });
  };

  const showResults = (options: ComboboxOption[]) => {
    setDisplayed(options);
    setIsOpen(options.length > 0);
  };

  const handleFocus = () => {
    positionDropdown();
    onSearch(inputValue)
      .then(showResults)
      .catch(() => {});
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInputValue(val);
    onChange(val);
    positionDropdown();

    setDisplayed([]);
    setIsOpen(false);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch(val)
        .then(showResults)
        .catch(() => {});
    }, 300);
  };

  const handleSelect = (option: ComboboxOption) => {
    setInputValue(option.label);
    onChange(option.value);
    setDisplayed([]);
    setIsOpen(false);
  };

  const handleBlur = () => {
    setTimeout(() => setIsOpen(false), 150);
  };

  const highlight = (label: string) => {
    if (!inputValue.trim()) return <span>{label}</span>;
    const idx = label.toLowerCase().indexOf(inputValue.toLowerCase());
    if (idx === -1) return <span>{label}</span>;
    return (
      <>
        {label.slice(0, idx)}
        <span className="font-semibold">{label.slice(idx, idx + inputValue.length)}</span>
        {label.slice(idx + inputValue.length)}
      </>
    );
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        value={inputValue}
        onChange={handleChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
      />

      {isOpen &&
        displayed.length > 0 &&
        createPortal(
          <ul
            style={dropdownStyle}
            className="bg-white dark:bg-zinc-900 border border-input rounded-md shadow-lg overflow-hidden"
            onMouseDown={(e) => e.preventDefault()}
          >
            <div className="max-h-48 overflow-y-auto py-1">
              {displayed.map((option, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:outline-none transition-colors"
                    onClick={() => handleSelect(option)}
                  >
                    {highlight(option.label)}
                    {option.description && (
                      <span className="block text-xs text-muted-foreground">
                        {option.description}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </div>
          </ul>,
          document.body,
        )}
    </div>
  );
}
