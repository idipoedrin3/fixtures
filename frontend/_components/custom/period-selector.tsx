import {capitalizeEachWord} from "#/_api/helpers";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Props = {
  value: string;
  onValueChange: (value: string) => void;
};

const FILTERS = [
  "all",
  "current_fiscal_year",
  "last_fiscal_year",
  // "last_fiscal_year_to_date",
  "last_month",
  // "last_month_to_date",
  "last_week",
  // "last_week_to_date",
  "last_year",
  // "last_year_to_date",
  "this_fiscal_year",
  // "this_fiscal_year_to_date",
  // "this_fiscal_year_to_last_month",
  "this_month",
  // "this_month_to_date",
  "this_week",
  // "this_week_to_date",
  "this_year",
  // "this_year_to_date",
  "today",
  "yesterday",
];

export default function PeriodSelector({value, onValueChange}: Props) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="w-max">
        <SelectValue placeholder="Select period" />
      </SelectTrigger>
      <SelectContent>
        {FILTERS.map((filter) => (
          <SelectItem value={filter} key={filter}>
            {capitalizeEachWord(filter)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
