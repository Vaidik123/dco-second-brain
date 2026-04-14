"use client";
import { useState, useEffect } from "react";
import { Search, ExternalLink, Tag, RefreshCw } from "lucide-react";
import { listItems, searchWiki, getTags, getStats, ingestUrl, type Item } from "@/lib/api";
import { formatDistanceToNow } from "date-fns";

const SOURCE_LABELS: Record<string, string> = {
  substack_dco: "Dco",
  substack_td: "Token Dispatch",
  slack: "Slack",
  twitter: "Twitter",
  manual: "Manual",
};

const SOURCE_COLORS: Record<string, string> = {
  substack_dco: "bg-blue-100 text-blue-700",
  substack_td: "bg-purple-100 text-purple-700",
  slack: "bg-green-100 text-green-700",
  twitter: "bg-sky-100 text-sky-700",
  manual: "bg-gray-100 text-gray-600",
};

export default function WikiPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [tags, setTags] = useState<{ tag: string; count: number }[]>([]);
  const [stats, setStats] = useState<{ total_items: number; by_source: Record<string, number> } | null>(null);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const load = async (reset = false) => {
    setLoading(true);
    const newOffset = reset ? 0 : offset;
    try {
      if (query) {
        const res = await searchWiki(query, sourceFilter || undefined, LIMIT);
        setItems(res.results);
        setTotal(res.count);
      } else {
        const res = await listItems(sourceFilter || undefined, tagFilter || undefined, LIMIT, newOffset);
        setItems(reset ? res.items : (prev) => [...prev, ...res.items] as Item[]);
        setTotal(res.total);
      }
      if (reset) setOffset(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(true);
    getTags().then(setTags);
    getStats().then(setStats);
  }, [sourceFilter, tagFilter]);

  useEffect(() => {
    const t = setTimeout(() => load(true), 400);
    return () => clearTimeout(t);
  }, [query]);

  const triggerIngest = async (type: string) => {
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    await fetch(`${API}/api/ingest/${type}`, { method: "POST" });
    alert(`${type} ingestion started in background`);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      {/* Header + stats */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Wiki</h1>
          {stats && (
            <p className="text-sm text-gray-500 mt-0.5">
              {stats.total_items} items —{" "}
              {Object.entries(stats.by_source)
                .map(([k, v]) => `${SOURCE_LABELS[k] || k}: ${v}`)
                .join(" · ")}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => triggerIngest("substack")}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Sync Substack
          </button>
        </div>
      </div>

      {/* Search + filters */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the knowledge base..."
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All sources</option>
          <option value="substack_dco">Dco Substack</option>
          <option value="substack_td">Token Dispatch</option>
          <option value="slack">Slack</option>
          <option value="twitter">Twitter</option>
        </select>
      </div>

      {/* Tags */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => setTagFilter("")}
            className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
              !tagFilter ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            All
          </button>
          {tags.slice(0, 20).map(({ tag, count }) => (
            <button
              key={tag}
              onClick={() => setTagFilter(tag === tagFilter ? "" : tag)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
                tagFilter === tag ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {tag} ({count})
            </button>
          ))}
        </div>
      )}

      {/* Items */}
      {loading && items.length === 0 ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No items yet.{" "}
          <button className="text-brand-600 underline" onClick={() => triggerIngest("substack")}>
            Sync Substack
          </button>{" "}
          to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <ItemCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* Load more */}
      {!query && items.length < total && (
        <button
          onClick={() => {
            setOffset((p) => p + LIMIT);
            load();
          }}
          className="w-full mt-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          Load more ({total - items.length} remaining)
        </button>
      )}
    </div>
  );
}

function ItemCard({ item }: { item: Item }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${SOURCE_COLORS[item.source] || "bg-gray-100 text-gray-600"}`}>
              {SOURCE_LABELS[item.source] || item.source}
            </span>
            {item.confidence_score > 1.2 && (
              <span className="px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700 font-medium">
                High confidence
              </span>
            )}
          </div>
          <a
            href={item.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-gray-900 hover:text-brand-700 line-clamp-1 flex items-center gap-1"
          >
            {item.title || "Untitled"}
            {item.url && <ExternalLink className="w-3.5 h-3.5 shrink-0 text-gray-400" />}
          </a>
          {item.summary && <p className="text-sm text-gray-500 mt-1 line-clamp-2">{item.summary}</p>}
          <div className="flex items-center gap-3 mt-2">
            {item.tags?.slice(0, 4).map((tag) => (
              <span key={tag} className="flex items-center gap-1 text-xs text-gray-400">
                <Tag className="w-3 h-3" /> {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="text-xs text-gray-400 shrink-0 text-right">
          {item.ingested_at && (
            <div>{formatDistanceToNow(new Date(item.ingested_at), { addSuffix: true })}</div>
          )}
          {item.access_count > 0 && <div className="mt-0.5">{item.access_count} lookups</div>}
        </div>
      </div>
    </div>
  );
}
