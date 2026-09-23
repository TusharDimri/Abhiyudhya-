import { scopeChips } from "../lib/scope";

// Persistent "you're already scoped to this" strip. When a filter or table
// column is hidden because we already know the answer (see lib/scope.js),
// that information isn't lost - it's surfaced here once instead of being
// asked for or repeated on every row.
export default function ScopeBadges({ profile, options }) {
  const chips = scopeChips(profile, options);
  if (chips.length === 0) return null;

  return (
    <div className="scope-strip">
      <span className="scope-strip-label">You're viewing</span>
      {chips.map((c, i) => (
        <span className="scope-chip" key={i}>{c.icon} {c.text}</span>
      ))}
    </div>
  );
}
