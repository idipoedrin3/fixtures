import {Icon} from "@iconify/react";

export default function Unauthorized() {
  return (
    <div className="text-base text-center flex flex-col items-center justify-center gap-4 min-h-[400px]">
      <Icon icon="hugeicons:circle-lock-02" className="size-10" />
      <div className="space-y-2">
        <h4 className="font-bold">Unauthorized.</h4>
        <p className="text-gray-500">
          This content is protected, you don't have permissions to view this section.
        </p>
      </div>
    </div>
  );
}
