"use client";

import { api } from "@/lib/api";
import { statusOf } from "@/lib/labels";
import type { BusinessRow } from "@/lib/types";
import { BUSY } from "@/lib/types";
import { useShow } from "@refinedev/core";
import { Alert, Button, Card, Descriptions, Popconfirm, Space, Tag, Typography } from "antd";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

function when(value: string | null | undefined) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ja-JP");
}

export default function BusinessShowPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [actionError, setActionError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const { query, result } = useShow<BusinessRow>({
    resource: "businesses",
    id: params.id,
    queryOptions: {
      refetchInterval: (current) => {
        const row = current.state.data?.data;
        const run = row?.latest_run?.status;
        if (BUSY.has(row?.status ?? "") || BUSY.has(run ?? "")) return 2000;
        return false;
      },
    },
  });

  const row = result;
  const status = statusOf(row?.status);
  const runStatus = statusOf(row?.latest_run?.status);
  const busy = BUSY.has(row?.status ?? "") || BUSY.has(row?.latest_run?.status ?? "");

  async function regenerate() {
    setWorking(true);
    setActionError(null);
    try {
      await api(`/businesses/${params.id}/generate`, { method: "POST" });
      await query.refetch();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "再生成を開始できませんでした");
    } finally {
      setWorking(false);
    }
  }

  async function remove() {
    setWorking(true);
    try {
      await api(`/businesses/${params.id}`, { method: "DELETE" });
      router.push("/businesses");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "削除できませんでした");
      setWorking(false);
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Link href="/businesses">事業者一覧へ戻る</Link>
        <Typography.Title level={3} style={{ marginTop: 8, marginBottom: 8 }}>
          {row?.name || "読み込み中"}
        </Typography.Title>
        <Space wrap>
          <Tag color={status.color}>{status.label}</Tag>
          {busy ? <Typography.Text type="secondary">生成の完了を待っています…</Typography.Text> : null}
        </Space>
      </div>

      {query.isError ? (
        <Alert type="error" showIcon message="事業者を読み込めません" description={query.error?.message} />
      ) : null}
      {actionError ? <Alert type="error" showIcon message={actionError} /> : null}
      {row?.last_error ? <Alert type="error" showIcon message="直近のエラー" description={row.last_error} /> : null}

      <Card loading={query.isLoading && !row}>
        <Descriptions column={{ xs: 1, sm: 1, md: 2 }} bordered size="small">
          <Descriptions.Item label="スラッグ">{row?.slug || "—"}</Descriptions.Item>
          <Descriptions.Item label="業種スキーマ">{row?.vertical_key || "—"}</Descriptions.Item>
          <Descriptions.Item label="schema.org">{row?.schema_org_type || "—"}</Descriptions.Item>
          <Descriptions.Item label="対応エリア">{(row?.service_area || []).join("、") || "—"}</Descriptions.Item>
          <Descriptions.Item label="提供 / 実績 / 地点">
            {row ? `${row.offering_count} / ${row.work_count} / ${row.conversion_point_count}` : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="更新">{when(row?.updated_at)}</Descriptions.Item>
          <Descriptions.Item label="生成ジョブ" span={2}>
            {row?.latest_run ? (
              <Space>
                <Tag color={runStatus.color}>{runStatus.label}</Tag>
                <span>{row.latest_run.step || ""}</span>
                <span>{row.latest_run.model || ""}</span>
              </Space>
            ) : (
              "—"
            )}
          </Descriptions.Item>
          <Descriptions.Item label="参照URL" span={2}>
            {(row?.source_urls || []).length
              ? row?.source_urls.map((url) => (
                  <div key={url}>
                    <Typography.Link href={url} target="_blank">
                      {url}
                    </Typography.Link>
                  </div>
                ))
              : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="補足説明" span={2}>
            {row?.source_description || "—"}
          </Descriptions.Item>
          <Descriptions.Item label="公開" span={2}>
            {row?.public_url ? (
              <Space direction="vertical">
                <Typography.Link href={row.public_url} target="_blank">
                  {row.public_url}
                </Typography.Link>
                {row.markdown_url ? (
                  <Typography.Link href={row.markdown_url} target="_blank">
                    Markdown
                  </Typography.Link>
                ) : null}
              </Space>
            ) : (
              "未公開"
            )}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {row?.summary ? <Card title="要約">{row.summary}</Card> : null}

      <Space wrap>
        <Link href={`/businesses/review/${params.id}`}>
          <Button type="primary">レビューを開く</Button>
        </Link>
        <Button onClick={regenerate} loading={working} disabled={busy}>
          再生成
        </Button>
        <Popconfirm title="この事業者を削除しますか？" okText="削除" cancelText="やめる" onConfirm={remove}>
          <Button danger disabled={working}>
            削除
          </Button>
        </Popconfirm>
      </Space>
    </Space>
  );
}
