import axios from "axios";

// Axios instance with JWT + transparent refresh (spec Part 7.8).
const api = axios.create({ baseURL: "/api" });

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export const tokens = {
  get access() { return localStorage.getItem("rnaf_access"); },
  get refresh() { return localStorage.getItem("rnaf_refresh"); },
  set({ access, refresh }) {
    if (access) localStorage.setItem("rnaf_access", access);
    if (refresh) localStorage.setItem("rnaf_refresh", refresh);
  },
  clear() {
    localStorage.removeItem("rnaf_access");
    localStorage.removeItem("rnaf_refresh");
  },
};

api.interceptors.request.use((config) => {
  const t = tokens.access;
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const { config, response } = error;
    if (response?.status === 401 && !config._retry && tokens.refresh) {
      config._retry = true;
      try {
        refreshing = refreshing || axios.post("/api/auth/refresh", {}, {
          headers: { Authorization: `Bearer ${tokens.refresh}` },
        });
        const { data } = await refreshing;
        refreshing = null;
        tokens.set({ access: data.access_token });
        config.headers.Authorization = `Bearer ${data.access_token}`;
        return api(config);
      } catch (e) {
        refreshing = null;
        tokens.clear();
        onUnauthorized();
        return Promise.reject(e);
      }
    }
    if (response?.status === 401) {
      tokens.clear();
      onUnauthorized();
    }
    return Promise.reject(error);
  }
);

export const apiError = (err) =>
  err?.response?.data?.message || err?.response?.data?.error || err.message || "Something went wrong";

export default api;
