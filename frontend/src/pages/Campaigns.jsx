import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Megaphone, Filter, ArrowRight, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import Card from "../components/Card";
import Button from "../components/Button";
import Badge from "../components/Badge";
import Input from "../components/Input";
import { formatDate } from "../utils/format";

export default function Campaigns() {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, total_pages: 1 });

  const fetchCampaigns = async () => {
    setLoading(true);
    setError(null);
    try {
      let endpoint = `/campaigns?page=${page}&page_size=15`;
      if (statusFilter !== "ALL") endpoint += `&status=${statusFilter}`;
      const res = await api.get(endpoint);
      setCampaigns(res.items || []);
      setPagination(res.pagination || { total: 0, total_pages: 1 });
    } catch (err) {
      setError(err.message || "Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, [page, statusFilter]);

  const getStatusVariant = (status) => {
    switch (status) {
      case "RUNNING":
      case "ACTIVE":
      case "LAUNCHING":
        return "info";
      case "COMPLETED":
        return "success";
      case "PAUSED":
        return "warning";
      case "CANCELLED":
        return "danger";
      case "SCHEDULED":
      case "READY":
        return "purple";
      default:
        return "default";
    }
  };

  const filteredCampaigns = campaigns.filter((c) =>
    search ? c.name.toLowerCase().includes(search.toLowerCase()) || c.product_name.toLowerCase().includes(search.toLowerCase()) : true
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="t-display-sm text-ink flex items-center gap-2.5">
            <Megaphone className="w-6 h-6 text-ink shrink-0" />
            Outreach Campaigns
          </h1>
          <p className="t-body-sm text-muted mt-1">
            Build, configure voice prompts, preview, and dispatch compliant voice AI campaigns.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchCampaigns} disabled={loading} title="Refresh campaigns">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button variant="primary" size="md" onClick={() => navigate("/app/campaigns/new")}>
            <Plus className="w-4 h-4 mr-1.5" />
            Create Campaign
          </Button>
        </div>
      </div>

      {/* Filters Bar */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            <span className="t-label text-muted-soft flex items-center gap-1.5 mr-2">
              <Filter className="w-3.5 h-3.5" /> Status:
            </span>
            {["ALL", "DRAFT", "SCHEDULED", "READY", "RUNNING", "PAUSED", "COMPLETED", "CANCELLED"].map((st) => (
              <button
                key={st}
                onClick={() => {
                  setStatusFilter(st);
                  setPage(1);
                }}
                className={`px-3 py-1 rounded-full t-label transition-colors border ${
                  statusFilter === st
                    ? "bg-primary text-white border-primary"
                    : "bg-surface-strong text-body hover:text-ink border-hairline"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
          <div className="w-full md:w-64">
            <Input
              type="text"
              placeholder="Search campaigns..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full text-sm"
            />
          </div>
        </div>
      </Card>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-semantic-error t-body-sm">
          {error}
        </div>
      )}

      {/* Campaigns Table */}
      <Card className="p-0 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-muted t-body-base">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
            Loading campaigns...
          </div>
        ) : filteredCampaigns.length === 0 ? (
          <div className="p-12 text-center">
            <Megaphone className="w-10 h-10 mx-auto text-muted-soft mb-3" />
            <h3 className="t-heading-sm text-ink mb-1">No campaigns found</h3>
            <p className="t-body-sm text-muted max-w-md mx-auto mb-5">
              {search || statusFilter !== "ALL"
                ? "No campaigns matched your current filters. Try resetting status or search criteria."
                : "Create your first voice outreach campaign to engage scored leads and customers."}
            </p>
            <Button variant="primary" size="sm" onClick={() => navigate("/app/campaigns/new")}>
              <Plus className="w-3.5 h-3.5 mr-1" /> Create Campaign
            </Button>
          </div>
        ) : (
          <div className="w-full overflow-hidden">
            <table className="w-full text-left border-collapse table-fixed">
              <colgroup>
                <col style={{ width: "22%" }} />
                <col style={{ width: "18%" }} />
                <col style={{ width: "10%" }} />
                <col style={{ width: "18%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "11%" }} />
                <col style={{ width: "10%" }} />
              </colgroup>
              <thead>
                <tr className="border-b border-hairline bg-surface-strong/50 text-muted text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2 px-2.5">Campaign Name</th>
                  <th className="py-2 px-2.5">Product & Audience</th>
                  <th className="py-2 px-2.5">Recipients</th>
                  <th className="py-2 px-2.5">Outreach Progress</th>
                  <th className="py-2 px-2.5">Status</th>
                  <th className="py-2 px-2.5">Last Updated</th>
                  <th className="py-2 px-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {filteredCampaigns.map((camp) => {
                  const total = camp.total_recipients || 0;
                  const contacted = camp.contacted_count || 0;
                  const pct = total > 0 ? Math.round((contacted / total) * 100) : 0;

                  return (
                    <tr key={camp.id} className="hover:bg-surface-strong/30 transition-colors">
                      <td className="py-2 px-2.5 truncate">
                        <Link to={`/app/campaigns/${camp.id}`} className="font-semibold text-ink hover:underline text-xs truncate block" title={camp.name}>
                          {camp.name}
                        </Link>
                      </td>
                      <td className="py-2 px-2.5 truncate">
                        <div className="text-xs text-ink font-medium truncate" title={camp.product_name}>{camp.product_name}</div>
                        <span className="inline-block px-1.5 py-0.2 mt-0.5 rounded text-[10px] font-mono uppercase bg-surface-strong text-muted">
                          {camp.entity_type}s
                        </span>
                      </td>
                      <td className="py-2 px-2.5 text-xs text-ink font-mono font-medium">
                        {total}
                      </td>
                      <td className="py-2 px-2.5">
                        <div className="flex items-center justify-between text-[10px] text-muted mb-0.5">
                          <span>{contacted}/{total}</span>
                          <span>{pct}%</span>
                        </div>
                        <div className="w-full h-1 rounded-full bg-surface-strong overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-2 px-2.5">
                        <Badge variant={getStatusVariant(camp.status)} className="text-[10px] px-1.5 py-0.5">{camp.status}</Badge>
                      </td>
                      <td className="py-2 px-2.5 text-[11px] text-muted font-mono truncate">
                        {formatDate(camp.updated_at)}
                      </td>
                      <td className="py-2 px-2.5 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/app/campaigns/${camp.id}`)}
                          className="!py-1 !px-2 text-xs"
                        >
                          View <ArrowRight className="w-3 h-3 ml-1" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
