"use client";

import {useState, useEffect} from "react";
import GenericModal from "#/_components/common/modals/custom-modal";
import {DEFAULT_DATA_API, DefaultDataCategory} from "#/_api/approvals.helpers";
import {showSuccessToast} from "#/_api/helpers";
import {showErrorToast} from "#/_lib/utils";
import SystemUnitSelector from "./systems-unit-modal";
import {IPaginatedResponse} from "#/_types/api.types";

interface AddFromSystemModalProps {
  isOpen: boolean;
  onClose: () => void;
  category_code: DefaultDataCategory;
  title: string;
  description?: string;
  onSuccess?: () => void | Promise<void>;
  createApi: (selectedItems: any[]) => Promise<void>;
  itemKey?: string;
  descriptionKey?: string;
}

export function AddFromSystemModal({
  isOpen,
  onClose,
  category_code,
  title,
  description = "Select one or more predefined items to add.",
  onSuccess,
  createApi,
  itemKey = "name",
  descriptionKey = "description",
}: AddFromSystemModalProps) {
  const [items, setItems] = useState<any[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [nextUrl, setNextUrl] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 500);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (!isOpen) {
      setItems([]);
      setSelectedKeys([]);
      setHasMore(true);
      setNextUrl(null);
      setError(null);
      setSearchQuery("");
      setDebouncedSearch("");
      return;
    }

    const fetchFirstPage = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await DEFAULT_DATA_API.fetchDefaults({
          category_code,
          page: 1,
          page_size: 10,
          fetchAllPages: false,
          search: searchQuery,
        });
        const paginated = res as IPaginatedResponse<any>;
        setItems(paginated.results || []);
        setHasMore(!!paginated.next);
        setNextUrl(paginated.next);
      } catch {
        setError("Failed to load items. Please try again.");
        setItems([]);
      } finally {
        setLoading(false);
      }
    };

    fetchFirstPage();
  }, [isOpen, category_code, debouncedSearch]);

  const handleLoadMore = async () => {
    if (!hasMore || loadingMore || !nextUrl) return;
    setLoadingMore(true);
    try {
      const res = await DEFAULT_DATA_API.fetchFromUrl(nextUrl);
      const paginated = res as any;
      setItems((prev) => [...prev, ...(paginated.results || [])]);
      setHasMore(!!paginated.next);
      setNextUrl(paginated.next);
    } catch {
      setError("Failed to load more items.");
    } finally {
      setLoadingMore(false);
    }
  };

  const handleConfirm = async () => {
    if (selectedKeys.length === 0) return;
    setSubmitting(true);
    const selectedItems = selectedKeys
      .map((key) => items.find((item) => item[itemKey] === key))
      .filter(Boolean) as any[];
    try {
      await createApi(selectedItems);
      showSuccessToast(`Added ${selectedKeys.length} item(s) successfully`);
      onSuccess?.();
      onClose();
    } catch (err: any) {
      showErrorToast(err?.message || "Failed to add selected items");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <GenericModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={handleConfirm}
      title={title}
      description={description}
      confirmText="Add Selected"
      disabled={selectedKeys.length === 0 || submitting}
      isLoading={submitting}
    >
      <div className="space-y-4 pt-1">
        {/* Search – compact, clean */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="8" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-input bg-background pl-9 py-2 text-sm shadow-sm transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/20 focus:outline-none placeholder:text-muted-foreground/70"
          />
        </div>

        <SystemUnitSelector
          units={items}
          selectedUnitNames={selectedKeys}
          onSelectionChange={setSelectedKeys}
          isLoading={loading}
          error={error}
          hasMore={hasMore}
          isLoadingMore={loadingMore}
          onLoadMore={handleLoadMore}
          itemKey={itemKey}
          descriptionKey={descriptionKey}
        />
      </div>
    </GenericModal>
  );
}
