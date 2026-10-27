"use client";

import { JsonEditor } from "@/components/json-editor";
import { SchemaForm } from "@/components/schema-form";
import { api } from "@/lib/api";
import { typeLabel } from "@/lib/labels";
import type { AdapterBinding, AdapterInfo, ConversionPointRow } from "@/lib/types";
import { List, useTable } from "@refinedev/antd";
import { Alert, Button, Drawer, Form, Input, Select, Space, Switch, Table, Typography } from "antd";
import { useEffect, useState } from "react";

export default function ConversionPointsPage() {
  const { tableProps, tableQuery } = useTable<ConversionPointRow>({
    resource: "conversion-points",
    syncWithLocation: false,
  });
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<ConversionPointRow | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<AdapterInfo[]>("/adapters")
      .then(setAdapters)
      .catch(() => setAdapters([]));
  }, []);

  function edit(row: ConversionPointRow) {
    setDraft(structuredClone(row));
    setSchemaError(null);
    setError(null);
    setOpen(true);
  }

  async function save() {
    if (!draft) return;
    if (schemaError) {
      setError("入力スキーマのJSONが壊れています");
      return;
    }
    setSaving(true);
    setError(null);
    const adaptersToSave: AdapterBinding[] = draft.adapters.length ? draft.adapters : [{ key: "internal", config: {} }];
    try {
      await api(`/conversion-points/${draft.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: draft.name,
          type: draft.type,
          description: draft.description,
          input_schema: draft.input_schema,
          external_url: draft.external_url,
          enabled: draft.enabled,
          adapters: adaptersToSave,
        }),
      });
      setOpen(false);
      await tableQuery.refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存できませんでした");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <List title="コンバージョン地点" canCreate={false}>
        <Table {...tableProps} rowKey="id" scroll={{ x: 860 }} locale={{ emptyText: "まだ地点がありません。公開されたカタログに地点が含まれます。" }}>
          <Table.Column<ConversionPointRow> dataIndex="business_name" title="事業者" />
          <Table.Column<ConversionPointRow> dataIndex="name" title="名称" />
          <Table.Column<ConversionPointRow> dataIndex="type" title="種別" render={(value: string) => typeLabel(value)} />
          <Table.Column<ConversionPointRow> dataIndex="enabled" title="有効" render={(value: boolean) => (value ? "有効" : "停止")} />
          <Table.Column<ConversionPointRow>
            title="送信先"
            render={(_, row) => row.adapters.map((item) => item.key).join("、") || "—"}
          />
          <Table.Column<ConversionPointRow>
            title=""
            render={(_, row) => (
              <Button size="small" onClick={() => edit(row)}>
                編集
              </Button>
            )}
          />
        </Table>
      </List>
      <Drawer
        title={draft ? `${draft.business_name} / ${draft.name}` : "地点"}
        width={560}
        open={open}
        onClose={() => setOpen(false)}
        extra={
          <Button type="primary" loading={saving} onClick={save}>
            保存
          </Button>
        }
      >
        {error ? <Alert type="error" showIcon message={error} style={{ marginBottom: 12 }} /> : null}
        {draft ? (
          <Form layout="vertical">
            <Form.Item label="名称">
              <Input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
            </Form.Item>
            <Form.Item label="種別">
              <Select
                value={draft.type}
                options={[
                  { value: "purchase", label: "購入意向" },
                  { value: "quote_request", label: "見積依頼" },
                  { value: "inquiry", label: "問い合わせ" },
                  { value: "booking", label: "予約" },
                  { value: "document_request", label: "資料請求" },
                  { value: "external_link", label: "外部リンク" },
                ]}
                onChange={(type) => setDraft({ ...draft, type })}
              />
            </Form.Item>
            <Form.Item label="説明">
              <Input.TextArea rows={3} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} />
            </Form.Item>
            <Form.Item label="有効">
              <Switch checked={draft.enabled} onChange={(enabled) => setDraft({ ...draft, enabled })} />
            </Form.Item>
            <Form.Item label="外部URL">
              <Input
                value={draft.external_url || ""}
                onChange={(event) => setDraft({ ...draft, external_url: event.target.value || null })}
              />
            </Form.Item>
            <Form.Item label="入力スキーマ">
              <JsonEditor
                resetKey={draft.id}
                value={draft.input_schema}
                onChange={(value, message) => {
                  setSchemaError(message);
                  if (!message && value && typeof value === "object") {
                    setDraft({ ...draft, input_schema: value as Record<string, unknown> });
                  }
                }}
              />
            </Form.Item>
            <Form.Item label="送信先">
              <Select
                mode="multiple"
                style={{ width: "100%" }}
                value={draft.adapters.map((item) => item.key)}
                options={adapters.map((item) => ({ value: item.key, label: item.title }))}
                onChange={(keys: string[]) =>
                  setDraft({
                    ...draft,
                    adapters: keys.map((key) => draft.adapters.find((item) => item.key === key) || { key, config: {} }),
                  })
                }
              />
            </Form.Item>
            {draft.adapters.map((binding) => {
              const info = adapters.find((item) => item.key === binding.key);
              if (!info || !Object.keys((info.config_schema.properties as object) || {}).length) return null;
              return (
                <div key={binding.key}>
                  <Typography.Text strong>{info.title}</Typography.Text>
                  <SchemaForm
                    schema={info.config_schema}
                    formData={binding.config}
                    onChange={(config) =>
                      setDraft({
                        ...draft,
                        adapters: draft.adapters.map((item) =>
                          item.key === binding.key ? { ...item, config: (config || {}) as Record<string, unknown> } : item,
                        ),
                      })
                    }
                  />
                </div>
              );
            })}
          </Form>
        ) : null}
      </Drawer>
    </>
  );
}
