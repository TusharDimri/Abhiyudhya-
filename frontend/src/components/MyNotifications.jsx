/* The Notifications page: every notification this user has had, newest
   first. Clicking one marks it read and opens the page to act on. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CATEGORY_ICON, openLink, timeAgo, useMarkRead, useMyNotifications } from "../lib/notifications";

export default function MyNotifications() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const navigate = useNavigate();
  const q = useMyNotifications({ page, pageSize: 15, unread: unreadOnly });
  const mark = useMarkRead();
  const items = q.data?.data || [];
  const pg = q.data?.pagination || { page: 1, pages: 1, total: 0 };

  const pick = (n) => {
    if (!n.is_read) mark.one.mutate(n.id);
    openLink(n.link, navigate);
  };

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Updates</div>
          <h1>🔔 Notifications</h1>
        </div>
        <div className="page-actions">
          {(q.data?.unread || 0) > 0 && (
            <button className="btn btn-ghost" onClick={() => mark.all.mutate()} disabled={mark.all.isPending}>Mark all as read</button>
          )}
        </div>
      </div>

      <div className="seg notif-seg" role="group" aria-label="Show">
        <button type="button" className={!unreadOnly ? "on" : ""} onClick={() => { setUnreadOnly(false); setPage(1); }}>All</button>
        <button type="button" className={unreadOnly ? "on" : ""} onClick={() => { setUnreadOnly(true); setPage(1); }}>
          Unread{q.data?.unread ? ` (${q.data.unread})` : ""}
        </button>
      </div>

      <div className="card notif-list">
        {q.isLoading && <div className="bell-empty muted">Loading…</div>}
        {q.isSuccess && items.length === 0 && (
          <div className="bell-empty muted">{unreadOnly ? "Nothing unread." : "No notifications yet."}</div>
        )}
        {items.map((n) => (
          <button type="button" key={n.id} className={`bell-item ${n.is_read ? "" : "unread"}`} onClick={() => pick(n)}>
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

      <div className="pager">
        <span className="info">{pg.total} notification{pg.total === 1 ? "" : "s"}</span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
        <span className="page-num">Page {pg.page} / {pg.pages || 1}</span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page >= (pg.pages || 1)} onClick={() => setPage((p) => p + 1)}>Next ›</button>
      </div>
    </div>
  );
}
