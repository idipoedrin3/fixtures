import {capitalizeEachWord} from "#/_api/helpers";
import {Button} from "@/components/ui/button";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";

type Props = {
  resource: string;
  link: string;
  label: string;
};

export default function RescourceNotFound({resource, link, label}: Props) {
  const router = useRouter();

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {capitalizeEachWord(resource)} Not Found
        </h3>
        <p className="text-gray-600 mb-4">
          The {resource.toLowerCase()} you're looking for doesn't exist or has been deleted.
        </p>
        <Button onClick={() => router.push(link)} className="rounded-xl">
          Back to {capitalizeEachWord(label)}
        </Button>
      </div>
    </div>
  );
}
