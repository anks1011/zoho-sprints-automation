import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ToastProvider } from "@/components/ui/Toast";

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
        <ToastProvider>
          <div className="app-shell">
            <Sidebar />
            <div className="main-content">
              <Header />
              <main>{children}</main>
            </div>
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}
