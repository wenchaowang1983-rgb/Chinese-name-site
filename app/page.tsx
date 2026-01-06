import Image from "next/image";

export default function Home() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans">
      <main className="w-full max-w-3xl px-6 py-16 bg-white">
        <div className="mb-8 flex items-center gap-3">
          <Image
            src="/next.svg"
            alt="Next.js logo"
            width={100}
            height={20}
            priority
          />
          <span className="text-sm text-zinc-500">Demo</span>
        </div>

        <div style={{ color: "red", fontSize: 48, marginBottom: 24 }}>
          TEST 123
        </div>

        <h1 className="text-3xl font-semibold text-black mb-4">
          Chinese Name Studio
        </h1>

        <p className="text-zinc-600 leading-7 mb-10">
          Generate a meaningful Chinese name based on your story.
        </p>

        <div className="flex gap-3">
          <a
            className="inline-flex h-11 items-center justify-center rounded-full bg-black px-5 text-white"
            href="#"
          >
            Start
          </a>
          <a
            className="inline-flex h-11 items-center justify-center rounded-full border border-zinc-200 px-5 text-black"
            href="https://nextjs.org/docs"
            target="_blank"
            rel="noopener noreferrer"
          >
            Docs
          </a>
        </div>
      </main>
    </div>
  );
}
