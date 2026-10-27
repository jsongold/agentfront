"use client";

import { api } from "@/lib/api";
import type { AnalyticsSummary } from "@/lib/types";
import { Alert, Card, Col, Row, Statistic, Table, Typography } from "antd";
import { useEffect, useState } from "react";

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AnalyticsSummary>("/analytics/summary")
      .then(setSummary)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "計測を読み込めません"));
  }, []);

  return (
    <div>
      <Typography.Title level={3}>計測</Typography.Title>
      <Typography.Paragraph type="secondary">
        こちらで見えるのは、MCPのツール呼び出し、エージェント向けページの取得、届いたコンバージョンです。エージェント内部の比較や検討は記録されません。
      </Typography.Paragraph>
      {error ? <Alert type="error" showIcon message={error} /> : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="MCP呼び出し" value={summary?.totals.mcp_calls ?? 0} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="ページ取得" value={summary?.totals.page_fetches ?? 0} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="コンバージョン" value={summary?.totals.conversions ?? 0} />
          </Card>
        </Col>
      </Row>
      <Card title="MCP呼び出し（ツール別）" style={{ marginTop: 16 }}>
        <Table
          rowKey={(row) => `${row.day}-${row.label}`}
          loading={!summary && !error}
          dataSource={summary?.mcp_calls ?? []}
          pagination={false}
          locale={{ emptyText: "まだ記録がありません" }}
        >
          <Table.Column dataIndex="day" title="日" />
          <Table.Column dataIndex="label" title="ツール" />
          <Table.Column dataIndex="count" title="件数" />
        </Table>
      </Card>
      <Card title="ページ取得（クローラ別）" style={{ marginTop: 16 }}>
        <Table
          rowKey={(row) => `${row.day}-${row.label}`}
          loading={!summary && !error}
          dataSource={summary?.page_fetches ?? []}
          pagination={false}
          locale={{ emptyText: "まだ記録がありません" }}
        >
          <Table.Column dataIndex="day" title="日" />
          <Table.Column dataIndex="label" title="分類" />
          <Table.Column dataIndex="count" title="件数" />
        </Table>
      </Card>
      <Card title="コンバージョン（種別）" style={{ marginTop: 16 }}>
        <Table
          rowKey={(row) => `${row.day}-${row.label}`}
          loading={!summary && !error}
          dataSource={summary?.conversions ?? []}
          pagination={false}
          locale={{ emptyText: "まだ記録がありません" }}
        >
          <Table.Column dataIndex="day" title="日" />
          <Table.Column dataIndex="label" title="種別" />
          <Table.Column dataIndex="count" title="件数" />
        </Table>
      </Card>
    </div>
  );
}
