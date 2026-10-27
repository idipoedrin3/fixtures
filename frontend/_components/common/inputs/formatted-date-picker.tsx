"use client";
import React, {useState, useEffect, useRef} from "react";
import {CalendarIcon} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Calendar} from "@/components/ui/calendar";
import {Label} from "@/components/ui/label";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {format, parseISO, isValid} from "date-fns";
import {useSelector} from "react-redux";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import {Icon} from "@iconify/react";
import {DATE_FORMAT_CHOICES} from "#/_types/api.types";
import {cn} from "@/lib/utils";

interface FormattedDatePickerProps {
  value?: string;
  referenceDate?: string;
  onChange?: (date: string | undefined) => void;
  includeTime?: boolean;
  label?: string;
  id?: string;
  placeholder?: string;
  description?: string;
  className?: string;
  inputClassName?: string;
  disabled?: boolean;
  minDate?: Date;
  maxDate?: Date;
  showOptional?: boolean;
  required?: boolean;
  showAsterisk?: boolean;
  title?: string;
  limitMaxWidth?: boolean;
}

function getDisplayFormat(institutionFormat: DATE_FORMAT_CHOICES): string {
  switch (institutionFormat) {
    case "dd/mm/yy":
      return "dd MMM yyyy";
    case "mm/dd/yy":
      return "MMM dd, yyyy";
    case "yy/mm/dd":
      return "yyyy MMM dd";
    default:
      return "dd MMM yyyy";
  }
}

function getInputOrder(institutionFormat: DATE_FORMAT_CHOICES): ("day" | "month" | "year")[] {
  switch (institutionFormat) {
    case "mm/dd/yy":
      return ["month", "day", "year"];
    case "yy/mm/dd":
      return ["year", "month", "day"];
    default:
      return ["day", "month", "year"];
  }
}

function normalizeDate(date: Date): Date {
  const normalized = new Date(date);
  normalized.setHours(0, 0, 0, 0);
  return normalized;
}

export function FormattedDatePicker({
  value,
  referenceDate,
  onChange,
  includeTime = false,
  label,
  id = "date",
  placeholder = "Select date",
  className = "",
  inputClassName = "",
  disabled = false,
  minDate,
  maxDate,
  required = false,
  showAsterisk = true,
  description = "",
  title = "",
  showOptional = false,
  limitMaxWidth = true,
}: FormattedDatePickerProps) {
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [dayInput, setDayInput] = useState<string>("");
  const [monthInput, setMonthInput] = useState<string>("");
  const [yearInput, setYearInput] = useState<string>("");
  const [timeInput, setTimeInput] = useState<string>("");
  const [dateFormat, setDateFormat] = useState("dd MMMM yyyy");
  const [validationMessage, setValidationMessage] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
  const [activeCalendarDropdown, setActiveCalendarDropdown] = useState<"month" | "year" | null>(
    null,
  );
  const [inputOrder, setInputOrder] = useState<("day" | "month" | "year")[]>([
    "day",
    "month",
    "year",
  ]);

  const currentInstitution = useSelector(selectSelectedInstitution);
  const dayRef = useRef<HTMLInputElement>(null);
  const monthRef = useRef<HTMLInputElement>(null);
  const yearRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (value) {
      const date = parseISO(value);
      if (isValid(date)) {
        setSelectedDate(date);
        setDayInput(String(date.getDate()).padStart(2, "0"));
        setMonthInput(String(date.getMonth() + 1).padStart(2, "0"));
        setYearInput(String(date.getFullYear()));
        setTimeInput(
          includeTime
            ? `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(
                2,
                "0",
              )}`
            : "",
        );
        setCurrentMonth(new Date(date.getFullYear(), date.getMonth(), 1));
        setValidationMessage("");
      } else {
        setSelectedDate(null);
        setDayInput("");
        setMonthInput("");
        setYearInput("");
        setTimeInput("");
        setValidationMessage("");
      }
    } else {
      setSelectedDate(null);
      setDayInput("");
      setMonthInput("");
      setYearInput("");
      setTimeInput("");
      setCurrentMonth(new Date());
      setValidationMessage("");
    }
  }, [includeTime, value]);

  const formatOutputValue = (date: Date, timeValue = timeInput) => {
    if (!includeTime) {
      return format(date, "yyyy-MM-dd");
    }

    const [hours, minutes] = timeValue.split(":").map(Number);
    const dateTime = new Date(date);
    dateTime.setHours(
      Number.isFinite(hours) ? hours : 0,
      Number.isFinite(minutes) ? minutes : 0,
      0,
      0,
    );

    return format(dateTime, "yyyy-MM-dd'T'HH:mm:ssxxx");
  };

  useEffect(() => {
    if (currentInstitution?.date_format) {
      setDateFormat(getDisplayFormat(currentInstitution.date_format));
      setInputOrder(getInputOrder(currentInstitution.date_format));
    }
  }, [currentInstitution]);

  const getNextField = (currentField: "day" | "month" | "year"): HTMLInputElement | null => {
    const currentIndex = inputOrder.indexOf(currentField);
    if (currentIndex < inputOrder.length - 1) {
      const nextField = inputOrder[currentIndex + 1];
      if (nextField === "day") return dayRef.current;
      if (nextField === "month") return monthRef.current;
      if (nextField === "year") return yearRef.current;
    }
    return null;
  };

  const getPrevField = (currentField: "day" | "month" | "year"): HTMLInputElement | null => {
    const currentIndex = inputOrder.indexOf(currentField);
    if (currentIndex > 0) {
      const prevField = inputOrder[currentIndex - 1];
      if (prevField === "day") return dayRef.current;
      if (prevField === "month") return monthRef.current;
      if (prevField === "year") return yearRef.current;
    }
    return null;
  };

  const handleDayChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, "").slice(0, 2);
    setDayInput(value);

    if (value.length === 2) {
      const dayNum = parseInt(value);
      if (dayNum >= 1 && dayNum <= 31) {
        const nextField = getNextField("day");
        nextField?.focus();
      }
    }

    validateAndUpdateDate(value, monthInput, yearInput);
  };

  const handleMonthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, "").slice(0, 2);
    setMonthInput(value);

    if (value.length === 2) {
      const monthNum = parseInt(value);
      if (monthNum >= 1 && monthNum <= 12) {
        const nextField = getNextField("month");
        nextField?.focus();
      }
    }

    validateAndUpdateDate(dayInput, value, yearInput);
  };

  const handleYearChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, "").slice(0, 4);
    setYearInput(value);

    if (value.length === 4) {
      const yearNum = parseInt(value);
      if (yearNum >= 1900) {
        const nextField = getNextField("year");
        nextField?.focus();
      }
    }

    validateAndUpdateDate(dayInput, monthInput, value);
  };

  const getDateRangeError = (date: Date) => {
    if (minDate && normalizeDate(date) < normalizeDate(minDate)) {
      return `Date must be on or after ${format(minDate, dateFormat)}.`;
    }
    if (maxDate && normalizeDate(date) > normalizeDate(maxDate)) {
      return `Date must be on or before ${format(maxDate, dateFormat)}.`;
    }

    return "";
  };

  const validateAndUpdateDate = (day: string, month: string, year: string) => {
    const dayNum = parseInt(day);
    const monthNum = parseInt(month);
    const yearNum = parseInt(year);

    if (
      day.length === 2 &&
      month.length === 2 &&
      year.length === 4 &&
      dayNum >= 1 &&
      dayNum <= 31 &&
      monthNum >= 1 &&
      monthNum <= 12 &&
      yearNum >= 1900
    ) {
      const date = new Date(yearNum, monthNum - 1, dayNum);
      const isRealDate = date.getMonth() === monthNum - 1 && date.getDate() === dayNum;
      const rangeError = isRealDate ? getDateRangeError(date) : "";

      if (isRealDate && !rangeError) {
        setSelectedDate(date);
        setCurrentMonth(new Date(date.getFullYear(), date.getMonth(), 1));
        setValidationMessage("");
        onChange?.(formatOutputValue(date));
        return;
      }

      setSelectedDate(null);
      setValidationMessage(rangeError || "Enter a valid date.");
      onChange?.(undefined);
      return;
    }

    if (day.length === 2 && month.length === 2 && year.length === 4) {
      setSelectedDate(null);
      setValidationMessage("Enter a valid date.");
      onChange?.(undefined);
      return;
    }

    if (!day && !month && !year) {
      setSelectedDate(null);
      setValidationMessage("");
      onChange?.(undefined);
      return;
    }

    setValidationMessage("");
  };

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
    field: "day" | "month" | "year",
  ) => {
    const input = e.currentTarget;
    const fieldValues = {day: dayInput, month: monthInput, year: yearInput};

    if (e.key === "Backspace") {
      if (input.selectionStart === 0 && input.selectionEnd === 0) {
        e.preventDefault();
        const prevField = getPrevField(field);
        if (prevField) {
          const prevFieldName = inputOrder[inputOrder.indexOf(field) - 1];
          const prevValue = fieldValues[prevFieldName];
          prevField.focus();
          prevField.setSelectionRange(prevValue.length, prevValue.length);
        }
      }
    } else if (e.key === "ArrowLeft") {
      if (input.selectionStart === 0) {
        e.preventDefault();
        const prevField = getPrevField(field);
        if (prevField) {
          const prevFieldName = inputOrder[inputOrder.indexOf(field) - 1];
          const prevValue = fieldValues[prevFieldName];
          prevField.focus();
          prevField.setSelectionRange(prevValue.length, prevValue.length);
        }
      }
    } else if (e.key === "ArrowRight") {
      if (input.selectionStart === input.value.length) {
        e.preventDefault();
        const nextField = getNextField(field);
        if (nextField) {
          nextField.focus();
          nextField.setSelectionRange(0, 0);
        }
      }
    }
  };

  const clearDate = () => {
    setSelectedDate(null);
    setDayInput("");
    setMonthInput("");
    setYearInput("");
    setTimeInput("");
    setValidationMessage("");
    onChange?.(undefined);
  };

  const handleDateSelect = (date: Date) => {
    setSelectedDate(date);
    setDayInput(String(date.getDate()).padStart(2, "0"));
    setMonthInput(String(date.getMonth() + 1).padStart(2, "0"));
    setYearInput(String(date.getFullYear()));
    setValidationMessage("");
    onChange?.(formatOutputValue(date));
    if (!includeTime) {
      setIsOpen(false);
    }
  };

  const handleTimePartChange = (part: "hour" | "minute", value: string) => {
    const [currentHour = "00", currentMinute = "00"] = timeInput.split(":");
    const nextTime = part === "hour" ? `${value}:${currentMinute}` : `${currentHour}:${value}`;

    setTimeInput(nextTime);

    if (selectedDate) {
      onChange?.(formatOutputValue(selectedDate, nextTime));
    }
  };

  const changeCalendarMonth = (offset: number) => {
    setCurrentMonth(
      (previous) => new Date(previous.getFullYear(), previous.getMonth() + offset, 1),
    );
    setActiveCalendarDropdown(null);
  };

  const isMonthDisabled = (monthIndex: number) => {
    const year = currentMonth.getFullYear();
    const firstDay = new Date(year, monthIndex, 1);
    const lastDay = new Date(year, monthIndex + 1, 0);
    return Boolean(
      (minDate && lastDay < normalizeDate(minDate)) ||
      (maxDate && firstDay > normalizeDate(maxDate)),
    );
  };

  const selectCalendarMonth = (monthIndex: number) => {
    if (isMonthDisabled(monthIndex)) return;
    setCurrentMonth((previous) => new Date(previous.getFullYear(), monthIndex, 1));
    setActiveCalendarDropdown(null);
  };

  const selectCalendarYear = (year: number) => {
    setCurrentMonth((previous) => new Date(year, previous.getMonth(), 1));
    setActiveCalendarDropdown(null);
  };

  const isDateDisabled = (date: Date) => {
    const normalizedDate = normalizeDate(date);
    if (minDate && normalizedDate < normalizeDate(minDate)) return true;
    if (maxDate && normalizedDate > normalizeDate(maxDate)) return true;
    return false;
  };

  const segmentInputClassName =
    "!h-auto !border-0 !bg-transparent !p-0 text-center text-base font-normal leading-none tabular-nums text-foreground shadow-none outline-none placeholder:text-muted-foreground/60 focus:!border-0 focus:outline-none focus:ring-0 disabled:cursor-not-allowed";

  const renderInputFields = () => {
    const fields = {
      day: (
        <input
          ref={dayRef}
          aria-label="Day"
          aria-invalid={Boolean(validationMessage)}
          type="text"
          inputMode="numeric"
          value={dayInput}
          onChange={handleDayChange}
          onKeyDown={(e) => handleKeyDown(e, "day")}
          onFocus={() => setIsOpen(true)}
          placeholder="DD"
          disabled={disabled}
          className={cn(segmentInputClassName, "w-7")}
          maxLength={2}
        />
      ),
      month: (
        <input
          ref={monthRef}
          aria-label="Month"
          aria-invalid={Boolean(validationMessage)}
          type="text"
          inputMode="numeric"
          value={monthInput}
          onChange={handleMonthChange}
          onKeyDown={(e) => handleKeyDown(e, "month")}
          onFocus={() => setIsOpen(true)}
          placeholder="MM"
          disabled={disabled}
          className={cn(segmentInputClassName, "w-7")}
          maxLength={2}
        />
      ),
      year: (
        <input
          ref={yearRef}
          aria-label="Year"
          aria-invalid={Boolean(validationMessage)}
          type="text"
          inputMode="numeric"
          value={yearInput}
          onChange={handleYearChange}
          onKeyDown={(e) => handleKeyDown(e, "year")}
          onFocus={() => setIsOpen(true)}
          placeholder="YYYY"
          disabled={disabled}
          className={cn(segmentInputClassName, "w-11")}
          maxLength={4}
        />
      ),
    };

    return (
      <div className="flex items-center justify-start gap-2">
        <div className="flex items-center justify-start gap-1.5">
          {inputOrder.map((field, index) => (
            <span key={field} className="flex items-center justify-start gap-1.5">
              {fields[field]}
              {index < inputOrder.length - 1 && (
                <span className="text-base text-muted-foreground" aria-hidden="true">
                  /
                </span>
              )}
            </span>
          ))}
        </div>

        {includeTime && (
          <>
            <span className="text-muted-foreground" aria-hidden="true">
              |
            </span>
            <span className="text-sm tabular-nums text-foreground">{timeInput || "--:--"}</span>
          </>
        )}
      </div>
    );
  };

  const hasInputValue = Boolean(dayInput || monthInput || yearInput || timeInput);
  const helperText = validationMessage || description;
  const today = new Date();
  const monthOptions = Array.from({length: 12}, (_, index) => ({
    label: format(new Date(2024, index, 1), "MMM"),
    value: index,
  }));
  const calendarStartMonth = minDate ?? new Date(1900, 0, 1);
  const calendarEndMonth = maxDate ?? new Date(today.getFullYear() + 100, 11, 31);
  const yearOptions = Array.from(
    {length: calendarEndMonth.getFullYear() - calendarStartMonth.getFullYear() + 1},
    (_, index) => calendarStartMonth.getFullYear() + index,
  );
  const quickDateOptions = [
    {
      label: "Yesterday",
      date: new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1),
    },
    {label: "Today", date: today},
  ];

  return (
    <div className={cn("w-full select-none", className)}>
      <div className={cn("flex w-full flex-col gap-3", limitMaxWidth && "max-w-sm")}>
        {label && (
          <Label htmlFor={id} className="px-1 text-sm font-medium">
            {label} {required && showAsterisk && <span className="text-red-500">*</span>}
            {showOptional && <span className="text-muted-foreground text-xs">(optional)</span>}
          </Label>
        )}

        <Popover
          open={isOpen}
          onOpenChange={(open) => {
            if (open && !disabled) {
              const reference = referenceDate ? parseISO(referenceDate) : undefined;
              const date =
                selectedDate && isValid(selectedDate)
                  ? selectedDate
                  : reference && isValid(reference)
                    ? reference
                    : new Date();
              setCurrentMonth(new Date(date.getFullYear(), date.getMonth(), 1));
            }
            if (!disabled) setIsOpen(open);
            if (!open) setActiveCalendarDropdown(null);
          }}
        >
          <PopoverTrigger asChild>
            <div
              id={id}
              role="group"
              aria-label={label ?? placeholder}
              aria-describedby={helperText ? `${id}-helper` : undefined}
              className={cn(
                "relative flex !h-[44px] min-w-fit items-center justify-between gap-2 rounded-md border border-input bg-background px-3 text-base transition-colors hover:border-accent focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
                validationMessage && "border-destructive focus-within:ring-destructive/30",
                disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
                inputClassName,
              )}
              onClick={() => !disabled && setIsOpen(true)}
            >
              {renderInputFields()}

              <div className="flex items-center gap-1">
                {hasInputValue && (
                  <Button
                    aria-label="Clear date"
                    variant="ghost"
                    type="button"
                    className="size-7 p-0 text-muted-foreground hover:bg-accent hover:text-foreground [&_svg]:!size-4"
                    onClick={(e) => {
                      e.stopPropagation();
                      clearDate();
                    }}
                  >
                    <Icon icon="hugeicons:cancel-01" className="size-4" />
                  </Button>
                )}
                <Button
                  aria-label={isOpen ? "Close calendar" : "Open calendar"}
                  variant="ghost"
                  type="button"
                  className="size-7 p-0 text-muted-foreground hover:bg-accent hover:text-foreground [&_svg]:!size-4"
                  onClick={(e) => {
                    e.stopPropagation();
                    !disabled && setIsOpen(!isOpen);
                  }}
                  disabled={disabled}
                >
                  <CalendarIcon className={cn("!size-4", selectedDate && "text-primary")} />
                </Button>
              </div>
            </div>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            sideOffset={8}
            className={cn(
              "z-[1100] w-[calc(100vw-2rem)] p-0",
              includeTime ? "max-w-[480px]" : "max-w-[340px]",
            )}
            onPointerDownCapture={(event) => {
              const target = event.target as HTMLElement;
              if (!target.closest("[data-calendar-dropdown-root]")) {
                setActiveCalendarDropdown(null);
              }
            }}
          >
            <div className="relative flex items-center justify-between border-b px-3 py-2">
              <Button
                aria-label="Previous month"
                type="button"
                variant="ghost"
                className="size-8 p-0 text-muted-foreground hover:bg-accent hover:text-foreground [&_svg]:!size-4"
                onClick={() => changeCalendarMonth(-1)}
              >
                <Icon icon="hugeicons:arrow-left-01" className="size-4" />
              </Button>

              <div className="flex items-center gap-1.5">
                <div className="relative" data-calendar-dropdown-root>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-input bg-background px-2.5 text-sm font-medium hover:bg-accent"
                    onClick={() =>
                      setActiveCalendarDropdown(activeCalendarDropdown === "month" ? null : "month")
                    }
                  >
                    {format(currentMonth, "MMM")}
                    <Icon icon="hugeicons:arrow-down-01" className="size-3.5" />
                  </button>

                  {activeCalendarDropdown === "month" && (
                    <div className="absolute left-1/2 top-full z-20 mt-1 grid w-48 -translate-x-1/2 grid-cols-3 gap-1 rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                      {monthOptions.map((month) => (
                        <button
                          key={month.value}
                          type="button"
                          disabled={isMonthDisabled(month.value)}
                          className={cn(
                            "h-8 rounded text-sm hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40",
                            month.value === currentMonth.getMonth() &&
                              "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                          )}
                          onClick={() => selectCalendarMonth(month.value)}
                        >
                          {month.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="relative" data-calendar-dropdown-root>
                  <button
                    type="button"
                    className="inline-flex h-8 items-center gap-1 rounded-md border border-input bg-background px-2.5 text-sm font-medium hover:bg-accent"
                    onClick={() =>
                      setActiveCalendarDropdown(activeCalendarDropdown === "year" ? null : "year")
                    }
                  >
                    {currentMonth.getFullYear()}
                    <Icon icon="hugeicons:arrow-down-01" className="size-3.5" />
                  </button>

                  {activeCalendarDropdown === "year" && (
                    <div className="absolute left-1/2 top-full z-20 mt-1 max-h-56 w-28 -translate-x-1/2 overflow-y-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                      {yearOptions.map((year) => (
                        <button
                          key={year}
                          type="button"
                          className={cn(
                            "h-8 w-full rounded text-sm hover:bg-accent hover:text-accent-foreground",
                            year === currentMonth.getFullYear() &&
                              "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                          )}
                          onClick={() => selectCalendarYear(year)}
                        >
                          {year}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <Button
                aria-label="Next month"
                type="button"
                variant="ghost"
                className="size-8 p-0 text-muted-foreground hover:bg-accent hover:text-foreground [&_svg]:!size-4"
                onClick={() => changeCalendarMonth(1)}
              >
                <Icon icon="hugeicons:arrow-right-01" className="size-4" />
              </Button>
            </div>

            <div className={cn(includeTime && "grid grid-cols-[minmax(0,1fr)_8rem]")}>
              <Calendar
                mode="single"
                captionLayout="label"
                hideNavigation
                selected={selectedDate ?? undefined}
                month={currentMonth}
                onMonthChange={setCurrentMonth}
                onSelect={(date) => {
                  if (date) handleDateSelect(date);
                }}
                disabled={isDateDisabled}
                startMonth={calendarStartMonth}
                endMonth={calendarEndMonth}
                className="w-full p-2 [--cell-size:2rem] [&_tbody_tr]:!border-0 [&_tr]:!border-0"
                classNames={{
                  month: "flex w-full flex-col gap-2",
                  month_caption: "hidden",
                  caption_label: "text-sm font-semibold",
                  nav: "hidden",
                  button_previous:
                    "h-8 w-8 select-none p-0 aria-disabled:opacity-50 [&_svg]:!size-4",
                  button_next: "h-8 w-8 select-none p-0 aria-disabled:opacity-50 [&_svg]:!size-4",
                  weekdays: "flex border-b border-border/70",
                  weekday:
                    "flex-1 select-none py-2 text-center text-xs font-medium text-muted-foreground",
                  week: "flex w-full !border-0",
                  day: "group/day relative aspect-square h-full w-full select-none p-0 text-center !border-0",
                }}
              />

              {includeTime && (
                <div className="flex flex-col gap-4 border-l bg-muted/20 px-3 py-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Icon icon="hugeicons:clock-01" className="size-4 text-muted-foreground" />
                    Time
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Hour</Label>
                    <Select
                      value={timeInput.split(":")[0] || "00"}
                      onValueChange={(value) => handleTimePartChange("hour", value)}
                    >
                      <SelectTrigger className="h-9 w-full">
                        <SelectValue placeholder="HH" />
                      </SelectTrigger>
                      <SelectContent className="max-h-60" style={{zIndex: 10000}}>
                        {Array.from({length: 24}, (_, hour) => {
                          const value = String(hour).padStart(2, "0");
                          return (
                            <SelectItem key={value} value={value}>
                              {value}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Minute</Label>
                    <Select
                      value={timeInput.split(":")[1] || "00"}
                      onValueChange={(value) => handleTimePartChange("minute", value)}
                    >
                      <SelectTrigger className="h-9 w-full">
                        <SelectValue placeholder="MM" />
                      </SelectTrigger>
                      <SelectContent className="max-h-60" style={{zIndex: 10000}}>
                        {Array.from({length: 60}, (_, minute) => {
                          const value = String(minute).padStart(2, "0");
                          return (
                            <SelectItem key={value} value={value}>
                              {value}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-2 border-t px-3 py-2">
              <div className="flex items-center gap-1.5">
                {quickDateOptions.map((option) => (
                  <Button
                    key={option.label}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 px-2.5"
                    disabled={isDateDisabled(option.date)}
                    onClick={() => handleDateSelect(option.date)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="ml-auto h-8 px-2.5"
                disabled={!hasInputValue}
                onClick={clearDate}
              >
                Clear
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        {helperText ? (
          <p
            id={`${id}-helper`}
            className={cn(
              "px-1 text-xs",
              validationMessage ? "text-destructive" : "text-muted-foreground",
            )}
          >
            {helperText}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default FormattedDatePicker;
