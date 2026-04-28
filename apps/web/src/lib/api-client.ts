import axios from "axios";

/**
 * All requests go through Next.js's `/api/proxy/*` route handler (Task 8),
 * which forwards to the FastAPI backend with cookies attached. This avoids
 * CORS pain in the browser and centralizes 401-redirect handling.
 */
export const api = axios.create({
  baseURL: "/api/proxy",
  withCredentials: true,
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (
      typeof window !== "undefined" &&
      error.response?.status === 401 &&
      !window.location.pathname.endsWith("/login")
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
