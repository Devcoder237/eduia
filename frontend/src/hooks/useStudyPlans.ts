import { useCallback, useState } from "react";
import { errorMessage, isAbortError, studyPlanApi, type StudyPlanInput, type StudyPlanOut } from "../services";
import { useResource } from "./useResource";

/** Plans d'étude actifs : génération, coche des jours, réorganisation, archivage. */
export function useStudyPlans() {
  const list = useResource<StudyPlanOut[]>((signal) => studyPlanApi.listActive(signal), []);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const plans = list.data ?? [];
  const { setData, reload } = list;

  const replacePlan = useCallback(
    (updated: StudyPlanOut) => setData(plans.map((p) => (p.id === updated.id ? updated : p))),
    [plans, setData],
  );

  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T | null> => {
    setActionError(null);
    try {
      return await action();
    } catch (e) {
      if (!isAbortError(e)) setActionError(errorMessage(e));
      return null;
    }
  }, []);

  const generate = useCallback(
    async (input: StudyPlanInput) => {
      setIsGenerating(true);
      const plan = await run(() => studyPlanApi.generate(input));
      setIsGenerating(false);
      if (plan) reload();
      return plan;
    },
    [run, reload],
  );

  const toggleDay = useCallback(
    async (planId: string, dayIndex: number, completed: boolean) => {
      const updated = await run(() => studyPlanApi.toggleDay(planId, dayIndex, completed));
      if (updated) replacePlan(updated);
    },
    [run, replacePlan],
  );

  const refresh = useCallback(
    async (planId: string) => {
      setIsRefreshing(true);
      const updated = await run(() => studyPlanApi.refresh(planId));
      setIsRefreshing(false);
      if (updated) replacePlan(updated);
    },
    [run, replacePlan],
  );

  const archive = useCallback(
    async (planId: string) => {
      const done = await run(() => studyPlanApi.archive(planId));
      if (done) setData(plans.filter((p) => p.id !== planId));
    },
    [run, plans, setData],
  );

  return {
    plans, isLoading: list.loading, loadError: list.error, actionError, isGenerating, isRefreshing,
    generate, toggleDay, refresh, archive, reload,
  };
}
