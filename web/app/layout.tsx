import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jhalak · Promos that hook in 10 seconds",
  description:
    "Drop a Google Drive folder of microdrama episodes. Jhalak watches and listens to every episode and cuts three ready-to-run promos with Indian-language narration and a cliffhanger ending.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
