export default function Loading() {
  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <div className="h-8 w-20 bg-gray-200 rounded animate-pulse mb-6" />
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="h-4 w-3/4 bg-gray-200 rounded animate-pulse mb-2" />
            <div className="h-3 w-full bg-gray-100 rounded animate-pulse mb-1" />
            <div className="h-3 w-2/3 bg-gray-100 rounded animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}
