import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { completeRequestTest, currentStudentEmail, getMyPassport, getMyPassportRequest, getSkillCatalogue, getSkillTest, listMySkillRequests, listNotifications, logoutStudent, requestPassport, requestVerificationCode, submitProofRequest, submitSkillGap, submitTestRequest, verifyAccountCode } from "@/lib/api";
import type { SkillRequest } from "@/lib/types";
import { toast } from "sonner";
import { PassportView } from "@/components/passport/PassportView";
import { useLang } from "@/lib/i18n";

export const Route = createFileRoute("/me")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "My passport · BTU AI Skills" },
      { name: "description", content: "Sign in with your BTU account to view and download your AI Skills Digital Passport." },
      { property: "og:title", content: "My AI Skills Digital Passport" },
      { property: "og:description", content: "View and download your BTU AI Skills Digital Passport." },
    ],
  }),
  component: MePage,
});

function MePage() {
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => setEmail(currentStudentEmail()), []);
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me", email], queryFn: () => getMyPassport(email!), enabled: !!email });

  if (!email) return <Login onLogin={setEmail} />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="no-print mb-8 flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Signed in as {email}</p>
          <h1 className="text-3xl">{data ? `Hello, ${data.firstName}` : "My passport"}</h1>
        </div>
        <Button variant="outline" onClick={() => { logoutStudent(); setEmail(null); qc.clear(); }}><LogOut /> Sign out</Button>
      </div>
      {isLoading ? <p className="text-muted-foreground">Loading…</p> : data?.versions.length ? <><PassportView passport={data} /><SkillRequestSection owned={new Set(data.versions.at(-1)?.skills.map((x) => x.skillId) ?? [])} /><SkillGapSection /></> : <PassportRequestSection hasShell={!!data} />}
    </div>
  );
}

function Login({ onLogin }: { onLogin: (e: string) => void }) {
  const { t } = useLang();
  const [value, setValue] = useState("btu-t-0001@example.org");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="text-3xl">{t("sign_in")}</h1>
      <p className="mt-2 text-muted-foreground">{t("sign_in_sub")}</p>
      {step === 1 ? (
        <form className="mt-8 space-y-3" onSubmit={async (e) => {
          e.preventDefault(); setBusy(true); setError("");
          try {
            const r = await requestVerificationCode(value);
            setDevCode(r.devCode); setStep(2);
          } catch { setError("Could not send the code. Is the backend running?"); }
          setBusy(false);
        }}>
          <Input type="email" value={value} onChange={(e) => setValue(e.target.value)} placeholder={t("email_ph")} required />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" disabled={busy}>{busy ? "…" : t("send_code")}</Button>
        </form>
      ) : (
        <form className="mt-8 space-y-3" onSubmit={async (e) => {
          e.preventDefault(); setBusy(true); setError("");
          const r = await verifyAccountCode(value, code);
          setBusy(false);
          if (r) onLogin(r.email); else setError("Incorrect or expired code.");
        }}>
          <p className="rounded-md bg-secondary p-3 text-sm">{t("code_sent")}</p>
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder={t("code_ph")} inputMode="numeric" maxLength={6} required className="font-mono" />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" disabled={busy}>{busy ? "…" : t("verify_btn")}</Button>
          <button type="button" className="text-xs text-muted-foreground underline" onClick={() => setStep(1)}>Use a different email</button>
        </form>
      )}
      <p className="mt-4 text-xs text-muted-foreground">Demo: request a code for any test email from the sheet, e.g. btu-t-0002@example.org.</p>
    </div>
  );
}

function PassportRequestSection({ hasShell }: { hasShell: boolean }) {
  const { t } = useLang();
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["my-passport-request"], queryFn: getMyPassportRequest });
  const notes = useQuery({ queryKey: ["my-notifications"], queryFn: listNotifications });
  const submit = useMutation({
    mutationFn: () => requestPassport(),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["my-passport-request"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(r.status === "READY" ? `${t("passport_ready")} ${r.passportId}` : t("waiting_staff"));
    },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
  });
  const r = status.data;
  return (
    <section className="mx-auto max-w-xl rounded-xl border border-border bg-card p-6">
      <h2 className="text-2xl">{t("request_passport")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{hasShell ? t("request_sub") : t("no_passport") + " " + t("request_sub")}</p>
      {r?.status === "READY" ? (
        <p className="mt-4 font-semibold text-success">{t("passport_ready")} {r.passportId}</p>
      ) : r?.status === "PENDING_STAFF" ? (
        <p className="mt-4 rounded-md bg-secondary p-3 text-sm font-semibold">{t("waiting_staff")}</p>
      ) : (
        <div className="mt-5">
          <Button onClick={() => submit.mutate()} disabled={submit.isPending}>{t("request_btn")}</Button>
        </div>
      )}
      {r?.status === "REJECTED" && <p className="mt-3 text-sm text-destructive">{r.note}</p>}
      {(notes.data ?? []).length > 0 && (
        <div className="mt-6">
          <h3 className="font-display text-sm">{t("notifications")}</h3>
          {(notes.data ?? []).map((n) => <p key={n.id} className="mt-1 text-sm text-muted-foreground">• {n.message}</p>)}
        </div>
      )}
    </section>
  );
}

const reqStatus: Record<string, string> = {
  PENDING: "bg-brand text-brand-foreground",
  PENDING_ADMIN: "bg-brand text-brand-foreground",
  AI_REVIEWED: "bg-stamp-cyan text-ink",
  NEEDS_TEST: "bg-stamp-pink text-background",
  APPROVED: "bg-success text-background",
  REJECTED: "bg-destructive text-destructive-foreground",
};

function SkillGapSection() {
  const [jd, setJd] = useState("");
  const gap = useMutation({ mutationFn: () => submitSkillGap(jd) });
  return (
    <section className="no-print mt-8 rounded-xl border border-border bg-card p-6">
      <h2 className="text-2xl">Skill-gap check</h2>
      <p className="mt-1 text-sm text-muted-foreground">Paste a job description — we diff its required skills against your verified passport skills and point each gap at the BTU activity that teaches it. Read-only; nothing is written to your passport.</p>
      <textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={5} className="mt-4 w-full rounded-md border border-input bg-background p-3 text-sm" placeholder="Paste the job description here…" />
      <Button className="mt-3" disabled={!jd.trim() || gap.isPending} onClick={() => gap.mutate()}>{gap.isPending ? "Analysing…" : "Check my gaps"}</Button>
      {gap.isError && <p className="mt-3 text-sm text-destructive">Skill-gap needs the Python backend.</p>}
      {gap.data && (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 text-sm">
          <div>
            <h3 className="font-display">Matched ({gap.data.matched.length})</h3>
            {gap.data.matched.map((s) => <p key={s.skillId} className="mt-1 text-success">✓ {s.skillName}</p>)}
          </div>
          <div>
            <h3 className="font-display">Missing ({gap.data.missing.length})</h3>
            {gap.data.suggestions.map(({ skill, learnVia }) => (
              <p key={skill.skillId} className="mt-1">• <b>{skill.skillName}</b> <span className="text-muted-foreground">— learn via: {learnVia || skill.skillCategory}</span></p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function NeedsTest({ request, onDone }: { request: SkillRequest; onDone: () => void }) {
  const test = useQuery({ queryKey: ["test", request.skillId], queryFn: () => getSkillTest(request.skillId) });
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [msg, setMsg] = useState("");
  const submit = useMutation({
    mutationFn: () => completeRequestTest(request.id, answers),
    onSuccess: () => { setMsg("Test passed — your request is now with an administrator."); onDone(); },
    onError: (e: Error) => setMsg(e.message.replace(/^\d+ /, "")),
  });
  return (
    <div className="mt-3 rounded-md bg-secondary p-3">
      <p className="text-xs font-semibold">This top-tier skill needs a passing test before admin review.</p>
      {(test.data?.questions ?? []).map((q, i) => (
        <fieldset key={q.id} className="mt-2">
          <legend className="text-xs font-semibold">{i + 1}. {q.question}</legend>
          {q.options.map((o, oi) => (
            <label key={oi} className="mt-1 flex cursor-pointer items-center gap-2 text-xs">
              <input type="radio" name={`${request.id}-${q.id}`} checked={answers[q.id] === oi} onChange={() => setAnswers({ ...answers, [q.id]: oi })} /> {o}
            </label>
          ))}
        </fieldset>
      ))}
      <Button size="sm" className="mt-3" disabled={!test.data || Object.keys(answers).length < (test.data?.questions.length ?? 5) || submit.isPending} onClick={() => submit.mutate()}>Submit test</Button>
      {msg && <p className="mt-2 text-xs font-semibold">{msg}</p>}
    </div>
  );
}

function SkillRequestSection({ owned }: { owned: Set<string> }) {
  const qc = useQueryClient();
  const catalogue = useQuery({ queryKey: ["catalogue"], queryFn: getSkillCatalogue });
  const mine = useQuery({ queryKey: ["my-requests"], queryFn: listMySkillRequests });
  const [skillId, setSkillId] = useState("");
  const [method, setMethod] = useState<"TEST" | "PROOF">("TEST");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [file, setFile] = useState<File | null>(null);
  const [desc, setDesc] = useState("");
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  const test = useQuery({ queryKey: ["test", skillId], queryFn: () => getSkillTest(skillId), enabled: !!skillId && method === "TEST" });

  const invalidate = () => { qc.invalidateQueries({ queryKey: ["my-requests"] }); };
  const submitTest = useMutation({
    mutationFn: () => submitTestRequest(skillId, answers),
    onSuccess: () => { setMsg("Request submitted — an administrator will review it."); toast.success("Skill request submitted"); invalidate(); },
    onError: (e: Error) => setMsg(e.message.replace(/^\d+ /, "")),
  });
  const submitProof = useMutation({
    mutationFn: () => submitProofRequest(skillId, desc, url, file),
    onSuccess: () => { setMsg("Proof submitted — an administrator will verify it."); toast.success("Skill request submitted"); invalidate(); },
    onError: (e: Error) => setMsg(e.message.replace(/^\d+ /, "")),
  });

  if (catalogue.isError) return null; // backend-only feature; hide in mock mode

  return (
    <section className="no-print mt-12 rounded-xl border border-border bg-card p-6">
      <h2 className="text-2xl">Request a skill addition</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Prove a skill BTU hasn't recorded yet. Take the skill test or upload proof — an administrator
        verifies it, and on approval it enters the official sheet and becomes a new version of this
        passport at the next sync.
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
        <select value={skillId} onChange={(e) => { setSkillId(e.target.value); setAnswers({}); setMsg(""); }}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm">
          <option value="">Choose a skill…</option>
          {(catalogue.data ?? []).map((s) => (
            <option key={s.skillId} value={s.skillId} disabled={owned.has(s.skillId)}>
              {s.skillName} — {s.skillCategory}{owned.has(s.skillId) ? " (already on passport)" : ""}
            </option>
          ))}
        </select>
        <div className="flex overflow-hidden rounded-md border border-input">
          {(["TEST", "PROOF"] as const).map((m) => (
            <button key={m} onClick={() => setMethod(m)}
              className={`px-4 py-2 text-sm font-semibold ${method === m ? "bg-brand text-brand-foreground" : "bg-background"}`}>
              {m === "TEST" ? "Take a test" : "Upload proof"}
            </button>
          ))}
        </div>
      </div>

      {skillId && method === "TEST" && (
        <div className="mt-5 space-y-4">
          {test.isLoading ? <p className="text-sm text-muted-foreground">Loading test…</p> :
            (test.data?.questions ?? []).map((q, i) => (
              <fieldset key={q.id} className="rounded-lg border border-border p-4">
                <legend className="px-1 text-sm font-semibold">{i + 1}. {q.question}</legend>
                {q.options.map((o, oi) => (
                  <label key={oi} className="mt-1 flex cursor-pointer items-center gap-2 text-sm">
                    <input type="radio" name={q.id} checked={answers[q.id] === oi}
                      onChange={() => setAnswers({ ...answers, [q.id]: oi })} /> {o}
                  </label>
                ))}
              </fieldset>
            ))}
          <p className="text-xs text-muted-foreground">Pass mark: {test.data?.passMark ?? 70}%. Grading is server-side.</p>
          <Button disabled={!test.data || Object.keys(answers).length < (test.data?.questions.length ?? 5) || submitTest.isPending}
            onClick={() => submitTest.mutate()}>
            {submitTest.isPending ? "Grading…" : "Submit test for review"}
          </Button>
        </div>
      )}

      {skillId && method === "PROOF" && (
        <div className="mt-5 space-y-3">
          <Input type="file" accept=".pdf,.png,.jpg,.jpeg,.zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Input placeholder="Or evidence URL (certificate, portfolio, GitHub…)" value={url} onChange={(e) => setUrl(e.target.value)} />
          <Input placeholder="What does this prove? (course, project, date…)" value={desc} onChange={(e) => setDesc(e.target.value)} />
          <p className="text-xs text-muted-foreground">Uploaded files are SHA-256 hashed on submission, so the exact evidence an admin approved can later be proven unchanged.</p>
          <Button disabled={(!file && !url) || submitProof.isPending} onClick={() => submitProof.mutate()}>
            {submitProof.isPending ? "Submitting…" : "Submit proof for review"}
          </Button>
        </div>
      )}

      {msg && <p className="mt-4 text-sm font-semibold">{msg}</p>}

      {(mine.data ?? []).length > 0 && (
        <div className="mt-8">
          <h3 className="font-display">My requests</h3>
          <div className="mt-3 space-y-2">
            {(mine.data ?? []).map((r: SkillRequest) => (
              <div key={r.id} className="rounded-lg border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-semibold">{r.skillName}</span>
                  <span className="text-muted-foreground">{r.method === "TEST" ? `Test ${r.testScore}%` : "Proof upload"}</span>
                  <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${reqStatus[r.status]}`}>{r.status}</span>
                  {r.status === "APPROVED" && <span className="text-xs text-muted-foreground">{r.recordId} · {r.recordSyncStatus === "SYNCED" ? "on passport" : "waiting for next sync"}</span>}
                  {r.adminNote && <span className="text-xs text-muted-foreground">“{r.adminNote}”</span>}
                  {r.reviewer && <span className="text-xs text-muted-foreground">Reviewer: {r.reviewer}</span>}
                </div>
                {r.aiSummary && <p className="mt-1 text-xs text-muted-foreground">AI review ({r.aiScore}% · {r.aiModel}): {r.aiSummary}</p>}
                {(r.proofLinks ?? []).length > 0 && <p className="mt-1 break-all text-xs text-muted-foreground">Proof: {r.proofLinks!.join(", ")}</p>}
                {r.status === "NEEDS_TEST" && <NeedsTest request={r} onDone={invalidate} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
