/**
 * Standard formatting utilities for editorial light design consistency.
 * Formats numbers, enums, languages, and sources to uniform Title Case.
 */

export function formatCurrency(amount) {
  if (amount === undefined || amount === null) return "₹0";
  return `₹${Math.round(Number(amount)).toLocaleString("en-IN")}`;
}

export function formatLanguage(lang) {
  if (!lang) return "—";
  const l = String(lang).toLowerCase();
  if (l === "telugu") return "Telugu";
  if (l === "hindi") return "Hindi";
  if (l === "english") return "English";
  return l.charAt(0).toUpperCase() + l.slice(1);
}

export function getLanguageVariant(lang) {
  const l = String(lang || "").toLowerCase();
  if (l === "telugu") return "purple";
  if (l === "hindi") return "info";
  return "default";
}

const SEGMENT_MAP = {
  STUDENT: "Student",
  RETIRED: "Retired",
  SELF_EMPLOYED: "Self Employed",
  SALARIED_CORP: "Salaried (Corporate)",
  SALARIED_IT: "Salaried (IT)",
  BUSINESS_OWNER: "Business Owner",
};

export function formatSegment(seg) {
  if (!seg) return "—";
  if (SEGMENT_MAP[seg]) return SEGMENT_MAP[seg];
  return String(seg)
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const SOURCE_MAP = {
  partner_referral: "Partner Referral",
  app_signup: "App Signup",
  web_form: "Web Form",
  campaign: "Campaign",
};

export function formatSource(src) {
  if (!src) return "—";
  if (SOURCE_MAP[src]) return SOURCE_MAP[src];
  return String(src)
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const REPAYMENT_MAP = {
  GOOD: "Good",
  AVERAGE: "Average",
  POOR: "Poor",
};

export function formatRepayment(rep) {
  if (!rep) return "—";
  return REPAYMENT_MAP[rep] || rep.charAt(0).toUpperCase() + rep.slice(1).toLowerCase();
}

export function getRepaymentVariant(rep) {
  const r = String(rep || "").toUpperCase();
  if (r === "GOOD") return "success";
  if (r === "AVERAGE") return "warning";
  return "danger";
}

export function formatRole(role) {
  if (!role) return "User";
  if (role === "SUPER_ADMIN") return "Super Admin";
  if (role === "EMPLOYEE") return "Employee";
  return role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
}

export function formatDate(dt) {
  if (!dt) return "—";
  try {
    const d = new Date(dt);
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(dt);
  }
}
