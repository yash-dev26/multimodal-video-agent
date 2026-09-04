import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-cyan-500/20 text-cyan-200 border border-cyan-500/40 hover:bg-cyan-500/30 hover:border-cyan-400 hover:shadow-cyan-glow active:scale-[0.98]",
        xenonite:
          "bg-teal-500/20 text-teal-200 border border-teal-500/40 hover:bg-teal-500/30 hover:border-teal-300 hover:shadow-xenonite-glow active:scale-[0.98]",
        astrophage:
          "bg-amber-500/20 text-amber-200 border border-amber-500/40 hover:bg-amber-500/30 hover:border-amber-300 hover:shadow-amber-glow active:scale-[0.98]",
        destructive:
          "bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 hover:border-red-400 active:scale-[0.98]",
        outline:
          "border border-cyan-900/60 bg-space-900/60 text-slate-300 hover:bg-cyan-950/40 hover:text-cyan-200 hover:border-cyan-700/60",
        secondary:
          "bg-slate-800/80 text-slate-200 border border-slate-700/60 hover:bg-slate-800 hover:text-white",
        ghost: "text-slate-300 hover:bg-cyan-950/40 hover:text-cyan-200",
        link: "text-cyan-400 underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded px-3 text-xs",
        lg: "h-11 rounded-md px-8 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
