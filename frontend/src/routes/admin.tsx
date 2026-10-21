import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { FileUp, RefreshCw, RotateCcw, Sheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { attestSkillRequest, decideNeedsReview, decidePassportRequest, decideSkillRequest, listNeedsReview, listPassportRequests, listPassports, listRecords, listSkillRequests, resetDemoData, revokeSkill, syncFromSheet, uploadExcel } from "@/lib/api";
import type { PassportRequest, SkillRequest, SyncResult } from "@/lib/types";

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
  const skillRequests = useQuery({ queryKey: ["skill-requests"], queryFn: listSkillRequests });
  const passportRequests = useQuery({ queryKey: ["passport-requests"], queryFn: listPassportRequests });
  const decidePassport = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => decidePassportRequest(id, action, notes[id] ?? ""),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["passport-requests"] });
      qc.invalidateQueries({ queryKey: ["passports"] });
      toast.success(r.status === "READY" ? `Passport ${r.passportId} is ready — student notified` : "Passport request rejected");
    },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
  });
  const [notes, setNotes] = useState<Record<number, string>>({});
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => decideSkillRequest(id, action, notes[id] ?? ""),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["skill-requests"] });
      qc.invalidateQueries({ queryKey: ["records"] });
      toast.success(r.status === "APPROVED" ? `${r.skillName} approved as ${r.recordId} — run Sync to issue it` : "Request rejected");
    },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
  });
  const attest = useMutation({
    mutationFn: ({ id, role }: { id: number; role: "Instructor" | "CareerCenter" }) => attestSkillRequest(id, role, role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["skill-requests"] }); toast.success("Attestation recorded"); },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
  });
  const flags = useQuery({ queryKey: ["needs-review"], queryFn: listNeedsReview });
  const decideFlag = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "release" | "reject" }) => decideNeedsReview(id, action),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["needs-review"] }); toast.success("Review flag updated — run Sync to process released records"); },
  });
  const revoke = useMutation({
    mutationFn: ({ passportId, recordId }: { passportId: string; recordId: string }) =>
      revokeSkill(passportId, recordId, window.prompt("Reason for revocation (shown to verifiers):") ?? "Revoked by BTU"),
    onSuccess: () => { qc.invalidateQueries(); toast.success("Skill revoked — new passport version issued"); },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
  });
  const [reqStatusFilter, setReqStatusFilter] = useState("");
  const [reqSkillFilter, setReqSkillFilter] = useState("");
  const [reqDateFilter, setReqDateFilter] = useState("");
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

  const upload = useMutation({
    mutationFn: (f: File) => uploadExcel(f, true),
    onSuccess: (r) => {
      if (r.sync) setLast(r.sync);
      qc.invalidateQueries();
      toast.success(`Excel imported: ${r.imported} new · ${r.updated} updated · ${r.skipped} skipped${r.newStudents ? ` · ${r.newStudents} new student(s) got passports` : ""}${r.sync ? ` · ${r.sync.synced} skills synced` : ""}`);
    },
    onError: (e: Error) => toast.error(e.message.replace(/^\d+ /, "")),
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
          <label className={`inline-flex cursor-pointer items-center gap-2 rounded-md border border-input px-3 py-2 text-sm font-medium ${upload.isPending ? "pointer-events-none opacity-50" : "hover:bg-secondary"}`}>
            <FileUp className="h-4 w-4" /> {upload.isPending ? "Uploading…" : "Upload Excel"}
            <input type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
          </label>
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
          <p>{last.processed} processed · {last.synced} added · {last.duplicates} duplicates skipped · {last.errors} errors · {last.flagged ?? 0} flagged for review</p>
          {last.log.filter((l) => l.status !== "SYNCED").map((l) => (
            <div key={l.recordId} className="text-muted-foreground">{l.recordId}: {l.status} — {l.note}</div>
          ))}
        </div>
      )}

      <Tabs defaultValue="records" className="mt-8">
        <TabsList>
          <TabsTrigger value="records"><Sheet /> Skill records</TabsTrigger>
          <TabsTrigger value="passports">Passports</TabsTrigger>
          <TabsTrigger value="prequests">Passport requests {(passportRequests.data ?? []).filter((r) => r.status === "PENDING_STAFF").length > 0 && `(${(passportRequests.data ?? []).filter((r) => r.status === "PENDING_STAFF").length})`}</TabsTrigger>
          <TabsTrigger value="requests">Skill requests {(skillRequests.data ?? []).filter((r) => ["PENDING", "PENDING_ADMIN", "NEEDS_TEST"].includes(r.status)).length > 0 && `(${(skillRequests.data ?? []).filter((r) => ["PENDING", "PENDING_ADMIN", "NEEDS_TEST"].includes(r.status)).length})`}</TabsTrigger>
          <TabsTrigger value="review">Needs review {(flags.data ?? []).length > 0 && `(${(flags.data ?? []).length})`}</TabsTrigger>
        </TabsList>
        <TabsContent value="records" className="mt-4">
          <p className="mb-3 text-xs text-muted-foreground">Upload Excel accepts the BTU workbook layout (.xlsx, headers on row 4, columns A–T — or camelCase headers). New rows are ingested and synced immediately; rows already present are updated, never duplicated.</p>
          <Input placeholder="Search name, Passport ID, skill…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-3 max-w-sm" />
          <div className="rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Record</TableHead><TableHead>Student</TableHead><TableHead>Passport</TableHead>
                  <TableHead>Skill</TableHead><TableHead>Category</TableHead><TableHead>Earned</TableHead>
                  <TableHead>Status</TableHead><TableHead>Version</TableHead><TableHead>Notes</TableHead><TableHead>Revoke</TableHead>
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
                      <TableCell>{r.syncStatus === "SYNCED" && !r.syncNotes?.startsWith("REVOKED") && (
                        <Button size="sm" variant="destructive" onClick={() => revoke.mutate({ passportId: r.passportId, recordId: r.recordId })}>Revoke</Button>
                      )}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
        <TabsContent value="prequests" className="mt-4">
          <div className="rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow><TableHead>Student</TableHead><TableHead>Student ID</TableHead><TableHead>Status</TableHead><TableHead>Passport</TableHead><TableHead>Note</TableHead><TableHead>Decision</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(passportRequests.data ?? []).map((r: PassportRequest) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.email}<div className="text-xs text-muted-foreground">{r.firstName} {r.lastName}</div></TableCell>
                    <TableCell className="font-mono text-xs">{r.studentId || "—"}</TableCell>
                    <TableCell><span className={`rounded px-2 py-0.5 text-[10px] font-bold ${statusStyle[r.status] ?? "bg-brand text-brand-foreground"}`}>{r.status}</span></TableCell>
                    <TableCell className="font-mono text-xs">{r.passportId || "—"}</TableCell>
                    <TableCell><Input placeholder="Optional note…" value={notes[r.id] ?? r.note ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} className="w-40" disabled={r.status !== "PENDING_STAFF"} /></TableCell>
                    <TableCell>
                      {r.status === "PENDING_STAFF" ? (
                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => decidePassport.mutate({ id: r.id, action: "approve" })}>Fulfil</Button>
                          <Button size="sm" variant="destructive" onClick={() => decidePassport.mutate({ id: r.id, action: "reject" })}>Reject</Button>
                        </div>
                      ) : <span className="text-xs text-muted-foreground">{r.decidedAt?.slice(0, 10)}</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {(passportRequests.data ?? []).length === 0 && <p className="p-4 text-sm text-muted-foreground">No passport requests yet.</p>}
            <p className="border-t border-border p-3 text-xs text-muted-foreground">Fulfil re-checks the sheet data for this student: if records now exist, the passport version is generated on the spot and the student is notified (in-app + email when SMTP is configured). If there is still no data, fulfil is refused — add the student's rows to the sheet first.</p>
          </div>
        </TabsContent>
        <TabsContent value="requests" className="mt-4">
          {skillRequests.isError ? (
            <p className="text-sm text-muted-foreground">Skill requests need the Python backend (VITE_API_BASE_URL).</p>
          ) : (
            <div className="rounded-xl border border-border bg-card">
              <div className="flex flex-wrap gap-2 border-b border-border p-3">
                <select value={reqStatusFilter} onChange={(e) => setReqStatusFilter(e.target.value)} className="rounded-md border border-input bg-background px-2 py-1 text-sm">
                  <option value="">All statuses</option>
                  {["SUBMITTED", "AI_REVIEWED", "NEEDS_TEST", "PENDING_ADMIN", "APPROVED", "REJECTED"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <Input placeholder="Filter by skill…" value={reqSkillFilter} onChange={(e) => setReqSkillFilter(e.target.value)} className="w-48" />
                <Input type="date" value={reqDateFilter} onChange={(e) => setReqDateFilter(e.target.value)} className="w-44" />
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead><TableHead>Skill</TableHead><TableHead>Evidence</TableHead>
                    <TableHead>Status</TableHead><TableHead>Admin note</TableHead><TableHead>Decision</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(skillRequests.data ?? []).filter((r) => (!reqStatusFilter || r.status === reqStatusFilter) && (!reqSkillFilter || r.skillName.toLowerCase().includes(reqSkillFilter.toLowerCase())) && (!reqDateFilter || r.createdAt.startsWith(reqDateFilter))).map((r: SkillRequest) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.studentEmail}<div className="text-xs text-muted-foreground">{r.passportId}</div></TableCell>
                      <TableCell>{r.skillName}<div className="text-xs text-muted-foreground">{r.skillCategory}</div></TableCell>
                      <TableCell className="max-w-56 text-xs">
                        {r.method === "TEST" ? <>Test score: <b>{r.testScore}%</b></> : <>{r.evidenceName || r.evidenceUrl || "Proof"}<div className="break-all font-mono text-[10px] text-muted-foreground">{r.evidenceHash && `sha256:${r.evidenceHash.slice(0, 16)}…`}</div></>}
                        {r.description && <div className="text-muted-foreground">{r.description}</div>}
                        {r.aiSummary && <div className="mt-1 text-muted-foreground">AI ({r.aiScore}%): {r.aiSummary}</div>}
                        {r.skillCategory === "AI Advanced Skill" && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            <Button size="sm" variant={r.instructorApproval ? "secondary" : "outline"} disabled={!!r.instructorApproval} onClick={() => attest.mutate({ id: r.id, role: "Instructor" })}>Instructor {r.instructorApproval ? "✓" : ""}</Button>
                            <Button size="sm" variant={r.careerCenterApproval ? "secondary" : "outline"} disabled={!!r.careerCenterApproval} onClick={() => attest.mutate({ id: r.id, role: "CareerCenter" })}>Career Center {r.careerCenterApproval ? "✓" : ""}</Button>
                          </div>
                        )}
                      </TableCell>
                      <TableCell><span className={`rounded px-2 py-0.5 text-[10px] font-bold ${statusStyle[r.status] ?? "bg-secondary"}`}>{r.status}</span>
                        {r.recordId && <div className="mt-1 text-xs text-muted-foreground">{r.recordId} · {r.recordSyncStatus ?? ""}</div>}</TableCell>
                      <TableCell><Input placeholder="Optional note…" value={notes[r.id] ?? r.adminNote ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} className="w-40" disabled={!["PENDING", "PENDING_ADMIN"].includes(r.status)} />{r.reviewer && <div className="mt-1 text-xs text-muted-foreground">Reviewer: {r.reviewer}</div>}</TableCell>
                      <TableCell>
                        {["PENDING", "PENDING_ADMIN"].includes(r.status) ? (
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => decide.mutate({ id: r.id, action: "approve" })}>Approve</Button>
                            <Button size="sm" variant="destructive" onClick={() => decide.mutate({ id: r.id, action: "reject" })}>Reject</Button>
                          </div>
                        ) : <span className="text-xs text-muted-foreground">{r.decidedAt?.slice(0, 10)}</span>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {(skillRequests.data ?? []).length === 0 && <p className="p-4 text-sm text-muted-foreground">No student skill requests yet.</p>}
              <p className="border-t border-border p-3 text-xs text-muted-foreground">Approving writes a NOT SYNCED row into the sheet dataset ({`Admin → Sync`} then issues it as a new passport version). Nothing reaches a passport without both an admin approval and a sync.</p>
            </div>
          )}
        </TabsContent>
        <TabsContent value="review" className="mt-4">
          <div className="rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow><TableHead>Record</TableHead><TableHead>Passport</TableHead><TableHead>Reason flagged</TableHead><TableHead>Flagged</TableHead><TableHead>Decision</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {(flags.data ?? []).map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="font-mono text-xs">{f.recordId}</TableCell>
                    <TableCell className="font-mono text-xs">{f.passportId}</TableCell>
                    <TableCell className="text-xs">{f.reason}</TableCell>
                    <TableCell className="text-xs">{f.createdAt.slice(0, 10)}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => decideFlag.mutate({ id: f.id, action: "release" })}>Release to sync</Button>
                        <Button size="sm" variant="destructive" onClick={() => decideFlag.mutate({ id: f.id, action: "reject" })}>Reject</Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {(flags.data ?? []).length === 0 && <p className="p-4 text-sm text-muted-foreground">Nothing flagged. Anomaly checks run inside Sync before any new version is issued.</p>}
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
