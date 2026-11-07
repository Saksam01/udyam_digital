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

function loadImage(blob: Blob): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("decode"));
    };
    img.src = url;
  });
}

export async function prepareUpload(f: File): Promise<File> {
  const bytes = await readBytes(f);
  const copy = new Blob([bytes], { type: f.type || "application/octet-stream" });
  if (!f.type.startsWith("image/")) return new File([copy], f.name, { type: copy.type });
  try {
    const img = await loadImage(copy);
    const scale = Math.min(1, MAX_W / img.naturalWidth, MAX_H / img.naturalHeight);
    if (scale === 1 && f.size < 1.5 * 1024 * 1024) return new File([copy], f.name, { type: f.type });
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return new File([copy], f.name, { type: f.type });
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const out = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/jpeg", 0.92));
    if (!out) return new File([copy], f.name, { type: f.type });
    return new File([out], f.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return new File([copy], f.name, { type: f.type });
  }
}
