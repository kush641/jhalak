import Link from "next/link";
import { Footer, Nav } from "@/components/Brand";

const beats = [
  { t: "0-10s", label: "Hook", text: "Lead close-ups + narrator sets the stakes", w: "24%", c: "from-[#2E6BFF] to-[#5B7BFF]" },
  { t: "10-25s", label: "Story", text: "Who she is, what she wants", w: "30%", c: "from-[#5B7BFF] to-[#8B5CF6]" },
  { t: "25-38s", label: "Escalation", text: "Sharpest lines, rising stakes", w: "28%", c: "from-[#8B5CF6] to-[#E0663A]" },
  { t: "38-45s", label: "Tease", text: "Cut on the cliffhanger", w: "18%", c: "from-[#E0663A] to-[#FF7A2E]" },
];

const steps = [
  { n: "01", title: "Drop your Drive folder", text: "Paste a Google Drive link with every episode of the series. Pick the episodes, the narration language and the length." },
  { n: "02", title: "Jhalak watches and listens", text: "Dialogue, background score and picture are separated, then every episode is read chunk by chunk, so what is said and what is seen stay in sync." },
  { n: "03", title: "Three promo scripts", text: "Two story synopses, one from the visuals and one from the dialogue, become three promo scripts: a 10-second hook, rising stakes and a cliffhanger tease." },
  { n: "04", title: "Stitched, narrated, ready", text: "Chunks are cut, narration is voiced in the language you pick, the score is remixed under it, and you download three vertical promos." },
];

const rows: [string, string, string, string][] = [
  ["Understands the story across episodes", "Yes, every episode", "No, one video at a time", "Yes, after viewing"],
  ["Engineered 10-second hook", "Built into every script", "Generic virality score", "Depends on the editor"],
  ["Ends on a cliffhanger, avoids spoilers", "Scores every chunk for both", "No", "Yes"],
  ["Indian-language narration", "Voiced in your language", "Captions only", "Studio booking"],
  ["Background score separated and remixed", "Yes", "No", "Yes"],
  ["Direct it in plain words", "\"Romance angle, end on the slap\"", "Limited presets", "Briefing calls"],
  ["Turnaround per series", "Minutes", "Minutes, wrong format", "2-3 days"],
];

const uses = [
  { title: "Performance ads", text: "Feed Meta and YouTube three creative angles per show and let the data pick the winner." },
  { title: "In-app trailers", text: "A hook-first trailer on every show page and paywall, refreshed when new episodes drop." },
  { title: "Daily social reels", text: "A new tease for every episode release, without queuing for the edit team." },
  { title: "New-language launches", text: "Launch a dubbed catalogue with promos narrated in the same language, on day one." },
];

export default function Home() {
  return (
    <main>
      <Nav />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div className="glow left-[-10%] top-[-20%] h-[420px] w-[420px] rounded-full bg-[#2E6BFF]" />
        <div className="glow right-[-5%] top-[10%] h-[380px] w-[380px] rounded-full bg-[#FF7A2E]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-16 md:grid-cols-[1.15fr_0.85fr] md:pt-24">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70">
              <span className="h-1.5 w-1.5 rounded-full bg-[#FF7A2E]" /> Built for microdrama studios
            </div>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
              Promos that hook <br />
              in <span className="grad-text">10 seconds.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-white/65">
              Drop a Google Drive folder of episodes. Jhalak watches and listens to the whole series, then cuts
              three ready-to-run vertical promos with Indian-language narration and a cliffhanger ending.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link href="/studio" className="btn-primary">Make three promos</Link>
              <a href="#how" className="btn-ghost">See how it works</a>
            </div>
            <div className="mt-10 grid max-w-lg grid-cols-3 gap-4 text-sm">
              {[["3", "promo cuts per run"], ["10s", "hook, by design"], ["0", "spoilers, by design"]].map(([a, b]) => (
                <div key={b}>
                  <div className="text-2xl font-semibold grad-text">{a}</div>
                  <div className="text-white/55">{b}</div>
                </div>
              ))}
            </div>
          </div>

          {/* phone mock: a promo built from beats */}
          <div className="mx-auto w-full max-w-[320px]">
            <div className="relative aspect-[9/19] rounded-[2.4rem] border border-white/15 bg-[#0d0d16] p-3 shadow-2xl shadow-violet-900/30">
              <div className="relative h-full overflow-hidden rounded-[1.9rem] bg-gradient-to-b from-[#1b1530] via-[#2a1630] to-[#3a1d1a]">
                <div className="absolute inset-0 opacity-60" style={{ background: "radial-gradient(circle at 50% 35%, rgba(255,122,46,.35), transparent 55%), radial-gradient(circle at 30% 70%, rgba(46,107,255,.35), transparent 50%)" }} />
                <div className="absolute left-4 top-5 rounded-full bg-black/40 px-2.5 py-1 text-[10px] font-medium tracking-wider text-white/80">PROMO · HOOK & TEASE</div>
                <div className="absolute inset-x-5 top-[38%] text-center">
                  <div className="text-[11px] uppercase tracking-[0.25em] text-white/50">Narrator</div>
                  <div className="mt-2 text-xl font-semibold leading-snug">&ldquo;एक दुल्हन... और एक राज़ जो सब बदल देगा।&rdquo;</div>
                </div>
                <div className="absolute inset-x-4 bottom-24 space-y-1.5">
                  {beats.map((b) => (
                    <div key={b.label} className="flex items-center gap-2 text-[10px] text-white/70">
                      <span className="w-12 shrink-0 text-white/45">{b.t}</span>
                      <span className="font-semibold text-white">{b.label}</span>
                      <span className="truncate">{b.text}</span>
                    </div>
                  ))}
                </div>
                <div className="absolute inset-x-4 bottom-10">
                  <div className="relative flex h-2 gap-0.5 overflow-hidden rounded-full">
                    {beats.map((b) => (
                      <div key={b.label} className={`h-full bg-gradient-to-r ${b.c}`} style={{ width: b.w }} />
                    ))}
                    <div className="playhead absolute top-[-3px] h-3.5 w-0.5 rounded bg-white" />
                  </div>
                  <div className="mt-3 text-center text-[11px] text-white/60">Episode 1 streaming now</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="border-t border-white/5 py-20">
        <div className="mx-auto max-w-6xl px-5">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-white/45">How it works</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">From a folder of episodes to three promos, in one run.</h2>
          <div className="mt-12 grid gap-5 md:grid-cols-4">
            {steps.map((s) => (
              <div key={s.n} className="card p-6">
                <div className="text-sm font-semibold grad-text">{s.n}</div>
                <h3 className="mt-3 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* THE FORMULA */}
      <section className="py-6">
        <div className="mx-auto max-w-6xl px-5">
          <div className="grad-border rounded-[1.5rem] p-8 md:p-10">
            <div className="grid gap-8 md:grid-cols-[0.9fr_1.1fr] md:items-center">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">The microdrama promo formula, automated.</h2>
                <p className="mt-3 text-white/60">
                  Every script follows the structure your best editors already use: stop the scroll, set the stakes,
                  escalate, and leave the viewer needing the next episode.
                </p>
              </div>
              <div className="flex h-24 w-full gap-1 overflow-hidden rounded-xl">
                {beats.map((b) => (
                  <div key={b.label} className={`flex flex-col justify-end bg-gradient-to-br ${b.c} p-3`} style={{ width: b.w }}>
                    <div className="text-xs font-semibold">{b.label}</div>
                    <div className="text-[10px] text-white/80">{b.t}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* COMPARE */}
      <section id="compare" className="py-20">
        <div className="mx-auto max-w-6xl px-5">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-white/45">Why Jhalak</p>
          <h2 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">Generic AI clippers were built for podcasts. Microdrama needs a story editor.</h2>
          <div className="mt-10 overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-white/[0.03] text-white/60">
                <tr>
                  <th className="p-4 font-medium" />
                  <th className="p-4 font-semibold text-white"><span className="grad-text">Jhalak</span></th>
                  <th className="p-4 font-medium">Generic AI clippers</th>
                  <th className="p-4 font-medium">Manual edit / agency</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([k, a, b, c]) => (
                  <tr key={k} className="border-t border-white/5">
                    <td className="p-4 text-white/75">{k}</td>
                    <td className="p-4 font-medium text-white">{a}</td>
                    <td className="p-4 text-white/50">{b}</td>
                    <td className="p-4 text-white/50">{c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* USE CASES */}
      <section id="usecases" className="border-t border-white/5 py-20">
        <div className="mx-auto max-w-6xl px-5">
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">One run, every place your shows need a promo.</h2>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {uses.map((u) => (
              <div key={u.title} className="card p-6">
                <h3 className="font-semibold">{u.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{u.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="pb-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="relative overflow-hidden rounded-[1.75rem] p-10 text-center md:p-16">
            <div className="grad-bg absolute inset-0 opacity-90" />
            <div className="relative">
              <h2 className="text-3xl font-semibold tracking-tight sm:text-5xl">Your next show deserves a promo today.</h2>
              <p className="mx-auto mt-4 max-w-xl text-white/85">Bring one series. Get three promos back, narrated in the language your audience watches in.</p>
              <Link href="/studio" className="mt-8 inline-block rounded-full bg-white px-6 py-3 font-semibold text-[#1b1530]">Open the Studio</Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}
