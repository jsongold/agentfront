"use client";

import { statusOf, typeLabel } from "@/lib/labels";
import type { ConversionRow } from "@/lib/types";
import { List, useTable } from "@refinedev/antd";
import { Table, Tag } from "antd";
import Link from "next/link";

function when(value: string) {
  return new Date(value).toLocaleString("ja-JP");
}

export default function ConversionsPage() {
  const { tableProps } = useTable<ConversionRow>({ resource: "conversions", syncWithLocation: false });

  return (
    <List title="受信した依頼" canCreate={false}>
      <Table {...tableProps} rowKey="id" scroll={{ x: 900 }} locale={{ emptyText: "まだ記録がありません" }}>
        <Table.Column<ConversionRow> dataIndex="created_at" title="日時" render={(value: string) => when(value)} />
        <Table.Column<ConversionRow> dataIndex="business_name" title="事業者" />
        <Table.Column<ConversionRow> dataIndex="conversion_name" title="地点" />
        <Table.Column<ConversionRow> dataIndex="conversion_type" title="種別" render={(value: string) => typeLabel(value)} />
        <Table.Column<ConversionRow>
          dataIndex="status"
          title="状態"
          render={(value: string) => {
            const status = statusOf(value);
            return <Tag color={status.color}>{status.label}</Tag>;
          }}
        />
        <Table.Column<ConversionRow> dataIndex="agent_name" title="エージェント" render={(value: string | null) => value || "—"} />
        <Table.Column<ConversionRow>
          dataIndex="request_text"
          title="依頼文"
          ellipsis
          render={(value: string | null) => value || "—"}
        />
        <Table.Column<ConversionRow>
          title=""
          render={(_, row) => <Link href={`/conversions/show/${row.id}`}>詳細</Link>}
        />
      </Table>
    </List>
  );
}
