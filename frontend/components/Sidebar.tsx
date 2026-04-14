"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, MessageSquare, BookOpen, FileText, Plus, Settings } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/wiki", label: "Wiki", icon: BookOpen },
  { href: "/article", label: "Article Assistant", icon: FileText },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col h-screen shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5 border-b border-gray-100">
        <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
          <Brain className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="font-semibold text-gray-900 text-sm leading-none">Second Brain</div>
          <div className="text-xs text-gray-400 mt-0.5">Dco Knowledge</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              path === href
                ? "bg-brand-50 text-brand-700"
                : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Quick add */}
      <div className="p-3 border-t border-gray-100">
        <AddUrlButton />
      </div>
    </aside>
  );
}

function AddUrlButton() {
  const handleAdd = async () => {
    const url = prompt("Paste a URL to add to the Second Brain:");
    if (!url) return;
    const { ingestUrl } = await import("@/lib/api");
    const result = await ingestUrl(url);
    if (result.status === "ingested") {
      alert(`Added: ${result.title || url}`);
    } else if (result.status === "already_exists") {
      alert("Already in the knowledge base.");
    } else {
      alert("Failed to ingest. Check the URL.");
    }
  };

  return (
    <button
      onClick={handleAdd}
      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
    >
      <Plus className="w-4 h-4" />
      Add URL
    </button>
  );
}
