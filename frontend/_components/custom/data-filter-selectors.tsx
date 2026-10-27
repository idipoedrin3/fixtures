import {Icon} from "@iconify/react";
import {useEffect, useRef, useState} from "react";
import {DatePickerWithRange} from "./date-range-input";
import {capitalizeEachWord} from "#/_api/helpers";
import {DATE_FILTERS, getDateRange} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type IDateFilterProps = {
  from: string;
  to: string;
  ordering: string;
};

type Props = {
  onChange(data: Omit<IDateFilterProps, "filter">): void;
  disabled?: boolean;
  defaultFilter?: DATE_FILTERS;
  showOrdering?: boolean;
};

export default function DateFilterSelectors({
  onChange,
  disabled,
  defaultFilter = DATE_FILTERS.THIS_MONTH,
  showOrdering = true,
}: Props) {
  const [filter, setFilter] = useState<string>(defaultFilter);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [ascending, setAscending] = useState(false);
  const isMounted = useRef(false);

  useEffect(() => {
    const range = getDateRange(filter as DATE_FILTERS);
    if (range) {
      setFromDate(range.from);
      setToDate(range.to);
    }
  }, [filter]);

  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true;
      return;
    }
    onChange({
      from: fromDate,
      to: toDate,
      ordering: showOrdering ? (ascending ? "created_at" : "-created_at") : "",
    });
  }, [filter, fromDate, toDate, ascending, showOrdering]);

  return (
    <div className="flex items-end gap-6 flex-nowrap w-full">
      {showOrdering && (
        <Button
          type="button"
          disabled={disabled}
          variant="ghost"
          className="whitespace-nowrap"
          onClick={() => setAscending((p) => !p)}
        >
          <Icon
            icon={!ascending ? "hugeicons:sort-by-down-02" : "hugeicons:sort-by-up-02"}
            className="size-5"
          />
          {!ascending ? "Descending" : "Ascending"}
        </Button>
      )}

      {/* Period Selector */}
      <Select disabled={disabled} value={filter} onValueChange={setFilter}>
        <SelectTrigger className="min-w-[180px]">
          <SelectValue placeholder="Select filter" />
        </SelectTrigger>

        <SelectContent>
          {Object.entries(DATE_FILTERS)
            .filter(([k]) => !k.toLowerCase().includes("fiscal"))
            .map(([k, v]) => (
              <SelectItem key={v} value={v}>
                {capitalizeEachWord(k.replaceAll("_", " "))}
              </SelectItem>
            ))}

          <SelectItem value="_custom_">Custom Range</SelectItem>
        </SelectContent>
      </Select>

      {/* Custom Range */}
      {filter === "_custom_" && (
        <>
          <DatePickerWithRange
            onChange={(range) => {
              if (range?.from) setFromDate(range.from.toISOString().slice(0, 10));

              if (range?.to) setToDate(range.to.toISOString().slice(0, 10));
            }}
          />

          <Button
            size="icon"
            variant="ghost"
            className="opacity-50"
            onClick={() => setFilter(DATE_FILTERS.THIS_MONTH)}
            disabled={disabled}
          >
            <Icon icon="hugeicons:undo" />
          </Button>
        </>
      )}
    </div>
  );
}
