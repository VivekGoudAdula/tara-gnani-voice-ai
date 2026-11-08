import React, { useState } from "react";
import { Download, FileSpreadsheet, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "../../api/client";
import Badge from "../Badge";
import Button from "../Button";

export default function ImportHistoryTable({ history = [], loading, onRefresh }) {
  const [downloadingId, setDownloadingId] = useState(null);
  const [downloadError, setDownloadError] = useState("");

  const downloadRejected = async (batchId) => {
    setDownloadingId(batchId);
    setDownloadError("");

    try {
      const blob = await api.get(`/imports/${batchId}/rejected.csv`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rejected_rows_${batchId.slice(-6)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message || "Failed to download rejected rows CSV.");
    } finally {
      setDownloadingId(null);
    }
  };

  const getStatusBadge = (status) => {
    if (status === "IMPORTED") return <Badge variant="success">Imported</Badge>;
    if (status === "VALIDATED") return <Badge variant="info">Validated (Pending Confirm)</Badge>;
    if (status === "EXPIRED") return <Badge variant="default">Expired</Badge>;
    return <Badge variant="danger">{status}</Badge>;
  };

  return (
    <div className="bg-surface-card rounded-2xl border border-hairline p-5 shadow-soft space-y-4 font-sans">
      <div className="flex items-center justify-between pb-3 border-b border-hairline">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-muted" />
          <h2 className="t-h2 text-ink">Import History</h2>
        </div>
        <span className="t-caption text-muted">{history.length} batches recorded</span>
      </div>

      {downloadError && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-700 rounded-xl text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{downloadError}</span>
        </div>
      )}

      {loading ? (
        <div className="p-8 text-center text-muted t-caption bg-canvas rounded-xl border border-hairline">
          Loading import history...
        </div>
      ) : history.length === 0 ? (
        <div className="p-8 text-center text-muted t-caption bg-canvas rounded-xl border border-hairline">
          No data import batches recorded yet. Upload a CSV file or load sample data above.
        </div>
      ) : (
        <div className="border border-hairline rounded-xl overflow-hidden bg-canvas">
          <table className="w-full text-left text-xs table-fixed border-collapse">
            <colgroup>
              <col style={{ width: "10%" }} />
              <col style={{ width: "20%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "16%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "11%" }} />
            </colgroup>
            <thead className="bg-surface-card border-b border-hairline text-muted text-[11px] font-semibold uppercase tracking-wider">
              <tr>
                <th className="py-2 px-2.5">Batch ID</th>
                <th className="py-2 px-2.5">File Name</th>
                <th className="py-2 px-2.5">Entity</th>
                <th className="py-2 px-2.5">Rows (Tot / Imp / Rej)</th>
                <th className="py-2 px-2.5">Status</th>
                <th className="py-2 px-2.5">Uploaded By</th>
                <th className="py-2 px-2.5">Timestamp</th>
                <th className="py-2 px-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {history.map((batch) => {
                const total = batch.counts?.total || 0;
                const imported = batch.counts?.imported || 0;
                const rejected = batch.counts?.rejected || 0;
                const timeStr = batch.created_at
                  ? new Date(batch.created_at).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "N/A";

                return (
                  <tr key={batch.id} className="hover:bg-surface-card/40 transition-colors">
                    <td className="py-2 px-2.5 font-mono text-[11px] text-muted-soft truncate">
                      {batch.id.slice(0, 8)}...
                    </td>
                    <td className="py-2 px-2.5 font-medium text-ink truncate text-xs" title={batch.file_name}>
                      {batch.file_name}
                    </td>
                    <td className="py-2 px-2.5 truncate">
                      <span className="capitalize font-medium text-ink text-xs">{batch.entity_type}</span>
                    </td>
                    <td className="py-2 px-2.5 font-mono text-muted text-[11px] truncate">
                      <span className="text-ink font-semibold">{total}</span> /{" "}
                      <span className="text-emerald-700 font-semibold">{imported}</span> /{" "}
                      <span className={rejected > 0 ? "text-rose-700 font-semibold" : "text-muted"}>
                        {rejected}
                      </span>
                    </td>
                    <td className="py-2 px-2.5 truncate">{getStatusBadge(batch.status)}</td>
                    <td className="py-2 px-2.5 text-muted text-xs truncate">{batch.uploaded_by || "User"}</td>
                    <td className="py-2 px-2.5 text-muted font-mono text-[11px] truncate">{timeStr}</td>
                    <td className="py-2 px-2.5 text-right">
                      {rejected > 0 ? (
                        <button
                          onClick={() => downloadRejected(batch.id)}
                          disabled={downloadingId === batch.id}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-strong hover:bg-surface-strong/80 text-ink text-[11px] font-medium transition-colors"
                          title="Download rejected rows with validation reasons"
                        >
                          <Download className="w-3 h-3 text-muted" />
                          <span>{downloadingId === batch.id ? "..." : "Rejections"}</span>
                        </button>
                      ) : (
                        <span className="text-muted-soft text-[11px]">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
