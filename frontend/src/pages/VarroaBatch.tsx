import { useCallback, useRef, useState } from "react";
import { Bug, Upload, X, Loader2, CheckCircle2, ImageIcon, FileImage } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatTile } from "@/components/StatTile";
import { cn } from "@/lib/utils";

interface BatchFile {
  id: string;
  file: File;
  preview: string;
  status: "pending" | "processing" | "done";
  count?: number;
}

const loadImage = (src: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });

export default function VarroaBatch() {
  const [files, setFiles] = useState<BatchFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((list: FileList | File[]) => {
    const incoming = Array.from(list)
      .filter((f) => f.type.startsWith("image/"))
      .map((file) => ({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`,
        file,
        preview: URL.createObjectURL(file),
        status: "pending" as const,
      }));
    setFiles((prev) => [...prev, ...incoming]);
  }, []);

  const remove = (id: string) =>
    setFiles((prev) => {
      const f = prev.find((x) => x.id === id);
      if (f) URL.revokeObjectURL(f.preview);
      return prev.filter((x) => x.id !== id);
    });

  const clear = () => {
    files.forEach((f) => URL.revokeObjectURL(f.preview));
    setFiles([]);
  };

  const runBatch = async () => {
    setRunning(true);
    for (const f of files) {
      setFiles((prev) => prev.map((x) => (x.id === f.id ? { ...x, status: "processing" } : x)));
      // Mock inference; replace with POST to your Flask /infer endpoint
      await new Promise((r) => setTimeout(r, 700));
      const count = Math.floor(Math.random() * 12);
      setFiles((prev) => prev.map((x) => (x.id === f.id ? { ...x, status: "done", count } : x)));
    }
    setRunning(false);
  };

  const totalMites = files.reduce((s, f) => s + (f.count ?? 0), 0);
  const processed = files.filter((f) => f.status === "done").length;
  const infested = files.filter((f) => (f.count ?? 0) > 0).length;

  return (
    <div className="container space-y-4 py-4 animate-fade-in">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold sm:text-2xl">
          <Bug className="h-5 w-5 text-primary" />
          Varroa Detection
        </h1>
        <p className="text-xs text-muted-foreground sm:text-sm">Batch image upload · YOLOv8 inference</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Images" value={files.length} icon={FileImage} accent="primary" />
        <StatTile label="Processed" value={`${processed}/${files.length || 0}`} icon={CheckCircle2} accent="success" />
        <StatTile label="Infested" value={infested} icon={Bug} accent="warning" />
        <StatTile label="Total mites" value={totalMites} icon={Bug} accent="destructive" />
      </div>

      {/* Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-6 text-center transition-all sm:p-10",
          dragOver
            ? "border-primary bg-primary/5 shadow-glow"
            : "border-border bg-card hover:border-primary/50 hover:bg-primary/5",
        )}
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-primary shadow-glow">
          <Upload className="h-6 w-6 text-primary-foreground" />
        </div>
        <div>
          <p className="text-sm font-semibold">Drop frames or tap to browse</p>
          <p className="mt-1 text-xs text-muted-foreground">JPG · PNG · WEBP — multi-select supported</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* Actions */}
      {files.length > 0 && (
        <div className="flex gap-2">
          <Button
            onClick={runBatch}
            disabled={running}
            className="flex-1 bg-gradient-primary text-primary-foreground shadow-glow hover:opacity-95"
          >
            {running ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Inferring…
              </>
            ) : (
              <>
                <Bug className="h-4 w-4" /> Run Detection ({files.length})
              </>
            )}
          </Button>
          <Button variant="outline" onClick={clear} disabled={running}>
            Clear
          </Button>
        </div>
      )}

      {/* Grid */}
      {files.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {files.map((f) => (
            <div
              key={f.id}
              className="group relative overflow-hidden rounded-xl border border-border bg-card shadow-elegant"
            >
              <div className="relative aspect-square bg-muted">
                <img src={f.preview} alt={f.file.name} className="h-full w-full object-cover" />
                {f.status === "processing" && (
                  <div className="absolute inset-0 flex items-center justify-center bg-background/70 backdrop-blur-sm">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  </div>
                )}
                {f.status === "done" && (
                  <div className="absolute right-2 top-2 rounded-md bg-primary px-2 py-0.5 font-mono text-[10px] font-bold text-primary-foreground shadow-glow">
                    {f.count} mites
                  </div>
                )}
                {!running && (
                  <button
                    onClick={() => remove(f.id)}
                    className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-md bg-background/80 text-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:bg-destructive hover:text-destructive-foreground"
                    aria-label="Remove"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              <div className="flex items-center gap-1.5 p-2">
                <ImageIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
                <p className="truncate text-[11px] text-muted-foreground">{f.file.name}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
