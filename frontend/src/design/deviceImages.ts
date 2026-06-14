/** 실사진 레지스트리 — vite가 해시 URL로 번들(jest는 스텁 문자열). */
import refrigerator from '../assets/devices/refrigerator.jpg';
import washer from '../assets/devices/washer.jpg';
import bundle from '../assets/cards/bundle.jpg';
import checkup from '../assets/cards/checkup.jpg';
import cleanair from '../assets/cards/cleanair.jpg';
import energy from '../assets/cards/energy.jpg';

// 기기 타입 → 사진(기기 행 썸네일·덱 카드).
export const DEVICE_IMAGE: Record<string, string> = {
  washer,
  refrigerator,
};

// 덱 카드 주제 → 사진(기기 사진이 없는 큐레이션 카드용).
export const CARD_IMAGE: Record<string, string> = {
  energy,
  checkup,
  bundle,
  cleanair,
};
