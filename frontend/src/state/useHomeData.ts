/** useHomeData — BFF /home 실데이터 조회(실패/미설정 시 fixture 폴백, 에러 숨김). */
import { useEffect, useState } from "react";
import { getHome, type ApiConfig } from "../transport/api";
import { homeSummary } from "../fixtures/journeys";

export function useHomeData(cfg: ApiConfig) {
  const [data, setData] = useState<any>(homeSummary.data);
  useEffect(() => {
    let alive = true;
    getHome(cfg).then((d) => { if (alive && d) setData(d); });
    return () => { alive = false; };
  }, [cfg.base, cfg.token]);
  return data;
}
