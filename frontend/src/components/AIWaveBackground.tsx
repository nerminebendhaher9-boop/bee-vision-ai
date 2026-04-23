import { useEffect, useRef } from "react";

/**
 * AIWaveBackground — Animated flowing neural-network style waves.
 * Uses the app's primary (orange) HSL token so it adapts to light/dark mode.
 * Pure canvas, no deps, GPU-friendly.
 */
export function AIWaveBackground({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // Read primary color from CSS variable so it reacts to dark/light mode
    const getPrimary = () => {
      const v = getComputedStyle(document.documentElement)
        .getPropertyValue("--primary")
        .trim();
      return v || "24 95% 53%";
    };

    const start = performance.now();
    const LINES = 22;

    const draw = (now: number) => {
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, w, h);

      const primary = getPrimary();

      for (let i = 0; i < LINES; i++) {
        const progress = i / LINES;
        const phase = t * 0.45 + progress * 4.2;

        ctx.beginPath();
        const steps = 60;
        for (let s = 0; s <= steps; s++) {
          const x = (s / steps) * w;
          const nx = s / steps;

          // Layered sine waves create the "flowing data" feel
          const y =
            h * 0.5 +
            Math.sin(nx * 5 + phase) * (h * 0.18) *
              Math.sin(phase * 0.7 + progress * 2) +
            Math.sin(nx * 11 + phase * 1.3 + progress * 6) * (h * 0.06) +
            (progress - 0.5) * h * 0.35;

          if (s === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }

        const alpha = 0.05 + (1 - Math.abs(progress - 0.5) * 2) * 0.18;
        ctx.strokeStyle = `hsla(${primary} / ${alpha})`;
        ctx.lineWidth = 0.8 + progress * 0.6;
        ctx.stroke();
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
    />
  );
}
