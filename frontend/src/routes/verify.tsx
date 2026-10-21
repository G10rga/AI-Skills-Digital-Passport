import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { verifyByCode, verifyDocumentContent } from "@/lib/api";
import type { VerifyResult } from "@/lib/types";

export const Route = createFileRoute("/verify")({
  ssr: false,
  validateSearch: (s: Record<string, unknown>): { code?: string | undefined } => ({ code: typeof s["code"] === "string" ? s["code"] : undefined }),
  head: () => ({
    meta: [
      { title: "Verify a passport · BTU AI Skills" },
      { name: "description", content: "Check that a BTU AI Skills Digital Passport is authentic and issued by BTU. No account needed." },
      { property: "og:title", content: "Verify a BTU AI Skills Digital Passport" },
      { property: "og:description", content: "Instant blockchain verification — no sign-up required." },
    ],
  }),
  component: VerifyPage,
});

function Check({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-card p-4">
      {ok ? <CheckCircle2 className="h-6 w-6 shrink-0 text-success" /> : <XCircle className="h-6 w-6 shrink-0 text-destructive" />}
      <div>
        <div className="font-display">{label}</div>
        <div className="text-sm text-muted-foreground">{detail}</div>
      </div>
    </div>
  );
}

function VerifyPage() {
  const { code } = Route.useSearch();
  const navigate = useNavigate();
  const [value, setValue] = useState(code ?? "");
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!code) { setResult(null); return; }
    setValue(code); setBusy(true);
    verifyByCode(code).then((r) => { setResult(r); setBusy(false); });
  }, [code]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-14">
      <ShieldCheck className="h-10 w-10 text-brand" />
      <h1 className="mt-3 text-4xl">Verify a passport</h1>
      <p className="mt-2 text-muted-foreground">Enter the verification code printed on the passport, or scan its QR code. No account needed.</p>
      <form className="mt-6 flex gap-2" onSubmit={(e) => { e.preventDefault(); navigate({ to: "/verify", search: { code: value.trim() } }); }}>
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="e.g. 000125-V1-3F9A1C2B" className="font-mono" />
        <Button disabled={busy || !value.trim()}>{busy ? "Checking…" : "Verify"}</Button>
      </form>

      {result && !busy && (result.found ? <Found r={result} /> : (
        <div className="mt-8 flex gap-3 rounded-xl border border-destructive bg-card p-5">
          <XCircle className="h-7 w-7 text-destructive" />
          <div>
            <div className="font-display text-lg">Not verified</div>
            <p className="text-sm text-muted-foreground">No passport issued by BTU matches this code. The document may be fake or the code mistyped.</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function Found({ r }: { r: VerifyResult }) {
  const p = r.passport!, v = r.version!;
  const ok = r.documentAuthentic && r.issuerAuthentic;
  return (
    <div className="mt-8 space-y-4">
      <div className={`rounded-xl p-5 ${ok ? "bg-success text-background" : "bg-destructive text-destructive-foreground"}`}>
        <div className="font-display text-2xl">{ok ? "AUTHENTIC PASSPORT" : "VERIFICATION FAILED"}</div>
        <div>{p.firstName} {p.lastName} · {p.passportId} · version V{v.version}</div>
      </div>
      {!r.isLatest && (
        <div className="flex gap-3 rounded-lg border border-brand bg-card p-4">
          <AlertTriangle className="h-6 w-6 shrink-0 text-brand" />
          <div className="text-sm">This is a genuine but <b>older version</b>. The latest valid version is <b>V{r.latestVersion}</b>.</div>
        </div>
      )}
      <Check ok={r.documentAuthentic} label="Document authenticity" detail="The passport content matches the fingerprint recorded on the blockchain — nothing was changed." />
      <Check ok={r.issuerAuthentic} label="Issuer authenticity" detail={`Signed by ${r.issuer!.name} (${r.issuer!.did}).`} />
      <Check ok={r.isLatest} label="Latest version" detail={r.isLatest ? "This is the current valid version." : `Superseded by V${r.latestVersion}.`} />

      <div className="rounded-lg border border-border bg-card p-4 text-sm">
        <div className="mb-2 font-display">Skills on this version ({v.skills.length})</div>
        <ul className="grid gap-1 sm:grid-cols-2">
          {v.skills.map((s) => <li key={s.recordId}>• {s.skillName} <span className="text-muted-foreground">({s.skillCategory})</span></li>)}
        </ul>
        <div className="mt-4 space-y-1 break-all font-mono text-[11px] text-muted-foreground">
          <div>Document hash: {v.documentHash}</div>
          <div>Transaction: {v.txHash}</div>
          <div>Network: {v.network} · block #{v.blockNumber}</div>
          <div>Issued: {new Date(v.issuedAt).toLocaleString()}</div>
        </div>
        <Link to="/passport/$passportId" params={{ passportId: p.passportId }} className="mt-3 inline-block font-semibold underline">View passport</Link>
      </div>
      <TamperDemo r={r} />
    </div>
  );
}

function TamperDemo({ r }: { r: VerifyResult }) {
  const p = r.passport!, v = r.version!;
  const [name, setName] = useState(p.firstName);
  const [out, setOut] = useState<{ matches: boolean; hash: string } | null>(null);
  return (
    <details className="rounded-lg border border-dashed border-border p-4 text-sm">
      <summary className="cursor-pointer font-semibold">Try it: what happens if someone edits the PDF?</summary>
      <p className="mt-2 text-muted-foreground">Change the first name as printed on the document and re-check it.</p>
      <div className="mt-3 flex gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
        <Button variant="outline" onClick={async () => {
          const res = await verifyDocumentContent({ ...p, firstName: name }, v.version, v.skills);
          setOut({ matches: res.matches, hash: res.recomputedHash });
        }}>Re-check</Button>
      </div>
      {out && (
        <p className={`mt-3 font-semibold ${out.matches ? "text-success" : "text-destructive"}`}>
          {out.matches ? "✓ Matches the blockchain record." : "✗ Fingerprint no longer matches — this document has been altered."}
          <span className="block break-all font-mono text-[10px] font-normal text-muted-foreground">{out.hash}</span>
        </p>
      )}
    </details>
  );
}
