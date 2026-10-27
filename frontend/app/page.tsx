"use client";

import { api } from "@/lib/api";
import { statusOf, typeLabel } from "@/lib/labels";
import type { AnalyticsSummary, MetaInfo } from "@/lib/types";
import { Alert, Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function when(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ja-JP");
}

export default function HomePage() {
  const [meta, setMeta] = useState<MetaInfo | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([api<MetaInfo>("/meta"), api<AnalyticsSummary>("/analytics/summary")])
      .then(([nextMeta, nextSummary]) => {
        setMeta(nextMeta);
        setSummary(nextSummary);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "管理APIに接続できません");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          エージェント向けカタログ
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          URLと短い説明から、AIエージェントが読んで比較し、見積依頼や問い合わせまで進めるカタログを作ります。公開ページ、JSON-LD、フィード、MCPは同じ中央モデルから出ます。
        </Typography.Paragraph>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          message="管理APIに接続できません"
          description={error}
          action={
            <Button size="small" onClick={load}>
              再読み込み
            </Button>
          }
        />
      ) : null}

      {meta && !meta.llm_configured ? (
        <Alert type="warning" showIcon message="生成にはAPIキーが必要です" description={meta.llm_hint} />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic title="公開中の事業者" value={summary?.businesses_published ?? 0} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic title="MCP呼び出し" value={summary?.totals.mcp_calls ?? 0} suffix="件 / 14日" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic title="エージェントページ取得" value={summary?.totals.page_fetches ?? 0} suffix="件 / 14日" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic title="コンバージョン" value={summary?.totals.conversions ?? 0} suffix="件 / 14日" />
          </Card>
        </Col>
      </Row>

      {meta ? (
        <Card title="接続先">
          <Space direction="vertical">
            <div>
              公開カタログ:{" "}
              <Typography.Link href={meta.public_base_url} target="_blank">
                {meta.public_base_url}
              </Typography.Link>
            </div>
            <div>
              MCP（streamable HTTP）: <Typography.Text code>{meta.mcp_url}</Typography.Text>
            </div>
            <div>
              受信メール（Mailpit）:{" "}
              <Typography.Link href={meta.mailpit_url} target="_blank">
                {meta.mailpit_url}
              </Typography.Link>
            </div>
            <div>
              生成モデル: <Typography.Text code>{meta.llm_model}</Typography.Text>
              {meta.llm_api_base ? (
                <>
                  {" "}
                  （<Typography.Text code>{meta.llm_api_base}</Typography.Text>）
                </>
              ) : null}
              {meta.llm_configured ? "（キー設定済み）" : "（キー未設定）"}
            </div>
          </Space>
        </Card>
      ) : null}

      <Card
        title="最近の依頼"
        extra={<Link href="/conversions">一覧へ</Link>}
      >
        <Table
          rowKey="id"
          loading={loading}
          pagination={false}
          dataSource={summary?.recent_conversions ?? []}
          locale={{ emptyText: "まだ記録がありません" }}
          scroll={{ x: 720 }}
        >
          <Table.Column
            title="日時"
            dataIndex="created_at"
            render={(value: string) => when(value)}
          />
          <Table.Column title="事業者" dataIndex="business_name" />
          <Table.Column
            title="種別"
            dataIndex="conversion_type"
            render={(value: string) => typeLabel(value)}
          />
          <Table.Column title="地点" dataIndex="conversion_name" />
          <Table.Column
            title="状態"
            dataIndex="status"
            render={(value: string) => {
              const status = statusOf(value);
              return <Tag color={status.color}>{status.label}</Tag>;
            }}
          />
          <Table.Column title="エージェント" dataIndex="agent_name" render={(value: string | null) => value || "—"} />
          <Table.Column
            title=""
            render={(_, row: { id: string }) => <Link href={`/conversions/show/${row.id}`}>詳細</Link>}
          />
        </Table>
      </Card>
    </Space>
  );
}
