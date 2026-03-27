import type { NextConfig } from "next";

const LEGACY_REDIRECT_ROUTES = [
  "/login",
  "/users",
  "/companies",
  "/agronegocio",
  "/categories",
  "/cnpj",
  "/cpf",
  "/domain-monitors",
  "/imoveis",
  "/licitacoes",
  "/market",
  "/notifications",
  "/origins",
  "/settings",
] as const;

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      ...LEGACY_REDIRECT_ROUTES.map((source) => ({
        source,
        destination: "/vagas",
        permanent: false,
      })),
      {
        source: "/cpf/:path*",
        destination: "/vagas",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
