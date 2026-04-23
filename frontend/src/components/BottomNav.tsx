import { NavLink } from "react-router-dom";
import { Crown, Bug } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { to: "/", label: "Queen Stream", icon: Crown },
  { to: "/varroa", label: "Varroa Batch", icon: Bug },
];

export function BottomNav() {
  return (
    <nav className="sticky bottom-0 z-40 border-t border-border/60 bg-background/90 backdrop-blur-lg md:hidden">
      <div className="grid grid-cols-2">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-1 py-2.5 text-xs font-medium transition-colors",
                isActive ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn("h-5 w-5", isActive && "drop-shadow-[0_0_6px_hsl(var(--primary))]")} />
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export function TopTabs() {
  return (
    <nav className="hidden border-b border-border/60 bg-background/60 md:block">
      <div className="container flex gap-1 py-2">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              cn(
                "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all",
                isActive
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
