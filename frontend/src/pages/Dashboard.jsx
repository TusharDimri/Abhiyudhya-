import { useState, useMemo } from "react";
import Icon from "../components/Icon";
import { ArrowRight, CircleCheck, Clock3, Timer } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { BarCard, StatusPie, TrendCard } from "../components/Charts";
import DateRange from "../components/DateRange";
import { isoDaysAgo } from "../lib/dates";
import { cardHref, QUICK_ACTIONS, DASHBOARD_SUBTITLE, VERIFICATION_LABELS } from "../lib/roleUi";

// each headline number's icon: a module's (Icon.jsx), or one of its own
const ICONS = {
  schools: "schools", labs: "labs", trainers: "trainers", students: "students", attendance: "attendance",
  guest_lectures: "guest-lectures", field_visits: "field-visits", open_issues: "issues",
  placements: "ojt-placements", my_open_issues: "principal-issues", diaries: "diaries",
  my_employer: "ojt-placements", assessments: "assessments", pending_issues_action: "issues",
};
const OWN_ICONS = {
  endorsed: CircleCheck, issues_resolved: CircleCheck, ojt_hours: Timer,
  pending_verification: Clock3, pending_endorsement: Clock3, class_pending_endorsement: Clock3,
};
const KpiIcon = ({ k }) => {
  const Own = OWN_ICONS[k];
  return Own ? <Own size={19} strokeWidth={1.8} /> : <Icon name={ICONS[k]} size={19} />;
};
const ACCENT = {
  open_issues: "warn", pending_verification: "warn", pending_endorsement: "warn", class_pending_endorsement: "warn",
  pending_issues_action: "warn",
  endorsed: "good", placements: "good", issues_resolved: "good",
};

// which charts each role sees (relevant-only, spec Part 5.20)
const ROLE_CHARTS = {
  SA: ["trend", "activity", "verification", "endorsement", "school"],
  OA: ["trend", "activity", "verification", "endorsement", "school"],
  DM: ["trend", "activity", "verification", "school"],
  PR: ["trend", "activity", "endorsement"],
  VT: ["trend", "verification"],
};

export default function Dashboard() {
  const { user, roleLabel } = useAuth();
  const { data: boot } = useBootstrap();
  const isSA = !!boot?.is_platform_admin;
  const orgOptions = boot?.options?.organisations || [];
  const [org, setOrg] = useState("");
  const [preset, setPreset] = useState("90d");
  const [range, setRange] = useState(() => {
    return { from: isoDaysAgo(90), to: "" };
  });

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    if (range.from) p.set("date_from", range.from);
    if (range.to) p.set("date_to", range.to);
    if (isSA && org) p.set("organisation_id", org);
    return p.toString();
  }, [range, isSA, org]);

  const use = (name, url) =>
    useQuery({ queryKey: ["dashboard", name, qs], queryFn: async () => (await api.get(url)).data });

  const summary = use("summary", `/dashboard/summary?${qs}`);
  const trend = use("trend", `/dashboard/timeseries?metric=attendance&${qs}`);
  const byAct = use("activity", `/dashboard/attendance-by-activity?${qs}`);
  const bySchool = use("school", `/dashboard/students-by-school?${qs}`);
  const byVerif = use("verification", `/dashboard/students-by-verification?${qs}`);
  const byEndorse = use("endorsement", `/dashboard/endorsement-status?${qs}`);

  const cards = summary.data?.cards || [];
  const charts = ROLE_CHARTS[user?.role] || ROLE_CHARTS.OA;
  const actions = QUICK_ACTIONS[user?.role] || [];
  const show = (k) => charts.includes(k);

  return (
    <div className="stack" style={{ gap: "1.3rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Overview</div>
          <h1>Welcome, {user?.full_name?.split(" ")[0]}</h1>
          <div className="muted" style={{ fontSize: ".88rem" }}>
            {roleLabel} · {isSA
              ? (org ? orgOptions.find((o) => o.value === org)?.label : "all organisations")
              : (DASHBOARD_SUBTITLE[user?.role] || "your data at a glance")}
          </div>
        </div>
        <div className="dash-controls">
          {isSA && (
            <select className={`select filter-ctl ${org ? "on" : ""}`} value={org} onChange={(e) => setOrg(e.target.value)}>
              <option value="">All organisations</option>
              {orgOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          )}
          <DateRange value={range} preset={preset} onChange={setRange} onPreset={setPreset} />
        </div>
      </div>

      <div className="kpi-grid">
        {summary.isLoading
          ? Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="card stat-card">
                <div className="skeleton" style={{ width: 38, height: 38, borderRadius: 10 }} />
                <div className="skeleton" style={{ width: "55%", height: 24, marginTop: 6 }} />
                <div className="skeleton" style={{ width: "70%", height: 12 }} />
              </div>
            ))
          : cards.map((c) => {
              const href = cardHref(c.key);
              const body = (
                <>
                  <div className="ico"><KpiIcon k={c.key} /></div>
                  <div className="val">{c.value?.toLocaleString?.() ?? c.value}</div>
                  <div className="lbl">{c.label}</div>
                  {href && <span className="stat-go">View <ArrowRight size={13} /></span>}
                </>
              );
              const cls = `card stat-card ${ACCENT[c.key] || ""}`;
              // the number is a question; clicking it opens the answer,
              // already filtered (see lib/roleUi.js)
              return href ? (
                <Link key={c.key} to={href} className={`${cls} stat-link`}>{body}</Link>
              ) : (
                <div key={c.key} className={cls}>{body}</div>
              );
            })}
      </div>

      {actions.length > 0 && (
        <div className="quick-actions">
          <span className="quick-label">Jump to</span>
          {actions.map((a) => (
            <Link key={a.to} to={a.to} className="quick-action">
              <span className="qa-ico"><Icon name={a.icon} size={17} /></span> {a.label}
            </Link>
          ))}
        </div>
      )}

      <div className="chart-grid">
        {show("trend") && (
          <TrendCard
            title="Attendance entries over time"
            subtitle="Daily entries in the selected period"
            data={trend.data?.data}
          />
        )}
        {show("activity") && (
          <BarCard title="Attendance by activity type" subtitle="What trainers spent time on" data={byAct.data?.data} labelKey="activity" valueKey="count" />
        )}
        {show("verification") && (
          <StatusPie title="Student verification" subtitle="Registration status split" data={byVerif.data?.data} />
        )}
        {show("endorsement") && (
          <StatusPie title="Attendance verification" subtitle="Verified by the Principal, or still waiting"
            data={byEndorse.data?.data?.map((d) => ({ ...d, status: VERIFICATION_LABELS[d.status] || d.status }))} />
        )}
        {show("school") && (
          <BarCard title="Students by school" subtitle="Top schools by enrolment" data={bySchool.data?.data} labelKey="school" valueKey="count" />
        )}
      </div>
    </div>
  );
}
