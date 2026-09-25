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
