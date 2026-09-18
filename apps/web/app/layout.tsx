import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "FlowRAGA",
  description: "Build, test, and evaluate RAG pipelines visually.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

