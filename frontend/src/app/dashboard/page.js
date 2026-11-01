"use client";
import { useEffect, useRef, useState } from "react";
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

  // Sprint 4: mock interview state
  const [tracks, setTracks] = useState([]);
  const [trackSel, setTrackSel] = useState("data-engineering");
  const [session, setSession] = useState(null);
  const [answerText, setAnswerText] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [iBusy, setIBusy] = useState(false);
  const [iError, setIError] = useState("");

  // Sprint 5: voice mode (Web Speech API) + analytics + TPO view
  const [analytics, setAnalytics] = useState(null);
  const [tpo, setTpo] = useState(null);
  const [voiceOn, setVoiceOn] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [usedVoice, setUsedVoice] = useState(false);
  const recogRef = useRef(null);

  function loadAll(token) {
    apiGet("/dashboard/stats", token).then(setStats).catch(() => {});
    apiGet("/resume/me", token).then((r) => {
      setResume(r);
      if (r && r.last_ats) setResult(r.last_ats);
    }).catch(() => {});
    apiGet("/interview/history", token).then((h) => setHistory(h.sessions || [])).catch(() => {});
    apiGet("/analytics/me", token).then(setAnalytics).catch(() => {});
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    const saved = localStorage.getItem("user");
    if (!token) { router.push("/login"); return; }
    if (saved) setUser(JSON.parse(saved));
    loadAll(token);
    apiGet("/interview/tracks", token).then((t) => setTracks(t.tracks || [])).catch(() => {});
    const parsed = saved ? JSON.parse(saved) : null;
    if (parsed?.role === "tpo") {
      apiGet("/tpo/overview", token).then(setTpo).catch(() => {});
    }
    setVoiceSupported(
      typeof window !== "undefined" &&
      (!!window.speechSynthesis || !!(window.SpeechRecognition || window.webkitSpeechRecognition))
    );
  }, [router]);

  // Sprint 5 voice helpers -------------------------------------------------
  function speak(text) {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-IN";
    u.rate = 1.02;
    window.speechSynthesis.speak(u);
  }

  // Read each new question aloud while voice mode is on.
  useEffect(() => {
    if (voiceOn && session?.current?.question) speak(session.current.question);
    setUsedVoice(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.current?.number, session?.session_id]);

  function toggleListening() {
    if (listening) { recogRef.current?.stop(); return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setIError("Voice input is not supported in this browser — Chrome works best."); return; }
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = true;
    rec.onresult = (e) => {
      let finalText = "";
      for (const r of e.results) if (r.isFinal) finalText += r[0].transcript + " ";
      if (finalText) {
        setUsedVoice(true);
        setAnswerText((prev) => (prev ? prev.replace(/\s+$/, "") + " " : "") + finalText.trim() + " ");
      }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recogRef.current = rec;
    setListening(true);
    rec.start();
  }

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

  async function startInterview() {
    setIBusy(true); setIError(""); setFeedback(null); setSummary(null); setAnswerText("");
    try {
      const token = localStorage.getItem("token");
      const s = await apiPost("/interview/start", { track: trackSel }, token);
      setSession(s);
    } catch (e) { setIError(e.message); }
    setIBusy(false);
  }

  async function submitAnswer() {
    if (answerText.trim().length < 3) { setIError("Type your answer first — aim for 40+ words with an example"); return; }
    setIBusy(true); setIError("");
    try {
      const token = localStorage.getItem("token");
      const r = await apiPost("/interview/answer", { session_id: session.session_id, answer: answerText, input_mode: usedVoice ? "voice" : "text" }, token);
      setFeedback(r.feedback);
      setAnswerText("");
      if (listening) recogRef.current?.stop();
      if (r.finished) {
        setSummary(r.summary);
        setSession(null);
        loadAll(token);
      } else {
        setSession({ ...session, current: r.next });
      }
    } catch (e) { setIError(e.message); }
    setIBusy(false);
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
        <div className="card"><p className="text-slate-500 text-sm">Mock Interviews</p><p className="text-3xl font-bold mt-2">{stats?.interviews_completed ?? 0}</p><p className="text-sm mt-2 text-indigo-600">{stats?.last_interview_score != null ? `Average score ${stats.last_interview_score}/100 — practise below ↓` : "Take your first interview below ↓"}</p></div>
        <div className="card"><p className="text-slate-500 text-sm">Readiness Score</p><p className="text-3xl font-bold mt-2">{stats?.readiness_score ?? 0}%</p><p className="text-sm mt-2">50% resume (ATS) + 50% interview performance</p></div>
      </div>

      {stats?.weak_topics?.length > 0 && (
        <div className="card mt-6">
          <h2 className="font-semibold">Focus Areas</h2>
          <ul className="list-disc ml-5 mt-2 text-slate-600">{stats.weak_topics.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      <div className="card mt-6">
        <h2 className="font-semibold text-lg">🎤 AI Mock Interview — now with Voice (Sprint 5)</h2>
        <p className="text-sm text-slate-600 mt-1">Five questions per session, scored instantly on key-point coverage, depth and structure — with the exact points you hit and missed. Turn on Voice Mode and the interviewer reads each question aloud; answer by speaking, just like a real interview.</p>

        {!session && !summary && (
          <div className="flex flex-wrap items-center gap-3 mt-4">
            <select value={trackSel} onChange={(e) => setTrackSel(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
              {tracks.map((t) => <option key={t.id} value={t.id}>{t.title} ({t.per_session} questions)</option>)}
            </select>
            <button onClick={startInterview} disabled={iBusy} className="bg-indigo-600 text-white px-4 py-2 rounded-lg disabled:opacity-50">{iBusy ? "Starting..." : "Start Interview"}</button>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={voiceOn} onChange={(e) => setVoiceOn(e.target.checked)} disabled={!voiceSupported} />
              🔊 Voice Mode {voiceSupported ? "" : "(not supported in this browser — try Chrome)"}
            </label>
          </div>
        )}

        {session && (
          <div className="mt-4">
            <p className="text-sm text-slate-500">{session.track_title} • Question {session.current.number} of {session.current.total}</p>
            <p className="font-medium mt-1">{session.current.question}
              {voiceSupported && <button onClick={() => speak(session.current.question)} className="ml-3 text-indigo-600 text-sm underline">🔊 Hear question</button>}
            </p>
            <textarea value={answerText} onChange={(e) => setAnswerText(e.target.value)} rows={6}
              placeholder="Type your answer — or tap the mic and speak it. Aim for 40-180 words, cover the key concepts, and add a concrete example..."
              className="w-full border rounded-lg p-3 mt-3 text-sm" />
            <div className="flex flex-wrap items-center gap-3 mt-3">
              <button onClick={submitAnswer} disabled={iBusy} className="bg-emerald-600 text-white px-4 py-2 rounded-lg disabled:opacity-50">{iBusy ? "Scoring..." : "Submit Answer"}</button>
              {voiceSupported && (
                <button onClick={toggleListening} className={`px-4 py-2 rounded-lg border ${listening ? "bg-red-600 text-white border-red-600" : ""}`}>
                  {listening ? "🔴 Listening… tap to stop" : "🎙️ Answer by voice"}
                </button>
              )}
              {usedVoice && !listening && <span className="text-xs text-slate-500">Voice answer — edit the transcript if needed, then submit.</span>}
            </div>
          </div>
        )}

        {iError && <p className="text-red-600 text-sm mt-3">{iError}</p>}

        {feedback && (
          <div className="mt-5 border-t pt-4">
            <p className="font-semibold">{feedback.verdict} — {feedback.score}/100 <span className="text-slate-500 font-normal text-sm">({feedback.word_count} words)</span></p>
            {feedback.matched_points?.length > 0 && <p className="text-sm mt-2"><b className="text-emerald-700">✓ You covered:</b> {feedback.matched_points.join(" · ")}</p>}
            {feedback.missed_points?.length > 0 && <p className="text-sm mt-1"><b className="text-red-600">✗ Missing:</b> {feedback.missed_points.join(" · ")}</p>}
            <p className="text-sm mt-2 text-slate-600">💡 {feedback.tip}</p>
          </div>
        )}

        {summary && (
          <div className="mt-5 border-t pt-4">
            <div className="flex items-end gap-3">
              <p className="text-5xl font-bold">{summary.overall_score}<span className="text-xl text-slate-500">/100</span></p>
              <p className="text-slate-600 pb-1">{summary.grade}</p>
            </div>
            <div className="mt-3 space-y-1 text-sm">
              {summary.per_question.map((q, i) => (
                <div key={i} className="flex justify-between gap-4 border-b border-slate-100 py-1"><span className="text-slate-600">{i + 1}. {q.question}</span><b>{q.score}</b></div>
              ))}
            </div>
            {summary.improvements?.length > 0 && <p className="text-sm mt-3"><b>Revise these points:</b> {summary.improvements.join(" · ")}</p>}
            {summary.voice_answers > 0 && <p className="text-sm mt-2 text-slate-600">🎙️ {summary.voice_answers} of {summary.per_question.length} answers given by voice.</p>}
            <button onClick={() => { setSummary(null); setFeedback(null); }} className="border px-4 py-2 rounded-lg mt-4 text-sm">Start Another Interview</button>
          </div>
        )}

        {history.length > 0 && (
          <div className="mt-5 border-t pt-4">
            <h3 className="font-semibold text-sm">Past Interviews</h3>
            <ul className="text-sm text-slate-600 mt-2 space-y-1">
              {history.slice(0, 5).map((h) => (
                <li key={h.session_id}>{h.track_title} — {h.status === "completed" ? `scored ${h.overall_score}/100` : `in progress (${h.questions_answered} answered)`} • {new Date(h.created_at).toLocaleString()}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {analytics && (analytics.interviews_completed > 0 || analytics.has_resume) && (
        <div className="card mt-6">
          <h2 className="font-semibold text-lg">📊 Your Insights — Sprint 5</h2>
          <div className="grid md:grid-cols-2 gap-6 mt-4">
            <div>
              <p className="text-sm font-medium">Readiness breakdown</p>
              <div className="max-w-sm">
                {bar("Resume (ATS)", analytics.ats_score, 100)}
                <p className="text-xs text-slate-500 mt-1">Contributes {analytics.ats_points}/50 points</p>
                {bar("Interviews (average)", analytics.interview_avg ?? 0, 100)}
                <p className="text-xs text-slate-500 mt-1">Contributes {analytics.interview_points}/50 points</p>
              </div>
              <p className="text-sm mt-4 text-slate-600">
                Practice so far: <b>{analytics.practice.total_answers}</b> answers • <b>{analytics.practice.total_words}</b> words
                {analytics.practice.voice_answers > 0 && <> • <b>{analytics.practice.voice_answers}</b> by voice 🎙️</>}
                {analytics.score_delta != null && <> • Score trend: <b>{analytics.score_delta >= 0 ? "+" : ""}{analytics.score_delta}</b> since your first interview</>}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium">Score trend</p>
              {analytics.trend.length > 0 ? (
                <div className="flex items-end gap-2 h-28 mt-2 border-b border-slate-200 pb-0">
                  {analytics.trend.slice(-8).map((t, i) => (
                    <div key={i} className="flex flex-col items-center justify-end h-full flex-1">
                      <span className="text-xs font-medium">{t.score}</span>
                      <div className="w-full max-w-8 bg-indigo-500 rounded-t" style={{ height: `${Math.max(8, t.score)}%` }} title={`${t.track_title}: ${t.score}`} />
                      <span className="text-[10px] text-slate-500 mt-1">{new Date(t.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>
                    </div>
                  ))}
                </div>
              ) : <p className="text-sm text-slate-500 mt-2">Finish an interview to start your trend.</p>}
              {analytics.tracks.length > 0 && (
                <div className="mt-4 space-y-1 text-sm">
                  {analytics.tracks.map((t) => (
                    <p key={t.track} className="text-slate-600">{t.track_title}: avg <b>{t.avg_score}</b> • best <b>{t.best_score}</b> • {t.sessions} session{t.sessions > 1 ? "s" : ""}</p>
                  ))}
                </div>
              )}
            </div>
          </div>
          {analytics.recurring_gaps.length > 0 && (
            <div className="mt-4 border-t pt-4">
              <p className="text-sm font-medium">Recurring gaps — points you keep missing</p>
              <p className="mt-2">{analytics.recurring_gaps.map((g, i) => (
                <span key={i} className="inline-block bg-amber-50 border border-amber-200 rounded px-2 py-0.5 mr-1 mt-1 text-xs">{g.point} ×{g.times_missed}</span>
              ))}</p>
            </div>
          )}
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

      {tpo && (
        <div className="card mt-6">
          <h2 className="font-semibold text-lg">🏫 TPO Overview — Sprint 5</h2>
          <p className="text-sm text-slate-600 mt-1">Placement-cell view of the whole cohort.</p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4 text-center">
            <div><p className="text-2xl font-bold">{tpo.cohort.total_students}</p><p className="text-xs text-slate-500">Students</p></div>
            <div><p className="text-2xl font-bold">{tpo.cohort.students_with_resume}</p><p className="text-xs text-slate-500">With resume</p></div>
            <div><p className="text-2xl font-bold">{tpo.cohort.students_interviewed}</p><p className="text-xs text-slate-500">Interviewed</p></div>
            <div><p className="text-2xl font-bold">{tpo.cohort.total_interviews}</p><p className="text-xs text-slate-500">Interviews done</p></div>
            <div><p className="text-2xl font-bold">{tpo.cohort.avg_readiness}%</p><p className="text-xs text-slate-500">Avg readiness</p></div>
          </div>
          {tpo.students.length > 0 && (
            <div className="overflow-x-auto mt-4">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-slate-500 border-b">
                  <th className="py-2 pr-3">Student</th><th className="py-2 pr-3">ATS</th><th className="py-2 pr-3">Interviews</th><th className="py-2 pr-3">Interview avg</th><th className="py-2">Readiness</th>
                </tr></thead>
                <tbody>
                  {tpo.students.map((s) => (
                    <tr key={s.email} className="border-b border-slate-100">
                      <td className="py-2 pr-3"><b>{s.name}</b><span className="block text-xs text-slate-500">{s.email}</span></td>
                      <td className="py-2 pr-3">{s.has_resume ? s.ats_score : "—"}</td>
                      <td className="py-2 pr-3">{s.interviews_completed}</td>
                      <td className="py-2 pr-3">{s.interview_avg ?? "—"}</td>
                      <td className="py-2 font-semibold">{s.readiness_score}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="card mt-6">
        <h2 className="font-semibold text-lg">Next Steps - Sprint Roadmap</h2>
        <ol className="list-decimal ml-5 mt-3 space-y-2 text-slate-600">
          <li><b>Sprint 1 (Done):</b> Auth + Dashboard UI — live on Vercel</li>
          <li><b>Sprint 2 (Done):</b> Resume upload & ATS scoring</li>
          <li><b>Sprint 3 (Done):</b> Database persistence (Supabase)</li>
          <li><b>Sprint 4 (Done):</b> AI Mock Interview with instant scoring</li>
          <li><b>Sprint 5 (Done):</b> Voice interviews + readiness analytics + TPO view</li>
          <li><b>Sprint 6 (idea):</b> Generative-AI evaluator + company-specific interview tracks</li>
        </ol>
      </div>
    </main>
  );
}
