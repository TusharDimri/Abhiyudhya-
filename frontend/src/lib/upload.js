import api from "./api";

/* Put a file in storage straight from the browser: the API hands out a
   one-time upload link (pre-signed), the file goes to that link, and what we
   keep is its storage key - saved on the record like any other answer. */
export async function uploadFile(file) {
  const { data } = await api.post("/uploads/presign", {
    filename: file.name,
    content_type: file.type || "application/octet-stream",
  });
  const res = await fetch(data.upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
  if (!res.ok) throw new Error(`Upload failed (${res.status})`);
  return data.public_path;
}

/* Phone photos are 2-4 MB. At 1600 px on the long side and JPEG quality 0.8
   they are about 300 KB - still clear as evidence, and far less to send over
   a school's mobile data and to keep in storage. A photo that can't be
   shrunk (an unusual format, an old browser) goes up as it is. */
const PHOTO_MAX_SIDE = 1600;
const PHOTO_QUALITY = 0.8;

export async function shrinkPhoto(file) {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size < 400 * 1024) return file;
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const scale = Math.min(1, PHOTO_MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";   // see-through parts of a PNG would turn black in a JPEG
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", PHOTO_QUALITY));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.[^.]*$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  } finally {
    URL.revokeObjectURL(url);
  }
}
