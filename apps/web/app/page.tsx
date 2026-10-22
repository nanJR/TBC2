import Link from "next/link";

import { BackendStatus } from "@/components/backend-status";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Home page. Later this links to the ASHA screening flow (app/(asha))
// and the district dashboard (app/(district)).
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">TBC²</h1>
        <p className="text-muted-foreground mt-1">AI-powered TB care coordinator</p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link href="/screen" className={buttonVariants({ size: "lg" })}>
          ASHA: screen a person
        </Link>
        <Link href="/dashboard" className={buttonVariants({ size: "lg", variant: "outline" })}>
          District dashboard
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System check</CardTitle>
          <CardDescription>Is the front end talking to the back end?</CardDescription>
        </CardHeader>
        <CardContent>
          <BackendStatus />
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs">
        Prototype for learning only. Not for clinical use. Public datasets and
        synthetic patients only.
      </p>
    </main>
  );
}
