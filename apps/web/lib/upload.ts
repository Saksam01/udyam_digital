const MAX_W = 1700;
const MAX_H = 2600;

export class UnreadableFile extends Error {}

async function readBytes(f: File): Promise<ArrayBuffer> {
  try {
    return await f.arrayBuffer();
  } catch {
    throw new UnreadableFile(f.name);
  }
}

type Decoded = { source: CanvasImageSource; width: number; height: number; done: () => void };

async function decode(blob: Blob): Promise<Decoded> {
  if (typeof createImageBitmap === "function") {
    try {
      const bmp = await createImageBitmap(blob);
      return { source: bmp, width: bmp.width, height: bmp.height, done: () => bmp.close() };
    } catch {
      /* fall back to an <img> */
    }
  }
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.decoding = "sync";
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("decode"));
    img.src = url;
  });
  if (img.decode) await img.decode().catch(() => {});
  return { source: img, width: img.naturalWidth, height: img.naturalHeight, done: () => URL.revokeObjectURL(url) };
}

function looksBlank(canvas: HTMLCanvasElement): boolean {
  const probe = document.createElement("canvas");
  probe.width = 64;
  probe.height = 64;
  const ctx = probe.getContext("2d");
  if (!ctx) return false;
  ctx.drawImage(canvas, 0, 0, 64, 64);
  const d = ctx.getImageData(0, 0, 64, 64).data;
  let min = 255;
  let max = 0;
  for (let i = 0; i < d.length; i += 4) {
    const v = (d[i] + d[i + 1] + d[i + 2]) / 3;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return max - min < 12;
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const h = setTimeout(() => reject(new Error("timeout")), ms);
    p.then(
      (v) => {
        clearTimeout(h);
        resolve(v);
      },
      (e) => {
        clearTimeout(h);
        reject(e);
      },
    );
  });
}

export async function prepareUpload(f: File): Promise<File> {
  const bytes = await readBytes(f);
  const copy = new Blob([bytes], { type: f.type || "application/octet-stream" });
  const original = new File([copy], f.name, { type: copy.type });
  if (!f.type.startsWith("image/")) return original;
  let pic: Decoded | null = null;
  try {
    pic = await withTimeout(decode(copy), 15000);
    if (!pic.width || !pic.height) return original;
    const scale = Math.min(1, MAX_W / pic.width, MAX_H / pic.height);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(pic.width * scale);
    canvas.height = Math.round(pic.height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return original;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(pic.source, 0, 0, canvas.width, canvas.height);
    if (looksBlank(canvas)) return original;
    const out = await withTimeout(new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.92)), 15000);
    if (!out || out.size < 2048) return original;
    return new File([out], f.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return original;
  } finally {
    pic?.done();
  }
}
