import Link from "next/link";
export default function Navbar() {
  return (
    <header className="bg-white border-b sticky top-0 z-10">
      <div className="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
        <Link href="/" className="font-bold text-xl text-indigo-600">PlacePrep AI</Link>
        <nav className="flex gap-3">
          <Link href="/login" className="px-4 py-2">Login</Link>
          <Link href="/signup" className="btn">Get Started Free</Link>
        </nav>
      </div>
    </header>
  );
}
