/* The bell beside the user's name: a red count of unread notifications, and
   a dropdown of the latest ones. Clicking one marks it read and opens the
   page to act on. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CATEGORY_ICON, openLink, timeAgo, useMarkRead, useMyNotifications } from "../lib/notifications";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const navigate = useNavigate();
  const q = useMyNotifications({ pageSize: 8, poll: true });
  const mark = useMarkRead();
  const unread = q.data?.unread || 0;
  const items = q.data?.data || [];

  // close on a click elsewhere or Escape
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);

  const pick = (n) => {
    if (!n.is_read) mark.one.mutate(n.id);
    setOpen(false);
    openLink(n.link, navigate);
  };

  return (
    <div className="bell" ref={box}>
      <button type="button" className="bell-btn" onClick={() => setOpen((o) => !o)}
        aria-label={unread ? `Notifications - ${unread} unread` : "Notifications"} aria-expanded={open}>
        <span aria-hidden="true">🔔</span>
        {unread > 0 && <span className="bell-count">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="bell-menu" role="menu">
          <div className="bell-head">
            <b>Notifications</b>
            {unread > 0 && (
              <button type="button" className="link-btn plain" onClick={() => mark.all.mutate()} disabled={mark.all.isPending}>
                Mark all as read
              </button>
            )}
          </div>
          <div className="bell-list">
            {q.isLoading && <div className="bell-empty muted">Loading…</div>}
            {q.isSuccess && items.length === 0 && <div className="bell-empty muted">No notifications yet.</div>}
            {items.map((n) => (
              <button type="button" key={n.id} className={`bell-item ${n.is_read ? "" : "unread"}`} onClick={() => pick(n)} role="menuitem">
                <span className="bell-ico" aria-hidden="true">{CATEGORY_ICON[n.category] || "🔔"}</span>
                <span className="bell-text">
                  <span className="bell-title">{n.title}</span>
                  {n.body && <span className="bell-body">{n.body}</span>}
                  <span className="bell-time">{timeAgo(n.created_at)}</span>
                </span>
                {!n.is_read && <span className="bell-dot" aria-label="unread" />}
              </button>
            ))}
          </div>
          <button type="button" className="bell-all" onClick={() => { setOpen(false); navigate("/app/notifications"); }}>
            See all notifications
          </button>
        </div>
      )}
    </div>
  );
}
