import { chatApi } from "../services";
import { useResource } from "./useResource";

export function useSessionHistory(subjectFilter?: string) {
  return useResource((signal) => chatApi.listSessions(subjectFilter, signal), [subjectFilter]);
}
