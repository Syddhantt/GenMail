import { Moon, Sun } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { useTheme } from "@/lib/theme"

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === "dark"
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="outline" size="xs" onClick={toggleTheme} aria-label="Toggle theme">
          {isDark ? <Sun className="size-3.5" /> : <Moon className="size-3.5" />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{isDark ? "Switch to light" : "Switch to dark"}</TooltipContent>
    </Tooltip>
  )
}
