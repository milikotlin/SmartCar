import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  devIndicators: false, // no development badge on the demonstration screens
};

export default withNextIntl(nextConfig);
