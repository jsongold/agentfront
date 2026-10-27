"use client";

import { api } from "@/lib/api";
import type {
  DiagnosticAgentFile,
  DiagnosticBotAccess,
  DiagnosticCheck,
  DiagnosticReport,
  DiagnosticSummary,
} from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Input,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useState } from "react";

const GRADE_COLOR: Record<string, string> = {
  A: "green",
  B: "blue",
  C: "gold",
  D: "orange",
  E: "red",
};

function when(value: string) {
  return new Date(value).toLocaleString("ja-JP");
}

export default function DiagnosticsPage() {
  const [url, setUrl] = useState("");
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [history, setHistory] = useState<DiagnosticSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(() => {
    api<DiagnosticSummary[]>("/diagnostics")
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  async function runDiagnostic() {
    const target = url.trim();
    if (!target) {
      setError("URLを入力してください");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await api<DiagnosticReport>("/diagnostics", {
        method: "POST",
        body: JSON.stringify({ url: target }),
      });
      setReport(next);
      loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "診断に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          エージェント可視性診断
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          任意のURLを取得し、AIエージェントがページを読めるか、robots.txtで拒否されていないか、構造化データやエージェント向けファイルがあるかを採点します。JavaScriptは実行しません。
        </Typography.Paragraph>
      </div>

      <Card>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            size="large"
            placeholder="https://example.com/"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onPressEnter={runDiagnostic}
          />
          <Button type="primary" size="large" loading={loading} onClick={runDiagnostic}>
            診断する
          </Button>
        </Space.Compact>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          公開URLのみ診断できます。ローカルやプライベートなアドレスは既定で拒否されます。
        </Typography.Paragraph>
      </Card>

      {error ? <Alert type="error" showIcon message="診断できませんでした" description={error} /> : null}

      {report ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic title="スコア" value={report.score} suffix="/ 100" />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="グレード"
                  value={report.grade}
                  suffix={<Tag color={GRADE_COLOR[report.grade] ?? "default"}>{report.grade}</Tag>}
                />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic title="読み取れた本文" value={report.text.characters} suffix="文字" />
              </Card>
            </Col>
          </Row>

          <Card title="取得結果">
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="URL">
                <Typography.Link href={report.final_url} target="_blank">
                  {report.final_url}
                </Typography.Link>
              </Descriptions.Item>
              <Descriptions.Item label="HTTPステータス">
                {report.fetch.status ?? "—"}
              </Descriptions.Item>
              <Descriptions.Item label="Content-Type">
                {report.fetch.content_type || "—"}
              </Descriptions.Item>
              <Descriptions.Item label="サイズ">
                {report.fetch.bytes.toLocaleString("ja-JP")} bytes
                {report.fetch.truncated ? "（上限で切り詰め）" : ""}
              </Descriptions.Item>
              <Descriptions.Item label="title">{report.meta.title || "—"}</Descriptions.Item>
              <Descriptions.Item label="description">
                {report.meta.description || "—"}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="チェック結果">
            <Table<DiagnosticCheck>
              rowKey="key"
              dataSource={report.checks}
              pagination={false}
              size="small"
              scroll={{ x: 720 }}
            >
              <Table.Column<DiagnosticCheck> dataIndex="label" title="チェック" />
              <Table.Column<DiagnosticCheck>
                dataIndex="passed"
                title="結果"
                width={90}
                render={(value: boolean) => (
                  <Tag color={value ? "green" : "red"}>{value ? "合格" : "要改善"}</Tag>
                )}
              />
              <Table.Column<DiagnosticCheck> dataIndex="weight" title="配点" width={70} />
              <Table.Column<DiagnosticCheck> dataIndex="detail" title="詳細" />
            </Table>
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="構造化データ" style={{ height: "100%" }}>
                <Space direction="vertical" size="small">
                  <Typography.Text>
                    JSON-LD {report.structured_data.syntax_counts["json-ld"] ?? 0}件 / 全体{" "}
                    {report.structured_data.count}件
                  </Typography.Text>
                  <Space wrap>
                    {report.structured_data.types.length ? (
                      report.structured_data.types.map((item) => <Tag key={item}>{item}</Tag>)
                    ) : (
                      <Typography.Text type="secondary">型は見つかりませんでした</Typography.Text>
                    )}
                  </Space>
                  <Space wrap>
                    {report.structured_data.business_types.length ? (
                      report.structured_data.business_types.map((item) => (
                        <Tag key={item} color="blue">
                          {item}
                        </Tag>
                      ))
                    ) : (
                      <Typography.Text type="secondary">
                        事業・商品・サービスを示す型はありません
                      </Typography.Text>
                    )}
                  </Space>
                </Space>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="読み取れる本文" style={{ height: "100%" }}>
                <Descriptions size="small" column={1}>
                  <Descriptions.Item label="文字数">
                    {report.text.characters.toLocaleString("ja-JP")}
                  </Descriptions.Item>
                  <Descriptions.Item label="語数">{report.text.words}</Descriptions.Item>
                  <Descriptions.Item label="本文比率">
                    {(report.text.ratio * 100).toFixed(1)}%
                  </Descriptions.Item>
                </Descriptions>
                {report.text.warning ? (
                  <Alert type="warning" showIcon message={report.text.warning} />
                ) : null}
              </Card>
            </Col>
          </Row>

          <Card
            title="robots.txt"
            extra={
              <Typography.Text type="secondary">
                {report.robots.url} / {report.robots.status ?? "取得失敗"}
              </Typography.Text>
            }
          >
            <Table<DiagnosticBotAccess>
              rowKey="name"
              dataSource={report.robots.bots}
              pagination={false}
              size="small"
              scroll={{ x: 560 }}
            >
              <Table.Column<DiagnosticBotAccess> dataIndex="name" title="ボット" />
              <Table.Column<DiagnosticBotAccess>
                dataIndex="allowed"
                title="判定"
                width={90}
                render={(value: boolean) => (
                  <Tag color={value ? "green" : "red"}>{value ? "許可" : "拒否"}</Tag>
                )}
              />
              <Table.Column<DiagnosticBotAccess> dataIndex="detail" title="詳細" />
            </Table>
          </Card>

          <Card title="エージェント向けファイル">
            <Table<DiagnosticAgentFile>
              rowKey="key"
              dataSource={report.agent_files}
              pagination={false}
              size="small"
              scroll={{ x: 720 }}
            >
              <Table.Column<DiagnosticAgentFile>
                dataIndex="label"
                title="ファイル"
                render={(value: string, row) => (
                  <Typography.Link href={row.url} target="_blank">
                    {value}
                  </Typography.Link>
                )}
              />
              <Table.Column<DiagnosticAgentFile>
                dataIndex="present"
                title="判定"
                width={90}
                render={(value: boolean) => (
                  <Tag color={value ? "green" : "red"}>{value ? "あり" : "なし"}</Tag>
                )}
              />
              <Table.Column<DiagnosticAgentFile>
                dataIndex="status"
                title="HTTP"
                width={80}
                render={(value: number | null) => value ?? "—"}
              />
              <Table.Column<DiagnosticAgentFile> dataIndex="detail" title="詳細" />
            </Table>
          </Card>

          {report.recommendations.length ? (
            <Card title="改善のヒント">
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {report.recommendations.map((item) => (
                  <li key={item} style={{ marginBottom: 6 }}>
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          ) : (
            <Alert type="success" showIcon message="すべてのチェックを満たしています" />
          )}
        </>
      ) : null}

      <Card title="最近の診断">
        <Table<DiagnosticSummary>
          rowKey="id"
          dataSource={history}
          pagination={false}
          size="small"
          locale={{ emptyText: "まだ診断がありません" }}
          scroll={{ x: 640 }}
        >
          <Table.Column<DiagnosticSummary>
            dataIndex="created_at"
            title="日時"
            render={(value: string) => when(value)}
          />
          <Table.Column<DiagnosticSummary>
            dataIndex="url"
            title="URL"
            ellipsis
            render={(value: string) => (
              <Typography.Link href={value} target="_blank">
                {value}
              </Typography.Link>
            )}
          />
          <Table.Column<DiagnosticSummary> dataIndex="score" title="スコア" width={90} />
          <Table.Column<DiagnosticSummary>
            dataIndex="grade"
            title="グレード"
            width={90}
            render={(value: string) => <Tag color={GRADE_COLOR[value] ?? "default"}>{value}</Tag>}
          />
        </Table>
      </Card>
    </Space>
  );
}
