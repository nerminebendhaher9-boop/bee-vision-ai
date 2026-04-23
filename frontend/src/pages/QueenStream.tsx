import { useEffect, useRef, useState, useCallback } from "react";
import { Crown, Activity, Camera, CameraOff, Gauge, Target, Radio } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatTile } from "@/components/StatTile";
import { cn } from "@/lib/utils";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

export default function QueenStream() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [streaming, setStreaming] = useState(false);
  const [annotated, setAnnotated] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [detections, setDetections] = useState(0);
  const [confidence, setConfidence] = useState(0);
  const [lastMsg, setLastMsg] = useState("");

  const start = async () => {
    setLastMsg("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { min: 1280, ideal: 1920 }, height: { min: 720, ideal: 1080 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStreaming(true);
      startInferenceLoop();
    } catch (e) {
      console.error("Camera error", e);
      setLastMsg("Camera access denied or unavailable");
    }
  };

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setStreaming(false);
    setAnnotated(null);
    setFps(0);
    setDetections(0);
    setConfidence(0);
  }, []);

  useEffect(() => () => stop(), [stop]);

  const startInferenceLoop = () => {
    let lastTime = performance.now();
    let frames = 0;

    intervalRef.current = setInterval(async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }

      ctx.drawImage(video, 0, 0);
      const base64 = canvas.toDataURL("image/jpeg", 0.92);

      try {
        const res = await fetch(`${BACKEND_URL}/infer`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ img: base64 }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          console.error("Inference error:", err);
          setLastMsg(err.error || `HTTP ${res.status}`);
          return;
        }

        const data = await res.json();
        if (data.img) setAnnotated(data.img);

        const meta = data.meta || {};
        setDetections(meta.queens ?? 0);
        const confs = (meta.detections || []).map((d: any) => d.confidence);
        setConfidence(confs.length ? Math.max(...confs) : 0);

        frames++;
        const now = performance.now();
        if (now - lastTime >= 1000) {
          setFps(frames);
          frames = 0;
          lastTime = now;
        }
      } catch (e) {
        console.error("Fetch error:", e);
        setLastMsg("Backend unreachable — is the server running on :7000?");
      }
    }, 200);
  };

  return (
    <div className="container space-y-4 py-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
            <Crown className="h-5 w-5 text-primary" />
            Queen Detection
          </h1>
          <p className="text-xs text-muted-foreground sm:text-sm">Live stream · YOLOv8 + ByteTrack</p>
        </div>
        <div
          className={cn(
            "flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
            streaming
              ? "border-success/40 bg-success/10 text-success"
              : "border-border bg-muted text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              streaming ? "bg-success animate-pulse-ring" : "bg-muted-foreground",
            )}
          />
          {streaming ? "LIVE" : "IDLE"}
        </div>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-noir shadow-elegant">
        <div className="relative aspect-video w-full">
          <video ref={videoRef} playsInline muted className="hidden" />
          <canvas ref={canvasRef} className="hidden" />

          {!streaming && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center">
              <img
                src="/bee-logo.png"
                alt="Bee mascot"
                width={80}
                height={80}
                loading="lazy"
                className="h-20 w-20 opacity-90 drop-shadow-[0_0_24px_hsl(var(--primary)/0.4)]"
              />
              <div>
                <p className="text-sm font-semibold text-foreground">Hive camera offline</p>
                <p className="text-xs text-muted-foreground">Start the stream — AI will detect the queen bee in real time</p>
              </div>
            </div>
          )}

          {streaming && annotated && (
            <img
              src={`data:image/jpeg;base64,${annotated}`}
              alt="Annotated stream"
              className="h-full w-full object-contain"
            />
          )}

          {streaming && !annotated && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="text-xs text-muted-foreground">Waiting for first inference…</p>
            </div>
          )}

          {streaming && (
            <>
              <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-1.5 rounded-md bg-black/60 px-2 py-1 font-mono text-[10px] text-white backdrop-blur">
                <Radio className="h-3 w-3 text-primary" /> {fps} FPS
              </div>
              <div className="pointer-events-none absolute right-3 top-3 rounded-md bg-primary/90 px-2 py-1 font-mono text-[10px] font-bold text-primary-foreground">
                REC
              </div>
            </>
          )}
        </div>

        {lastMsg && (
          <div className="border-t border-border/40 bg-destructive/10 px-3 py-1.5 text-[11px] text-destructive">
            {lastMsg}
          </div>
        )}

        <div className="flex items-center gap-2 border-t border-border/40 bg-background/40 p-3 backdrop-blur">
          {!streaming ? (
            <Button onClick={start} className="flex-1 bg-gradient-primary text-primary-foreground shadow-glow hover:opacity-95">
              <Camera className="h-4 w-4" /> Start Stream
            </Button>
          ) : (
            <Button onClick={stop} variant="destructive" className="flex-1">
              <CameraOff className="h-4 w-4" /> Stop Stream
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="FPS" value={fps} icon={Gauge} accent="primary" />
        <StatTile label="Detections" value={detections} icon={Target} accent="success" hint="Queen events" />
        <StatTile
          label="Confidence"
          value={`${(confidence * 100).toFixed(0)}%`}
          icon={Activity}
          accent="warning"
        />
        <StatTile label="Status" value={streaming ? "ON" : "OFF"} icon={Radio} accent={streaming ? "success" : "destructive"} />
      </div>
    </div>
  );
}

