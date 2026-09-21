import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "Zoho Sprints AI Automation | Story & Task Management",
  description: "Automated AI task breakdown, dependency mapping, and idempotent subtask creation for Zoho Sprints.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main-content">
            <Header />
            <main>{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
