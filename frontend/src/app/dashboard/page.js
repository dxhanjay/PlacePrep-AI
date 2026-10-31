"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState(null); const [stats, setStats] = useState(null);
  useEffect(() => {
    const token = localStorage.getItem("token");
    const saved = localStorage.getItem("user");
    if (!token) { router.push("/login"); return; }
    if (saved) setUser(JSON.parse(saved));
    apiGet("/dashboard/stats", token).then(setStats).catch(() => {});
  }, [router]);

  function logout() { localStorage.clear(); router.push("/login"); }
  if (!user) return <main className="p-8">Loading...</main>;
  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center">
        <div><h1 className="text-2xl font-bold">Welcome, {user.name} 👋</h1><p className="text-slate-500">{user.email} • {user.role}</p></div>
        <button onClick={logout} className="border px-4 py-2 rounded-lg">Logout</button>
      </div>
      <div className="grid md:grid-cols-3 gap-6 mt-8">
        <div className="card"><p className="text-slate-500 text-sm">ATS Score</p><p className="text-3xl font-bold mt-2">{stats?.ats_score ?? 0}/100</p><p className="text-sm mt-2 text-indigo-600">Upload resume in Sprint 2 →</p></div>
        <div className="card"><p className="text-slate-500 text-sm">Mock Interviews</p><p className="text-3xl font-bold mt-2">{stats?.interviews_completed ?? 0}</p><p className="text-sm mt-2 text-indigo-600">Start interview in Sprint 4 →</p></div>
        <div className="card"><p className="text-slate-500 text-sm">Readiness Score</p><p className="text-3xl font-bold mt-2">{stats?.readiness_score ?? 0}%</p><p className="text-sm mt-2">Complete resume + 1 interview to unlock</p></div>
      </div>
      <div className="card mt-6">
        <h2 className="font-semibold text-lg">Next Steps - Sprint Roadmap</h2>
        <ol className="list-decimal ml-5 mt-3 space-y-2 text-slate-600">
          <li><b>Sprint 1 (Done):</b> Auth + Dashboard UI</li>
          <li><b>Sprint 2:</b> Resume upload & ATS scoring</li>
          <li><b>Sprint 3:</b> Resume vs JD skill-gap</li>
          <li><b>Sprint 4-5:</b> AI Mock Interview (text + voice)</li>
        </ol>
      </div>
    </main>
  );
}
