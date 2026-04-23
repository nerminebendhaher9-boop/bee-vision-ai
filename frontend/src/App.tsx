import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AppHeader } from "@/components/AppHeader";
import { BottomNav, TopTabs } from "@/components/BottomNav";
import { AIWaveBackground } from "@/components/AIWaveBackground";
import Index from "./pages/Index.tsx";
import VarroaBatch from "./pages/VarroaBatch.tsx";
import NotFound from "./pages/NotFound.tsx";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <div className="relative flex min-h-screen flex-col bg-background">
            {/* Animated AI signature — flowing neural waves in primary color */}
            <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden opacity-60 [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_75%)]">
              <AIWaveBackground />
            </div>
            <div className="relative z-10 flex min-h-screen flex-col">
              <AppHeader />
              <TopTabs />
              <main className="flex-1 pb-2">
                <Routes>
                  <Route path="/" element={<Index />} />
                  <Route path="/varroa" element={<VarroaBatch />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </main>
              <BottomNav />
            </div>
          </div>
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
