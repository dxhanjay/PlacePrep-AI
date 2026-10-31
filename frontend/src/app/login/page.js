"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost } from "../../lib/api";

export default function Login() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  async function onSubmit(e) {
    e.preventDefault(); setLoading(true); setError("");
    try {
      const data = await apiPost("/auth/login", form);
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));
      router.push("/dashboard");
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }
  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="card w-full max-w-md">
        <h1 className="text-2xl font-bold">Welcome back</h1>
        {error && <p className="bg-red-50 text-red-600 p-3 rounded mt-4 text-sm">{error}</p>}
        <label className="block mt-5 text-sm font-medium">Email<input type="email" className="input" required onChange={e=>setForm({...form,email:e.target.value})} /></label>
        <label className="block mt-4 text-sm font-medium">Password<input type="password" className="input" required onChange={e=>setForm({...form,password:e.target.value})} /></label>
        <button className="btn w-full mt-6" disabled={loading}>{loading ? "Logging in..." : "Login"}</button>
        <p className="text-sm text-center mt-4">New here? <Link className="text-indigo-600" href="/signup">Create account</Link></p>
      </form>
    </main>
  );
}
