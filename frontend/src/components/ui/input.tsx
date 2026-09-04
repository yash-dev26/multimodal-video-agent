import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-md border border-gold-500/25 bg-obsidian-900/70 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-600 focus-visible:outline-none focus-visible:border-gold-400 focus-visible:ring-1 focus-visible:ring-gold-400/50 disabled:cursor-not-allowed disabled:opacity-50 transition-all font-mono",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
