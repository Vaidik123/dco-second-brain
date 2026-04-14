"use client";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Send, Brain, ExternalLink } from "lucide-react";
import { streamChat, type Source } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

const STARTERS = [
  "What have we written about DeFi regulation?",
  "Summarize Dco's recent thesis on AI x crypto",
  "What research do we have on stablecoins?",
  "What are the key themes in Token Dispatch this month?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [model, setModel] = useState<string>("claude-haiku-4-5-20251001");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text?: string) => {
    const userText = text || input.trim();
    if (!userText || loading) return;

    setInput("");
    const newMessages: Message[] = [...messages, { role: "user", content: userText }];
    setMessages(newMessages);
    setLoading(true);

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages([...newMessages, assistantMsg]);

    try {
      const apiMessages = newMessages.map((m) => ({ role: m.role, content: m.content }));
      for await (const chunk of streamChat(apiMessages, sourceFilter || undefined, model)) {
        if (chunk.type === "text") {
          setMessages((prev) => {
            const last = { ...prev[prev.length - 1] };
            last.content += chunk.content;
            return [...prev.slice(0, -1), last];
          });
        } else if (chunk.type === "sources") {
          setMessages((prev) => {
            const last = { ...prev[prev.length - 1], sources: chunk.sources };
            return [...prev.slice(0, -1), last];
          });
        }
      }
    } catch (e) {
      setMessages((prev) => {
        const last = { ...prev[prev.length - 1], content: "Error: Could not reach the backend." };
        return [...prev.slice(0, -1), last];
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-3 flex items-center justify-between shrink-0">
        <h1 className="font-semibold text-gray-900">Chat with Second Brain</h1>
        <div className="flex items-center gap-2">
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="claude-haiku-4-5-20251001">⚡ Haiku (Fast)</option>
          <option value="claude-sonnet-4-6">🧠 Sonnet (Smarter)</option>
        </select>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All sources</option>
          <option value="substack_dco">Dco Substack</option>
          <option value="substack_td">Token Dispatch</option>
          <option value="slack">Slack #research</option>
          <option value="twitter">Twitter</option>
        </select>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="max-w-2xl mx-auto">
            <div className="flex justify-center mb-8">
              <div className="w-16 h-16 bg-brand-500 rounded-2xl flex items-center justify-center">
                <Brain className="w-9 h-9 text-white" />
              </div>
            </div>
            <h2 className="text-center text-xl font-semibold text-gray-900 mb-2">What do you want to know?</h2>
            <p className="text-center text-gray-500 text-sm mb-8">
              Ask anything about Dco's research, articles, and knowledge base.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left p-3 text-sm text-gray-600 bg-white border border-gray-200 rounded-xl hover:bg-brand-50 hover:border-brand-200 hover:text-brand-700 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto space-y-6">
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                {m.role === "user" ? (
                  <div className="bg-brand-500 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-lg text-sm">
                    {m.content}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-5 py-4 text-sm prose-custom">
                      <ReactMarkdown>{m.content || "▋"}</ReactMarkdown>
                    </div>
                    {m.sources && m.sources.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">Sources</p>
                        <div className="flex flex-wrap gap-2">
                          {m.sources.map((s) => (
                            <a
                              key={s.id}
                              href={s.url || "#"}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 hover:bg-brand-50 text-xs text-gray-600 hover:text-brand-700 rounded-full transition-colors"
                            >
                              {s.title ? s.title.slice(0, 40) : s.source}
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white px-4 py-3 shrink-0">
        <div className="max-w-2xl mx-auto flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your research..."
            rows={1}
            className="flex-1 resize-none border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            style={{ maxHeight: 120 }}
          />
          <button
            onClick={() => send()}
            disabled={!input.trim() || loading}
            className="p-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
