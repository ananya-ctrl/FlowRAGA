"use client";

import { FormEvent, useState } from "react";
import { AnswerResult, askProject } from "@/lib/auth-api";

export function ProjectChat({ projectId, accessToken }: Readonly<{projectId: string; accessToken: string}>) {
  const [question, setQuestion] = useState(""); const [result, setResult] = useState<AnswerResult | null>(null);
  const [pending, setPending] = useState(false); const [error, setError] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setPending(true); setError(""); setResult(null); void askProject(accessToken, projectId, question).then(setResult).catch((reason: Error) => setError(reason.message)).finally(() => setPending(false)); }
  return <section className="chat-panel"><p className="eyebrow">Grounded Q&amp;A</p><h2>Ask your indexed documents</h2><form onSubmit={submit}><textarea required minLength={2} maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What do these documents say about…?" /><button className="primary" disabled={pending}>{pending ? "Retrieving evidence…" : "Ask FlowRAGA"}</button></form>{error && <p className="form-error">{error}</p>}{result && <div className="answer-card"><p>{result.answer}</p><small>{result.retrieval_ms} ms retrieval{result.generation_ms !== null ? ` · ${result.generation_ms} ms generation` : ""} · {result.model}</small>{result.sources.length > 0 && <details><summary>{result.sources.length} evidence sources</summary><div className="source-list">{result.sources.map((source) => <article key={source.chunk_id}><strong>[{source.label}] {source.filename}</strong><span>Similarity {(source.score * 100).toFixed(1)}% · chunk {source.position + 1}</span><p>{source.content}</p></article>)}</div></details>}</div>}</section>;
}
