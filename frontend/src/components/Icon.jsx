/* One icon set for the whole app (lucide - clean line icons), instead of
   emoji: each module and each kind of notification has its own. */
import {
  Bell, BookMarked, BookOpen, Briefcase, BriefcaseBusiness, Building, Building2, Bus, CalendarCheck,
  CalendarRange, ClipboardCheck, ClipboardList, Database, Factory, FileText, Flag, FlaskConical, GraduationCap,
  LayoutDashboard, Link2, Map, MapPin, MessageSquare, MessageSquareWarning, Mic, Monitor, NotebookPen,
  NotebookText, Presentation, School, ScrollText, Tags, Trash2, TriangleAlert, UserCheck, UserCog, UserRound, Users,
  UsersRound, Wrench, CircleDot,
} from "lucide-react";

// a module (by its key) and the fixed pages
const ICONS = {
  // pages
  dashboard: LayoutDashboard, notifications: Bell, master: Database, profile: UserRound,
  users: UsersRound, audit: ScrollText, trash: Trash2,
  // master data
  organisations: Building2, states: Map, districts: MapPin, "district-managers": UserCog, schools: School, principals: GraduationCap,
  trainers: Presentation, labs: FlaskConical, "academic-years": CalendarRange, sectors: Factory,
  "job-roles": BriefcaseBusiness, "social-categories": Tags, modules: BookOpen, units: BookMarked, sessions: NotebookText,
  // people
  students: Users, assessments: ClipboardCheck,
  // daily operations
  attendance: CalendarCheck, "class-attendance": ClipboardList, "principal-issues": MessageSquareWarning,
  issues: TriangleAlert, "org-issues": Flag, "field-visits": Bus, "guest-lectures": Mic, equipment: Monitor,
  "equipment-maintenance": Wrench,
  // internship
  employers: Building, "employer-student-maps": Link2, diaries: NotebookPen, "ojt-placements": Briefcase,
  feedback: MessageSquare,
};

// what a notification is about
const CATEGORY = {
  issue: TriangleAlert, maintenance: Wrench, equipment: Monitor, verification: UserCheck,
  attendance: CalendarCheck, guest_lecture: Mic, leaving: FileText, admin: Building2,
};

export default function Icon({ name, size = 18, strokeWidth = 1.8, className = "" }) {
  const C = ICONS[name] || CircleDot;
  return <C size={size} strokeWidth={strokeWidth} className={`ic ${className}`} aria-hidden="true" />;
}

export function CategoryIcon({ category, size = 18 }) {
  const C = CATEGORY[category] || Bell;
  return <C size={size} strokeWidth={1.8} className="ic" aria-hidden="true" />;
}
