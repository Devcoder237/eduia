import { adminApi } from "../services";
import { useResource } from "./useResource";

export function useAdminStats() {
  return useResource((signal) => adminApi.getStats(signal), []);
}
