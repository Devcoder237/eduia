import { requestVoid } from "./http";
import type { ActivityModule } from "../utils/activity";

export const activityApi = {
  /** Signale `seconds` secondes d'activité réelle dans un module (réponse vide, 204). */
  beat: (module: ActivityModule, seconds: number) =>
    requestVoid("/activity/heartbeat", { method: "POST", body: { module, seconds } }),
};