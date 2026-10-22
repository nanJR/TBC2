"use client";
// District dashboard: who is most likely to stop treatment this week,
// and the next steps the agent suggests, which a person approves or rejects.

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { decideAction, getActions, getWeeklyRisk, type Action, type RiskEntry } from "@/lib/api";

const ACTION_LABELS: Record<Action["type"], string> = {
  sms: "SMS reminder",
  home_visit: "Home visit",
  nutrition_support: "Nutrition support",
};

export default function DashboardPage() {
  const [risk, setRisk] = useState<RiskEntry[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load both lists once when the page opens.
  useEffect(() => {
    Promise.all([getWeeklyRisk(20), getActions()])
      .then(([r, a]) => {
        setRisk(r);
        setActions(a);
      })
      .catch(() => setError("Could not reach the back end. Is it running?"));
  }, []);

  async function decide(id: number, decision: "approve" | "reject") {
    const updated = await decideAction(id, decision);
    // Replace just the changed action in the list.
    setActions((list) => list.map((a) => (a.action_id === id ? updated : a)));
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8">
      <Link href="/" className="text-muted-foreground text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold">District dashboard</h1>
      {error && <p className="text-destructive text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Suggested actions</CardTitle>
          <CardDescription>Nothing is sent until you approve it.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {actions.map((a) => (
            <div key={a.action_id} className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center">
              <div className="flex-1">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {ACTION_LABELS[a.type]} · {a.patient_id}
                  {a.status !== "pending" && (
                    <Badge variant={a.status === "approved" ? "default" : "outline"}>{a.status}</Badge>
                  )}
                </div>
                <p className="text-muted-foreground text-sm">{a.draft}</p>
              </div>
              {a.status === "pending" && (
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => decide(a.action_id, "approve")}>Approve</Button>
                  <Button size="sm" variant="outline" onClick={() => decide(a.action_id, "reject")}>
                    Reject
                  </Button>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Highest dropout risk this week</CardTitle>
          <CardDescription>
            {risk[0]?.is_mock ? "Scores come from simple rules until the real model is trained." : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Patient</TableHead>
                <TableHead>District</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Main reasons</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {risk.map((r) => (
                <TableRow key={r.patient.patient_id}>
                  <TableCell className="font-mono text-xs">{r.patient.patient_id}</TableCell>
                  <TableCell>{r.patient.district}</TableCell>
                  <TableCell>
                    <Badge variant={r.risk_score >= 0.6 ? "destructive" : "secondary"}>
                      {Math.round(r.risk_score * 100)}%
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">{r.reasons.join(", ")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </main>
  );
}
