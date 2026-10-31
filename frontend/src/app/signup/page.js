"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost } from "../../lib/api";

export default function Signup() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "student" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault(); setLoading(true); setError("");
    try {
      const data = await apiPost("/auth/signup", form);
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      router.push("/dashboard");
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="card w-full max-w-md">
        <h1 className="text-2xl font-bold">Create account</h1>
        <p className="text-slate-500 mt-1">Start preparing smarter today.</p>
        {error && <p className="bg-red-50 text-red-600 p-3 rounded mt-4 text-sm">{error}</p>}
        <label className="block mt-5 text-sm font-medium">Full Name<input className="input" required onChange={e=>setForm({...form,name:e.target.value})} /></label>
        <label className="block mt-4 text-sm font-medium">Email<input type="email" className="input" required onChange={e=>setForm({...form,email:e.target.value})} /></label>
        <label className="block mt-4 text-sm font-medium">Password<input type="password" className="input" required minLength={6} onChange={e=>setForm({...form,password:e.target.value})} /></label>
        <label className="block mt-4 text-sm font-medium">I am a
          <select className="input" onChange={e=>setForm({...form,role:e.target.value})}>
            <option value="student">Student</option><option value="tpo">TPO / Faculty</option>
          </select></label>
        <button className="btn w-full mt-6" disabled={loading}>{loading ? "Creating..." : "Sign Up"}</button>
        <p className="text-sm text-center mt-4">Already have an account? <Link className="text-indigo-600" href="/login">Login</Link></p>
      </form>
    </main>
  );
}
