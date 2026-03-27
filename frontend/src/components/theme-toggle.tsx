"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = useMemo(() => {
    if (!mounted) return true;
    return resolvedTheme !== "light";
  }, [mounted, resolvedTheme]);

  const nextThemeLabel = isDark ? "modo claro" : "modo escuro";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-9 rounded-full"
          aria-label={`Ativar ${nextThemeLabel}`}
          onClick={() => setTheme(isDark ? "light" : "dark")}
        >
          {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          <span className="sr-only">{`Ativar ${nextThemeLabel}`}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{isDark ? "Ativar modo claro" : "Ativar modo escuro"}</TooltipContent>
    </Tooltip>
  );
}
