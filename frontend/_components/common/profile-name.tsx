"use client";

import {Avatar, AvatarFallback, AvatarImage} from "@/components/ui/avatar";
import {cn} from "@/lib/utils";

type ProfileNameProps = {
  name?: string | null;
  imageSrc?: string | null;
  fallbackName?: string;
  className?: string;
  avatarClassName?: string;
  nameClassName?: string;
};

export function ProfileName({
  name,
  imageSrc,
  fallbackName = "Automated",
  className,
  avatarClassName,
  nameClassName,
}: ProfileNameProps) {
  const displayName = name?.trim() || fallbackName;

  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      <Avatar className={cn("size-7", avatarClassName)}>
        <AvatarImage
          src={imageSrc || "/images/profile-placeholder.jpg"}
          alt={displayName}
          className="object-cover"
        />
        <AvatarFallback delayMs={0}>
          {displayName
            .split(" ")
            .filter(Boolean)
            .map((part) => part[0])
            .join("")
            .toUpperCase()
            .slice(0, 2)}
        </AvatarFallback>
      </Avatar>

      <span className={cn("truncate", nameClassName)}>{displayName}</span>
    </div>
  );
}
