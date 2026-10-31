"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost, apiUpload } from "../../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState(null);
  const [resume, setResume] = useState(null);
  const [file, setFile] = useState(null);
  const [jd, setJd] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function loadAll(token) {
    apiGet("/dashboard/stats", token).then(setStats).catch(() => {});
    apiGet("/resume/me", token).then((r) => {
      setResume(r);
      if (r && r.last_ats) setResult(r.last_ats);
    }).catch(() => {});
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    const saved = localStorage.getItem("user");
    if (!token) { router.push("/login"); return; }
    if (saved) setUser(JSON.parse(saved));
    loadAll(token);
  }, [router]);

  async function handleUpload() {
    if (!file) { setError("Choose a PDF resume first"); return; }
    setBusy("upload"); setError(""); setNotice("");
    try {
      const token = localStorage.getItem("token");
      const r = await apiUpload("/resume/upload", file, token);
      setNotice(`Uploaded "${r.filename}" — ${r.word_count} words parsed, ${r.skills_detected.length} skills detected.`);
      setResult(null);
      loadAll(token);
    } catch (e) { setError(e.message); }
    setBusy("");
  }

  async function handleAnalyze() {
    if (jd.trim().length < 50) { setError("Paste a fuller job description first (at least a paragraph)"); return; }
    setBusy("analyze"); setError(""); setNotice("");
    try {
      const token = localStorage.getItem("token");
      const r = await apiPost("/resume/ats", { job_description: jd }, token);
      setResult(r);
      apiGet("/dashboard/stats", token).then(setStats).catch(() => {});
    } catch (e) { setError(e.message); }
    setBusy("");
  }

  function logout() { localStorage.clear(); router.push("/login"); }
  if (!user) return <main className="p-8">Loading...</main>;

  const bar = (label, val, max) => (
    <div className="mt-2">
      <div className="flex justify-between text-sm"><span>{label}</span><span>{val}/{max}</span></div>
      <div className="h-2 bg-slate-200 rounded mt-1">
        <div className="h-2 bg-indigo-600 rounded" style={{ width: `${Math.min(100, (val / max) * 100)}%` }} />
      </div>
    </div>
  );

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center">
        <div><h1 className="text-2xl font-bold">Welcome, {user.name} 👋</h1><p className="text-slate-500">{user.email} • {user.role}</p></div>
        <button onClick={logout} className="border px-4 py-2 rounded-lg">Logout</button>
      </div>

      <div className="grid md:grid-cols-3 gap-6 mt-8">
        <div className="card"><p className="text-slate-500 text-sm">ATS Score</p><p className="text-3xl font-bold mt-2">{stats?.ats_score ?? 0}/100</p><p className="text-sm mt-2 text-indigo-600">{resume?.has_resume ? "Based on your last ATS check ↓" : "Upload your resume below ↓"}</p></div>
        <div className="card"><p className="text-slate-500 text-sm">Mock Interviews</p><p className="text-3xl font-bold mt-2">{stats?.interviews_completed ?? 0}</p><p className="text-sm mt-2 text-indigo-600">Start interview in Sprint 4 →</p></div>
        <div className="card"><p className="text-slate-500 text-sm">Readiness Score</p><p className="text-3xl font-bold mt-2">{stats?.readiness_score ?? 0}%</p><p className="text-sm mt-2">Complete resume + 1 interview to unlock</p></div>
      </div>

      {stats?.weak_topics?.length > 0 && (
        <div className="card mt-6">
          <h2 className="font-semibold">Focus Areas</h2>
          <ul className="list-disc ml-5 mt-2 text-slate-600">{stats.weak_topics.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      <div className="card mt-6">
        <h2 className="font-semibold text-lg">📄 Resume & ATS Check — Sprint 2</h2>

        {resume?.has_resume ? (
          <p className="text-sm text-slate-600 mt-2">Current resume: <b>{resume.filename}</b> • {resume.word_count} words • {resume.skills_detected.length} skills detected
            <span className="block mt-1">{resume.skills_detected.slice(0, 14).map((s) => <span key={s} className="inline-block bg-slate-100 rounded px-2 py-0.5 mr-1 mt-1 text-xs">{s}</span>)}</span>
          </p>
        ) : (
          <p className="text-sm text-slate-600 mt-2">No resume uploaded yet. Upload a text-based PDF to parse it and detect your skills.</p>
        )}

        <div className="flex flex-wrap items-center gap-3 mt-4">
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-sm" />
          <button onClick={handleUpload} disabled={busy === "upload"} className="bg-indigo-600 text-white px-4 py-2 rounded-lg disabled:opacity-50">{busy === "upload" ? "Uploading..." : "Upload Resume (PDF)"}</button>
        </div>

        <textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={7}
          placeholder="Paste a job description here (e.g. a Data Engineering internship JD from LinkedIn) and click Analyze to score your resume against it..."
          className="w-full border rounded-lg p-3 mt-5 text-sm" />
        <button onClick={handleAnalyze} disabled={busy === "analyze" || !resume?.has_resume} className="bg-emerald-600 text-white px-4 py-2 rounded-lg mt-3 disabled:opacity-50">{busy === "analyze" ? "Analyzing..." : "Analyze Against This JD"}</button>
        {!resume?.has_resume && <span className="text-sm text-slate-500 ml-3">Upload a resume first to enable analysis.</span>}

        {error && <p className="text-red-600 text-sm mt-3">{error}</p>}
        {notice && <p className="text-emerald-700 text-sm mt-3">{notice}</p>}

        {result && (
          <div className="mt-6 border-t pt-5">
            <div className="flex items-end gap-3">
              <p className="text-5xl font-bold">{result.score}<span className="text-xl text-slate-500">/100</span></p>
              <p className="text-slate-500 text-sm pb-1">ATS match for {result.filename}<br />{result.keyword_basis}</p>
            </div>
            <div className="max-w-md">
              {bar("Keyword / skill match", result.breakdown.keyword_match, 60)}
              {bar("Resume sections", result.breakdown.sections, 25)}
              {bar("Length", result.breakdown.length, 10)}
              {bar("Action verbs", result.breakdown.action_verbs, 5)}
            </div>
            {result.matched_skills?.length > 0 && (
              <p className="mt-4 text-sm"><b className="text-emerald-700">Matched skills:</b> {result.matched_skills.map((s) => <span key={s} className="inline-block bg-emerald-50 border border-emerald-200 rounded px-2 py-0.5 mr-1 mt-1 text-xs">{s}</span>)}</p>
            )}
            {result.missing_skills?.length > 0 && (
              <p className="mt-3 text-sm"><b className="text-red-600">Missing from your resume:</b> {result.missing_skills.map((s) => <span key={s} className="inline-block bg-red-50 border border-red-200 rounded px-2 py-0.5 mr-1 mt-1 text-xs">{s}</span>)}</p>
            )}
            <div className="mt-4 text-sm">
              <b>How to improve:</b>
              <ul className="list-disc ml-5 mt-1 text-slate-600">{result.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          </div>
        )}
      </div>

      <div className="card mt-6">
        <h2 className="font-semibold text-lg">Next Steps - Sprint Roadmap</h2>
        <ol className="list-decimal ml-5 mt-3 space-y-2 text-slate-600">
          <li><b>Sprint 1 (Done):</b> Auth + Dashboard UI — live on Vercel</li>
          <li><b>Sprint 2 (Done):</b> Resume upload & ATS scoring</li>
          <li><b>Sprint 3:</b> Database persistence (Supabase) + saved ATS history</li>
          <li><b>Sprint 4-5:</b> AI Mock Interview (text + voice)</li>
        </ol>
      </div>
    </main>
  );
}
