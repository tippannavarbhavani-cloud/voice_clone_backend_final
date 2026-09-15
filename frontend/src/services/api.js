import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

const ACCESS_KEY = "trueline_access_token";
const REFRESH_KEY = "trueline_refresh_token";

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// If a request 401s, try once to refresh the access token before giving up.
let refreshPromise = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const refresh = tokenStore.getRefresh();

    if (error.response?.status === 401 && refresh && !original._retried) {
      original._retried = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_BASE_URL}/api/auth/refresh/`, { refresh })
            .finally(() => {
              refreshPromise = null;
            });
        }
        const { data } = await refreshPromise;
        tokenStore.set(data.access, refresh);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        tokenStore.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------- Auth ----------
export async function registerUser(payload) {
  const { data } = await api.post("/api/auth/register/", payload);
  tokenStore.set(data.access, data.refresh);
  return data;
}

export async function loginUser(payload) {
  const { data } = await api.post("/api/auth/login/", payload);
  tokenStore.set(data.access, data.refresh);
  return data;
}

export async function logoutUser() {
  const refresh = tokenStore.getRefresh();
  try {
    if (refresh) await api.post("/api/auth/logout/", { refresh });
  } finally {
    tokenStore.clear();
  }
}

export async function getProfile() {
  const { data } = await api.get("/api/auth/profile/");
  return data;
}

export async function updateProfile(payload) {
  const { data } = await api.patch("/api/auth/profile/", payload);
  return data;
}

// ---------- Analyze ----------
export async function analyzeFile(file, source = "upload") {
  const formData = new FormData();
  formData.append("audio_file", file);
  formData.append("source", source);
  const { data } = await api.post("/api/detection/analyze/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function analyzeUrl(audioUrl) {
  const { data } = await api.post("/api/detection/analyze-url/", { audio_url: audioUrl });
  return data;
}

export function buildLiveDetectSocketUrl() {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  const token = tokenStore.getAccess();
  return `${wsBase}/ws/live-detect/?token=${token}`;
}

// ---------- Dashboard ----------
export async function getDashboard() {
  const { data } = await api.get("/api/detection/dashboard/");
  return data;
}

// ---------- History ----------
export async function getHistory(params = {}) {
  const { data } = await api.get("/api/detection/history/", { params });
  return data;
}

export async function getHistoryDetail(id) {
  const { data } = await api.get(`/api/detection/history/${id}/`);
  return data;
}

export async function deleteHistoryItem(id) {
  await api.delete(`/api/detection/history/${id}/`);
}

// ---------- Settings / preferences ----------
export async function getPreferences() {
  const { data } = await api.get("/api/detection/preferences/");
  return data;
}

export async function updatePreferences(payload) {
  const { data } = await api.patch("/api/detection/preferences/", payload);
  return data;
}

// ---------- Security alerts ----------
export async function getAlerts(params = {}) {
  const { data } = await api.get("/api/detection/alerts/", { params });
  return data;
}

export async function acknowledgeAlert(id) {
  const { data } = await api.post(`/api/detection/alerts/${id}/acknowledge/`);
  return data;
}

export default api;
