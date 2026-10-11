import { useState, useEffect, useMemo, useRef } from "react";
import Icon from "./Icon";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Plus, Search } from "lucide-react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { MODULES, groupOf, labelOf, ORG_ADMIN_SCOPE } from "../lib/modules";
import { useOrgScope } from "../lib/orgScope";
import ScopePicker, { ScopeEmpty } from "./ScopePicker";
import { useBootstrap } from "../hooks/useBootstrap";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import DataTable from "./DataTable";
import ResourceForm from "./ResourceForm";
import WorkflowDialog from "./WorkflowDialog";
import Filters from "./Filters";
import TargetProgress from "./TargetProgress";
import PromoteDialog from "./PromoteDialog";
import StudentHistory, { HistoryList } from "./StudentHistory";
import TcIssueDialog from "./TcIssueDialog";
import ResolveDialog from "./ResolveDialog";
import RecordView from "./RecordView";
import LoginCreated from "./LoginCreated";
import BulkVerify from "./BulkVerify";
import { DistanceLegend, EndorsementLegend } from "./DistanceDot";
import { visibleFilters, visibleColumns } from "../lib/scope";
import { EMPTY_HINTS } from "../lib/roleUi";
import { toDMY } from "../lib/dates";

const CONTROL_KEYS = ["page", "page_size", "q", "sort", "order", "new"];
const PAGE_SIZES = [15, 25, 50, 100];

/* One module's list: search, filters, table, paging, and the create/edit
   drawer. Can also be embedded in another page (the Students tabs):
     resourceKey  which module, instead of the URL's
     embedded     no page heading - the host page has its own
     readOnly     a list to look at: no create, edit, delete or row actions
     onlyActions  row actions to keep (e.g. ["verify"])
     hideCreate   no "New" button (the host adds records its own way)
     fixedParams  filters the host fixes (e.g. only students to verify)
     scopeKey     whose District -> School pick this list uses (default: its
                  resource - each list keeps its own)                       */
export default function ResourcePage({ resourceKey, embedded, readOnly, onlyActions, hideCreate, fixedParams, scopeKey } = {}) {
  const params = useParams();
  const resource = resourceKey || params.resource;
  const mod = MODULES[resource];
  const qc = useQueryClient();
  const { push } = useToast();
  const { data: boot } = useBootstrap();
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();

  // Smart-form prefill: the backend already resolved everything we know about
  // this user (their school/lab/trainer/student record + current year) into
  // my_scope.profile, so new records come pre-populated and those fields are
  // shown read-only instead of asked for.
  const formContext = useMemo(() => ({ ...(boot?.my_scope?.profile || {}) }), [boot]);

  const [editing, setEditing] = useState(null);
  const [workflow, setWorkflow] = useState(null);
  const [newLogin, setNewLogin] = useState(null);   // a login just made with a new trainer / principal
  const [pageAction, setPageAction] = useState(null);
  const [searchInput, setSearchInput] = useState(sp.get("q") || "");

  // nothing is listed until an admin picks where to look: an org admin a
  // district, then a school; a super admin an organisation first, then the same
  const [orgScope, setOrgScope] = useOrgScope(scopeKey || resource);
  const saGate = user?.role === "SA" && resource !== "organisations";
  const gate = ["OA", "DM", "DEPT"].includes(user?.role) ? ORG_ADMIN_SCOPE[resource]
    : saGate ? { needs: "org", param: null, ...ORG_ADMIN_SCOPE[resource], withOrg: true } : null;
  const gateValue = gate && gate.needs !== "org" ? orgScope[`${gate.needs}_id`] : null;
  const gateOpen = !gate || ((!gate.withOrg || !!orgScope.organisation_id) && (gate.needs === "org" || !!gateValue));

  const perm = boot?.resources?.[resource];
  const canWrite = perm?.can_write && !readOnly;            // may add
  const canEdit = canWrite && perm?.can_edit !== false;       // may change (nothing is ever deleted)
  // a role may be offered just the filters that matter to it
  const roleFilters = mod?.filtersFor?.[user?.role];
  const filterCols = (perm?.filters || []).filter((c) => !roleFilters || roleFilters.includes(c));
  const isSA = !!boot?.is_platform_admin;
  const orgOptions = boot?.options?.organisations || [];
  const orgScoped = resource !== "organisations";
  const orgFilter = sp.get("organisation_id") || "";

  // ---- read state from the URL (single source of truth) ----
  const page = Number(sp.get("page") || 1);
  const pageSize = Number(sp.get("page_size") || 15);
  const q = sp.get("q") || "";
  const sort = sp.get("sort") || "";
  const order = sp.get("order") || "desc";
  const filterValues = useMemo(() => {
    const v = {};
    for (const c of filterCols) if (sp.get(c) != null) v[c] = sp.get(c);
    return v;
  }, [sp, filterCols]);

  // Hide filters (and table columns) that repeat something already fixed by
  // this user's scope - e.g. a Trainer/Principal locked to one school
  // shouldn't be asked to "filter" by the only school they can ever see.
  // Row actions are workflow transitions the server gates by role
  // (workflow.py). Only offer the ones this role can actually complete.
  const rowActions = useMemo(
    () => (readOnly && !onlyActions ? [] : (mod?.rowActions || []))
      .filter((a) => typeof a === "string" || a.roles.includes(user?.role))
      .map((a) => (typeof a === "string" ? a : a.action))
      .filter((a) => !onlyActions || onlyActions.includes(a)),
    [mod, user?.role, readOnly, onlyActions]
  );

  const profile = boot?.my_scope?.profile;
  const visibleFilterCols = useMemo(
    () => visibleFilters(filterCols, profile).filter((c) => !(fixedParams && c in fixedParams)),
    [filterCols, profile, fixedParams],
  );
  const shownColumns = useMemo(
    () => visibleColumns(mod?.columns || [], boot?.options, profile, user?.role),
    [mod, boot?.options, profile, user?.role]
  );

  // keep the search box in sync when navigating between modules
  useEffect(() => { setSearchInput(sp.get("q") || ""); }, [resource]); // eslint-disable-line

  // `?new=1` opens the create drawer on arrival, so a "Log today's attendance"
  // shortcut lands in the form rather than on the list in front of it.
  useEffect(() => {
    if (sp.get("new") !== "1") return;
    const next = new URLSearchParams(sp);
    next.delete("new");
    setSp(next, { replace: true });
    if (canWrite) setEditing({});
  }, [sp, canWrite]); // eslint-disable-line

  // A notification points at its record: `?focus=<id>` (older links said
  // `_open`). The list opens on the page that holds it; the row flashes.
  const focusId = sp.get("focus") || "";
  const [flashId, setFlashId] = useState(null);
  useEffect(() => {
    const legacy = sp.get("_open");
    if (!legacy) return;
    const next = new URLSearchParams(sp);
    next.delete("_open");
    next.delete("_act");
    next.set("focus", legacy);
    setSp(next, { replace: true });
  }, [sp]); // eslint-disable-line

  // helper: patch the URL params, resetting to page 1 for anything but paging
  const patch = (changes, resetPage = true) => {
    const next = new URLSearchParams(sp);
    for (const [k, val] of Object.entries(changes)) {
      if (val === "" || val == null) next.delete(k);
      else next.set(k, val);
    }
    if (resetPage && !("page" in changes)) next.set("page", "1");
    setSp(next, { replace: true });
  };

  // debounce the search box -> URL
  useEffect(() => {
    const t = setTimeout(() => {
      if ((sp.get("q") || "") !== searchInput) patch({ q: searchInput });
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]); // eslint-disable-line

  // ---- build the API query from URL state ----
  const apiParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("page", page);
    p.set("page_size", pageSize);
    if (q) p.set("search", q);
    if (sort) { p.set("sort", sort); p.set("order", order); }
    for (const [k, v] of Object.entries(filterValues)) if (v !== "" && k !== "new") p.set(k, v);
    if (isSA && orgFilter && orgScoped && !gate) p.set("organisation_id", orgFilter);
    if (gate?.withOrg && orgScope.organisation_id) p.set("organisation_id", orgScope.organisation_id);
    if (gate?.param && gateValue) p.set(gate.param, gateValue);
    for (const [k, v] of Object.entries(fixedParams || {})) p.set(k, v);
    if (focusId) p.set("focus", focusId);   // the server picks the page that holds it
    return p.toString();
  }, [page, pageSize, q, sort, order, filterValues, isSA, orgFilter, orgScoped, gate?.param, gate?.withOrg, gateValue, orgScope.organisation_id, fixedParams, focusId]); // eslint-disable-line

  const list = useQuery({
    queryKey: ["list", resource, apiParams],
    queryFn: async () => (await api.get(`/${resource}?${apiParams}`)).data,
    placeholderData: keepPreviousData,
    enabled: !!mod && gateOpen,
  });

  // the focused record arrived: stay on its page, flash its row for 2 seconds.
  // Not under the link's filters? It changed since (verified, resolved...):
  // drop those filters once and look again, so it still opens on the record.
  const widened = useRef("");
  useEffect(() => {
    const f = list.data?.focus;
    if (!focusId || !f || f.id !== focusId) return undefined;
    const next = new URLSearchParams(sp);
    if (!f.found && widened.current !== focusId && Object.keys(filterValues).length) {
      widened.current = focusId;
      for (const k of Object.keys(filterValues)) next.delete(k);
      next.delete("page");
      setSp(next, { replace: true });
      return undefined;
    }
    next.delete("focus");
    if (f.found) {
      next.set("page", String(f.page));
      setFlashId(focusId);
    } else {
      push("That record isn't in this list any more - it may have changed since the notification.", "info");
    }
    setSp(next, { replace: true });
    return undefined;
  }, [list.data, focusId]); // eslint-disable-line
  useEffect(() => {
    if (!flashId) return undefined;
    const t = setTimeout(() => setFlashId(null), 2200);
    return () => clearTimeout(t);
  }, [flashId]);

  const save = useMutation({
    mutationFn: async (payload) =>
      editing?.id
        ? (await api.put(`/${resource}/${editing.id}`, payload)).data
        : (await api.post(`/${resource}`, payload)).data,
    onSuccess: (saved) => {
      push(editing?.id ? "Saved changes" : `${mod.singular} created`, "success");
      if (saved?.login) setNewLogin({ name: saved.full_name, ...saved.login });   // (login.name wins when sent)
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["list", resource] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["targets", resource] });
    },
    onError: (e) => push(apiError(e), "error"),
  });

  const verifyStudent = useMutation({
    mutationFn: async (id) => (await api.post(`/workflow/students/${id}/verify`, { verification_status: "verified" })).data,
    onSuccess: () => {
      push("Student verified", "success");
      setWorkflow(null);
      for (const k of [["list", resource], ["view", resource], ["dashboard"], ["promotion"]]) qc.invalidateQueries({ queryKey: k });
    },
    onError: (e) => push(apiError(e), "error"),
  });

  // the org admin checks the TC and marks the student as left, for good
  const confirmLeft = useMutation({
    mutationFn: async (id) => (await api.post(`/promotion/students/${id}/left`)).data,
    onSuccess: (r) => {
      push(`Marked as left (${r.enrolment_status})`, "success");
      setWorkflow(null);
      for (const k of [["list", resource], ["view", resource], ["dashboard"], ["promotion"], ["roster"]]) qc.invalidateQueries({ queryKey: k });
    },
    onError: (e) => push(apiError(e), "error"),
  });

  // some records (a trainer's, a principal's) carry more than the list row
  // shows - their profile and tables - so the edit form opens the whole record
  const openEdit = async (r) => {
    if (!mod?.fetchOnEdit) { setEditing(r); return; }
    try {
      setEditing((await api.get(`/${resource}/${r.id}`)).data);
    } catch (e) {
      push(apiError(e), "error");
    }
  };

  // the Principal ticks attendance records and verifies them together; the
  // ticks are for what's on screen, so they clear when the list changes
  const bulkVerify = user?.role === "PR" && rowActions.includes("endorse");
  const [picked, setPicked] = useState(() => new Set());
  useEffect(() => { setPicked(new Set()); }, [apiParams]);
  const select = bulkVerify ? {
    can: (r) => r.endorsement_status !== "endorsed" && !r.past_year,
    ids: picked,
    toggle: (id) => setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    }),
    setAll: (ids) => setPicked(new Set(ids)),
  } : null;

  if (!mod) return <div className="card card-pad">Unknown module: {resource}</div>;

  const onSort = (key) => {
    if (sort === key) patch({ order: order === "asc" ? "desc" : "asc" }, false);
    else patch({ sort: key, order: "asc" }, false);
  };

  // With no search box the page size sits at the end of the filters row
  // instead of alone on a row of its own.
  // org admins narrow things down with the district / school picker and filters instead
  const showSearch = mod.searchable !== false && (perm?.search?.length ?? 0) > 0 && !["OA", "DM", "DEPT", "SA"].includes(user?.role);
  const toolbarRow = showSearch || (isSA && orgScoped && !gate);
  const pageSizeBox = (
    <select className="select pagesize" value={pageSize} onChange={(e) => patch({ page_size: e.target.value })} aria-label="Rows per page">
      {PAGE_SIZES.map((n) => <option key={n} value={n}>{n} / page</option>)}
    </select>
  );

  const rows = list.data?.data || [];
  const pg = list.data?.pagination || { total: 0, pages: 1, page };
  const from = pg.total === 0 ? 0 : (pg.page - 1) * pageSize + 1;
  const to = Math.min(pg.page * pageSize, pg.total);

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      {!embedded && (
        <div className="page-head">
          <div>
            <div className="crumb">{groupOf(mod, user?.role)}</div>
            <h1><span className="page-ico"><Icon name={resource} size={20} /></span>{mod.pageTitle || labelOf(mod, user?.role)}</h1>
          </div>
          <div className="page-actions">
            {!readOnly && (mod.pageActions || []).filter((a) => a.roles.includes(user?.role)).map((a) => (
              <button key={a.key} className="btn btn-ghost" onClick={() => setPageAction(a.key)}>{a.label}</button>
            ))}
            {canWrite && !hideCreate && (
              <button className="btn btn-accent" onClick={() => setEditing({})}><Plus size={16} /> {mod.addLabel || `New ${mod.singular}`}</button>
            )}
          </div>
        </div>
      )}

      {gate && <ScopePicker needs={gate.needs} scope={orgScope} isSA={!!gate.withOrg}
        setScope={(next) => { setOrgScope(next); patch({}); }} boot={boot} />}

      {!gateOpen && <ScopeEmpty needs={gate.needs} label={labelOf(mod, user?.role)} isSA={!!gate.withOrg} />}

      {gateOpen && mod.yearlyTarget && (
        <TargetProgress
          schoolId={gate?.needs === "school" ? gateValue : undefined}
          resource={resource}
          picked={{ academic_year: sp.get("academic_year"), class_grade: sp.get("class_grade"), lab_id: sp.get("lab_id") }}
          // show exactly the records counted towards that level and year
          onPick={(r) => patch({ academic_year: r.academic_year, class_grade: r.class_grade, lab_id: r.lab_id })}
        />
      )}

      {gateOpen && (<>
      {toolbarRow && (
      <div className="toolbar">
        {showSearch && (
          <div className="search-wrap">
            <span className="search-ico"><Search size={15} /></span>
            <input
              className="input search"
              placeholder={`${mod.searchHint || `Search ${mod.label.toLowerCase()}`}…`}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            {searchInput && <button className="search-clear" onClick={() => setSearchInput("")}>×</button>}
          </div>
        )}
        <div className="grow" />
        {isSA && orgScoped && !gate && (
          <select className={`select filter-ctl ${orgFilter ? "on" : ""}`} value={orgFilter} onChange={(e) => patch({ organisation_id: e.target.value })}>
            <option value="">All organisations</option>
            {orgOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        )}
        {pageSizeBox}
      </div>
      )}

      <Filters
        filters={visibleFilterCols}
        fields={mod.fields}
        boot={boot}
        values={filterValues}
        onChange={(col, val) => patch({ [col]: val })}
        onClear={() => patch(Object.fromEntries(filterCols.map((c) => [c, ""])))}
        aside={toolbarRow ? null : pageSizeBox}
        schoolId={gate?.needs === "school" ? gateValue : undefined}
      />

      {shownColumns.some((c) => c.dot === "distance") && <DistanceLegend />}
      {shownColumns.some((c) => c.dot === "endorsement") && <EndorsementLegend />}

      <DataTable
        columns={shownColumns}
        rows={rows}
        flashId={flashId}
        loading={list.isLoading}
        sort={sort}
        order={order}
        onSort={onSort}
        canWrite={canEdit}
        rowActions={rowActions}
        onEdit={openEdit}
        onRowAction={(action, r) => setWorkflow({ action, row: r })}
        emptyHint={EMPTY_HINTS[resource]?.[user?.role]}
        emptyAction={canWrite && !hideCreate ? (mod.addLabel || `New ${mod.singular}`) : null}
        onEmptyAction={() => setEditing({})}
        select={select}
      />

      {bulkVerify && rows.some((r) => select.can(r)) && (
        <BulkVerify resource={resource} ids={picked} onClear={() => setPicked(new Set())}
          onDone={() => { setPicked(new Set()); qc.invalidateQueries({ queryKey: ["list", resource] }); }} />
      )}

      <div className="pager">
        <span className="info">
          {list.isFetching ? "Loading…" : `Showing ${from}–${to} of ${pg.total}`}
        </span>
        <button className="btn btn-ghost btn-sm" aria-label="First page" disabled={pg.page <= 1} onClick={() => patch({ page: 1 }, false)}><ChevronsLeft size={15} /><span className="pager-word"> First</span></button>
        <button className="btn btn-ghost btn-sm" aria-label="Previous page" disabled={pg.page <= 1} onClick={() => patch({ page: pg.page - 1 }, false)}><ChevronLeft size={15} /><span className="pager-word"> Prev</span></button>
        <span className="page-num">Page {pg.page} / {pg.pages || 1}</span>
        <button className="btn btn-ghost btn-sm" aria-label="Next page" disabled={pg.page >= (pg.pages || 1)} onClick={() => patch({ page: pg.page + 1 }, false)}><span className="pager-word">Next </span><ChevronRight size={15} /></button>
        <button className="btn btn-ghost btn-sm" aria-label="Last page" disabled={pg.page >= (pg.pages || 1)} onClick={() => patch({ page: pg.pages }, false)}><span className="pager-word">Last </span><ChevronsRight size={15} /></button>
      </div>
      </>)}

      {editing !== null && (
        <ResourceForm
          resource={resource}
          mod={mod}
          initial={editing.id ? editing : null}
          boot={boot}
          context={gate ? {
            ...formContext, state_id: orgScope.state_id, district_id: orgScope.district_id,
            school_id: orgScope.school_id, linked_school_id: orgScope.school_id,
          } : formContext}
          isSA={isSA}
          orgScoped={orgScoped}
          orgOptions={orgOptions}
          role={user?.role}
          saving={save.isPending}
          onClose={() => setEditing(null)}
          onSubmit={(payload) => save.mutate(payload)}
        />
      )}

      {pageAction === "promote" && (
        <PromoteDialog
          onClose={() => setPageAction(null)}
          onDone={() => {
            setPageAction(null);
            qc.invalidateQueries({ queryKey: ["list", resource] });
            qc.invalidateQueries({ queryKey: ["promotion"] });
            qc.invalidateQueries({ queryKey: ["roster"] });
          }}
        />
      )}

      {workflow?.action === "history" && (
        <StudentHistory row={workflow.row} onClose={() => setWorkflow(null)} />
      )}

      {newLogin && <LoginCreated {...newLogin} onDone={() => setNewLogin(null)} />}

      {workflow?.action === "view" && (
        <RecordView mod={mod} resource={resource} row={workflow.row} onClose={() => setWorkflow(null)} />
      )}

      {workflow?.action === "verify" && resource === "students" && (
        <RecordView
          mod={mod} resource={resource} row={workflow.row} onClose={() => setWorkflow(null)}
          title={`Verify ${workflow.row.full_name || "student"}`}
          subtitle="Check every detail below, then verify the student."
          footer={(rec) => (
            <>
              <button type="button" className="btn btn-ghost" onClick={() => setWorkflow(null)}>Close</button>
              <button type="button" className="btn btn-primary"
                disabled={verifyStudent.isPending || rec.verification_status === "verified"}
                onClick={() => verifyStudent.mutate(rec.id)}>
                {verifyStudent.isPending ? "Verifying…" : rec.verification_status === "verified" ? "Verified" : "Verify student"}
              </button>
            </>
          )}
        />
      )}

      {workflow?.action === "record" && (
        <RecordView mod={mod} resource={resource} row={workflow.row} onClose={() => setWorkflow(null)}
          title={workflow.row.full_name || mod.singular}
          subtitle={[workflow.row.status_label || workflow.row.enrolment_status, workflow.row.school_name].filter(Boolean).join(" · ")}>
          {() => (
            <section className="view-section">
              <h4 className="view-section-title">History</h4>
              <HistoryList studentId={workflow.row.id} />
            </section>
          )}
        </RecordView>
      )}

      {workflow?.action === "resolve" && (
        <ResolveDialog resource={resource} row={workflow.row} onClose={() => setWorkflow(null)}
          onDone={() => { setWorkflow(null); for (const k of [["list", resource], ["dashboard"]]) qc.invalidateQueries({ queryKey: k }); }} />
      )}

      {workflow?.action === "tc" && (
        <TcIssueDialog row={workflow.row} onClose={() => setWorkflow(null)}
          onDone={() => { setWorkflow(null); qc.invalidateQueries({ queryKey: ["list", resource] }); }} />
      )}

      {workflow?.action === "leftverify" && (
        <RecordView mod={mod} resource={resource} row={workflow.row} onClose={() => setWorkflow(null)}
          title={`Verify TC · ${workflow.row.full_name || "Student"}`}
          subtitle="Check the Transfer Certificate, then mark the student as left."
          footer={(rec) => (
            <>
              <button type="button" className="btn btn-ghost" onClick={() => setWorkflow(null)}>Close</button>
              <button type="button" className="btn btn-danger" disabled={confirmLeft.isPending || rec.leaving_stage !== "tc_issued"}
                onClick={() => confirmLeft.mutate(rec.id)}>
                {confirmLeft.isPending ? "Saving…" : `Verify TC & mark as left`}
              </button>
            </>
          )}>
          {(rec) => (
            <section className="view-section tc-block">
              <h4 className="view-section-title">Transfer Certificate</h4>
              <dl className="view-grid">
                <div className="view-item"><dt>Leaving as</dt><dd>{rec.leaving_type || "—"}</dd></div>
                <div className="view-item"><dt>Reason (from the trainer)</dt><dd>{rec.left_reason || "—"}</dd></div>
                <div className="view-item"><dt>TC number</dt><dd>{rec.tc_number || "—"}</dd></div>
                <div className="view-item"><dt>TC date</dt><dd>{toDMY(rec.tc_issued_on) || "—"}</dd></div>
                <div className="view-item wide"><dt>Photo of the TC</dt><dd>
                  {rec.tc_src ? <a href={rec.tc_src} target="_blank" rel="noreferrer"><img className="view-photo" src={rec.tc_src} alt="TC" /></a>
                    : <span className="muted">{rec.tc_url ? "Attached (not available here)" : "No photo"}</span>}
                </dd></div>
              </dl>
            </section>
          )}
        </RecordView>
      )}

      {workflow && !["history", "view", "record", "tc", "leftverify", "resolve"].includes(workflow.action) && !(workflow.action === "verify" && resource === "students") && (
        <WorkflowDialog
          resource={resource}
          action={workflow.action}
          row={workflow.row}
          onClose={() => setWorkflow(null)}
          onDone={() => { setWorkflow(null); qc.invalidateQueries({ queryKey: ["list", resource] }); }}
        />
      )}
    </div>
  );
}
