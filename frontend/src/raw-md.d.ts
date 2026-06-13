// `?raw` import(아키텍처 문서 텍스트 번들)용 타입 선언.
declare module "*.md?raw" {
  const content: string;
  export default content;
}
