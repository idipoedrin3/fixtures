"use client";

import {Loader2} from "lucide-react";

type FixedLoaderProps = {
  className?: string;
  fixed?: boolean;
};
const FixedLoader = ({className, fixed = true}: FixedLoaderProps) => {
  return (
    <div
      className={`${className} inset-0 ${fixed ? "fixed" : "absolute"} z-50 bg-gray-500/10 flex items-center justify-center`}
    >
      <span className="mx-auto">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </span>
    </div>
  );
};

export default FixedLoader;
