/**
 * 템플릿 렌더러 — kind → 컴포넌트 레지스트리(response-templates §7, frontend-architecture §4).
 * 모르는 kind·스키마 불일치는 text 폴백. 각 컴포넌트는 template.data만 렌더(CTA는 SectionView).
 */
import React from "react";
import { StyleSheet, View } from "react-native";
import { Badge, Body, Caption, Card, Title } from "../components/primitives";
import { color, font, space } from "../design/tokens";
import type { Template } from "../types/contract";

const DEVICE_KO: Record<string, string> = {
  washer: "세탁기", refrigerator: "냉장고", air_purifier: "공기청정기",
};
const won = (n: number) => `₩${Number(n).toLocaleString("ko-KR")}`;
const sevTone = (s: string) => (s === "critical" ? "danger" : s === "warning" ? "warning" : "neutral");

function TextTemplate({ data }: { data: any }) {
  return <Body>{data?.message ?? ""}</Body>;
}

function DeviceStatus({ data }: { data: any }) {
  const d = data.device ?? {};
  const healthy = d.status === "ONLINE";
  return (
    <View>
      <View style={styles.rowBetween}>
        <Title>{DEVICE_KO[d.type] ?? d.type} · {d.model}</Title>
        <Badge label={healthy ? "정상" : d.status === "UNHEALTHY" ? "점검 필요" : "오프라인"}
               tone={healthy ? "success" : "warning"} />
      </View>
      {(data.anomalies ?? []).map((a: any, i: number) => (
        <View key={i} style={styles.anomaly}>
          <Badge label={a.type === "error_code" ? "오류코드" : "소모품"} tone={sevTone(a.severity)} />
          <View style={{ flex: 1 }}><Body>{a.detail}</Body></View>
        </View>
      ))}
    </View>
  );
}

function GuideSteps({ data }: { data: any }) {
  return (
    <View>
      <View style={styles.rowBetween}>
        <Title>해결 가이드</Title>
        {data.coverage === "free" ? <Badge label="무상" tone="success" /> :
         data.coverage === "paid" ? <Badge label="유상" tone="warning" /> : null}
      </View>
      {(data.steps ?? []).map((s: any) => (
        <View key={s.order} style={styles.step}>
          <View style={styles.stepNum}><Body>{s.order}</Body></View>
          <View style={{ flex: 1 }}>
            <Body>{s.instruction}</Body>
            {s.safety && s.safety !== "none" ? (
              <View style={{ marginTop: space.xs }}>
                <Badge label={s.safety === "danger" ? "위험" : "주의"}
                       tone={s.safety === "danger" ? "danger" : "warning"} />
              </View>
            ) : null}
          </View>
        </View>
      ))}
      {(data.sources ?? []).map((src: any, i: number) => (
        <Caption key={i}>출처: {src.title}</Caption>
      ))}
    </View>
  );
}

function ProductCard({ data }: { data: any }) {
  return (
    <View style={styles.rowBetween}>
      <View style={{ flex: 1 }}>
        <Title>{data.name}</Title>
        <Caption>{data.sku ?? data.model}</Caption>
        <Body>{won(data.price)}</Body>
      </View>
      <Badge label={data.in_stock ? "재고 있음" : "품절"} tone={data.in_stock ? "success" : "danger"} />
    </View>
  );
}

function AmountRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.amountRow}>
      <Body muted={!strong}>{label}</Body>
      <Body>{strong ? <Title>{value}</Title> : value}</Body>
    </View>
  );
}

function OrderSummary({ data }: { data: any }) {
  const s = data.summary ?? data;
  return (
    <View>
      <Title>주문 요약</Title>
      {(data.order?.items ?? []).map((it: any, i: number) => (
        <View key={i} style={styles.rowBetween}><Body>{it.name} × {it.qty}</Body><Body>{won(it.unit_price * it.qty)}</Body></View>
      ))}
      <View style={styles.divider} />
      <AmountRow label="상품 금액" value={won(s.subtotal)} />
      <AmountRow label="배송비" value={s.shipping_fee ? won(s.shipping_fee) : "무료"} />
      {s.discount ? <AmountRow label="할인" value={`-${won(s.discount)}`} /> : null}
      <View style={styles.divider} />
      <AmountRow label="총 결제금액" value={won(s.total)} strong />
    </View>
  );
}

function Confirmation({ data }: { data: any }) {
  return (
    <View>
      <Badge label="주문 확인 필요" tone="primary" />
      <View style={{ height: space.sm }} />
      <OrderSummary data={data} />
    </View>
  );
}

function RecommendationList({ data }: { data: any }) {
  return (
    <View>
      <Title>추천 제품</Title>
      {(data.products ?? []).map((p: any, i: number) => (
        <View key={i} style={styles.recRow}>
          <View style={{ flex: 1 }}>
            <Body>{p.name}</Body>
            <Caption>{Object.values(p.specs ?? {}).join(" · ")}</Caption>
          </View>
          <Body>{won(p.price)}</Body>
        </View>
      ))}
    </View>
  );
}

function HomeSummary({ data }: { data: any }) {
  return (
    <View>
      <Title>{data.user}님, 안녕하세요</Title>
      {(data.alerts ?? []).map((a: any, i: number) => (
        <Card key={i} style={{ marginTop: space.sm, backgroundColor: color.warningTint, borderColor: "transparent" }}>
          <View style={styles.anomaly}>
            <Badge label="알림" tone={sevTone(a.severity)} />
            <View style={{ flex: 1 }}><Body>{a.detail}</Body></View>
          </View>
        </Card>
      ))}
      <View style={{ height: space.md }} />
      <Caption>연결된 기기</Caption>
      {(data.devices ?? []).map((d: any, i: number) => (
        <View key={i} style={styles.deviceRow}>
          <Body>{DEVICE_KO[d.type] ?? d.type}</Body>
          <Badge label={d.status === "ONLINE" ? "정상" : "점검 필요"} tone={d.status === "ONLINE" ? "success" : "warning"} />
        </View>
      ))}
    </View>
  );
}

export const REGISTRY: Record<string, React.ComponentType<{ data: any }>> = {
  text: TextTemplate,
  device_status: DeviceStatus,
  guide_steps: GuideSteps,
  product_card: ProductCard,
  order_summary: OrderSummary,
  confirmation: Confirmation,
  recommendation_list: RecommendationList,
  home_summary: HomeSummary,
};

/** kind → 컴포넌트. 미등록은 text 폴백(§7). */
export function TemplateView({ template }: { template: Template }) {
  const Comp = REGISTRY[template.kind] ?? REGISTRY.text;
  const data = REGISTRY[template.kind] ? template.data : { message: stringifyFallback(template) };
  return <Comp data={data} />;
}

function stringifyFallback(t: Template): string {
  return (t.data && (t.data as any).message) || `[지원하지 않는 형식: ${t.kind}]`;
}

const styles = StyleSheet.create({
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm },
  anomaly: { flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.sm },
  step: { flexDirection: "row", gap: space.md, marginTop: space.md, alignItems: "flex-start" },
  stepNum: {
    width: 24, height: 24, borderRadius: 12, backgroundColor: color.primaryTint,
    alignItems: "center", justifyContent: "center",
  },
  divider: { height: 1, backgroundColor: color.border, marginVertical: space.sm },
  amountRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 2 },
  recRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: space.sm },
  deviceRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: space.sm,
    borderBottomWidth: 1, borderBottomColor: color.border },
});
