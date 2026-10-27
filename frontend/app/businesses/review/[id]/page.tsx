"use client";

import { CatalogEditor } from "@/components/catalog-editor";
import { JsonEditor } from "@/components/json-editor";
import { api } from "@/lib/api";
import { statusOf } from "@/lib/labels";
import type { AdapterInfo, Catalog, ReviewPayload, VerticalSchemaView } from "@/lib/types";
import { BUSY } from "@/lib/types";
import { Alert, Button, Card, Col, Empty, Form, Input, Row, Space, Spin, Tabs, Tag, Typography } from "antd";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const EMPTY_SCHEMA: Record<string, unknown> = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  type: "object",
  additionalProperties: false,
  properties: {},
};

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [schemaMeta, setSchemaMeta] = useState<Pick<VerticalSchemaView, "key" | "title" | "description"> | null>(null);
  const [schemaDocument, setSchemaDocument] = useState<Record<string, unknown> | null>(null);
  const [revision, setRevision] = useState("0");
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [jsonErrors, setJsonErrors] = useState<Record<string, string | null>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const applyReview = useCallback((data: ReviewPayload, replaceEditor: boolean) => {
    setReview(data);
    if (!replaceEditor) return;
    setCatalog(data.catalog ? structuredClone(data.catalog) : null);
    setSchemaMeta(
      data.vertical_schema
        ? {
            key: data.vertical_schema.key,
            title: data.vertical_schema.title,
            description: data.vertical_schema.description,
          }
        : { key: "vertical", title: "", description: "" },
    );
    setSchemaDocument(data.vertical_schema?.json_schema ?? EMPTY_SCHEMA);
    setRevision(`${data.run?.id ?? "none"}-${data.vertical_schema?.version ?? 0}-${data.run?.finished_at ?? ""}`);
    setJsonErrors({});
  }, []);

  useEffect(() => {
    let stop = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    api<AdapterInfo[]>("/adapters")
      .then((rows) => {
        if (!stop) setAdapters(rows);
      })
      .catch(() => {
        if (!stop) setAdapters([]);
      });

    async function tick(replaceEditor: boolean) {
      try {
        const data = await api<ReviewPayload>(`/businesses/${params.id}/review`);
        if (stop) return;
        setLoadError(null);
        const busy = BUSY.has(data.run?.status ?? "") || BUSY.has(data.business.status);
        applyReview(data, replaceEditor || busy);
        if (busy) timer = setTimeout(() => tick(true), 2000);
      } catch (err) {
        if (!stop) setLoadError(err instanceof Error ? err.message : "レビューを読み込めません");
      } finally {
        if (!stop) setLoading(false);
      }
    }

    tick(true);
    return () => {
      stop = true;
      if (timer) clearTimeout(timer);
    };
  }, [params.id, applyReview]);

  function onJsonError(key: string, message: string | null) {
    setJsonErrors((current) => ({ ...current, [key]: message }));
  }

  const jsonError = Object.values(jsonErrors).find((item) => item) || null;
  const busy = BUSY.has(review?.run?.status ?? "") || BUSY.has(review?.business.status ?? "");

  async function persist(publish: boolean) {
    if (!catalog || !schemaDocument) return;
    if (jsonError) {
      setSaveError("JSONが壊れているため保存できません");
      return;
    }
    setSaving(true);
    setSaveError(null);
    setNotice(null);
    try {
      const saved = await api<ReviewPayload>(`/businesses/${params.id}/review`, {
        method: "PUT",
        body: JSON.stringify({
          catalog: {
            ...catalog,
            vertical_key: schemaMeta?.key || catalog.vertical_key,
          },
          vertical_schema: {
            key: schemaMeta?.key || "vertical",
            title: schemaMeta?.title || schemaMeta?.key || "vertical",
            description: schemaMeta?.description || "",
            json_schema: schemaDocument,
          },
        }),
      });
      applyReview(saved, true);
      if (publish) {
        await api(`/businesses/${params.id}/publish`, { method: "POST" });
        const refreshed = await api<ReviewPayload>(`/businesses/${params.id}/review`);
        applyReview(refreshed, true);
        setNotice("公開しました。エージェント向けページとMCPの検索対象になっています。");
      } else {
        setNotice("レビューを保存しました。公開するまで検索対象は以前の内容のままです。");
      }
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "保存できませんでした");
    } finally {
      setSaving(false);
    }
  }

  const runStatus = statusOf(review?.run?.status || review?.business.status);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <div>
        <Link href={`/businesses/show/${params.id}`}>事業者の詳細へ戻る</Link>
        <Typography.Title level={3} style={{ marginTop: 8, marginBottom: 8 }}>
          生成レビュー {review?.business.name ? `— ${review.business.name}` : ""}
        </Typography.Title>
        <Space wrap>
          <Tag color={runStatus.color}>{runStatus.label}</Tag>
          {review?.vertical_schema ? (
            <Typography.Text type="secondary">
              スキーマ {review.vertical_schema.key} v{review.vertical_schema.version}
            </Typography.Text>
          ) : null}
        </Space>
      </div>

      {loadError ? <Alert type="error" showIcon message={loadError} /> : null}
      {saveError ? <Alert type="error" showIcon message="保存できませんでした" description={saveError} /> : null}
      {notice ? <Alert type="success" showIcon message={notice} /> : null}
      {review?.run?.error ? <Alert type="error" showIcon message="生成エラー" description={review.run.error} /> : null}
      {review?.business.last_error ? <Alert type="warning" showIcon message={review.business.last_error} /> : null}
      {busy ? <Alert type="info" showIcon message="取得と生成が進んでいます。完了すると右欄にカタログが出ます。" /> : null}

      {loading && !review ? (
        <Spin />
      ) : (
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={10}>
            <Card title="取得した原文" size="small">
              {review?.sources.length ? (
                <Tabs
                  items={review.sources.map((source, index) => ({
                    key: String(index),
                    label: source.ok ? source.title || `資料 ${index + 1}` : `失敗 ${index + 1}`,
                    children: (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Typography.Link href={source.url} target="_blank">
                          {source.url}
                        </Typography.Link>
                        {source.error ? <Alert type="error" showIcon message={source.error} /> : null}
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            maxHeight: 640,
                            overflow: "auto",
                            background: "#f7f7f5",
                            padding: 12,
                            margin: 0,
                          }}
                        >
                          {source.text || "本文を取得できませんでした。"}
                        </pre>
                      </Space>
                    ),
                  }))}
                />
              ) : (
                <Empty description="まだ取得した原文がありません" />
              )}
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            {catalog && schemaMeta ? (
              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                <Card title="業種スキーマ" size="small">
                  <Typography.Paragraph type="secondary">
                    この事業者向けの追加項目です。新しい項目はスキーマの版を上げて保存します。データベースのマイグレーションは不要です。
                  </Typography.Paragraph>
                  <Form layout="vertical">
                    <Row gutter={12}>
                      <Col xs={24} md={8}>
                        <Form.Item label="キー">
                          <Input
                            value={schemaMeta.key}
                            onChange={(event) => setSchemaMeta({ ...schemaMeta, key: event.target.value })}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={16}>
                        <Form.Item label="タイトル">
                          <Input
                            value={schemaMeta.title}
                            onChange={(event) => setSchemaMeta({ ...schemaMeta, title: event.target.value })}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item label="JSON Schema">
                      <JsonEditor
                        resetKey={`${revision}-schema`}
                        value={schemaDocument}
                        rows={12}
                        onChange={(value, error) => {
                          onJsonError("schema", error);
                          if (!error && value && typeof value === "object") {
                            setSchemaDocument(value as Record<string, unknown>);
                          }
                        }}
                      />
                    </Form.Item>
                  </Form>
                </Card>
                <CatalogEditor
                  catalog={catalog}
                  revision={revision}
                  schemaDocument={schemaDocument}
                  adapters={adapters}
                  jsonError={jsonError}
                  onChange={setCatalog}
                  onJsonError={onJsonError}
                />
                <Space wrap>
                  <Button type="primary" loading={saving} disabled={busy} onClick={() => persist(true)}>
                    保存して公開
                  </Button>
                  <Button loading={saving} disabled={busy} onClick={() => persist(false)}>
                    下書き保存
                  </Button>
                  {review?.business.public_url ? (
                    <Typography.Link href={review.business.public_url} target="_blank">
                      公開ページを開く
                    </Typography.Link>
                  ) : null}
                </Space>
              </Space>
            ) : (
              <Card>
                <Empty description={busy ? "生成が終わるまでお待ちください" : "編集できるカタログがまだありません"} />
              </Card>
            )}
          </Col>
        </Row>
      )}
    </Space>
  );
}
