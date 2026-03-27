import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return [
      {
        source: "/users",
        destination: "/cpf",
        permanent: true,
      },
      {
        source: "/companies",
        destination: "/cnpj",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
