import "./globals.css";

export const metadata = {
  title: "DUAT Arena",
  description:
    "Stress testing for trading bots and AI agents — survive flash crashes, liquidity shocks, and panic markets.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
