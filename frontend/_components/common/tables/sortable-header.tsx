import {useState} from "react";
import {capitalizeEachWord} from "#/_api/helpers";
import {Icon} from "@iconify/react";
import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {Input} from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface SortableHeaderFilterOption {
  label: string;
  value: string;
  description?: string;
  avatarUrl?: string | null;
}

export interface SortableHeaderFilterGroup {
  label: string;
  options: SortableHeaderFilterOption[];
  value?: string | string[];
  onChange: (value: string | string[]) => void;
  selectionMode?: "single" | "multiple";
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  loading?: boolean;
  showSearch?: boolean;
  showAvatars?: boolean;
  searchPlaceholder?: string;
  emptyMessage?: string;
  onOpen?: () => void;
}

interface SortableHeaderProps {
  label: string | (() => string);
  capitalizeLabel?: boolean;
  field: string;
  isAsc: (field: string) => boolean;
  isDesc: (field: string) => boolean;
  onSort: (value: string) => void;
  onRemove: (field: string) => void;
  filterOptions?: SortableHeaderFilterOption[];
  filterSelectionMode?: "single" | "multiple";
  filterValue?: string | string[];
  onFilterChange?: (value: string | string[]) => void;
  filterSearchValue?: string;
  onFilterSearchChange?: (value: string) => void;
  filterLoading?: boolean;
  filterHasMore?: boolean;
  onFilterLoadMore?: () => void;
  showFilterSearch?: boolean;
  showFilterAvatars?: boolean;
  filterSearchPlaceholder?: string;
  allowSorting?: boolean;
  onFilterOpen?: () => void;
  filterGroups?: SortableHeaderFilterGroup[];
}

function selectedValues(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value;
  return !value || value === "all" ? [] : [value];
}

function FilterOptionsList({
  options,
  value = "all",
  onChange,
  selectionMode = "single",
  searchValue,
  onSearchChange,
  loading = false,
  hasMore = false,
  onLoadMore,
  showSearch = false,
  showAvatars = false,
  searchPlaceholder = "Search...",
  emptyMessage = "No options found",
}: {
  options: SortableHeaderFilterOption[];
  value?: string | string[];
  onChange: (value: string | string[]) => void;
  selectionMode?: "single" | "multiple";
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  loading?: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  showSearch?: boolean;
  showAvatars?: boolean;
  searchPlaceholder?: string;
  emptyMessage?: string;
}) {
  const [internalSearch, setInternalSearch] = useState("");
  const search = searchValue ?? internalSearch;
  const selected = selectedValues(value);
  const normalizedSearch = search.trim().toLowerCase();
  const visibleOptions = onSearchChange
    ? options
    : options.filter(
        (option) =>
          option.label.toLowerCase().includes(normalizedSearch) ||
          option.description?.toLowerCase().includes(normalizedSearch),
      );

  const changeOption = (optionValue: string) => {
    if (selectionMode === "single") {
      onChange(optionValue);
      return;
    }

    onChange(
      selected.includes(optionValue)
        ? selected.filter((selectedValue) => selectedValue !== optionValue)
        : [...selected, optionValue],
    );
  };

  return (
    <>
      {showSearch && (
        <div
          className="border-b bg-popover px-1.5 py-2"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <div className="relative">
            <Icon
              icon="hugeicons:search-01"
              className="absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              value={search}
              onChange={(event) =>
                onSearchChange
                  ? onSearchChange(event.target.value)
                  : setInternalSearch(event.target.value)
              }
              placeholder={searchPlaceholder}
              className="h-8 rounded-none !border-0 bg-transparent pl-7 text-sm shadow-none focus-visible:!border-0 focus-visible:ring-0 focus-visible:ring-offset-0"
            />
          </div>
        </div>
      )}

      <div
        className="max-h-72 overflow-y-auto p-1.5"
        onScroll={(event) => {
          const element = event.currentTarget;
          const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= 24;

          if (nearBottom && hasMore && !loading) {
            onLoadMore?.();
          }
        }}
      >
        {selected.length > 0 && (
          <DropdownMenuItem
            onSelect={() => onChange(selectionMode === "multiple" ? [] : "all")}
            className="gap-2 px-2"
          >
            <Icon icon="hugeicons:undo" className="text-muted-foreground" />
            <span>Reset</span>
          </DropdownMenuItem>
        )}

        {visibleOptions.map((option) => {
          const checked = selected.includes(option.value);

          return (
            <DropdownMenuCheckboxItem
              key={option.value}
              checked={checked}
              onCheckedChange={() => changeOption(option.value)}
              onSelect={(event) => {
                if (selectionMode === "multiple") event.preventDefault();
              }}
              className="gap-3 rounded-lg px-2 py-2 [&>span:first-child]:hidden"
            >
              {showAvatars && (
                <Avatar className="size-9 shrink-0">
                  {option.avatarUrl && <AvatarImage src={option.avatarUrl} alt={option.label} />}
                  <AvatarFallback
                    delayMs={0}
                    className="bg-primary/10 text-xs font-semibold text-primary"
                  >
                    {option.label
                      .split(" ")
                      .filter(Boolean)
                      .map((part) => part[0])
                      .join("")
                      .toUpperCase()
                      .slice(0, 2)}
                  </AvatarFallback>
                </Avatar>
              )}

              <span className="min-w-0 flex-1 text-left">
                <span className="block truncate text-sm font-medium">{option.label}</span>
                {option.description && (
                  <span className="block truncate text-xs text-muted-foreground">
                    {option.description}
                  </span>
                )}
              </span>

              {checked && (
                <Icon icon="hugeicons:tick-02" className="size-4 shrink-0 text-primary" />
              )}
            </DropdownMenuCheckboxItem>
          );
        })}

        {loading && (
          <div className="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted-foreground">
            <Icon icon="hugeicons:loading-03" className="size-4 animate-spin" />
            Loading...
          </div>
        )}

        {!loading && visibleOptions.length === 0 && (
          <div className="px-3 py-6 text-center text-sm text-muted-foreground">{emptyMessage}</div>
        )}
      </div>
    </>
  );
}

export function SortableHeader({
  label,
  capitalizeLabel = true,
  field,
  isAsc,
  isDesc,
  onSort,
  onRemove,
  filterOptions,
  filterValue = "all",
  onFilterChange,
  filterSelectionMode = "single",
  filterSearchValue,
  onFilterSearchChange,
  filterLoading = false,
  filterHasMore = false,
  onFilterLoadMore,
  showFilterSearch = false,
  showFilterAvatars = false,
  filterSearchPlaceholder = "Search...",
  allowSorting = true,
  onFilterOpen,
  filterGroups,
}: SortableHeaderProps) {
  const active = isAsc(field) || isDesc(field);
  const selectedFilterValues = selectedValues(filterValue);
  const filterActive =
    selectedFilterValues.length > 0 ||
    Boolean(filterGroups?.some((group) => selectedValues(group.value).length > 0));
  const rawLabel = typeof label === "function" ? label() : label;
  const resolvedLabel = capitalizeLabel ? capitalizeEachWord(rawLabel) : rawLabel;

  return (
    <span className="inline-flex items-center gap-1.5 align-middle">
      <span>{resolvedLabel}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="inline-flex size-5 shrink-0 items-center justify-center rounded hover:bg-gray-100"
            onClick={(event) => event.stopPropagation()}
          >
            <Icon
              icon="hugeicons:sorting-05"
              className={`size-4 ${active || filterActive ? "text-primary" : "text-gray-400"}`}
            />
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="w-44">
          {allowSorting && (
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <Icon icon="hugeicons:sorting-05" />
                Sort
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-40">
                <DropdownMenuItem
                  className={isAsc(field) ? "bg-primary/10 font-medium text-primary" : ""}
                  onSelect={() => onSort(field)}
                >
                  <Icon icon="hugeicons:sorting-02" />
                  Ascending
                </DropdownMenuItem>
                <DropdownMenuItem
                  className={isDesc(field) ? "bg-primary/10 font-medium text-primary" : ""}
                  onSelect={() => onSort(`-${field}`)}
                >
                  <Icon icon="hugeicons:sorting-01" />
                  Descending
                </DropdownMenuItem>
                {active && (
                  <DropdownMenuItem
                    className="text-muted-foreground"
                    onSelect={() => onRemove(field)}
                  >
                    <Icon icon="hugeicons:undo" />
                    Reset sorting
                  </DropdownMenuItem>
                )}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          )}

          {((filterOptions && onFilterChange) || Boolean(filterGroups?.length)) && (
            <DropdownMenuSub
              onOpenChange={(open) => {
                if (open) onFilterOpen?.();
              }}
            >
              <DropdownMenuSubTrigger>
                <Icon icon="hugeicons:filter-horizontal" />
                Filter by
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent
                className={filterGroups?.length ? "w-52 p-1.5" : "w-72 overflow-hidden p-0"}
              >
                {filterGroups?.length
                  ? filterGroups.map((group) => (
                      <DropdownMenuSub
                        key={group.label}
                        onOpenChange={(open) => {
                          if (open) group.onOpen?.();
                        }}
                      >
                        <DropdownMenuSubTrigger>
                          <Icon icon="hugeicons:filter-horizontal" />
                          {group.label}
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent className="w-72 overflow-hidden p-0">
                          <FilterOptionsList
                            options={group.options}
                            value={group.value}
                            onChange={group.onChange}
                            selectionMode={group.selectionMode}
                            searchValue={group.searchValue}
                            onSearchChange={group.onSearchChange}
                            loading={group.loading}
                            showSearch={group.showSearch}
                            showAvatars={group.showAvatars}
                            searchPlaceholder={group.searchPlaceholder}
                            emptyMessage={group.emptyMessage}
                          />
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                    ))
                  : filterOptions &&
                    onFilterChange && (
                      <FilterOptionsList
                        options={filterOptions}
                        value={filterValue}
                        onChange={onFilterChange}
                        selectionMode={filterSelectionMode}
                        searchValue={filterSearchValue}
                        onSearchChange={onFilterSearchChange}
                        loading={filterLoading}
                        hasMore={filterHasMore}
                        onLoadMore={onFilterLoadMore}
                        showSearch={showFilterSearch}
                        showAvatars={showFilterAvatars}
                        searchPlaceholder={filterSearchPlaceholder}
                      />
                    )}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </span>
  );
}
