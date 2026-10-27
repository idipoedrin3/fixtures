"use client";

import {useState, useEffect} from "react";
import {ArrowRight, Loader2, X} from "lucide-react";
import {Icon} from "@iconify/react";

import {FEATURE_REGISTRY} from "./feature-registry";

import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {cn} from "@/lib/utils";

interface SearchResult {
  label: string;
  url: string;
  match_score: number;
}

interface FeatureSearchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function calculateMatchScore(query: string, keyword: string): number {
  const queryLower = query.toLowerCase().trim();
  const keywordLower = keyword.toLowerCase().trim();

  if (keywordLower === queryLower) {
    return 100;
  }

  if (keywordLower.includes(queryLower)) {
    const ratio = queryLower.length / keywordLower.length;

    return Math.round(80 + ratio * 20);
  }

  if (queryLower.includes(keywordLower)) {
    return 75;
  }

  const queryWords = queryLower.split(/\s+/);
  const keywordWords = keywordLower.split(/\s+/);

  let matchingWords = 0;

  for (const qWord of queryWords) {
    for (const kWord of keywordWords) {
      if (qWord === kWord || qWord.includes(kWord) || kWord.includes(qWord)) {
        matchingWords++;
        break;
      }
    }
  }

  if (matchingWords > 0) {
    const ratio = matchingWords / Math.max(queryWords.length, keywordWords.length);

    return Math.round(50 + ratio * 25);
  }

  return 0;
}

export default function FeatureSearchDialog({open, onOpenChange}: FeatureSearchDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const delayedSearch = setTimeout(() => {
      if (searchQuery.trim()) {
        performSearch(searchQuery);
      } else {
        setSearchResults([]);
      }
    }, 100);

    return () => clearTimeout(delayedSearch);
  }, [searchQuery]);

  useEffect(() => {
    if (!open) {
      setSearchQuery("");
      setSearchResults([]);
    }
  }, [open]);

  // Prevent body scroll when dropdown is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }

    // Cleanup on unmount
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [open]);

  const performSearch = (query: string) => {
    setLoading(true);

    setTimeout(() => {
      const matched: SearchResult[] = [];

      for (const feature of FEATURE_REGISTRY) {
        let bestScore = 0;

        for (const keyword of feature.keywords) {
          const score = calculateMatchScore(query, keyword);

          if (score > bestScore) {
            bestScore = score;
          }
        }

        const labelScore = calculateMatchScore(query, feature.label);

        if (labelScore > bestScore) {
          bestScore = labelScore;
        }

        if (bestScore > 50) {
          matched.push({
            label: feature.label,
            url: feature.url,
            match_score: bestScore,
          });
        }
      }

      matched.sort((a, b) => b.match_score - a.match_score);

      setSearchResults(matched);
      setLoading(false);
    }, 50);
  };

  const handleFeatureClick = (url: string) => {
    router.push(url);
    onOpenChange(false);
  };

  const getMatchScoreColor = (score: number) => {
    if (score >= 90) return "bg-green-500";
    if (score >= 70) return "bg-yellow-500";

    return "bg-red-500";
  };

  if (!open) return null;

  return (
    <div
      className="absolute right-0 top-full mt-2 w-80 bg-white border rounded-lg shadow-lg z-50 p-4 max-h-[calc(100vh-100px)] overflow-hidden"
      data-search-dropdown
    >
      <div className="space-y-3 h-full flex flex-col">
        <div className="flex items-center justify-between flex-shrink-0">
          <h3 className="font-semibold text-sm">Search Features</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="h-6 w-6 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="relative flex-shrink-0">
          <Icon
            icon="hugeicons:search-01"
            className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground"
          />
          <Input
            placeholder="Search for features..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 text-sm"
            autoFocus
          />
        </div>

        <div className="flex-1 overflow-y-auto space-y-1">
          {loading && (
            <div className="flex items-center justify-center py-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              <span className="text-sm">Searching...</span>
            </div>
          )}

          {!loading && searchResults.length === 0 && searchQuery.trim() && (
            <div className="py-4 text-center text-muted-foreground text-sm">No features found</div>
          )}

          {!loading && searchResults.length > 0 && (
            <>
              {searchResults.map((result, index) => (
                <Button
                  key={index}
                  variant="ghost"
                  onClick={() => handleFeatureClick(result.url)}
                  className="w-full justify-between h-auto p-2 text-left hover:bg-accent"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{result.label}</div>
                    <div className="flex items-center mt-1 space-x-2">
                      <span className="text-xs text-muted-foreground">
                        Match: {result.match_score}%
                      </span>
                      <div className="flex-1 max-w-16 bg-secondary rounded-full h-1">
                        <div
                          className={cn(
                            "h-1 rounded-full transition-all duration-300",
                            getMatchScoreColor(result.match_score),
                          )}
                          style={{width: `${result.match_score}%`}}
                        />
                      </div>
                    </div>
                  </div>
                  <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                </Button>
              ))}
            </>
          )}

          {!loading && searchQuery.trim() === "" && (
            <div className="py-4 text-center text-muted-foreground text-sm">
              Start typing to search...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
