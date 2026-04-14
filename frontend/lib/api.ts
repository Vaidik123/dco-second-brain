const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function* streamChat(
  messages: { role: string; content: string }[],
  sourceFilter?: string,
  model?: string
): AsyncGenerator<{ type: "text"; content: string } | { type: "sources"; sources: Source[] }> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, source_filter: sourceFilter || null, model }),
  });

  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") return;
        if (currentEvent === "sources") {
          yield { type: "sources", sources: JSON.parse(data) };
          currentEvent = "";
        } else {
          yield { type: "text", content: data };
        }
      }
    }
  }
}

export async function searchWiki(query: string, source?: string, limit = 10): Promise<SearchResult> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (source) params.set("source", source);
  const res = await fetch(`${API_URL}/api/search?${params}`);
  return res.json();
}

export async function listItems(source?: string, tag?: string, limit = 20, offset = 0): Promise<ItemList> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (source) params.set("source", source);
  if (tag) params.set("tag", tag);
  const res = await fetch(`${API_URL}/api/items?${params}`);
  return res.json();
}

export async function getTags(): Promise<{ tag: string; count: number }[]> {
  const res = await fetch(`${API_URL}/api/tags`);
  return res.json();
}

export async function getStats(): Promise<{ total_items: number; by_source: Record<string, number> }> {
  const res = await fetch(`${API_URL}/api/stats`);
  return res.json();
}

export async function ingestUrl(url: string): Promise<{ status: string; title?: string }> {
  const res = await fetch(`${API_URL}/api/ingest/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, source: "manual" }),
  });
  return res.json();
}

export async function analyzeArticle(text: string, topicHint?: string): Promise<ArticleAnalysis> {
  const res = await fetch(`${API_URL}/api/article/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, topic_hint: topicHint }),
  });
  return res.json();
}

export async function uploadArticleFile(file: File, topicHint?: string): Promise<ArticleAnalysis> {
  const formData = new FormData();
  formData.append("file", file);
  if (topicHint) formData.append("topic_hint", topicHint);
  const res = await fetch(`${API_URL}/api/article/upload`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}

// --- Types ---
export interface Source {
  id: string;
  title: string | null;
  url: string | null;
  source: string;
}

export interface Item {
  id: string;
  title: string | null;
  url: string | null;
  source: string;
  author: string | null;
  summary: string | null;
  tags: string[];
  published_at: string | null;
  ingested_at: string;
  confidence_score: number;
  access_count: number;
}

export interface SearchResult {
  query: string;
  results: (Item & { chunk_text: string; relevance_score: number })[];
  count: number;
}

export interface ItemList {
  items: Item[];
  total: number;
  offset: number;
  limit: number;
}

export interface ArticleAnalysis {
  analysis: string;
  sources_used: (Source & { tags: string[]; relevance_score: number })[];
}
