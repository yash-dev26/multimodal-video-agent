import { useTheme } from "next-themes";
import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-obsidian-900 group-[.toaster]:text-ink-100 group-[.toaster]:border-gold-500/30 group-[.toaster]:shadow-glow-gold-sm font-mono",
          description: "group-[.toast]:text-ink-400",
          actionButton:
            "group-[.toast]:bg-gold-500 group-[.toast]:text-obsidian-950",
          cancelButton:
            "group-[.toast]:bg-obsidian-800 group-[.toast]:text-ink-400",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };



