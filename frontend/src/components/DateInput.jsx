import { useEffect, useRef, useState } from "react";
import { CalendarDays } from "lucide-react";
import { toDMY, fromDMY } from "../lib/dates";

/* A date field that reads and types as DD/MM/YYYY.

   The browser's own <input type="date"> shows dates in the browser
   language's order (MM/DD/YYYY on an English-US Chrome) and can't be told
   otherwise, so the visible box is plain text; the calendar button opens the
   native picker, kept hidden behind it. `value` / `onChange` are ISO
   (YYYY-MM-DD), like every other date in the app. */
export default function DateInput({ value, onChange, min, max, className = "", placeholder = "DD/MM/YYYY" }) {
  const [text, setText] = useState(toDMY(value) || "");
  const picker = useRef(null);

  // follow changes from outside (a default, a reset, the picker)
  useEffect(() => { setText(toDMY(value) || ""); }, [value]);

  const type = (raw) => {
    // add the slashes as they type: 25092026 -> 25/09/2026
    const digits = raw.replace(/\D/g, "").slice(0, 8);
    const t = raw.includes("/")
      ? raw.replace(/[^\d/]/g, "").slice(0, 10)
      : [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join("/");
    setText(t);
    if (!t) return onChange("");
    const iso = fromDMY(t);
    if (iso) onChange(iso);
  };

  const openPicker = () => {
    const el = picker.current;
    if (!el) return;
    try { el.showPicker(); } catch { el.focus(); }
  };

  return (
    <div className={`date-input ${className}`}>
      <input
        className="input"
        inputMode="numeric"
        placeholder={placeholder}
        value={text}
        onChange={(e) => type(e.target.value)}
        // half-typed or impossible dates snap back to the last good one
        onBlur={() => setText(toDMY(value) || "")}
      />
      <button type="button" className="date-btn" onClick={openPicker} aria-label="Open calendar" title="Open calendar"><CalendarDays size={16} /></button>
      <input
        ref={picker}
        type="date"
        className="date-native"
        tabIndex={-1}
        aria-hidden="true"
        value={value || ""}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
