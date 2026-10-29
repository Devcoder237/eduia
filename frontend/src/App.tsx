import { Suspense, lazy, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useT } from "./i18n";
import { AuthProvider, useAuth, useRetryAuth } from "./context/AuthContext";
import { PUBLIC_PAGES, useRoute, type Page } from "./lib/router";
import { useServerWake } from "./hooks/useServerWake";
import { useActivityTracker } from "./hooks/useActivityTracker";
import { moduleForPage } from "./utils/activity";
import { AppLayout } from "./layouts/AppLayout";
import { WakeScreen } from "./components/WakeScreen";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Alert, Button, Spinner } from "./components/ui";
import { BrandMark } from "./components/Brand";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";

// Chargement à la demande : le premier affichage (page d'accueil) reste léger, même en 3G.
const TutorPage = lazy(() => import("./pages/TutorPage"));
const ExercisePage = lazy(() => import("./pages/ExercisePage"));
const QuizPage = lazy(() => import("./pages/QuizPage"));
const ExamPage = lazy(() => import("./pages/ExamPage"));
const ProgressPage = lazy(() => import("./pages/ProgressPage"));
const HistoryPage = lazy(() => import("./pages/HistoryPage"));
const StudyPlanPage = lazy(() => import("./pages/StudyPlanPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const TeacherPage = lazy(() => import("./pages/TeacherPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const LegalPage = lazy(() => import("./pages/LegalPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));

/** Pages qui gardent leur état en cours (question, réponses, chronomètre) quand on change d'écran. */
const KEEP_ALIVE: readonly Page[] = ["exercise", "quiz", "exam"];

function Splash({ children }: { children?: ReactNode }) {
  return (
    <div className="fullscreen-msg">
      <BrandMark size={56} />
      {children}
    </div>
  );
}

function Shell() {
  const { t } = useT();
  const auth = useAuth();
  const retryAuth = useRetryAuth();
  const route = useRoute();
  const wake = useServerWake();
  const [visited, setVisited] = useState<Page[]>([]);
  const { page, params, navigate, replace } = route;
  const redirected = useRef(false);

  const authed = auth.status === "authenticated";
  const isPublic = PUBLIC_PAGES.includes(page);

  // Garde de navigation : écrans privés réservés aux connectés ; « login » inutile une fois connecté.
  useEffect(() => {
    if (auth.status === "loading" || auth.status === "unavailable") return;
    if (!authed && !isPublic) replace("login");
    else if (authed && page === "login") replace("tutor");
    else if (authed && page === "landing" && !redirected.current && window.location.hash === "") {
      redirected.current = true;
      replace("tutor"); // un utilisateur connecté qui ouvre le site arrive directement sur le tuteur
    }
  }, [auth.status, authed, isPublic, page, replace]);

  useEffect(() => {
    if (authed && KEEP_ALIVE.includes(page)) setVisited((v) => (v.includes(page) ? v : [...v, page]));
  }, [authed, page]);

  // Déconnexion : on oublie les écrans mis en cache (aucune donnée de l'utilisateur précédent).
  useEffect(() => {
    if (!authed) setVisited([]);
  }, [authed]);
  // Temps d'utilisation réel (invisible) : uniquement pour un élève connecté, sur les écrans privés.
  useActivityTracker(authed ? moduleForPage(page) : null);
  // Les écrans connectés et la connexion exigent un serveur réveillé ; la page d'accueil, non.
  const needsServer = page !== "landing" && page !== "legal";
  if (needsServer && wake.state !== "ready" && wake.state !== "checking") {
    return <WakeScreen elapsedSec={wake.elapsedSec} down={wake.state === "down"} onRetry={wake.retry} />;
  }

  if (page === "legal") {
    return <Suspense fallback={<Spinner />}><LegalPage onBack={() => navigate(authed ? "settings" : "landing")} /></Suspense>;
  }

  if (page === "reset") {
    return (
      <Suspense fallback={<Spinner />}>
        <ResetPasswordPage token={params.token ?? ""} onDone={() => navigate("login")} onRequestNew={() => navigate("login", { forgot: "1" })} />
      </Suspense>
    );
  }

  if (page === "landing") {
    return (
      <LandingPage
        serverWaking={wake.state === "waking"}
        onStart={() => navigate(authed ? "tutor" : "login")}
        onLogin={() => navigate(authed ? "tutor" : "login")}
        onLegal={() => navigate("legal")}
      />
    );
  }

  if (auth.status === "loading" || (needsServer && wake.state === "checking")) {
    return <Splash><Spinner label={t("app.loading")} /></Splash>;
  }

  if (auth.status === "unavailable") {
    return (
      <Splash>
        <Alert tone="error">{t("error.network")}</Alert>
        <Button onClick={retryAuth}>{t("common.retry")}</Button>
      </Splash>
    );
  }

  if (!authed) return <LoginPage onHome={() => navigate("landing")} onLegal={() => navigate("legal")} initialForgot={params.forgot === "1"} />;

  const openSession = (sessionId: string) => navigate("tutor", { session: sessionId });
  const go = (target: Page, extra?: Record<string, string>) => navigate(target, extra);

  return (
    <AppLayout page={page} onNavigate={go}>
      <Suspense fallback={<Spinner />}>
        {page === "tutor" && <TutorPage onNavigate={go} openSessionId={params.session} onSessionOpened={() => replace("tutor")} />}
        {page === "progress" && <ProgressPage onNavigate={go} />}
        {page === "history" && <HistoryPage onOpenSession={openSession} />}
        {page === "studyplans" && <StudyPlanPage />}
        {page === "settings" && <SettingsPage onNavigate={go} />}
        {page === "teacher" && auth.user?.is_teacher && <TeacherPage />}
        {page === "admin" && auth.user?.is_admin && <AdminPage />}
        {visited.includes("exercise") && <div hidden={page !== "exercise"}><ExercisePage /></div>}
        {visited.includes("quiz") && <div hidden={page !== "quiz"}><QuizPage /></div>}
        {visited.includes("exam") && <div hidden={page !== "exam"}><ExamPage /></div>}
      </Suspense>
    </AppLayout>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </ErrorBoundary>
  );
}
