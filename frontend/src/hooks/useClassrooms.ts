import { useCallback, useState } from "react";
import { classroomApi, errorMessage, isAbortError, type ClassroomOut } from "../services";
import { useResource } from "./useResource";

/** Classes de l'enseignant connecté. */
export function useClassrooms() {
  const list = useResource<ClassroomOut[]>((signal) => classroomApi.listMine(signal), []);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const { data, setData } = list;

  const create = useCallback(
    async (name: string, level: string) => {
      setIsCreating(true);
      setCreateError(null);
      try {
        const created = await classroomApi.create({ name, level });
        setData([created, ...(data ?? [])]);
        return created;
      } catch (e) {
        if (!isAbortError(e)) setCreateError(errorMessage(e));
        return null;
      } finally {
        setIsCreating(false);
      }
    },
    [data, setData],
  );

  return { classrooms: data ?? [], isLoading: list.loading, error: list.error, isCreating, createError, create, reload: list.reload };
}

export function useClassroomReport(classroomId: string | null) {
  return useResource(
    async (signal) => (classroomId ? classroomApi.getReport(classroomId, signal) : null),
    [classroomId],
  );
}

/** Classes rejointes par l'élève connecté (réglages). */
export function useJoinedClassrooms() {
  return useResource((signal) => classroomApi.listJoined(signal), []);
}
