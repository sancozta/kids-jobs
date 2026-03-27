import axios from "axios";
import { resolveAgentApiUrl, resolveBackendApiUrl, resolveCpfApiUrl, resolveScrapingApiUrl } from "@/lib/service-urls";

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

export const agentApi = axios.create({
  baseURL: resolveAgentApiUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

export const cpfApi = axios.create({
  baseURL: resolveCpfApiUrl(),
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

agentApi.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  },
);

cpfApi.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  },
);
