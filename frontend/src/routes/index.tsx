import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ShieldCheck, RefreshCw, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Stamp, categoryLabel } from "@/components/passport/Stamp";
import { PassportTag } from "@/components/SiteHeader";
import type { SkillCategory } from "@/lib/types";

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

const cats: SkillCategory[] = ["AI Skill", "AI Applied Skill", "AI Advanced Skill"];

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
              A single, verifiable record of every AI skill a BTU student earns — updated as they grow, verified on the blockchain.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" className="bg-brand text-brand-foreground hover:bg-brand/90" asChild>
                <Link to="/me">Open my passport <ArrowRight /></Link>
              </Button>
              <Button size="lg" variant="outline" className="border-ink-foreground/30 bg-transparent hover:bg-sidebar-accent hover:text-ink-foreground" asChild>
                <Link to="/verify" search={{ code: undefined }}><ShieldCheck /> Verify a passport</Link>
              </Button>
            </div>
          </div>
          <div className="relative min-h-72">
            <div className="absolute right-6 top-0 rotate-[4deg] border-2 border-ink-foreground bg-brand px-5 py-2 font-display text-lg text-brand-foreground">ISSUED BY BUSINESS AND TECHNOLOGY UNIVERSITY</div>
            <div className="absolute left-4 top-16 flex h-40 w-40 items-center justify-center rounded-full border-4 border-ink bg-stamp-green font-display text-7xl text-ink">✱</div>
            <div className="absolute right-0 top-32 rotate-[-12deg] border-2 border-dashed border-ink-foreground bg-stamp-magenta px-5 py-3 font-display text-2xl">BLOCKCHAIN VERIFIED</div>
            <div className="absolute left-20 top-60 rotate-[16deg] bg-stamp-pink px-6 py-2 font-display text-xl">LATEST AI SKILLSET</div>
            <div className="absolute bottom-0 right-24 hidden h-0 w-0 border-x-[90px] border-b-[150px] border-x-transparent border-b-stamp-cyan md:block" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <h2 className="text-4xl text-brand">UNDERSTANDING AI SKILLS STAMPS</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {cats.map((c) => (
            <div key={c} className="rounded-xl border border-border bg-card p-6">
              <div className="flex h-24 items-center"><Stamp category={c} size={90} /></div>
              <h3 className="mt-4 text-xl">{c.toUpperCase()}</h3>
              <p className="text-sm uppercase text-muted-foreground">{categoryLabel[c]}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 max-w-2xl text-sm text-muted-foreground">
          The three stamp types represent different learning formats and depths of engagement. They do not form a mandatory sequence.
        </p>
      </section>

      <section className="bg-secondary">
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-20 md:grid-cols-3">
          {[
            { icon: RefreshCw, t: "Grows with you", d: "When BTU records a new skill, it's added to your existing passport as a new version. Your Passport ID never changes." },
            { icon: ShieldCheck, t: "Verified on chain", d: "Each version is fingerprinted and anchored on the blockchain. Any edit to the PDF fails verification." },
            { icon: FileDown, t: "Download & share", d: "Download your passport as a PDF, or share a verification link on LinkedIn. Employers need no account to check it." },
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
