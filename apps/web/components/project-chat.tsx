"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  AnswerResult,
  askProject,
  ChatMessage,
  Conversation,
  deleteConversation,
  exportConversation,
  getConversation,
  listConversations,
  saveAnswerFeedback,
} from "@/lib/auth-api";

export function ProjectChat({ projectId, accessToken }: Readonly<{ projectId: string; accessToken: string }>) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<"hybrid" | "vector" | "keyword">("hybrid");
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState(0.25);
  const [rerank, setRerank] = useState(true);

  useEffect(() => { void listConversations(accessToken, projectId).then(setConversations); }, [accessToken, projectId]);

  function openConversation(id: string) {
    setConversationId(id);
    setResult(null);
    void getConversation(accessToken, projectId, id).then((item) => setMessages(item.messages));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const asked = question;
    setPending(true);
    setError("");
    setResult(null);
    void askProject(accessToken, projectId, asked, { topK, similarityThreshold: threshold, retrievalMode: mode, rerank, conversationId })
      .then((answer) => {
        setResult(answer);
        setConversationId(answer.conversation_id);
        setQuestion("");
        setMessages((items) => [
          ...items,
          { id: `local-${Date.now()}`, role: "user", content: asked, sources: null, trace: null, created_at: new Date().toISOString() },
          { id: answer.message_id, role: "assistant", content: answer.answer, sources: answer.sources, trace: answer.trace, created_at: new Date().toISOString() },
        ]);
        return listConversations(accessToken, projectId);
      })
      .then(setConversations)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setPending(false));
  }

  function download() {
    if (!conversationId) return;
    void exportConversation(accessToken, projectId, conversationId).then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "flowraga-conversation.md";
      link.click();
      URL.revokeObjectURL(url);
    });
  }

  return (
    <section className="chat-panel">
      <div className="chat-layout">
        <aside className="conversation-sidebar">
          <button className="quiet-button" onClick={() => { setConversationId(undefined); setMessages([]); setResult(null); }}>+ New conversation</button>
          {conversations.map((item) => (
            <button className={item.id === conversationId ? "conversation-active" : ""} key={item.id} onClick={() => openConversation(item.id)}>
              {item.title}
            </button>
          ))}
        </aside>

        <div className="chat-main">
          <p className="eyebrow">Grounded Q&amp;A</p>
          <h2>Ask your indexed documents</h2>

          <details className="retrieval-settings">
            <summary>Retrieval settings</summary>
            <div>
              <label>Mode
                <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
                  <option value="hybrid">Hybrid</option>
                  <option value="vector">Vector</option>
                  <option value="keyword">Keyword</option>
                </select>
              </label>
              <label>Top K<input type="number" min="1" max="20" value={topK} onChange={(event) => setTopK(Number(event.target.value))} /></label>
              <label>Threshold<input type="number" min="0" max="1" step="0.05" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} /></label>
              <label><input type="checkbox" checked={rerank} onChange={(event) => setRerank(event.target.checked)} /> Rerank</label>
            </div>
          </details>

          {messages.map((message) => (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <strong>{message.role === "user" ? "You" : "FlowRAGA"}</strong>
              <p>{message.content}</p>
              {message.role === "assistant" && conversationId && !message.id.startsWith("local-") && (
                <div className="feedback-actions">
                  <button onClick={() => void saveAnswerFeedback(accessToken, projectId, conversationId, message.id, 1)}>Helpful</button>
                  <button onClick={() => void saveAnswerFeedback(accessToken, projectId, conversationId, message.id, -1)}>Not helpful</button>
                </div>
              )}
              {message.trace && (
                <details>
                  <summary>Retrieval trace</summary>
                  <pre>{JSON.stringify(message.trace, null, 2)}</pre>
                </details>
              )}
            </article>
          ))}

          <form onSubmit={submit}>
            <textarea required minLength={2} maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What do these documents say about\u2026?" />
            <button className="primary" disabled={pending}>{pending ? "Retrieving evidence\u2026" : "Ask FlowRAGA"}</button>
          </form>
          {error && <p className="form-error">{error}</p>}

          {result?.sources.length ? (
            <details className="answer-card" open>
              <summary>{result.sources.length} evidence sources</summary>
              <div className="source-list">
                {result.sources.map((source) => (
                  <article key={source.chunk_id}>
                    <strong>[{source.label}] {source.filename}</strong>
                    <span>Score {source.score.toFixed(4)} &middot; chunk {source.position + 1}</span>
                    <p>{source.content}</p>
                  </article>
                ))}
              </div>
            </details>
          ) : null}

          <div className="chat-tools">
            <button className="quiet-button" disabled={!conversationId} onClick={download}>Export Markdown</button>
            {conversationId && (
              <button
                className="quiet-button"
                onClick={() => {
                  if (!window.confirm("Delete this conversation?")) return;
                  void deleteConversation(accessToken, projectId, conversationId).then(() => {
                    setConversations((items) => items.filter((item) => item.id !== conversationId));
                    setConversationId(undefined);
                    setMessages([]);
                  });
                }}
              >
                Delete conversation
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
