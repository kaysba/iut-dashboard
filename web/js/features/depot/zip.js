/* Lecture du répertoire central d'un ZIP, sans bibliothèque : liste des fichiers qu'il contient. */
export async function zipEntries(blob) {
  const tailLen = Math.min(blob.size, 65557);
  const tail = new DataView(await blob.slice(blob.size - tailLen).arrayBuffer());
  let eocd = -1;
  for (let i = tailLen - 22; i >= 0; i--) if (tail.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("Ce fichier n'est pas un ZIP valide.");
  const cdSize = tail.getUint32(eocd + 12, true), cdOff = tail.getUint32(eocd + 16, true);
  if (cdOff === 0xffffffff) throw new Error("ZIP64 : liste non disponible.");
  const cd = new DataView(await blob.slice(cdOff, cdOff + cdSize).arrayBuffer());
  const entries = [];
  for (let p = 0; p + 46 <= cd.byteLength && cd.getUint32(p, true) === 0x02014b50;) {
    const flags = cd.getUint16(p + 8, true), size = cd.getUint32(p + 24, true);
    const n = cd.getUint16(p + 28, true), e = cd.getUint16(p + 30, true), c = cd.getUint16(p + 32, true);
    const name = new TextDecoder(flags & 0x800 ? "utf-8" : "windows-1252").decode(new Uint8Array(cd.buffer, cd.byteOffset + p + 46, n));
    entries.push({ name, size, dir: name.endsWith("/") });
    p += 46 + n + e + c;
  }
  return entries;
}
