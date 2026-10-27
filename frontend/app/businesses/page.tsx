"use client";

import { statusOf } from "@/lib/labels";
import type { BusinessRow } from "@/lib/types";
import { List, useTable } from "@refinedev/antd";
import { Space, Table, Tag } from "antd";
import Link from "next/link";

export default function BusinessesPage() {
  const { tableProps } = useTable<BusinessRow>({ resource: "businesses", syncWithLocation: false });

  return (
    <List title="事業者" createButtonProps={{ children: "事業者を登録" }}>
      <Table
        {...tableProps}
        rowKey="id"
        scroll={{ x: 860 }}
        locale={{ emptyText: "まだ事業者がありません。URLと説明を登録すると生成が始まります。" }}
      >
        <Table.Column<BusinessRow> dataIndex="name" title="名称" />
        <Table.Column<BusinessRow>
          dataIndex="status"
          title="状態"
          render={(value: string) => {
            const status = statusOf(value);
            return <Tag color={status.color}>{status.label}</Tag>;
          }}
        />
        <Table.Column<BusinessRow>
          title="対応エリア"
          render={(_, row) => (row.service_area || []).join("、") || "—"}
        />
        <Table.Column<BusinessRow> dataIndex="vertical_key" title="業種スキーマ" render={(value: string | null) => value || "—"} />
        <Table.Column<BusinessRow> dataIndex="offering_count" title="提供" />
        <Table.Column<BusinessRow>
          title=""
          render={(_, row) => (
            <Space>
              <Link href={`/businesses/show/${row.id}`}>詳細</Link>
              <Link href={`/businesses/review/${row.id}`}>レビュー</Link>
              {row.public_url ? (
                <a href={row.public_url} target="_blank" rel="noreferrer">
                  公開ページ
                </a>
              ) : null}
            </Space>
          )}
        />
      </Table>
    </List>
  );
}
