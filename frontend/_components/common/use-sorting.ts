import {useState} from "react";

export function useSorting() {
  const [ordering, setOrdering] = useState<string[]>([]);

  const handleSort = (value: string) => {
    setOrdering((prev) => {
      if (prev.includes(value)) return prev.filter((o) => o !== value);
      const opposite = value.startsWith("-") ? value.slice(1) : `-${value}`;
      const without = prev.filter((o) => o !== opposite);
      return [value, ...without]; // last clicked = highest priority
    });
  };

  const removeSort = (field: string) => {
    setOrdering((prev) => prev.filter((o) => o !== field && o !== `-${field}`));
  };

  const isAsc = (field: string) => ordering.includes(field);
  const isDesc = (field: string) => ordering.includes(`-${field}`);

  const orderingParam = ordering.join(",");

  return {ordering: orderingParam, handleSort, removeSort, isAsc, isDesc};
}
