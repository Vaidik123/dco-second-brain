"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import ReactMarkdown from "react-markdown";
import { Upload, FileText, ExternalLink, Loader2, Sparkles } from "lucide-react";
import { analyzeArticle, uploadArticleFile, type ArticleAnalysis } from "@/lib/api";

export default function ArticlePage() {
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [topicHint, setTopicHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ArticleAnalysis | null>(null);

  const analyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await analyzeArticle(text, topicHint || undefined);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setLoading(true);
    setResult(null);
    setMode("upload");
    try {
      const res = await uploadArticleFile(file, topicHint || undefined);
      setResult(res);
    } finally {
      setLoading(false);
    }
  }, [topicHint]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/plain": [".txt"], "text/markdown": [".md"] },
    maxFiles: 1,
  });

  return (
    <div className="max-w-4xl mx-auto px-6 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Article Assistant</h1>
        <p className="text-sm text-gray-500 mt-1">
          Paste your draft or upload a file — get research suggestions from the knowledge base.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Input side */}
        <div className="space-y-4">
          <div className="flex gap-2">
            {(["paste", "upload"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                  mode === m ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {m === "paste" ? "Paste text" : "Upload file"}
              </button>
            ))}
          </div>

          {mode === "paste" ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste your draft article here..."
              rows={16}
              className="w-full text-sm border border-gray-200 rounded-xl p-4 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          ) : (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
                isDragActive ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <input {...getInputProps()} />
              <Upload className="w-8 h-8 text-gray-400 mx-auto mb-3" />
              <p className="text-sm text-gray-600">
                {isDragActive ? "Drop it here" : "Drag & drop a .txt or .md file, or click to browse"}
              </p>
            </div>
          )}

          <input
            value={topicHint}
            onChange={(e) => setTopicHint(e.target.value)}
            placeholder="Topic hint (optional) — e.g. 'DeFi yield farming'"
            className="w-full text-sm border border-gray-200 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />

          <button
            onClick={analyze}
            disabled={!text.trim() || loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Find Relevant Research
              </>
            )}
          </button>
        </div>

        {/* Result side */}
        <div className="space-y-4">
          {!result && !loading && (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400 border border-dashed border-gray-200 rounded-xl">
              <FileText className="w-10 h-10 mb-3" />
              <p className="text-sm">Analysis will appear here</p>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <Loader2 className="w-8 h-8 animate-spin mb-3 text-brand-500" />
              <p className="text-sm">Searching knowledge base...</p>
            </div>
          )}

          {result && (
            <>
              <div className="bg-white border border-gray-200 rounded-xl p-5 text-sm prose-custom overflow-y-auto max-h-[480px]">
                <ReactMarkdown>{result.analysis}</ReactMarkdown>
              </div>

              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                  Sources searched ({result.sources_used.length})
                </p>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {result.sources_used.map((s) => (
                    <a
                      key={s.id}
                      href={s.url || "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-2 p-2.5 bg-gray-50 hover:bg-brand-50 rounded-lg transition-colors group"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-gray-800 group-hover:text-brand-700 line-clamp-1">
                          {s.title || "Untitled"}
                        </p>
                        <p className="text-xs text-gray-400">{s.source}</p>
                      </div>
                      <ExternalLink className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
                    </a>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
