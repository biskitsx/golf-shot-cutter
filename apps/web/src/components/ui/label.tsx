import { cn } from "@/lib/utils";
import type { LabelHTMLAttributes } from "react";

export function Label({
  className,
  ...rest
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    // biome-ignore lint/a11y/noLabelWithoutControl: generic Label primitive; consumers provide htmlFor or wrap an input
    <label
      className={cn("text-sm font-medium leading-none", className)}
      {...rest}
    />
  );
}
