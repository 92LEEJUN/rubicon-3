/**
 * 템플릿 렌더러 — kind → 컴포넌트 레지스트리(response-templates §7, frontend-architecture §4).
 * 모르는 kind·스키마 불일치는 text 폴백. 각 컴포넌트는 template.data만 렌더(CTA는 SectionView).
 *
 * 보강: 미디어(이미지·영상) 렌더, 인터랙션(choices·booking 선택·수량 스텝퍼),
 *      시각 강화(소모품 수명 게이지·추천 카드·진행 타임라인), 주문/확인 흐름.
 */
import React, { useState } from "react";
import { Image, Pressable, StyleSheet, View } from "react-native";
import { Badge, Body, Caption, Card, Title } from "../components/primitives";
import { color, font, space } from "../design/tokens";
import type { Template } from "../types/contract";

const DEVICE_KO: Record<string, string> = {
  washer: "세탁기", refrigerator: "냉장고", air_purifier: "공기청정기",
};
const CONS_KO: Record<string, string> = {
  drain_filter: "배수 필터", water_filter: "정수필터", hepa_filter: "HEPA 필터",
};
const won = (n: number) => `₩${Number(n).toLocaleString("ko-KR")}`;
const sevTone = (s: string) => (s === "critical" ? "danger" : s === "warning" ? "warning" : "neutral");
const fmtTime = (iso: string) => {
  try { const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:00`; }
  catch { return iso; }
};

/** 썸네일 — 이미지 URL 있으면 렌더, 없으면 아이콘 플레이스홀더(오프라인 안전). */
function Thumb({ uri, icon = "📦", size = 56 }: { uri?: string; icon?: string; size?: number }) {
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: 12 }} resizeMode="cover" />;
  return (
    <View style={[styles.thumb, { width: size, height: size }]}>
      <Body>{icon}</Body>
    </View>
  );
}

/** 소모품 수명 게이지 — 임계치 이하면 경고색. */
function Gauge({ label, value, threshold }: { label: string; value: number; threshold: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const low = value <= threshold;
  return (
    <View style={styles.gauge}>
      <View style={styles.rowBetween}>
        <Caption>{label}</Caption>
        <Caption>{pct}%{low ? " · 교체 권장" : ""}</Caption>
      </View>
      <View style={styles.gaugeTrack}>
        <View style={[styles.gaugeFill, { width: `${pct}%` as any, backgroundColor: low ? color.warning : color.success }]} />
      </View>
    </View>
  );
}

function TextTemplate({ data }: { data: any }) {
  return <Body>{data?.message ?? ""}</Body>;
}

function DeviceStatus({ data }: { data: any }) {
  const d = data.device ?? {};
  const healthy = d.status === "ONLINE";
  const consumables = d.consumables ?? [];
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
      {consumables.length ? (
        <View style={styles.gaugeGroup}>
          {consumables.map((c: any, i: number) => (
            <Gauge key={i} label={CONS_KO[c.name] ?? c.name} value={c.life_remaining} threshold={c.threshold} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

function MediaChips({ media }: { media: any[] }) {
  if (!media?.length) return null;
  return (
    <View style={styles.mediaRow}>
      {media.map((m: any, i: number) => (
        <View key={i} style={styles.mediaChip}>
          <Caption>{m.type === "video" ? "▶ " : "🖼 "}{m.title ?? (m.type === "video" ? "영상" : "이미지")}</Caption>
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
            <MediaChips media={s.media} />
          </View>
        </View>
      ))}
      {(data.sources ?? []).map((src: any, i: number) => (
        <Caption key={i}>출처: {src.title}</Caption>
      ))}
    </View>
  );
}

/** 수량 스텝퍼 + 합계 — 인터랙션. */
function QtyStepper({ price }: { price: number }) {
  const [qty, setQty] = useState(1);
  return (
    <View style={styles.qtyRow}>
      <Caption>수량</Caption>
      <View style={styles.stepper}>
        <Pressable testID="qty-dec" onPress={() => setQty((q) => Math.max(1, q - 1))} style={styles.stepBtn}><Body>−</Body></Pressable>
        <View style={styles.qtyVal}><Body>{qty}</Body></View>
        <Pressable testID="qty-inc" onPress={() => setQty((q) => q + 1)} style={styles.stepBtn}><Body>＋</Body></Pressable>
      </View>
      <View style={{ flex: 1 }} />
      <Body muted>합계 {won(price * qty)}</Body>
    </View>
  );
}

function ProductCard({ data }: { data: any }) {
  return (
    <View>
      <View style={styles.prodRow}>
        <Thumb uri={data.image} icon="🧩" />
        <View style={{ flex: 1 }}>
          <Title>{data.name}</Title>
          <Caption>{data.sku ?? data.model}</Caption>
          <Body>{won(data.price)}</Body>
        </View>
        <Badge label={data.in_stock ? "재고 있음" : "품절"} tone={data.in_stock ? "success" : "danger"} />
      </View>
      {data.in_stock ? <QtyStepper price={data.price} /> : null}
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
  const o = data.order ?? {};
  return (
    <View>
      <Title>주문 요약</Title>
      {(o.items ?? []).map((it: any, i: number) => (
        <View key={i} style={styles.rowBetween}><Body>{it.name} × {it.qty}</Body><Body>{won(it.unit_price * it.qty)}</Body></View>
      ))}
      <View style={styles.divider} />
      <AmountRow label="상품 금액" value={won(s.subtotal)} />
      <AmountRow label="배송비" value={s.shipping_fee ? won(s.shipping_fee) : "무료"} />
      {s.discount ? <AmountRow label="할인" value={`-${won(s.discount)}`} /> : null}
      <View style={styles.divider} />
      <AmountRow label="총 결제금액" value={won(s.total)} strong />
      {(data.delivery_eta || data.address) ? (
        <View style={styles.metaBox}>
          {data.delivery_eta ? <Caption>🚚 도착 예정: {data.delivery_eta}</Caption> : null}
          {data.address ? <Caption>📍 {data.address}</Caption> : null}
        </View>
      ) : null}
    </View>
  );
}

function Confirmation({ data }: { data: any }) {
  return (
    <View>
      <View style={styles.gateBanner}>
        <Badge label="주문 확인 필요" tone="primary" />
        <Caption>결제하기 전 한 번 더 확인해 주세요 (되돌릴 수 없어요).</Caption>
      </View>
      <View style={{ height: space.sm }} />
      <OrderSummary data={data} />
      {data.payment_method ? <Caption>결제수단: {data.payment_method}</Caption> : null}
    </View>
  );
}

function RecommendationList({ data }: { data: any }) {
  return (
    <View>
      <Title>추천 제품</Title>
      {(data.products ?? []).map((p: any, i: number) => (
        <View key={i} style={styles.recCard}>
          <Thumb uri={p.image} icon="✨" size={52} />
          <View style={{ flex: 1 }}>
            <View style={styles.rowBetween}>
              <Body>{p.name}</Body>
              {p.reason ? <Badge label={p.reason} tone="primary" /> : null}
            </View>
            <View style={styles.specRow}>
              {Object.values(p.specs ?? {}).map((v: any, k: number) => (
                <View key={k} style={styles.specChip}><Caption>{String(v)}</Caption></View>
              ))}
            </View>
            <Body>{won(p.price)}</Body>
          </View>
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

function StatusTracker({ data }: { data: any }) {
  return (
    <View>
      <Title>{data.title ?? "진행 상태"}</Title>
      {(data.steps ?? []).map((s: any, i: number) => (
        <View key={i} style={styles.trackRow}>
          <View style={[styles.dot, s.done ? styles.dotDone : null]}>
            <Caption>{s.done ? "✓" : String(i + 1)}</Caption>
          </View>
          <View style={{ flex: 1 }}><Body muted={!s.done}>{s.label}</Body></View>
          {s.at ? <Caption>{s.at}</Caption> : null}
        </View>
      ))}
    </View>
  );
}

function Bridge({ data }: { data: any }) {
  const summary = data.summary ?? {};
  return (
    <View>
      <Badge label="빠른 보기" tone="primary" />
      <View style={{ height: space.sm }} />
      {summary.device ? <DeviceStatus data={summary} /> : <Body>{summary.message ?? data.message ?? ""}</Body>}
    </View>
  );
}

function HandoffCard({ data }: { data: any }) {
  return (
    <View>
      <View style={styles.rowBetween}>
        <Title>{data.title ?? "방문 수리 예약"}</Title>
        <Badge label={data.visit_type === "REPAIR" ? "출장 수리" : "상담"} tone="primary" />
      </View>
      <Body muted>{data.message ?? "전문 기사의 방문 수리를 예약할 수 있어요."}</Body>
    </View>
  );
}

/** 라디오 행 — booking·choices 공용 선택 UI. */
function RadioRow({ on, onPress, children, testID }:
  { on: boolean; onPress: () => void; children: React.ReactNode; testID?: string }) {
  return (
    <Pressable testID={testID} onPress={onPress} style={[styles.radioRow, on && styles.radioRowOn]}>
      <View style={[styles.radio, on && styles.radioOn]}>{on ? <View style={styles.radioDot} /> : null}</View>
      <View style={{ flex: 1 }}>{children}</View>
    </Pressable>
  );
}

function Booking({ data }: { data: any }) {
  const [sel, setSel] = useState<number | null>(null);
  return (
    <View>
      <Title>방문 시간 선택</Title>
      {(data.slots ?? []).map((s: any, i: number) => (
        <RadioRow key={i} testID={`slot-${i}`} on={sel === i} onPress={() => setSel(i)}>
          <View style={styles.rowBetween}>
            <Body>{fmtTime(s.start)} ~ {fmtTime(s.end)}</Body>
            <Badge label="선택 가능" tone="success" />
          </View>
        </RadioRow>
      ))}
      <View style={[styles.confirmBtn, sel == null && { opacity: 0.5 }]}>
        <Body>{sel == null ? "시간을 선택하세요" : "예약 확정"}</Body>
      </View>
    </View>
  );
}

function Choices({ data }: { data: any }) {
  const [sel, setSel] = useState<number | null>(null);
  const opts: any[] = data.options ?? data.choices ?? [];
  return (
    <View>
      <Body>{data.question ?? data.prompt ?? "선택해 주세요"}</Body>
      <View style={{ height: space.sm }} />
      {opts.map((o, i) => {
        const label = typeof o === "string" ? o : (o.label ?? o.value ?? "");
        return <RadioRow key={i} testID={`choice-${i}`} on={sel === i} onPress={() => setSel(i)}><Body>{label}</Body></RadioRow>;
      })}
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
  status_tracker: StatusTracker,
  bridge: Bridge,
  handoff_card: HandoffCard,
  booking: Booking,
  choices: Choices,
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

  thumb: { backgroundColor: color.surfaceAlt, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  prodRow: { flexDirection: "row", gap: space.md, alignItems: "center" },
  qtyRow: { flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.md },
  stepper: { flexDirection: "row", alignItems: "center", backgroundColor: color.surfaceAlt, borderRadius: 999 },
  stepBtn: { width: 32, height: 32, alignItems: "center", justifyContent: "center" },
  qtyVal: { minWidth: 28, alignItems: "center" },

  mediaRow: { flexDirection: "row", flexWrap: "wrap", gap: space.xs, marginTop: space.sm },
  mediaChip: { backgroundColor: color.primaryTint, borderRadius: 999, paddingHorizontal: space.sm, paddingVertical: 3 },

  gauge: { marginTop: space.sm },
  gaugeGroup: { marginTop: space.md, gap: space.xs },
  gaugeTrack: { height: 8, borderRadius: 4, backgroundColor: color.surfaceAlt, marginTop: 4, overflow: "hidden" },
  gaugeFill: { height: 8, borderRadius: 4 },

  metaBox: { marginTop: space.sm, gap: 2 },
  gateBanner: { backgroundColor: color.primaryTint, borderRadius: 12, padding: space.md, gap: space.xs },

  recCard: { flexDirection: "row", gap: space.md, alignItems: "center", marginTop: space.md },
  specRow: { flexDirection: "row", flexWrap: "wrap", gap: space.xs, marginVertical: 4 },
  specChip: { backgroundColor: color.surfaceAlt, borderRadius: 999, paddingHorizontal: space.sm, paddingVertical: 2 },

  deviceRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: space.sm,
    borderBottomWidth: 1, borderBottomColor: color.border },
  trackRow: { flexDirection: "row", alignItems: "center", gap: space.md, marginTop: space.sm },
  dot: { width: 24, height: 24, borderRadius: 12, backgroundColor: color.surfaceAlt, alignItems: "center", justifyContent: "center" },
  dotDone: { backgroundColor: color.successTint },

  radioRow: { flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.sm, paddingHorizontal: space.sm,
    borderRadius: 12, borderWidth: 1, borderColor: color.border, marginTop: space.sm },
  radioRowOn: { borderColor: color.primary, backgroundColor: color.primaryTint },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: color.textMuted, alignItems: "center", justifyContent: "center" },
  radioOn: { borderColor: color.primary },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: color.primary },
  confirmBtn: { marginTop: space.md, backgroundColor: color.primaryTint, borderRadius: 999, paddingVertical: space.md, alignItems: "center" },
});
