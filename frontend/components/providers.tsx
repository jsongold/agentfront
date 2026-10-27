"use client";

import { Refine } from "@refinedev/core";
import { RefineThemes, ThemedLayout, ThemedTitle, useNotificationProvider } from "@refinedev/antd";
import routerProvider from "@refinedev/nextjs-router";
import dataProvider from "@refinedev/simple-rest";
import { AimOutlined, LineChartOutlined, MessageOutlined, SafetyCertificateOutlined, ShopOutlined } from "@ant-design/icons";
import { App as AntdApp, ConfigProvider } from "antd";
import jaJP from "antd/locale/ja_JP";
import axios from "axios";
import "@refinedev/antd/dist/reset.css";

const http = axios.create();
http.interceptors.request.use((config) => {
  const token = process.env.NEXT_PUBLIC_ADMIN_TOKEN;
  if (token) {
    config.headers["X-Admin-Token"] = token;
  }
  return config;
});

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Refine
      routerProvider={routerProvider}
      dataProvider={dataProvider("/backend-api/api", http)}
      notificationProvider={useNotificationProvider}
      resources={[
        {
          name: "businesses",
          list: "/businesses",
          create: "/businesses/create",
          show: "/businesses/show/:id",
          meta: { label: "事業者", icon: <ShopOutlined /> },
        },
        {
          name: "conversion-points",
          list: "/conversion-points",
          meta: { label: "コンバージョン地点", icon: <AimOutlined /> },
        },
        {
          name: "conversions",
          list: "/conversions",
          show: "/conversions/show/:id",
          meta: { label: "受信した依頼", icon: <MessageOutlined /> },
        },
        {
          name: "analytics",
          list: "/analytics",
          meta: { label: "計測", icon: <LineChartOutlined /> },
        },
        {
          name: "diagnostics",
          list: "/diagnostics",
          meta: { label: "エージェント可視性診断", icon: <SafetyCertificateOutlined /> },
        },
      ]}
      options={{ syncWithLocation: true, warnWhenUnsavedChanges: false }}
    >
      <ThemedLayout Title={({ collapsed }) => <ThemedTitle collapsed={collapsed} text="agentfront" />}>
        {children}
      </ThemedLayout>
    </Refine>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider locale={jaJP} theme={RefineThemes.Blue}>
      <AntdApp>
        <Shell>{children}</Shell>
      </AntdApp>
    </ConfigProvider>
  );
}
