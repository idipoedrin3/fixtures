import Image from "next/image";

type EmptyStateProps = {
  title?: string;
  description?: string;
  hideImage?: boolean;
};

export function EmptyState({
  title = "No Data",
  description = "There is no data to show you right now.",
  hideImage = false,
}: EmptyStateProps) {
  return (
    <div className="text-sm sm:text-base text-center flex flex-col items-center justify-center gap-3 sm:gap-4 px-4 min-h-[300px] sm:min-h-[450px]">
      {!hideImage && (
        <Image
          width={89}
          height={89}
          src="/images/nodata.png"
          alt=""
          className="w-16 h-16 sm:w-[89px] sm:h-[89px]"
        />
      )}
      <div className="space-y-2 max-w-xs sm:max-w-sm">
        <h4 className="font-bold capitalize">{title}</h4>
        <p className="text-gray-500">{description}</p>
      </div>
    </div>
  );
}
