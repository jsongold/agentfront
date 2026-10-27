"use client";

import { statusOf, typeLabel } from "@/lib/labels";
import type { ConversionRow } from "@/lib/types";
import { useShow } from "@refinedev/core";
import { Alert, Card, Descriptions, Space, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useParams } from "next/navigation";

export default function ConversionShowPage() {
  const params = useParams<{ id: string }>();
  const { query, result } = useShow<ConversionRow>({ resource: "conversions", id: params.id });
  const status = statusOf(result?.status);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Link href="/conversions">依頼一覧へ戻る</Link>
        <Typography.Title level={3} style={{ marginTop: 8 }}>
          {result?.conversion_name || "依頼"}
        </Typography.Title>
        <Tag color={status.color}>{status.label}</Tag>
      </div>
      {query.isError ? <Alert type="error" showIcon message="依頼を読み込めません" description={query.error?.message} /> : null}
      <Card loading={query.isLoading && !result}>
        <Descriptions bordered size="small" column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="事業者">{result?.business_name}</Descriptions.Item>
          <Descriptions.Item label="種別">{typeLabel(result?.conversion_type)}</Descriptions.Item>
          <Descriptions.Item label="エージェント">{result?.agent_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="分類">{result?.agent_class || "—"}</Descriptions.Item>
          <Descriptions.Item label="日時" span={2}>
            {result?.created_at ? new Date(result.created_at).toLocaleString("ja-JP") : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="依頼文" span={2}>
            {result?.request_text || "—"}
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="入力内容" loading={query.isLoading && !result}>
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(result?.payload ?? {}, null, 2)}</pre>
      </Card>
      <Card title="送信結果">
        <Table
          rowKey="id"
          pagination={false}
          dataSource={result?.deliveries ?? []}
          locale={{ emptyText: "送信記録がありません" }}
        >
          <Table.Column dataIndex="adapter_key" title="アダプタ" />
          <Table.Column
            dataIndex="status"
            title="状態"
            render={(value: string) => {
              const item = statusOf(value);
              return <Tag color={item.color}>{item.label}</Tag>;
            }}
          />
          <Table.Column dataIndex="detail" title="詳細" render={(value: string | null) => value || "—"} />
        </Table>
      </Card>
    </Space>
  );
}
