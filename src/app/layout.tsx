import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Binance Futures Bot Dashboard",
  description: "Binance USDT-M Futures Auto Trading Bot Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
