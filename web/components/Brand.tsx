import Link from "next/link";

export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <linearGradient id="jg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2E6BFF" />
          <stop offset="0.5" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#FF7A2E" />
        </linearGradient>
      </defs>
      <circle cx="14" cy="20" r="10" fill="none" stroke="url(#jg)" strokeWidth="2.4" />
      <circle cx="26" cy="20" r="10" fill="none" stroke="url(#jg)" strokeWidth="2.4" />
      <path d="M17.5 15.5 L24.5 20 L17.5 24.5 Z" fill="url(#jg)" />
    </svg>
  );
}

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <Mark />
      <span className="text-lg font-semibold tracking-[0.06em]">JHALAK</span>
    </Link>
  );
}

export function Nav({ studio = false }: { studio?: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-[#07070c]/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        {studio ? (
          <nav className="flex items-center gap-5 text-sm text-white/70">
            <Link href="/studio" className="hover:text-white">New promo run</Link>
            <Link href="/" className="hover:text-white">Home</Link>
          </nav>
        ) : (
          <nav className="flex items-center gap-6 text-sm text-white/70">
            <a href="#how" className="hidden hover:text-white sm:inline">How it works</a>
            <a href="#compare" className="hidden hover:text-white sm:inline">Why Jhalak</a>
            <a href="#usecases" className="hidden hover:text-white md:inline">Use cases</a>
            <Link href="/studio" className="btn-primary !px-4 !py-2 text-sm">Open Studio</Link>
          </nav>
        )}
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-white/5 py-10 text-sm text-white/50">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <Mark size={20} /> <span>Jhalak, promo studio for microdrama</span>
        </div>
        <div>Built in India on Sarvam&apos;s Indian-language speech and language models.</div>
      </div>
    </footer>
  );
}
