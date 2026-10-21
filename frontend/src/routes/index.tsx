import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight, ShieldCheck, RefreshCw, FileDown, Fingerprint, KeyRound, Link2,
  ScanSearch, XCircle, CheckCircle2, Database, Award, Building2, GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Stamp, categoryLabel } from "@/components/passport/Stamp";
import { PassportTag } from "@/components/SiteHeader";
import seed from "@/data/records.json";
import type { SkillCategory, SkillRecord } from "@/lib/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "BTU AI Skills Digital Passport" },
      { name: "description", content: "BTU's blockchain-verified record of students' AI skills. View, download and verify AI Skills Digital Passports." },
      { property: "og:title", content: "BTU AI Skills Digital Passport" },
      { property: "og:description", content: "Blockchain-verified AI skills, issued by Business and Technology University." },
    ],
  }),
  component: Home,
});

const records = seed as SkillRecord[];
const cats: SkillCategory[] = ["AI Skill", "AI Applied Skill", "AI Advanced Skill"];

// Accurate numbers, computed from the actual demo dataset (not hard-coded claims).
const stats = [
  { n: String(new Set(records.map((r) => r.passportId)).size), l: "students with a passport in the demo set" },
  { n: String(records.length), l: "verified skill records in the BTU sheet" },
  { n: String(new Set(records.map((r) => r.skillId)).size), l: "distinct AI skills across 3 stamp levels" },
  { n: String(records.filter((r) => r.syncStatus === "SYNCED").length), l: "skills already issued in a V1 passport" },
  { n: String(records.filter((r) => r.syncStatus !== "SYNCED").length), l: "skills waiting for the next sync" },
  { n: "5,000+", l: "passports per year the system is designed to handle" },
];

const examples = (c: SkillCategory) =>
  [...new Set(records.filter((r) => r.skillCategory === c).map((r) => r.skillName))].slice(0, 4);

const badgeOf = (c: SkillCategory) => records.find((r) => r.skillCategory === c)?.badgeCode ?? "";

const steps = [
  {
    icon: Database, t: "1 · BTU records the skill",
    d: "An authorised BTU staff member adds the student's confirmed skill to the Google Sheet (columns A–P). The system never decides who deserves a skill — it only processes what BTU has verified.",
  },
  {
    icon: RefreshCw, t: "2 · Sync creates a new version",
    d: "On sync, new skills are appended to the student's existing passport as version V2, V3, … The Passport ID, name and first-issued date never change, and no second passport is ever created. Duplicates are skipped; invalid rows are rejected without touching existing data.",
  },
  {
    icon: Fingerprint, t: "3 · The version is fingerprinted",
    d: "The passport's canonical content — name, Passport ID, first-issued date, version number, issuer DID and the full sorted skill list (ID, name, category, badge, date, description) — is serialised in a fixed format and hashed with SHA-256. This fingerprint is printed on the document as its verification code.",
  },
  {
    icon: KeyRound, t: "4 · BTU signs it, the hash is anchored",
    d: "BTU signs the fingerprint with its private Ed25519 key (issuer: did:web:btu.edu.ge) and the hash is anchored on-chain with a transaction hash and block number. The private key never leaves BTU's server — nobody else can produce that signature.",
  },
  {
    icon: ScanSearch, t: "5 · Anyone verifies — no account needed",
    d: "An employer types the verification code into the public Verify page. The system looks up the issued version, recomputes the fingerprint from the document's content, checks BTU's signature, and reports whether this version is still the latest.",
  },
];

const attacks = [
  {
    a: "Edit a name, skill or date on the PDF",
    r: "The changed field changes the canonical content, so the recomputed SHA-256 no longer equals the anchored fingerprint.",
    v: "Document authenticity — FAIL",
  },
  {
    a: "Add an invented skill to a real passport",
    r: "The extra skill enters the hashed skill list (hash mismatch), and it has no matching record in BTU's sheet or version registry.",
    v: "Document authenticity — FAIL",
  },
  {
    a: "Fabricate a whole passport and compute its own hash",
    r: "Anyone can hash a fake document — but they cannot forge BTU's Ed25519 signature, mint a verification code that exists in the registry, or create an anchor from BTU's issuer identity (did:web:btu.edu.ge).",
    v: "Issuer authenticity — FAIL",
  },
  {
    a: "Copy a genuine verification code onto a fake document",
    r: "The code resolves to the real issued version; the fake content is compared against that version's fingerprint and does not match.",
    v: "Document authenticity — FAIL",
  },
  {
    a: "Present an older, genuine version",
    r: "It passes both authenticity checks — it really was issued — but the verifier is told it has been superseded and which version is current.",
    v: "Authentic, but NOT latest",
  },
];

function Home() {
  return (
    <div>
      <section className="bg-ink text-ink-foreground">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 md:grid-cols-2 md:py-28">
          <div>
            <PassportTag />
            <h1 className="mt-6 text-5xl leading-[0.9] md:text-7xl">
              AI SKILLS
              <br />
              <span className="font-sans font-light">DIGITAL PASSPORT</span>
            </h1>
            <p className="mt-6 max-w-md text-lg opacity-80">
              One permanent, verifiable record of every AI skill a BTU student earns — issued once,
              updated as a new version for every new skill, and impossible to fabricate: each version is
              fingerprinted with SHA-256, signed by BTU, and anchored on the blockchain.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" className="bg-brand text-brand-foreground hover:bg-brand/90" asChild>
                <Link to="/me">Open my passport <ArrowRight /></Link>
              </Button>
              <Button size="lg" variant="outline" className="border-ink-foreground/30 bg-transparent hover:bg-sidebar-accent hover:text-ink-foreground" asChild>
                <Link to="/verify" search={{ code: undefined }}><ShieldCheck /> Verify a passport</Link>
              </Button>
            </div>
            <p className="mt-6 font-mono text-xs opacity-60">
              Try the live demo code: 000125-V1-8C757F04 — Giorgi Kapanadze, version V1
            </p>
          </div>
          <div className="relative min-h-72">
            <div className="absolute right-6 top-0 rotate-[4deg] border-2 border-ink-foreground bg-brand px-5 py-2 font-display text-lg text-brand-foreground">ISSUED BY BUSINESS AND TECHNOLOGY UNIVERSITY</div>
            <div className="absolute left-4 top-16 flex h-40 w-40 items-center justify-center rounded-full border-4 border-ink bg-stamp-green font-display text-7xl text-ink">✱</div>
            <div className="absolute right-0 top-32 rotate-[-12deg] border-2 border-dashed border-ink-foreground bg-stamp-magenta px-5 py-3 font-display text-2xl">BLOCKCHAIN VERIFIED</div>
            <div className="absolute left-20 top-60 rotate-[16deg] bg-stamp-pink px-6 py-2 font-display text-xl">LATEST AI SKILLSET</div>
            <div className="absolute bottom-0 right-24 hidden h-0 w-0 border-x-[90px] border-b-[150px] border-x-transparent border-b-stamp-cyan md:block" />
          </div>
        </div>
        <div className="border-t border-ink-foreground/20">
          <div className="mx-auto grid max-w-7xl grid-cols-2 gap-6 px-4 py-10 sm:grid-cols-3 lg:grid-cols-6">
            {stats.map((s) => (
              <div key={s.l}>
                <div className="font-display text-3xl text-brand">{s.n}</div>
                <div className="mt-1 text-xs uppercase tracking-wide opacity-70">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <h2 className="text-4xl text-brand">HOW BLOCKCHAIN VERIFICATION WORKS</h2>
        <p className="mt-4 max-w-3xl text-muted-foreground">
          A PDF on its own proves nothing — anyone can edit one. Trust comes from three independent
          checks that a forged document cannot pass at the same time: the content fingerprint, BTU's
          digital signature, and the on-chain anchor.
        </p>
        <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {steps.map(({ icon: I, t, d }) => (
            <div key={t} className="rounded-xl border border-border bg-card p-6">
              <I className="h-8 w-8 text-brand" />
              <h3 className="mt-3 text-xl">{t}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{d}</p>
            </div>
          ))}
          <div className="rounded-xl border border-brand bg-card p-6 font-mono text-xs">
            <div className="font-display text-base">A REAL V1 FINGERPRINT</div>
            <p className="mt-3 break-all text-muted-foreground">
              SHA-256 of Giorgi Kapanadze's V1 canonical passport:
              <span className="mt-2 block text-foreground">8c757f04f4e9264acbfa0042cdefc9508524c350990acfdffc935c32995f35ea</span>
            </p>
            <p className="mt-3 text-muted-foreground">
              Change one letter of his name and the fingerprint becomes a completely different
              number — try it in the tamper demo on the Verify page.
            </p>
          </div>
        </div>
      </section>

      <section className="bg-secondary">
        <div className="mx-auto max-w-7xl px-4 py-20">
          <h2 className="text-4xl">WHY IT CAN'T BE FABRICATED</h2>
          <p className="mt-4 max-w-3xl text-muted-foreground">
            Every version must pass <b>document authenticity</b> (content unchanged since issuance),
            <b> issuer authenticity</b> (really issued by BTU) and a <b>latest-version</b> check.
            Here is what happens to each kind of forgery:
          </p>
          <div className="mt-10 overflow-hidden rounded-xl border border-border bg-card">
            {attacks.map((x, i) => (
              <div key={x.a} className={`grid gap-2 p-5 md:grid-cols-[1fr_1.4fr_auto] md:items-center ${i ? "border-t border-border" : ""}`}>
                <div className="flex items-start gap-2 font-semibold">
                  <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" /> {x.a}
                </div>
                <p className="text-sm text-muted-foreground">{x.r}</p>
                <span className="h-fit rounded bg-destructive px-2 py-1 text-center font-mono text-[11px] font-bold text-destructive-foreground md:w-52">{x.v}</span>
              </div>
            ))}
            <div className="grid gap-2 border-t border-border bg-success/10 p-5 md:grid-cols-[1fr_1.4fr_auto] md:items-center">
              <div className="flex items-start gap-2 font-semibold">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" /> Present the genuine, latest version
              </div>
              <p className="text-sm text-muted-foreground">Recomputed fingerprint equals the anchored one, BTU's signature verifies against its published public key, and no newer version exists.</p>
              <span className="h-fit rounded bg-success px-2 py-1 text-center font-mono text-[11px] font-bold text-background md:w-52">AUTHENTIC PASSPORT</span>
            </div>
          </div>
          <p className="mt-6 max-w-3xl text-xs text-muted-foreground">
            Honest limits, stated plainly: verification proves a document is exactly what BTU issued —
            it does not by itself prove how well a student performed; that judgement stays with BTU's
            assessment process recorded in the sheet. In this hackathon deployment the on-chain anchor
            is a deterministic testnet simulation (Polygon Amoy); the production anchor submits the
            same hash from BTU's issuer wallet, and BTU's Ed25519 public key is published at the
            issuer endpoint so signature checks never require trusting this website.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <h2 className="text-4xl text-brand">UNDERSTANDING AI SKILLS STAMPS</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {cats.map((c) => (
            <div key={c} className="rounded-xl border border-border bg-card p-6">
              <div className="flex h-24 items-center"><Stamp category={c} size={90} /></div>
              <h3 className="mt-4 text-xl">{c.toUpperCase()}</h3>
              <p className="text-sm uppercase text-muted-foreground">{categoryLabel[c]} · badge {badgeOf(c)}</p>
              <ul className="mt-4 space-y-1 text-sm text-muted-foreground">
                {examples(c).map((e) => <li key={e}>• {e}</li>)}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-6 max-w-2xl text-sm text-muted-foreground">
          The three stamp types represent different learning formats and depths of engagement
          ({stats[2].n} distinct skills in the current catalogue). They do not form a mandatory sequence —
          a student's passport simply collects whichever verified skills BTU records for them.
        </p>
      </section>

      <section className="bg-ink text-ink-foreground">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-20 md:grid-cols-3">
          {[
            { icon: GraduationCap, t: "For students", d: "Sign in with your BTU email to see your passport, watch it gain versions as you earn skills, and download or share it. Your Passport ID is yours for life." },
            { icon: Building2, t: "For employers", d: "No account, no phone call to the university. Enter the code printed on the passport and get an instant answer: authentic or not, issued by BTU or not, latest version or superseded." },
            { icon: Award, t: "For BTU", d: "Staff only maintain the Google Sheet. Sync validates every row, skips duplicates, rejects bad data without touching issued versions, writes results back to the sheet, and anchors each new version automatically." },
          ].map(({ icon: I, t, d }) => (
            <div key={t}>
              <I className="h-8 w-8 text-brand" />
              <h3 className="mt-3 text-xl">{t}</h3>
              <p className="mt-2 opacity-75">{d}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-ink-foreground/20">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-10">
            <div className="flex items-center gap-3">
              <Link2 className="h-6 w-6 text-brand" />
              <p className="max-w-xl text-sm opacity-80">Every passport version carries its fingerprint, BTU signature reference, transaction hash, network and block number — check one now, no sign-up required.</p>
            </div>
            <Button size="lg" className="bg-brand text-brand-foreground hover:bg-brand/90" asChild>
              <Link to="/verify" search={{ code: "000125-V1-8C757F04" }}><ShieldCheck /> Verify the demo passport</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid gap-6 md:grid-cols-3">
          {[
            { icon: RefreshCw, t: "Grows with you", d: "When BTU records a new skill, it's added to your existing passport as a new version. Your Passport ID never changes." },
            { icon: ShieldCheck, t: "Verified on chain", d: "Each version is fingerprinted, signed by BTU and anchored. Any edit to the document fails verification." },
            { icon: FileDown, t: "Download & share", d: "Download your passport as a PDF, or share a verification link. Employers need no account to check it." },
          ].map(({ icon: I, t, d }) => (
            <div key={t}>
              <I className="h-8 w-8 text-brand" />
              <h3 className="mt-3 text-xl">{t}</h3>
              <p className="mt-2 text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
