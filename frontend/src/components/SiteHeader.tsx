import { Link } from "@tanstack/react-router";
import { useLang } from "@/lib/i18n";

export function BtuMark({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span className="font-display text-2xl leading-none">BTU</span>
      <span className="text-[9px] font-semibold leading-tight">ბიზნესისა და<br />ტექნოლოგიების<br />უნივერსიტეტი</span>
    </div>
  );
}

export function PassportTag({ className = "" }: { className?: string }) {
  return (
    <div className={`inline-block bg-brand px-3 py-1 leading-tight text-brand-foreground ${className}`}>
      <div className="text-sm">AI SKILLS</div>
      <div className="font-display text-base">DIGITAL PASSPORT</div>
    </div>
  );
}

const nav = [
  { to: "/verify", key: "nav_verify" },
  { to: "/me", key: "nav_me" },
  { to: "/admin", key: "nav_admin" },
] as const;

export function SiteHeader() {
  const { lang, setLang, t } = useLang();
  return (
    <header className="no-print sticky top-0 z-30 bg-ink text-ink-foreground">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-3">
          <span className="font-display text-xl text-brand">✱</span>
          <BtuMark />
        </Link>
        <nav className="flex items-center gap-1 text-sm font-semibold">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className="rounded-md px-3 py-2 transition-colors hover:bg-sidebar-accent"
              activeProps={{ className: "text-brand" }}
            >
              {t(n.key)}
            </Link>
          ))}
          <div className="ml-2 flex overflow-hidden rounded-md border border-ink-foreground/30 text-xs">
            {(["en", "ka"] as const).map((l) => (
              <button key={l} onClick={() => setLang(l)}
                className={`px-2 py-1.5 font-bold ${lang === l ? "bg-brand text-brand-foreground" : ""}`}>
                {l === "en" ? "EN" : "ქა"}
              </button>
            ))}
          </div>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="no-print mt-20 border-t border-border">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-6 text-xs font-bold tracking-wide text-muted-foreground">
        <span>BUSINESS AND TECHNOLOGY UNIVERSITY</span>
        <span>AI SKILLS DIGITAL PASSPORT</span>
      </div>
    </footer>
  );
}
