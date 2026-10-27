import type { Metadata } from "next";
import { Suspense } from "react";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { Providers } from "@/components/providers";
import "./globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "agentfront 管理",
  description: "事業者カタログの生成、公開、コンバージョンを扱う運営者画面",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>
        <AntdRegistry>
          <Suspense fallback={null}>
            <Providers>{children}</Providers>
          </Suspense>
        </AntdRegistry>
      </body>
    </html>
  );
}
