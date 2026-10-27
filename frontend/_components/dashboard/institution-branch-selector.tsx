"use client";

import {useState, useEffect, useRef} from "react";
import {useSelector} from "react-redux";
import {useDispatch} from "react-redux";
import {Icon} from "@iconify/react";
import {TruncatedText} from "../common/truncated-text";

import {
  selectAttachedInstitutions,
  selectSelectedBranches,
  selectSelectedInstitution,
} from "@/store/auth/selectors";
import {setSelectedBranches, setSelectedInstitution} from "@/store/auth/actions";
import {Branch} from "#/_types/api.types";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";

export function InstitutionBranchSelector() {
  const [showDropdown, setShowDropdown] = useState(false);
  const InstitutionsAttached = useSelector(selectAttachedInstitutions);
  const selectedInstitution = useSelector(selectSelectedInstitution);
  const selectedBranches = useSelector(selectSelectedBranches);
  const dispatch = useDispatch();
  const router = useRouter();
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    router.refresh();
  }, [selectedBranches]);

  useEffect(() => {
    if (InstitutionsAttached.length > 0 && !selectedInstitution) {
      dispatch(setSelectedInstitution(InstitutionsAttached[0]));
      if (
        InstitutionsAttached.length &&
        InstitutionsAttached[0].branches &&
        InstitutionsAttached[0].branches.length > 0 &&
        selectedBranches.length === 0
      ) {
        dispatch(setSelectedBranches([InstitutionsAttached[0].branches[0]]));
      }
    }
  }, [InstitutionsAttached, selectedInstitution, selectedBranches]);

  const handleBranchToggle = (branch: Branch) => {
    const isSelected = selectedBranches.some((b) => b.id === branch.id);
    if (isSelected) {
      dispatch(setSelectedBranches(selectedBranches.filter((b) => b.id !== branch.id)));
    } else {
      dispatch(setSelectedBranches([...selectedBranches, branch]));
    }
  };

  const handleSelectAll = () => {
    const allBranches = InstitutionsAttached.flatMap((inst) => inst.branches || []);
    if (selectedBranches.length === allBranches.length) {
      dispatch(setSelectedBranches([]));
    } else {
      dispatch(setSelectedBranches(allBranches));
    }
  };

  const getDisplayText = () => {
    if (selectedBranches.length === 0) return "Select Branch";
    if (selectedBranches.length === 1) {
      return selectedBranches[0].branch_name;
    }
    const allBranches = InstitutionsAttached.flatMap((inst) => inst.branches || []);
    if (selectedBranches.length === allBranches.length) return "All Branches";
    return `${selectedBranches.length} Branches Selected`;
  };

  const allBranches = InstitutionsAttached.flatMap((inst) => inst.branches || []);

  return (
    <div className="relative w-72" ref={dropdownRef}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={showDropdown}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("button")) return;
          setShowDropdown(!showDropdown);
        }}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget) return;
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setShowDropdown(!showDropdown);
          }
        }}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-full hover:bg-slate-100 transition-colors"
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Icon icon="hugeicons:building-04" className="shrink-0 text-lg text-slate-600" />
          <div className="min-w-0 flex-1 text-left">
            <TruncatedText
              text={getDisplayText()}
              singleLine
              className="w-full"
              textClassName="text-sm font-semibold text-slate-800"
            />
          </div>
        </div>
        <Icon
          icon="hugeicons:arrow-down-01"
          className={`ml-3 shrink-0 text-base text-slate-600 transition-transform ${
            showDropdown ? "rotate-180" : ""
          }`}
        />
      </div>

      {showDropdown && (
        <div className="absolute top-full mt-2 w-72 bg-white rounded-lg shadow-lg border border-slate-200 py-2 z-50 max-h-80 overflow-y-auto">
          <button
            onClick={handleSelectAll}
            className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition-colors text-left border-b border-slate-100"
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-4 h-4 border-2 rounded flex items-center justify-center ${
                  selectedBranches.length === allBranches.length
                    ? "bg-blue-600 border-blue-600"
                    : "border-slate-300"
                }`}
              >
                {selectedBranches.length === allBranches.length && (
                  <Icon icon="hugeicons:tick-01" className="text-white text-xs" />
                )}
              </div>
              <span className="text-sm font-medium text-slate-800">Select All</span>
            </div>
          </button>

          {InstitutionsAttached.map((institution) => (
            <div key={institution.id}>
              {institution.branches?.map((branch) => (
                <button
                  key={branch.id}
                  onClick={() => handleBranchToggle(branch)}
                  className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-4 h-4 border-2 rounded flex items-center justify-center ${
                        selectedBranches.some((b) => b.id === branch.id)
                          ? "bg-blue-600 border-blue-600"
                          : "border-slate-300"
                      }`}
                    >
                      {selectedBranches.some((b) => b.id === branch.id) && (
                        <Icon icon="mdi:check" className="text-white text-xs" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-800">{branch.branch_name}</p>
                      <p className="text-xs text-slate-500">{branch.branch_location}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ))}

          <button
            onClick={() => {
              setShowDropdown(false);
              router.push("/branches");
            }}
            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left border-t border-slate-100"
          >
            <Icon icon="hugeicons:building-04" className="text-base text-slate-600" />
            <span className="text-sm font-medium text-slate-800">Manage Branches</span>
          </button>
        </div>
      )}
    </div>
  );
}
