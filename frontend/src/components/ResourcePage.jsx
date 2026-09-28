import { useState, useEffect, useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { MODULES, groupOf, ORG_ADMIN_SCOPE } from "../lib/modules";
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
import StudentHistory from "./StudentHistory";
import RecordView from "./RecordView";
import LoginCreated from "./LoginCreated";
import { DistanceLegend, EndorsementLegend } from "./DistanceDot";
import { visibleFilters, visibleColumns } from "../lib/scope";
import { EMPTY_HINTS } from "../lib/roleUi";

const CONTROL_KEYS = ["page", "page_size", "q", "sort", "order", "new"];
const PAGE_SIZES = [15, 25, 50, 100];

/* One module's list: search, filters, table, paging, and the create/edit
   drawer. Can also be embedded in another page (the Students tabs):
     resourceKey  which module, instead of the URL's
     embedded     no page heading - the host page has its own
     readOnly     a list to look at: no create, edit, delete or row actions
     onlyActions  row actions to keep (e.g. ["verify"])
     hideCreate   no "New" button (the host adds records its own way)        */
export default function ResourcePage({ resourceKey, embedded, readOnly, onlyActions, hideCreate } = {}) {
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

  // an org admin picks a district, then a school, before anything is listed
  const [orgScope, setOrgScope] = useOrgScope();
  const gate = user?.role === "OA" ? ORG_ADMIN_SCOPE[resource] : null;
  const gateValue = gate ? orgScope[`${gate.needs}_id`] : null;
  const gateOpen = !gate || !!gateValue;

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
  const visibleFilterCols = useMemo(() => visibleFilters(filterCols, profile), [filterCols, profile]);
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
    if (isSA && orgFilter && orgScoped) p.set("organisation_id", orgFilter);
    if (gate && gateValue) p.set(gate.param, gateValue);
    return p.toString();
  }, [page, pageSize, q, sort, order, filterValues, isSA, orgFilter, orgScoped, gate, gateValue]);

  const list = useQuery({
    queryKey: ["list", resource, apiParams],
    queryFn: async () => (await api.get(`/${resource}?${apiParams}`)).data,
    placeholderData: keepPreviousData,
    enabled: !!mod && gateOpen,
  });

  const save = useMutation({
    mutationFn: async (payload) =>
      editing?.id
        ? (await api.put(`/${resource}/${editing.id}`, payload)).data
        : (await api.post(`/${resource}`, payload)).data,
    onSuccess: (saved) => {
      push(editing?.id ? "Saved changes" : `${mod.singular} created`, "success");
      if (saved?.login) setNewLogin({ name: saved.full_name, ...saved.login });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["list", resource] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["targets", resource] });
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

  if (!mod) return <div className="card card-pad">Unknown module: {resource}</div>;

  const onSort = (key) => {
    if (sort === key) patch({ order: order === "asc" ? "desc" : "asc" }, false);
    else patch({ sort: key, order: "asc" }, false);
  };

  // With no search box the page size sits at the end of the filters row
  // instead of alone on a row of its own.
  // org admins narrow things down with the district / school picker and filters instead
  const showSearch = mod.searchable !== false && (perm?.search?.length ?? 0) > 0 && user?.role !== "OA";
  const toolbarRow = showSearch || (isSA && orgScoped);
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
            <h1>{mod.icon} {mod.label}</h1>
          </div>
          <div className="page-actions">
            {!readOnly && (mod.pageActions || []).filter((a) => a.roles.includes(user?.role)).map((a) => (
              <button key={a.key} className="btn btn-ghost" onClick={() => setPageAction(a.key)}>{a.label}</button>
            ))}
            {canWrite && !hideCreate && (
              <button className="btn btn-accent" onClick={() => setEditing({})}>＋ New {mod.singular}</button>
            )}
          </div>
        </div>
      )}

      {gate && <ScopePicker needs={gate.needs} scope={orgScope} setScope={(next) => { setOrgScope(next); patch({}); }} boot={boot} />}

      {!gateOpen && <ScopeEmpty needs={gate.needs} label={mod.label} />}

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
            <span className="search-ico">🔍</span>
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
        {isSA && orgScoped && (
          <select className={`select filter-ctl ${orgFilter ? "on" : ""}`} value={orgFilter} onChange={(e) => patch({ organisation_id: e.target.value })}>
            <option value="">🏢 All organisations</option>
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
        loading={list.isLoading}
        sort={sort}
        order={order}
        onSort={onSort}
        canWrite={canEdit}
        rowActions={rowActions}
        onEdit={openEdit}
        onRowAction={(action, r) => setWorkflow({ action, row: r })}
        emptyHint={EMPTY_HINTS[resource]?.[user?.role]}
        emptyAction={canWrite && !hideCreate ? `New ${mod.singular}` : null}
        onEmptyAction={() => setEditing({})}
      />

      <div className="pager">
        <span className="info">
          {list.isFetching ? "Loading…" : `Showing ${from}–${to} of ${pg.total}`}
        </span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page <= 1} onClick={() => patch({ page: 1 }, false)}>« First</button>
        <button className="btn btn-ghost btn-sm" disabled={pg.page <= 1} onClick={() => patch({ page: pg.page - 1 }, false)}>‹ Prev</button>
        <span className="page-num">Page {pg.page} / {pg.pages || 1}</span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page >= (pg.pages || 1)} onClick={() => patch({ page: pg.page + 1 }, false)}>Next ›</button>
        <button className="btn btn-ghost btn-sm" disabled={pg.page >= (pg.pages || 1)} onClick={() => patch({ page: pg.pages }, false)}>Last »</button>
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

      {workflow && !["history", "view"].includes(workflow.action) && (
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
