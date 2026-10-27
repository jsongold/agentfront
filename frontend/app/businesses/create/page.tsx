"use client";

import { api } from "@/lib/api";
import type { BusinessRow } from "@/lib/types";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Space, Typography } from "antd";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

const SAMPLES = [
  { label: "青葉設計室のサンプル", url: "http://localhost:8765/fixtures/aoba" },
  { label: "光枠フィルムのサンプル", url: "http://localhost:8765/fixtures/kogaku" },
];

export default function CreateBusinessPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [urls, setUrls] = useState<string[]>([""]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function setUrl(index: number, value: string) {
    setUrls((current) => current.map((item, i) => (i === index ? value : item)));
  }

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const created = await api<BusinessRow>("/businesses", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim() || null,
          description,
          urls: urls.map((item) => item.trim()).filter(Boolean),
        }),
      });
      router.push(`/businesses/show/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登録に失敗しました");
      setSaving(false);
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%", maxWidth: 760 }}>
      <div>
        <Link href="/businesses">事業者一覧へ戻る</Link>
        <Typography.Title level={3} style={{ marginTop: 8 }}>
          事業者を登録
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          公開ページのURLと、運営者が知っている補足を入れて生成を開始します。クロール結果から業種スキーマを提案し、項目を埋めたカタログをレビュー画面に出します。
        </Typography.Paragraph>
      </div>

      {error ? <Alert type="error" showIcon message="登録できませんでした" description={error} /> : null}

      <Card>
        <Form layout="vertical" onFinish={submit}>
          <Form.Item label="呼び方（任意）" extra="空欄でも生成できます。公開名はレビューで確定します。">
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="株式会社青葉設計室" />
          </Form.Item>
          <Form.Item label="参照URL" extra="http または https。サンプルはローカルの固定ページです。">
            <Space direction="vertical" style={{ width: "100%" }}>
              {urls.map((url, index) => (
                <Space.Compact key={index} style={{ width: "100%" }}>
                  <Input
                    value={url}
                    placeholder="https://example.com/about"
                    onChange={(event) => setUrl(index, event.target.value)}
                  />
                  {urls.length > 1 ? (
                    <Button
                      icon={<MinusCircleOutlined />}
                      onClick={() => setUrls((current) => current.filter((_, i) => i !== index))}
                    />
                  ) : null}
                </Space.Compact>
              ))}
              <Button icon={<PlusOutlined />} onClick={() => setUrls((current) => [...current, ""])}>
                URLを追加
              </Button>
              <Space wrap>
                {SAMPLES.map((sample) => (
                  <Button key={sample.url} size="small" onClick={() => setUrls([sample.url])}>
                    {sample.label}
                  </Button>
                ))}
              </Space>
            </Space>
          </Form.Item>
          <Form.Item
            label="説明"
            extra="URLが無いときは10文字以上必要です。料金の目安や対応エリアなど、ページに無い事実を補います。"
          >
            <Input.TextArea
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="鎌倉を中心に木造住宅の設計と監理を行う。新築の目安は2800万円から。"
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            生成を開始
          </Button>
        </Form>
      </Card>
    </Space>
  );
}
