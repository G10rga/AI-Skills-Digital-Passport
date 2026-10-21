import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { RefreshCw, RotateCcw, Sheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listPassports, listRecords, resetDemoData, syncFromSheet } from "@/lib/api";
import type { SyncResult } from "@/lib/types";

export const Route = createFileRoute("/admin")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "BTU admin · AI Skills Passport" },
      { name: "description", content: "Sync verified skills from Google Sheets and manage AI Skills Digital Passports." },
      { property: "og:title", content: "BTU AI Skills Passport — admin" },
      { property: "og:description", content: "Manage and sync AI Skills Digital Passports." },
    ],
  }),
  component: AdminPage,
});

const statusStyle: Record<string, string> = {
  SYNCED: "bg-success text-background",
  "NOT SYNCED": "bg-brand text-brand-foreground",
  DUPLICATE: "bg-secondary text-muted-foreground",
  ERROR: "bg-destructive text-destructive-foreground",
  NEW: "bg-stamp-cyan text-ink",
};

function AdminPage() {
  const qc = useQueryClient();
  const records = useQuery({ queryKey: ["records"], queryFn: listRecords });
  const passports = useQuery({ queryKey: ["passports"], queryFn: listPassports });
  const [q, setQ] = useState("");
  const [last, setLast] = useState<SyncResult | null>(null);

  const sync = useMutation({
    mutationFn: syncFromSheet,
    onSuccess: (r) => {
      setLast(r);
      qc.invalidateQueries();
      toast.success(`${r.synced} skills synced · ${r.passportsUpdated.length} passports updated`);
    },
  });

  const rows = useMemo(() => {
    const s = q.toLowerCase();
    return (records.data ?? []).filter((r) => !s || `${r.firstName} ${r.lastName} ${r.passportId} ${r.skillName} ${r.studentId}`.toLowerCase().includes(s));
  }, [records.data, q]);

  const pending = (records.data ?? []).filter((r) => r.syncStatus !== "SYNCED" && r.syncStatus !== "DUPLICATE").length;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl">Passport admin</h1>
          <p className="text-muted-foreground">Skill records from the BTU Google Sheet. Syncing adds new skills to existing passports and anchors a new version.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={async () => { await resetDemoData(); setLast(null); qc.invalidateQueries(); toast("Demo data reset"); }}><RotateCcw /> Reset demo</Button>
          <Button onClick={() => sync.mutate()} disabled={sync.isPending} className="bg-brand text-brand-foreground hover:bg-brand/90">
            <RefreshCw className={sync.isPending ? "animate-spin" : ""} /> {sync.isPending ? "Syncing…" : `Sync from Google Sheets (${pending})`}
          </Button>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        {[
          ["Passports", passports.data?.length ?? "–"],
          ["Issued", passports.data?.filter((p) => p.latestVersion).length ?? "–"],
          ["Skill records", records.data?.length ?? "–"],
          ["Waiting to sync", pending],
        ].map(([l, n]) => (
          <div key={l as string} className="rounded-xl border border-border bg-card p-4">
            <div className="text-xs font-bold text-muted-foreground">{(l as string).toUpperCase()}</div>
            <div className="font-display text-3xl">{n}</div>
          </div>
        ))}
      </div>

      {last && (
        <div className="mt-6 rounded-xl border border-border bg-card p-4 text-sm">
          <div className="font-display">Last sync</div>
          <p>{last.processed} processed · {last.synced} added · {last.duplicates} duplicates skipped · {last.errors} errors</p>
          {last.log.filter((l) => l.status !== "SYNCED").map((l) => (
            <div key={l.recordId} className="text-muted-foreground">{l.recordId}: {l.status} — {l.note}</div>
          ))}
        </div>
      )}

      <Tabs defaultValue="records" className="mt-8">
        <TabsList>
          <TabsTrigger value="records"><Sheet /> Skill records</TabsTrigger>
          <TabsTrigger value="passports">Passports</TabsTrigger>
        </TabsList>
        <TabsContent value="records" className="mt-4">
          <Input placeholder="Search name, Passport ID, skill…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-3 max-w-sm" />
          <div className="rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Record</TableHead><TableHead>Student</TableHead><TableHead>Passport</TableHead>
                  <TableHead>Skill</TableHead><TableHead>Category</TableHead><TableHead>Earned</TableHead>
                  <TableHead>Status</TableHead><TableHead>Version</TableHead><TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => {
                  const st = r.syncStatus ?? "NEW";
                  return (
                    <TableRow key={r.recordId}>
                      <TableCell className="font-mono text-xs">{r.recordId}</TableCell>
                      <TableCell>{r.firstName} {r.lastName}<div className="text-xs text-muted-foreground">{r.studentId}</div></TableCell>
                      <TableCell><Link to="/passport/$passportId" params={{ passportId: r.passportId }} className="underline">{r.passportId}</Link></TableCell>
                      <TableCell>{r.skillName}</TableCell>
                      <TableCell className="text-xs">{r.skillCategory}</TableCell>
                      <TableCell className="text-xs">{r.dateEarned}</TableCell>
                      <TableCell><span className={`rounded px-2 py-0.5 text-[10px] font-bold ${statusStyle[st]}`}>{st}</span></TableCell>
                      <TableCell>{r.syncedVersion ?? "–"}</TableCell>
                      <TableCell className="max-w-48 text-xs text-muted-foreground">{r.syncNotes}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
        <TabsContent value="passports" className="mt-4">
          <div className="rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow><TableHead>Passport ID</TableHead><TableHead>Student</TableHead><TableHead>Program</TableHead><TableHead>Version</TableHead><TableHead>Skills</TableHead><TableHead>Pending</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(passports.data ?? []).map((p) => (
                  <TableRow key={p.passportId}>
                    <TableCell><Link to="/passport/$passportId" params={{ passportId: p.passportId }} className="font-semibold underline">{p.passportId}</Link></TableCell>
                    <TableCell>{p.fullName}</TableCell>
                    <TableCell className="text-xs">{p.program}</TableCell>
                    <TableCell>{p.latestVersion ? `V${p.latestVersion}` : "Not issued"}</TableCell>
                    <TableCell>{p.skillCount}</TableCell>
                    <TableCell>{p.pendingCount || ""}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
