import { Sparkles } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import beeLogo from "@/assets/bee-logo.png";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-lg">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
            <img
              src={beeLogo}
              alt="BEE AI PRO bee mascot logo"
              width={40}
              height={40}
              className="h-8 w-8 object-contain drop-shadow-sm"
            />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="flex items-center gap-1.5 text-sm font-bold tracking-tight">
              BEE AI <span className="text-gradient-primary">PRO</span>
              <span className="inline-flex items-center gap-0.5 rounded-full border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-primary">
                <Sparkles className="h-2.5 w-2.5" /> AI
              </span>
            </span>
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              Bee colony intelligence · YOLOv8
            </span>
          </div>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
