import Navbar from "../components/Navbar";
import Link from "next/link";
export default function Home() {
  return (
    <main>
      <Navbar />
      <section className="max-w-6xl mx-auto px-4 py-16 text-center">
        <h1 className="text-4xl md:text-5xl font-bold leading-tight">Crack Placements with <span className="text-indigo-600">Real-Time AI Interviews</span></h1>
        <p className="mt-4 text-lg text-slate-600 max-w-2xl mx-auto">Upload your resume, get your ATS score, and practice voice mock interviews with instant AI feedback - built for final year students.</p>
        <div className="mt-8 flex gap-4 justify-center">
          <Link href="/signup" className="btn">Start Mock Interview</Link>
          <Link href="/login" className="px-5 py-2.5 border rounded-lg">I have an account</Link>
        </div>
        <div className="grid md:grid-cols-3 gap-6 mt-16 text-left">
          {[
            ["📄 Resume Analyzer", "ATS score + skill gap vs any Job Description in seconds."],
            ["🎙️ AI Mock Interview", "Voice-based interview based on YOUR resume and target role."],
            ["📊 Readiness Dashboard", "Track weak topics, scores and progress towards placement."],
          ].map(([t, d]) => (<div key={t} className="card"><h3 className="font-semibold text-lg">{t}</h3><p className="text-slate-600 mt-2">{d}</p></div>))}
        </div>
      </section>
    </main>
  );
}
