import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Download, Linkedin, Link2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Passport } from "@/lib/types";
import { PassportDocument } from "./PassportDocument";

export function PassportView({ passport }: { passport: Passport }) {
  const latest = passport.versions.at(-1);
  const [selected, setSelected] = useState(latest?.version ?? 0);
  const v = passport.versions.find((x) => x.version === selected) ?? latest;

  if (!v) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card p-10 text-center">
        <h2 className="text-2xl">Passport not issued yet</h2>
        <p className="mt-2 text-muted-foreground">
          {passport.firstName} {passport.lastName} ({passport.passportId}) has skills waiting for the next sync from BTU.
        </p>
      </div>
    );
  }

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const verifyUrl = `${origin}/verify?code=${v.verificationCode}`;
  const publicUrl = `${origin}/passport/${passport.passportId}`;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_300px]">
      <div className="min-w-0">
        <PassportDocument passport={passport} version={v} verifyUrl={verifyUrl} />
      </div>
      <aside className="no-print space-y-4 lg:sticky lg:top-20 lg:self-start">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-xs font-bold text-muted-foreground">PASSPORT ID</div>
          <div className="font-display text-xl">{passport.passportId}</div>
          <div className="mt-3 text-xs font-bold text-muted-foreground">VERIFICATION CODE</div>
          <div className="font-display">{v.verificationCode}</div>
          <div className="mt-4 grid gap-2">
            <Button onClick={() => window.print()}><Download /> Download PDF</Button>
            <Button variant="outline" asChild>
              <a href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(publicUrl)}`} target="_blank" rel="noreferrer">
                <Linkedin /> Share on LinkedIn
              </a>
            </Button>
            <Button variant="outline" onClick={() => { navigator.clipboard.writeText(verifyUrl); toast.success("Verification link copied"); }}>
              <Link2 /> Copy verification link
            </Button>
            <Button variant="ghost" asChild>
              <Link to="/verify" search={{ code: v.verificationCode }}><ShieldCheck /> Verify this version</Link>
            </Button>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-2 text-xs font-bold text-muted-foreground">VERSION HISTORY</div>
          <ul className="space-y-1">
            {[...passport.versions].reverse().map((x) => (
              <li key={x.version}>
                <button
                  onClick={() => setSelected(x.version)}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-secondary ${x.version === v.version ? "bg-secondary font-semibold" : ""}`}
                >
                  <span>V{x.version} · {x.skills.length} skills</span>
                  {x.version === latest?.version ? (
                    <span className="rounded bg-success px-1.5 py-0.5 text-[10px] font-bold text-background">LATEST</span>
                  ) : (
                    <span className="text-[10px] text-muted-foreground">superseded</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-3 break-all text-[10px] text-muted-foreground">
            Anchored on {v.network} · block #{v.blockNumber}<br />tx {v.txHash.slice(0, 22)}…
          </div>
        </div>
      </aside>
    </div>
  );
}
