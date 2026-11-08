import React from "react";
import { ChevronLeft, ChevronRight, Inbox } from "lucide-react";

export default function DataTable({
  columns,
  data = [],
  loading = false,
  pagination = null,
  onPageChange = null,
  onRowClick = null,
  emptyMessage = "No records found.",
  emptyAction = null,
}) {
  return (
    <div className="w-full bg-surface-card border border-hairline rounded-xl overflow-hidden shadow-soft">
      <div className="w-full overflow-hidden">
        <table className="w-full text-left text-body table-fixed border-collapse">
          <colgroup>
            {columns.map((col, idx) => {
              let widthStyle = undefined;
              if (col.width) {
                if (col.width.startsWith("w-[")) {
                  widthStyle = col.width.slice(3, -1);
                } else if (!col.width.startsWith("w-")) {
                  widthStyle = col.width;
                }
              } else {
                widthStyle = `${100 / columns.length}%`;
              }
              return (
                <col
                  key={idx}
                  className={col.width && col.width.startsWith("w-") ? col.width : ""}
                  style={widthStyle ? { width: widthStyle } : undefined}
                />
              );
            })}
          </colgroup>
          <thead className="bg-canvas-soft/80 border-b border-hairline">
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={`px-2 py-2 text-[11px] font-semibold tracking-wider uppercase text-muted-soft truncate ${col.className || ""}`}
                  title={typeof col.header === "string" ? col.header : undefined}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {loading ? (
              // Static grey loading skeleton (no shimmer)
              [...Array(5)].map((_, rIdx) => (
                <tr key={rIdx} className="h-11 sm:h-12">
                  {columns.map((_, cIdx) => (
                    <td key={cIdx} className="px-3 sm:px-4">
                      <div className="h-4 bg-hairline rounded-md w-3/4 max-w-[120px]" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-16 text-center">
                  <div className="flex flex-col items-center justify-center gap-3 text-muted">
                    <div className="w-10 h-10 rounded-full bg-surface-strong flex items-center justify-center text-muted">
                      <Inbox className="w-5 h-5" />
                    </div>
                    <p className="t-body-md text-body">{emptyMessage}</p>
                    {emptyAction && <div className="mt-2">{emptyAction}</div>}
                  </div>
                </td>
              </tr>
            ) : (
              data.map((row, rowIdx) => (
                <tr
                  key={row.id || rowIdx}
                  id={`data-row-${rowIdx}`}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`h-10 sm:h-10 transition-colors ${
                    onRowClick ? "cursor-pointer hover:bg-canvas-soft" : "hover:bg-canvas-soft/50"
                  }`}
                >
                  {columns.map((col, colIdx) => (
                    <td
                      key={colIdx}
                      className={`px-2 py-1.5 text-xs text-body truncate ${col.className || ""}`}
                    >
                      {col.render ? col.render(row) : row[col.accessor] ?? "—"}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && pagination.total > 0 && (
        <div className="px-4 py-3 bg-canvas-soft/60 border-t border-hairline flex items-center justify-between t-caption text-muted">
          <div>
            Showing{" "}
            <span className="t-body-strong text-ink">
              {Math.min((pagination.page - 1) * pagination.page_size + 1, pagination.total)}
            </span>{" "}
            to{" "}
            <span className="t-body-strong text-ink">
              {Math.min(pagination.page * pagination.page_size, pagination.total)}
            </span>{" "}
            of <span className="t-body-strong text-ink">{pagination.total}</span> records
          </div>
          <div className="flex items-center gap-2">
            <button
              id="pagination-prev-btn"
              disabled={pagination.page <= 1 || loading}
              onClick={() => onPageChange && onPageChange(pagination.page - 1)}
              className="p-1.5 rounded-md hover:bg-surface-strong disabled:opacity-40 disabled:cursor-not-allowed border border-hairline transition-colors"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4 text-ink" />
            </button>
            <span className="px-1 t-caption">
              Page <span className="text-ink t-body-strong">{pagination.page}</span> of{" "}
              <span className="text-ink t-body-strong">{pagination.total_pages || 1}</span>
            </span>
            <button
              id="pagination-next-btn"
              disabled={pagination.page >= pagination.total_pages || loading}
              onClick={() => onPageChange && onPageChange(pagination.page + 1)}
              className="p-1.5 rounded-md hover:bg-surface-strong disabled:opacity-40 disabled:cursor-not-allowed border border-hairline transition-colors"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4 text-ink" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
