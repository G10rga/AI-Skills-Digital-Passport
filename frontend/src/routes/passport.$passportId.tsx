import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { getPassport } from "@/lib/api";
import { PassportView } from "@/components/passport/PassportView";

export const Route = createFileRoute("/passport/$passportId")({
  ssr: false,
  head: ({ params }) => ({
    meta: [
      { title: `Passport ${params.passportId} · BTU AI Skills` },
      { name: "description", content: `BTU AI Skills Digital Passport ${params.passportId}.` },
      { property: "og:title", content: `BTU AI Skills Digital Passport ${params.passportId}` },
      { property: "og:description", content: "Blockchain-verified AI skills issued by BTU." },
    ],
  }),
  component: PassportPage,
});

function PassportPage() {
  const { passportId } = Route.useParams();
  const { data, isLoading } = useQuery({ queryKey: ["passport", passportId], queryFn: () => getPassport(passportId) });
  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      {isLoading ? (
        <p className="text-muted-foreground">Loading passport…</p>
      ) : !data ? (
        <div className="py-20 text-center">
          <h1 className="text-3xl">Passport not found</h1>
          <Link to="/verify" search={{ code: undefined }} className="mt-4 inline-block underline">Verify by code instead</Link>
        </div>
      ) : (
        <PassportView passport={data} />
      )}
    </div>
  );
}
