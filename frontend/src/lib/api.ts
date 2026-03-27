import axios from "axios";
import { resolveBackendApiUrl, resolveScrapingApiUrl } from "@/lib/service-urls";

export const api = axios.create({
  baseURL: resolveBackendApiUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

export const scrapingApi = axios.create({
  baseURL: resolveScrapingApiUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  },
);

scrapingApi.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  },
);
