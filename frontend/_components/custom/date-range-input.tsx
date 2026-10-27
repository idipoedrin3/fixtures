import * as React from "react";
import {format} from "date-fns";
import {DateRange} from "react-day-picker";
import {Icon} from "@iconify/react";

import {cn} from "@/lib/utils";
import {Button} from "@/components/ui/button";
import {Calendar} from "@/components/ui/calendar";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";

interface Props {
  className?: string;
  onChange(range: DateRange): void;
  reset?: boolean;
  variant?: "ghost" | "default" | "outline";
  disabled?: boolean;
}

export function DatePickerWithRange({
  className,
  onChange,
  reset,
  variant = "ghost",
  disabled,
}: Props) {
  const [date, setDate] = React.useState<DateRange | undefined>(undefined);

  React.useEffect(() => {
    if (date) {
      onChange(date);
    }
  }, [date]);
  React.useEffect(() => {
    if (reset) setDate(undefined);
  }, [reset]);

  return (
    <div className={cn("grid gap-2", className)}>
      <Popover>
        <PopoverTrigger asChild disabled={disabled}>
          <Button
            variant={variant}
            className={cn(
              "justify-start text-left font-normal text-base hover:bg-transparent",
              !date && "text-muted-foreground",
            )}
          >
            <span className="flex-grow">
              {date?.from ? (
                date.to ? (
                  <>
                    {format(date.from, "LLL dd")} - {format(date.to, "LLL dd")}
                  </>
                ) : (
                  format(date.from, "LLL dd")
                )
              ) : (
                "Pick a range"
              )}
            </span>
            <Icon icon="hugeicons:arrow-down-01" className="opacity-60" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="range"
            defaultMonth={date?.from}
            selected={date}
            onSelect={(range) => {
              setDate(range);
            }}
            numberOfMonths={2}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}
