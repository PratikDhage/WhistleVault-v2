/**
 * Shared client-side helpers used across pages.
 */

/** fetch() wrapper that attaches the CSRF token and sane JSON defaults. */
async function apiFetch(url, options = {}) {
  const opts = {
    method: options.method || "GET",
    headers: {
      "X-CSRFToken": window.CSRF_TOKEN || "",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      Accept: "application/json",
      ...(options.headers || {}),
    },
    credentials: "same-origin",
  };
  if (options.body) opts.body = JSON.stringify(options.body);

  const res = await fetch(url, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* no JSON body */
  }
  if (!res.ok) {
    const message = (data && data.error) || `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function timeAgo(isoString) {
  const seconds = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  const units = [
    ["year", 31536000], ["month", 2592000], ["day", 86400],
    ["hour", 3600], ["minute", 60],
  ];
  for (const [label, secs] of units) {
    const value = Math.floor(seconds / secs);
    if (value >= 1) return `${value} ${label}${value > 1 ? "s" : ""} ago`;
  }
  return "just now";
}

function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
