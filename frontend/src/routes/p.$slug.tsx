import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getPublicProfile } from "@/lib/api";

export const Route = createFileRoute("/p/$slug")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Verified profile · BTU AI Skills" },
      { name: "description", content: "Shareable BTU-verified AI skills profile." },
    ],
  }),
  component: PublicProfilePage,
});

function PublicProfilePage() {
  const { slug } = Route.useParams();
  const { data, isLoading, isError } = useQuery({ queryKey: ["public", slug], queryFn: () => getPublicProfile(slug) });
  return (
    <div className="mx-auto max-w-3xl px-4 py-14">
      <ShieldCheck className="h-10 w-10 text-brand" />
      {isLoading ? <p className="mt-4 text-muted-foreground">Loading…</p> : isError || !data ? (
        <>
          <h1 className="mt-3 text-4xl">Profile not found</h1>
          <p className="mt-2 text-muted-foreground">This verified-profile link is not recognised.</p>
        </>
      ) : (
        <>
          <h1 className="mt-3 text-4xl">{data.firstName} {data.lastName}</h1>
          <p className="mt-1 text-muted-foreground">{data.program} · {data.educationLevel} · Passport {data.passportId} · first issued {data.firstIssued}</p>
          <div className="mt-6 rounded-xl border border-border bg-card p-5">
            <div className="font-display">Verified AI skills ({data.skills.length}) — latest version V{data.latestVersion}</div>
            <ul className="mt-3 space-y-2">
              {data.skills.map((s) => (
                <li key={s.recordId} className="flex flex-wrap justify-between gap-2 text-sm">
                  <span className="font-semibold">{s.skillName}</span>
                  <span className="text-muted-foreground">{s.skillCategory} · {s.badgeCode} · {s.dateEarned}</span>
                </li>
              ))}
            </ul>
            {data.verificationCode && (
              <Button asChild className="mt-5">
                <Link to="/verify" search={{ code: data.verificationCode }}>Verify latest version</Link>
              </Button>
            )}
          </div>
          <Link to="/passport/$passportId" params={{ passportId: data.passportId }} className="mt-4 inline-block underline">View full passport document</Link>
        </>
      )}
    </div>
  );
}
