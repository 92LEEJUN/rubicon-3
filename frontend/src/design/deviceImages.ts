/** 기기 실사진 레지스트리 — vite가 해시 URL로 번들(jest는 스텁 문자열). */
import refrigerator from '../assets/devices/refrigerator.jpg';
import washer from '../assets/devices/washer.jpg';

export const DEVICE_IMAGE: Record<string, string> = {
  washer,
  refrigerator,
};
