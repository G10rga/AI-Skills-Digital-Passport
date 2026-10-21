import { QRCodeSVG } from "qrcode.react";
import type { ReactNode } from "react";
import type { Passport, PassportVersion, SkillCategory } from "@/lib/types";
import { BtuMark, PassportTag } from "@/components/SiteHeader";
import { Stamp } from "./Stamp";

const fmt = (d: string) => {
  const [y, m, day] = d.slice(0, 10).split("-");
  return `${day}.${m}.${y}`;
};

function Page({ children, passportId, footerRight = true }: { children: ReactNode; passportId: string; footerRight?: boolean }) {
  return (
    <div className="passport-page rounded-[28px] bg-ink p-3 shadow-xl">
      <div className="rounded-[22px] bg-secondary p-3">
        <div className="relative flex aspect-[1.414/1] flex-col overflow-hidden rounded-xl border border-border bg-card p-[4%] text-card-foreground">
          {children}
          <div className={`mt-auto flex items-end justify-between gap-4 pt-4 ${footerRight ? "" : "flex-row-reverse"}`}>
            <div className="flex items-end gap-5">
              <PassportTag />
              <BtuMark />
            </div>
            <div className="text-sm">PASSPORT ID: <span className="font-display">{passportId}</span></div>
          </div>
        </div>
      </div>
      <div className="px-3 pt-2 font-display text-xs tracking-wide text-ink-foreground">BUSINESS AND TECHNOLOGY UNIVERSITY</div>
    </div>
  );
}

function Cover({ p, v, verifyUrl }: { p: Passport; v: PassportVersion; verifyUrl: string }) {
  return (
    <Page passportId={p.passportId}>
      <div className="flex justify-between">
        <h1 className="text-[clamp(1.6rem,5vw,4rem)] leading-[0.9]">
          AI SKILLS
          <br />
          <span className="font-sans font-light">DIGITAL PASSPORT</span>
        </h1>
        <div className="flex flex-col font-display text-3xl leading-none text-brand">
          <span>✱</span><span>✱</span><span>✱</span>
        </div>
      </div>
      <div className="mt-6 border-t border-border pt-6 grid grid-cols-2 gap-6">
        <div className="space-y-3 text-[clamp(0.8rem,1.6vw,1.4rem)]">
          <div><span className="font-display">NAME: </span>{p.firstName.toUpperCase()}</div>
          <div><span className="font-display">SURNAME: </span>{p.lastName.toUpperCase()}</div>
          <div className="pt-2 text-xs text-muted-foreground">{p.program} · {p.educationLevel}</div>
        </div>
        <div className="space-y-3 text-[clamp(0.8rem,1.6vw,1.4rem)]">
          <div><span className="font-display">DATE OF ISSUE: </span>{fmt(p.firstIssued)}</div>
          <div className="text-xs text-muted-foreground">Version V{v.version} · issued {fmt(v.issuedAt)}</div>
        </div>
      </div>
      <div className="relative mt-4 flex flex-1 items-center justify-between">
        <div className="relative hidden h-40 w-80 sm:block">
          <div className="absolute left-10 top-0 -rotate-3 border-2 border-ink bg-brand px-3 py-1 font-display text-xs">ISSUED BY BUSINESS AND TECHNOLOGY UNIVERSITY</div>
          <div className="absolute left-0 top-8 flex h-24 w-24 items-center justify-center rounded-full border-4 border-ink bg-stamp-green font-display text-4xl">✱</div>
          <div className="absolute left-24 top-12 rotate-[-8deg] border-2 border-dashed border-background bg-stamp-magenta px-3 py-1 font-display text-sm text-background">BLOCKCHAIN VERIFIED</div>
          <div className="absolute left-8 top-[7.5rem] rotate-[18deg] bg-stamp-pink px-4 py-1 font-display text-sm text-background">LATEST AI SKILLSET</div>
        </div>
        <div className="flex flex-col items-center gap-1">
          <QRCodeSVG value={verifyUrl} size={92} />
          <div className="text-[10px] text-muted-foreground">VERIFICATION CODE</div>
          <div className="font-display text-xs">{v.verificationCode}</div>
        </div>
      </div>
    </Page>
  );
}

const stampInfo: { cat: SkillCategory; title: string; sub: string; text: string; rep: string }[] = [
  { cat: "AI Skill", title: "AI SKILL", sub: "FOCUSED LEARNING", text: "Awarded through an eligible focused learning experience, such as a workshop, masterclass, seminar, guest speaker session, or similar short-format activity.", rep: "Development of a defined AI competency." },
  { cat: "AI Applied Skill", title: "AI APPLIED SKILL", sub: "APPLIED LEARNING", text: "Awarded through an eligible extended practical learning experience, typically lasting two to three days, such as an intensive workshop, bootcamp, hackathon, or challenge.", rep: "Hands-on application of a defined AI competency." },
  { cat: "AI Advanced Skill", title: "AI ADVANCED SKILL", sub: "EXTENDED ACADEMIC LEARNING", text: "Awarded through the successful completion of an eligible semester-long academic course in which the respective AI competency constitutes a defined and assessed component of the course learning outcomes.", rep: "Extended and formally assessed development of an AI competency." },
];

function About({ p }: { p: Passport }) {
  return (
    <Page passportId={p.passportId} footerRight={false}>
      <div className="grid flex-1 grid-cols-[1fr_2fr] gap-6 text-[clamp(0.5rem,0.9vw,0.75rem)]">
        <div className="space-y-2 border-r border-border pr-6">
          <h2 className="text-[clamp(1rem,2.4vw,1.9rem)] leading-none">ABOUT<br />THE AI SKILLS<br /><span className="font-sans font-light">DIGITAL PASSPORT</span></h2>
          <p>The BTU AI Skills Digital Passport is your personalized and verifiable record of AI competencies developed throughout your university experience.</p>
          <p>AI Skill Stamps may be earned through eligible academic courses, workshops, masterclasses, hackathons, intensive programs, guest speaker sessions, and other AI-related learning experiences recognized by BTU.</p>
          <p>Participation in the Passport is voluntary. There is no required number or combination of stamps and no predefined pathway.</p>
          <p>As new competencies are developed and recognized, additional stamps are added to the Passport, progressively creating an individual AI competency profile.</p>
          <div className="font-display text-brand tracking-[0.4em]">✱✱✱✱✱✱✱</div>
        </div>
        <div className="space-y-3">
          <h2 className="text-[clamp(0.9rem,2.2vw,1.8rem)] leading-none text-brand">UNDERSTANDING AI SKILLS STAMPS</h2>
          <div className="grid grid-cols-2 gap-4">
            {stampInfo.map((s) => (
              <div key={s.cat} className="space-y-1">
                <div className="flex items-start justify-between gap-2">
                  <div><div className="font-display text-[1.2em]">{s.title}</div><div>{s.sub}</div></div>
                  <Stamp category={s.cat} size={46} />
                </div>
                <p>{s.text}</p>
                <p><b>Represents:</b> {s.rep}</p>
              </div>
            ))}
            <div className="space-y-1 text-center">
              <div className="font-display">HOW THE PASSPORT GROWS</div>
              {["LEARN", "DEMONSTRATE", "EARN", "VERIFY", "BUILD YOUR AI PROFILE"].map((x) => (
                <div key={x}><span className="text-brand">✱</span> {x}</div>
              ))}
            </div>
          </div>
          <div className="rounded-md bg-secondary p-2">
            <b>IMPORTANT</b>
            <p>The three stamp types represent different learning formats and depths of engagement. They do not constitute a mandatory sequence.</p>
          </div>
        </div>
      </div>
    </Page>
  );
}

function Skillset({ p, v }: { p: Passport; v: PassportVersion }) {
  const cells = [...v.skills, ...Array(Math.max(0, 10 - v.skills.length)).fill(null)];
  return (
    <Page passportId={p.passportId}>
      <h2 className="text-[clamp(1rem,2.2vw,1.8rem)] leading-none">VERIFIED AI SKILLSET</h2>
      <p className="mb-3 text-xs font-semibold">Collection of BTU-verified AI skill Stamps</p>
      <div className="grid flex-1 grid-cols-5 gap-2">
        {cells.map((s, i) => (
          <div key={s?.recordId ?? i} className="flex flex-col rounded-lg border border-border">
            <div className="border-b border-border py-0.5 text-center text-[9px]">{s ? fmt(s.dateEarned) : ""}</div>
            {s && (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 p-1 text-center">
                <Stamp category={s.skillCategory} size={44} />
                <div className="font-display text-[clamp(0.45rem,0.8vw,0.7rem)] leading-tight">{s.skillName.toUpperCase()}</div>
                <div className="text-[clamp(0.4rem,0.7vw,0.6rem)]">{s.skillCategory.toUpperCase()}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </Page>
  );
}

function Detailed({ p, v }: { p: Passport; v: PassportVersion }) {
  return (
    <Page passportId={p.passportId} footerRight={false}>
      <h2 className="text-[clamp(1rem,2.2vw,1.8rem)] leading-none">AI SKILLS DETAILED INFORMATION</h2>
      <p className="mb-3 text-xs font-semibold">Detailed record of verified AI skills and learning experiences</p>
      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-[clamp(0.45rem,0.8vw,0.7rem)]">
          <thead className="font-display">
            <tr className="border-b border-border">
              {["STAMP TYPE", "SKILL", "DESCRIPTION", "BADGE", "DATE EARNED"].map((h) => (
                <th key={h} className="border-r border-border p-2 last:border-r-0">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {v.skills.map((s) => (
              <tr key={s.recordId} className="border-b border-border last:border-b-0">
                <td className="border-r border-border p-1 text-center"><Stamp category={s.skillCategory} size={34} /></td>
                <td className="border-r border-border p-1 text-center font-display">{s.skillName.toUpperCase()}</td>
                <td className="border-r border-border p-1 text-center uppercase">{s.skillDescription}</td>
                <td className="border-r border-border p-1 text-center">{s.badgeCode}</td>
                <td className="p-1 text-center">{fmt(s.dateEarned)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Page>
  );
}

export function PassportDocument({ passport, version, verifyUrl }: { passport: Passport; version: PassportVersion; verifyUrl: string }) {
  return (
    <div className="space-y-8">
      <Cover p={passport} v={version} verifyUrl={verifyUrl} />
      <About p={passport} />
      <Skillset p={passport} v={version} />
      <Detailed p={passport} v={version} />
    </div>
  );
}
