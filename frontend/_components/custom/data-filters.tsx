import {Icon} from "@iconify/react";
import {useEffect, useState} from "react";
import {DatePickerWithRange} from "./date-range-input";
import {capitalizeEachWord} from "#/_api/helpers";
import {DATE_FILTERS} from "#/_lib/utils";
import {Button} from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {formatDate} from "date-fns";

export type DateFilterProps = {
  filter: string;
  from: string;
  to: string;
  ordering: string;
};

type Props = {
  onChange(data: DateFilterProps): void;
  disabled?: boolean;
  dateRange?: boolean;
  sorting?: boolean;
};

export default function DateFilters({onChange, disabled, sorting, dateRange}: Props) {
  const [fdate, setFDate] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [ascending, setAscending] = useState(false);

  useEffect(() => {
    const filters = {
      filter: fdate == "_custom_" ? "" : fdate,
      from: fdate != "_custom_" ? "" : fromDate,
      to: fdate != "_custom_" ? "" : toDate,
      ordering: ascending ? "created_at" : "-created_at",
    };

    onChange(filters);
  }, [fdate, fromDate, toDate, ascending]);

  return (
    <div className="flex gap-4 items-center flex-wrap">
      {sorting ? (
        <Button
          type="button"
          disabled={disabled}
          variant="ghost"
          onClick={() => setAscending((p) => !p)}
        >
          <Icon
            icon={!ascending ? "hugeicons:sort-by-down-02" : "hugeicons:sort-by-up-02"}
            className="size-5"
          />
          {!ascending ? "Descending" : "Ascending"}
        </Button>
      ) : null}

      {dateRange ? (
        <>
          <div>
            <Select disabled={disabled} value={fdate} onValueChange={(v) => setFDate(v)}>
              <SelectTrigger className="h-8 w-44 rounded-lg bg-white text-sm border-gray-200">
                <SelectValue placeholder="Select filter" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(DATE_FILTERS).map(([k, v], i) => (
                  <SelectItem key={i} value={v}>
                    {capitalizeEachWord(k.replaceAll("_", " "))}
                  </SelectItem>
                ))}
                <SelectItem value="_custom_">Custom Range</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {fdate == "_custom_" ? (
            <>
              <DatePickerWithRange
                onChange={(range) => {
                  if (range?.from) setFromDate(formatDate(range.from, "yyyy-MM-dd"));
                  if (range?.to) setToDate(formatDate(range.to, "yyyy-MM-dd"));
                }}
              />
              <Button
                onClick={() => {
                  setFDate(DATE_FILTERS.THIS_MONTH);
                  setFromDate("");
                  setToDate("");
                }}
                size={"icon"}
                variant={"ghost"}
                className="opacity-50"
                disabled={disabled}
              >
                <Icon icon="hugeicons:undo" />
              </Button>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
