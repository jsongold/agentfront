"use client";

import type { CompletenessReport } from "@/lib/types";
import { Alert, Space, Tag, Typography } from "antd";

export function CompletenessAlert({ report }: { report: CompletenessReport | null | undefined }) {
  if (!report || (report.missing.length === 0 && report.empty.length === 0)) return null;
  const items = [
    ...report.missing.map((item) => ({ ...item, kind: "未設定" as const })),
    ...report.empty.map((item) => ({ ...item, kind: "空欄" as const })),
  ];
  return (
    <Alert
      type="warning"
      showIcon
      message={`必須項目の充足率 ${report.score}%（${report.filled}/${report.total}）`}
      description={
        <Space direction="vertical" size={4}>
          <Typography.Text type="secondary">
            業種「{report.title || report.profile}」で買い手が比較に使う項目です。
          </Typography.Text>
          {items.map((item) => (
            <div key={`${item.kind}-${item.key}`}>
              <Tag color={item.kind === "未設定" ? "red" : "orange"}>{item.kind}</Tag>
              {item.title}
            </div>
          ))}
        </Space>
      }
    />
  );
}
