/* A photo answer on a form: "Take photo" opens the camera straight away,
   "Choose from gallery" (beside it) picks one already on the device.
   On a phone the camera is the phone's own camera app (the `capture` input);
   on a laptop there's no such app, so the webcam opens here in a small
   window instead. Whatever is picked is uploaded and its storage key becomes
   the field's value. */
import { useEffect, useRef, useState } from "react";
import { Camera, Image as ImageIcon, RefreshCw, X } from "lucide-react";
import { shrinkPhoto, uploadFile } from "../lib/upload";

const isTouch = () => typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;
const canStream = () => !!navigator.mediaDevices?.getUserMedia;

export default function PhotoInput({ value, onChange, onError, label = "Photo" }) {
  const cameraRef = useRef(null);
  const galleryRef = useRef(null);
  const [preview, setPreview] = useState("");      // this browser's copy, to show what was taken
  const [busy, setBusy] = useState(false);
  const [webcam, setWebcam] = useState(false);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const take = async (file) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { onError?.("Choose a photo (an image file)."); return; }
    setBusy(true);
    try {
      const photo = await shrinkPhoto(file);
      const key = await uploadFile(photo);
      setPreview(URL.createObjectURL(photo));
      onChange(key);
      onError?.("");
    } catch {
      onError?.("The photo couldn't be uploaded - check the connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const openCamera = () => {
    if (!isTouch() && canStream()) setWebcam(true);
    else cameraRef.current?.click();
  };
  const clear = () => { setPreview(""); onChange(""); };

  return (
    <div className="photo-input">
      {/* the phone's camera app, and the gallery - hidden, opened by the buttons */}
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { take(e.target.files[0]); e.target.value = ""; }} />
      <input ref={galleryRef} type="file" accept="image/*" hidden
        onChange={(e) => { take(e.target.files[0]); e.target.value = ""; }} />

      {value ? (
        <div className="photo-done">
          {preview ? <img src={preview} alt={label} /> : <span className="photo-attached"><ImageIcon size={18} /> Photo attached</span>}
          <div className="photo-done-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={openCamera} disabled={busy}>
              <RefreshCw size={14} /> Retake
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={clear} disabled={busy} aria-label={`Remove ${label}`}>
              <X size={14} /> Remove
            </button>
          </div>
        </div>
      ) : (
        <div className="photo-buttons">
          <button type="button" className="btn btn-primary" onClick={openCamera} disabled={busy}>
            <Camera size={16} /> {busy ? "Uploading…" : "Take photo"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => galleryRef.current?.click()} disabled={busy}>
            <ImageIcon size={16} /> Choose from gallery
          </button>
        </div>
      )}

      {webcam && (
        <Webcam onClose={() => setWebcam(false)} onShot={(file) => { setWebcam(false); take(file); }}
          onFail={() => { setWebcam(false); cameraRef.current?.click(); }} />
      )}
    </div>
  );
}

/* The laptop's webcam, live, with a button to take the picture. */
function Webcam({ onClose, onShot, onFail }) {
  const videoRef = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let stream;
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => {
        stream = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setError("The camera couldn't be opened - allow camera access in the browser, or choose from the gallery."));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, []);

  const snap = () => {
    const v = videoRef.current;
    if (!v?.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d").drawImage(v, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) onShot(new File([blob], `photo-${Date.now()}.jpg`, { type: "image/jpeg" }));
    }, "image/jpeg", 0.9);
  };

  return (
    <div className="overlay camera-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer camera-box">
        <header>
          <h3 style={{ margin: 0 }}>Take photo</h3>
          <button type="button" className="close" onClick={onClose}><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          {error
            ? <p className="hint">{error}</p>
            : <video ref={videoRef} autoPlay playsInline muted className="camera-video" />}
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={error ? onFail : onClose}>
            {error ? "Choose a file instead" : "Cancel"}
          </button>
          {!error && <button type="button" className="btn btn-primary" onClick={snap}><Camera size={16} /> Capture</button>}
        </footer>
      </div>
    </div>
  );
}
