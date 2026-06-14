/** 실험·롤아웃(Runtime A/B) — S8(ADR-0064) barrel. */
export {
  bucket,
  assignLocal,
  fetchAssignments,
  type VariantDef,
  type ExperimentDef,
  type ExperimentClientConfig,
} from './client';
export { useVariant, resolveVariant, type UseVariantOptions } from './useVariant';
