import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { currentStudentEmail, getMyPassport, loginStudent, logoutStudent } from "@/lib/api";
import { PassportView } from "@/components/passport/PassportView";

export const Route = createFileRoute("/me")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "My passport · BTU AI Skills" },
      { name: "description", content: "Sign in with your BTU account to view and download your AI Skills Digital Passport." },
      { property: "og:title", content: "My AI Skills Digital Passport" },
      { property: "og:description", content: "View and download your BTU AI Skills Digital Passport." },
    ],
  }),
  component: MePage,
});

function MePage() {
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => setEmail(currentStudentEmail()), []);
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me", email], queryFn: () => getMyPassport(email!), enabled: !!email });

  if (!email) return <Login onLogin={setEmail} />;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="no-print mb-8 flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Signed in as {email}</p>
          <h1 className="text-3xl">{data ? `Hello, ${data.firstName}` : "My passport"}</h1>
        </div>
        <Button variant="outline" onClick={() => { logoutStudent(); setEmail(null); qc.clear(); }}><LogOut /> Sign out</Button>
      </div>
      {isLoading ? <p className="text-muted-foreground">Loading…</p> : data ? <PassportView passport={data} /> : <p>No passport found for this account.</p>}
    </div>
  );
}

function Login({ onLogin }: { onLogin: (e: string) => void }) {
  const [value, setValue] = useState("btu-t-0001@example.org");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-md px-4 py-20">
      <h1 className="text-3xl">Sign in with BTU</h1>
      <p className="mt-2 text-muted-foreground">Use your BTU university account to see your passport.</p>
      <form
        className="mt-8 space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          const r = await loginStudent(value);
          setBusy(false);
          if (r) onLogin(r.email); else setError("No passport is linked to this BTU email.");
        }}
      >
        <Input type="email" value={value} onChange={(e) => setValue(e.target.value)} placeholder="name@btu.edu.ge" required />
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" disabled={busy}>{busy ? "Signing in…" : "Continue with BTU account"}</Button>
      </form>
      <p className="mt-4 text-xs text-muted-foreground">Demo: any test email from the sheet works, e.g. btu-t-0002@example.org.</p>
    </div>
  );
}
