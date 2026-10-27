"use client";

import {
  DependencyList,
  ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {Icon} from "@iconify/react";
import {useSelector} from "react-redux";
import {Button} from "@/components/ui/button";
import {type IPaginatedResponse} from "#/_types/api.types";
import {cn} from "@/lib/utils";
import {selectSelectedBranches} from "@/store/auth/selectors";
import {defineEndpoint} from "#/_api/services/_base";

type BaseService = ReturnType<typeof defineEndpoint>;

type FetchFromUrlFn<T> = (args: {url: string}) => Promise<IPaginatedResponse<T>>;
type FetchFirstPageFn<T, Q extends Record<string, any> = Record<string, any>> = (args: {
  query?: Q;
  page?: number;
}) => Promise<IPaginatedResponse<T>>;

export type PaginatedTableWrapperProps<T, Q extends Record<string, any> = Record<string, any>> = {
  fetchFirstPage: FetchFirstPageFn<T, Q>;
  fetchFromUrl: FetchFromUrlFn<T>;
  service?: BaseService;
  query?: Q;
  deps?: DependencyList;
  paginationMode?: "buttons" | "infinite";
  customInfiniteLoader?: boolean;
  className?: string;
  footerClassName?: string;
  showFooter?: boolean;
  showResultsSummary?: boolean;
  stickyActionsColumn?: boolean;
  onError?: (err: unknown) => void;
  children: (ctx: {
    infiniteLoader: ReactNode;
    data: IPaginatedResponse<T> | null;
    loading: boolean;
    refreshing: boolean;
    loadingMore: boolean;
    refresh: () => Promise<void>;
    goNext: () => Promise<void>;
    goPrev: () => Promise<void>;
    getRowNumber: (index: number) => number;
  }) => ReactNode;
};

export function PaginatedTableWrapper<T, Q extends Record<string, any> = Record<string, any>>({
  fetchFirstPage,
  fetchFromUrl,
  service,
  query,
  deps = [],
  paginationMode = "buttons",
  customInfiniteLoader = false,
  className,
  footerClassName,
  showFooter = true,
  showResultsSummary = false,
  stickyActionsColumn = false,
  onError,
  children,
}: PaginatedTableWrapperProps<T, Q>) {
  const [data, setData] = useState<IPaginatedResponse<T> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(1);
  const selectedBranches = useSelector(selectSelectedBranches);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  // Refs so callbacks never go stale
  const fetchFirstPageRef = useRef(fetchFirstPage);
  fetchFirstPageRef.current = fetchFirstPage;

  const queryRef = useRef(query);
  queryRef.current = query;

  const dataRef = useRef(data);
  dataRef.current = data;

  // Generation of the newest first-page request, used to discard responses that belong to a
  // filter selection the user has already moved on from.
  const requestIdRef = useRef(0);
  // Generation that produced the rows currently on screen. A `next`/`previous` URL is only
  // valid for the generation it was returned with, so paging must compare against this.
  const dataGenerationRef = useRef(0);
  // `next` URL already requested in infinite mode. `loadingMore` is stale inside the
  // IntersectionObserver callback, so this ref de-duplicates page requests.
  const requestedNextRef = useRef<string | null>(null);

  const handleError = useRef((err: unknown) => {
    if (onError) onError(err);
    else console.warn(err);
  });

  const refresh = useCallback(async () => {
    // A new selection always restarts pagination from page one.
    const requestId = ++requestIdRef.current;
    requestedNextRef.current = null;
    setLoadingMore(false);

    if (!dataRef.current) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await (service ? service.getPaginated : fetchFirstPageRef.current)({
        ...queryRef.current,
        page: 1,
      } as any);
      if (requestId !== requestIdRef.current) return;
      dataGenerationRef.current = requestId;
      setData(res as IPaginatedResponse<T>);
      setCurrentPage(1);
      setPageSize(Math.max(res.results.length, 1));
    } catch (e) {
      if (requestId === requestIdRef.current) handleError.current(e);
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [service]);

  const goPrev = useCallback(async () => {
    if (dataGenerationRef.current !== requestIdRef.current) return;
    if (!dataRef.current?.previous) return;
    const requestId = dataGenerationRef.current;
    setLoading(true);
    try {
      const res = await (service ? service.getPaginatedFromUrl : fetchFromUrl)({
        url: dataRef.current.previous,
      });
      if (requestId !== requestIdRef.current) return;
      setData(res as IPaginatedResponse<T>);
      setCurrentPage((page) => Math.max(page - 1, 1));
    } catch (e) {
      if (requestId === requestIdRef.current) handleError.current(e);
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [service, fetchFromUrl]);

  const goNext = useCallback(async () => {
    // The rows on screen belong to an older selection; their `next` URL is not usable until
    // the new first page has arrived.
    if (dataGenerationRef.current !== requestIdRef.current) return;
    const nextUrl = dataRef.current?.next;
    if (!nextUrl) return;

    if (paginationMode === "infinite") {
      // `loadingMore` is not reliable inside the IntersectionObserver callback.
      if (requestedNextRef.current === nextUrl) return;
      requestedNextRef.current = nextUrl;
      setLoadingMore(true);
    } else {
      if (loadingMore) return;
      setLoading(true);
    }

    // Tag the request with the generation whose `next` URL we follow, not the newest generation.
    const requestId = dataGenerationRef.current;

    try {
      const res = (await (service ? service.getPaginatedFromUrl : fetchFromUrl)({
        url: nextUrl,
      })) as IPaginatedResponse<T>;

      // A newer selection superseded this page; never append its rows.
      if (requestId !== requestIdRef.current) return;

      if (paginationMode === "infinite") {
        setData((current) => ({
          ...res,
          results: [...(current?.results ?? []), ...res.results],
        }));
      } else {
        setData(res);
        setCurrentPage((page) => page + 1);
      }
    } catch (e) {
      if (requestId === requestIdRef.current) {
        requestedNextRef.current = null;
        handleError.current(e);
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [service, fetchFromUrl, loadingMore, paginationMode]);

  const goToPage = useCallback(
    async (page: number) => {
      if (dataGenerationRef.current !== requestIdRef.current) return;
      if (page === currentPage || loading) return;

      const paginationUrl = dataRef.current?.next || dataRef.current?.previous;
      if (!paginationUrl) return;

      const requestId = dataGenerationRef.current;
      setLoading(true);
      try {
        const url = new URL(paginationUrl, window.location.origin);
        url.searchParams.set("page", String(page));

        const res = await (service ? service.getPaginatedFromUrl : fetchFromUrl)({
          url: url.toString(),
        });

        if (requestId !== requestIdRef.current) return;
        setData(res as IPaginatedResponse<T>);
        setCurrentPage(page);
      } catch (e) {
        if (requestId === requestIdRef.current) handleError.current(e);
      } finally {
        if (requestId === requestIdRef.current) setLoading(false);
      }
    },
    [currentPage, loading, service, fetchFromUrl],
  );

  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  const isFirstBranchMount = useRef(true);

  // Invalidate before the debounce starts so old responses cannot update the new selection.
  useLayoutEffect(() => {
    requestIdRef.current += 1;
    requestedNextRef.current = null;
    dataRef.current = null;
    setData(null);
    setCurrentPage(1);
    setLoading(true);
    setRefreshing(false);
    setLoadingMore(false);

    return () => {
      requestIdRef.current += 1;
    };
  }, [...deps, selectedBranches]);

  useEffect(() => {
    if (dataRef.current) setRefreshing(true);
    const timer = setTimeout(() => refreshRef.current(), 400);
    return () => clearTimeout(timer);
  }, [...deps]);

  useEffect(() => {
    if (isFirstBranchMount.current) {
      isFirstBranchMount.current = false;
      return;
    }
    const timer = setTimeout(() => refreshRef.current(), 500);
    return () => clearTimeout(timer);
  }, [selectedBranches]);

  useEffect(() => {
    if (paginationMode !== "infinite" || !data?.next || loadingMore || loading || refreshing) {
      return;
    }

    const target = loadMoreRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void goNext();
      },
      {rootMargin: "160px"},
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [data?.next, goNext, loadingMore, loading, refreshing, paginationMode]);

  const rangeStart = data?.results.length ? (currentPage - 1) * pageSize + 1 : 0;

  const getRowNumber = useCallback(
    (index: number) => {
      if (paginationMode === "infinite") {
        return index + 1;
      }

      return (currentPage - 1) * pageSize + index + 1;
    },
    [currentPage, pageSize, paginationMode],
  );

  const rangeEnd = data ? Math.min(rangeStart + data.results.length - 1, data.count) : 0;
  const totalPages = data ? Math.max(Math.ceil(data.count / pageSize), 1) : 1;
  const paginationItems: Array<number | "ellipsis"> =
    totalPages <= 7
      ? Array.from({length: totalPages}, (_, index) => index + 1)
      : currentPage <= 4
        ? [1, 2, 3, 4, 5, "ellipsis", totalPages]
        : currentPage >= totalPages - 3
          ? [
              1,
              "ellipsis",
              totalPages - 4,
              totalPages - 3,
              totalPages - 2,
              totalPages - 1,
              totalPages,
            ]
          : [1, "ellipsis", currentPage - 1, currentPage, currentPage + 1, "ellipsis", totalPages];

  const infiniteLoader =
    paginationMode === "infinite" && (data?.next || loadingMore || showResultsSummary) ? (
      <div ref={loadMoreRef} className="flex min-h-12 shrink-0 items-center justify-center py-3">
        {loadingMore && (
          <Icon icon="hugeicons:loading-03" className="size-5 animate-spin text-muted-foreground" />
        )}
        {showResultsSummary && !data?.next && data && (
          <p className="text-sm text-muted-foreground">Showing all {data.results.length} results</p>
        )}
      </div>
    ) : null;

  return (
    <>
      <div
        className={cn(
          "flex-grow min-h-0 flex flex-col",
          stickyActionsColumn && [
            "[&_table_th:last-child]:sticky",
            "[&_table_th:last-child]:right-0",
            "[&_table_th:last-child]:z-20",
            "[&_table_th:last-child]:bg-background",
            "[&_table_td:last-child]:sticky",
            "[&_table_td:last-child]:right-0",
            "[&_table_td:last-child]:z-10",
            "[&_table_td:last-child]:bg-background",
            "[&_table_td:last-child]:shadow-[-1px_0_0_hsl(var(--border))]",
            "[&_table_tbody_tr:hover_td:last-child]:bg-muted",
          ],
          className,
        )}
      >
        {children({
          infiniteLoader,
          data,
          loading: loading && data === null,
          refreshing: refreshing || (loading && data !== null),
          loadingMore,
          refresh,
          goNext,
          goPrev,
          getRowNumber,
        })}

        {!customInfiniteLoader && infiniteLoader}
      </div>

      {paginationMode === "buttons" && showFooter && (data?.next || data?.previous) && (
        <div className={cn("shrink-0 flex items-end justify-between pt-2", footerClassName)}>
          <p className="text-sm text-gray-500">
            Showing {rangeStart} to {rangeEnd} of {data.count}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={goPrev}
              disabled={!data.previous || loading}
              className="h-9 rounded-md px-3 disabled:cursor-not-allowed"
            >
              Previous
            </Button>

            {paginationItems.map((item, index) =>
              item === "ellipsis" ? (
                <span
                  key={`ellipsis-${index}`}
                  className="flex h-9 min-w-9 items-center justify-center px-2 text-muted-foreground"
                >
                  …
                </span>
              ) : (
                <Button
                  key={item}
                  variant={item === currentPage ? "default" : "ghost"}
                  size="sm"
                  className="h-9 min-w-9 rounded-md px-3"
                  disabled={loading}
                  onClick={() => void goToPage(item)}
                >
                  {item}
                </Button>
              ),
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={goNext}
              disabled={!data.next || loading}
              className="h-9 rounded-md px-3 disabled:cursor-not-allowed"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
