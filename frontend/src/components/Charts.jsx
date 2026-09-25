import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
  PieChart, Pie, Legend, AreaChart, Area,
} from "recharts";
import { toDMY } from "../lib/dates";

/* Chart colours (dataviz method):
   - magnitude bars = single sequential hue (navy)
   - status pie     = reserved status palette (never reused for series) */
const NAVY = "#274d7d";
const GRID = "#eef1f5";
const AXIS = "#667085";

const STATUS_COLORS = {
  verified: "#167f4b", endorsed: "#167f4b", resolved: "#167f4b", completed: "#167f4b",
  pending: "#b7791f", submitted: "#274d7d", "in-progress": "#b7791f", ongoing: "#274d7d",
  rejected: "#c0392b", returned: "#c0392b", open: "#b7791f",
};
const statusColor = (s) => STATUS_COLORS[String(s).toLowerCase()] || NAVY;

function CardShell({ title, subtitle, children, empty }) {
  return (
    <div className="card chart-card">
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <span className="chart-sub">{subtitle}</span>}
      </div>
      {empty ? <div className="empty" style={{ padding: "2rem 0" }}>No data yet.</div> : children}
    </div>
  );
}

const tooltipStyle = {
  contentStyle: { borderRadius: 10, border: "1px solid #e4e7ec", boxShadow: "0 4px 16px rgba(16,24,40,.1)", fontSize: 13 },
  cursor: { fill: "rgba(39,77,125,.06)" },
};

export function BarCard({ title, subtitle, data, labelKey, valueKey, height = 300 }) {
  const rows = (data || []).map((d) => ({ label: String(d[labelKey] ?? "—"), value: d[valueKey] }));
  return (
    <CardShell title={title} subtitle={subtitle} empty={rows.length === 0}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 28, bottom: 4, left: 8 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" allowDecimals={false} tick={{ fill: AXIS, fontSize: 12 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis type="category" dataKey="label" width={150} tick={{ fill: "#344054", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip {...tooltipStyle} />
          <Bar dataKey="value" fill={NAVY} radius={[0, 4, 4, 0]} maxBarSize={22} label={{ position: "right", fill: AXIS, fontSize: 11 }} />
        </BarChart>
      </ResponsiveContainer>
    </CardShell>
  );
}

export function TrendCard({ title, subtitle, data, height = 260, span = 2 }) {
  const rows = (data || []).map((d) => ({ date: d.date, value: d.count }));
  return (
    <div className="card chart-card" style={{ gridColumn: `span ${span}` }}>
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <span className="chart-sub">{subtitle}</span>}
      </div>
      {rows.length === 0 ? (
        <div className="empty" style={{ padding: "2rem 0" }}>No activity in this period.</div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={rows} margin={{ top: 6, right: 16, bottom: 4, left: -12 }}>
            <defs>
              <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={NAVY} stopOpacity={0.25} />
                <stop offset="100%" stopColor={NAVY} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="date" tick={{ fill: AXIS, fontSize: 11 }} axisLine={{ stroke: GRID }} tickLine={false}
                   tickFormatter={(d) => String(toDMY(d)).slice(0, 5)} minTickGap={24} />
            <YAxis allowDecimals={false} tick={{ fill: AXIS, fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
            <Tooltip {...tooltipStyle} labelFormatter={(d) => toDMY(d)} />
            <Area type="monotone" dataKey="value" stroke={NAVY} strokeWidth={2} fill="url(#trendFill)" dot={false} activeDot={{ r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export function StatusPie({ title, subtitle, data, height = 300 }) {
  const rows = (data || []).map((d) => ({ name: d.status, value: d.count }));
  const total = rows.reduce((a, b) => a + b.value, 0);
  return (
    <CardShell title={title} subtitle={subtitle} empty={total === 0}>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={2}
               stroke="#fff" strokeWidth={2}>
            {rows.map((r) => <Cell key={r.name} fill={statusColor(r.name)} />)}
          </Pie>
          <Tooltip {...tooltipStyle} cursor={false} />
          <Legend verticalAlign="bottom" height={30} iconType="circle"
                  formatter={(v) => <span style={{ color: "#344054", fontSize: 12, textTransform: "capitalize" }}>{v}</span>} />
        </PieChart>
      </ResponsiveContainer>
    </CardShell>
  );
}
