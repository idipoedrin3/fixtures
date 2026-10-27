import {getBadgeStyle} from "#/_lib/utils";
import {capitalizeEachWord} from "#/_api/helpers";
import {Badge as CNBadge} from "@/components/ui/badge";
import {cn} from "@/lib/utils";

type Props = {
  status?: string;
  children?: any;
  [key: string]: any;
};

export function Badge({status, className, children, ...rest}: Props) {
  return (
    <CNBadge {...rest} className={cn(className, getBadgeStyle(status || ""))}>
      {children ? children : capitalizeEachWord(status || "")}
    </CNBadge>
  );
}
