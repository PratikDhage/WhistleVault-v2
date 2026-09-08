(function () {
  const root = document.querySelector("[data-post-id]");
  const postId = root.dataset.postId;

  const detailEl = document.getElementById("admin-post-detail");
  const commentsContainer = document.getElementById("admin-comments-container");
  const commentsEmpty = document.getElementById("admin-comments-empty");
  const commentTemplate = document.getElementById("admin-comment-template");

  const STATUSES = ["open", "under_review", "resolved"];
  const STATUS_LABELS = { open: "Open", under_review: "Under Review", resolved: "Resolved" };

  function renderPost(post) {
    const images = (post.image_urls || [])
      .map((url) => `<img src="${url}" class="rounded-lg border border-vault-800 max-h-96 w-full object-cover mb-3" alt="attachment">`)
      .join("");

    const flagBanner = post.ai_flagged
      ? `<div class="bg-rose-500/10 border border-rose-500/40 text-rose-300 text-xs rounded-lg px-3.5 py-2.5 mb-4">
           🚩 AI flagged this post${post.ai_flag_reason ? ": " + escapeHtml(post.ai_flag_reason) : "."}
         </div>`
      : "";
    const reportBanner = post.report_count > 0
      ? `<div class="bg-amber-500/10 border border-amber-500/40 text-amber-300 text-xs rounded-lg px-3.5 py-2.5 mb-4">
           <p class="font-semibold mb-2">${post.report_count} community report(s) on this post.</p>
           <ul class="list-disc pl-4 space-y-1">${(post.reports || []).map((report) => `<li>${escapeHtml(report.reason)} <span class="text-amber-400/70">(${timeAgo(report.created_at)})</span></li>`).join("")}</ul>
         </div>`
      : "";

    const statusOptions = STATUSES.map(
      (s) => `<option value="${s}" ${s === post.status ? "selected" : ""}>${STATUS_LABELS[s]}</option>`
    ).join("");

    detailEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full bg-vault-800 text-vault-300">${escapeHtml(post.category)}</span>
      </div>
      <h1 class="text-2xl font-extrabold mb-1 leading-snug">${escapeHtml(post.title)}</h1>
      <p class="text-xs text-vault-400 mb-4">Author: <span class="text-vault-200 font-medium">${escapeHtml(post.author_username)}</span> · Posted ${timeAgo(post.created_at)}</p>
      ${flagBanner}${reportBanner}
      ${images}
      <p class="text-sm text-vault-100 whitespace-pre-wrap break-words leading-relaxed mb-5">${escapeHtml(post.content)}</p>
      <div class="flex items-center justify-between text-xs text-vault-500 border-t border-vault-800 pt-4">
        <div class="flex items-center gap-2">
          <label class="text-vault-400">Status:</label>
          <select id="status-select" class="bg-vault-950 border border-vault-800 rounded-lg px-2 py-1.5 text-xs text-vault-200 focus:outline-none focus:ring-2 focus:ring-vault-500">
            ${statusOptions}
          </select>
        </div>
        <div class="flex items-center gap-3">
          <span>▲ ${post.upvotes} upvotes · 👁 ${post.view_count} views</span>
          <button id="admin-delete-btn" class="px-3 py-1.5 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-300 hover:bg-rose-500/25 text-xs font-semibold transition-colors">
            🗑 Remove post
          </button>
        </div>
      </div>
    `;

    document.getElementById("status-select").addEventListener("change", async (e) => {
      try {
        await apiFetch(`/admin/posts/${postId}/status`, { method: "POST", body: { status: e.target.value } });
      } catch (err) {
        alert(err.message);
      }
    });

    document.getElementById("admin-delete-btn").addEventListener("click", async () => {
      if (!confirm("Remove this post from the platform? This cannot be undone.")) return;
      try {
        await apiFetch(`/admin/posts/${postId}/delete`, { method: "POST" });
        window.location.href = "/admin/dashboard";
      } catch (err) {
        alert(err.message);
      }
    });
  }

  function renderComment(comment) {
    const frag = commentTemplate.content.cloneNode(true);
    const node = frag.querySelector(".comment-node");

    node.querySelector(".comment-author").textContent = comment.author_username;
    node.querySelector(".comment-content").textContent = comment.content;
    node.querySelector(".comment-time").textContent = timeAgo(comment.created_at);
    if (comment.is_op) node.querySelector(".op-badge").classList.remove("hidden");
    if (comment.deleted) {
      node.querySelector(".comment-content").classList.add("italic", "text-vault-500");
    }

    const deleteBtn = node.querySelector(".delete-comment-btn");
    if (comment.deleted) {
      deleteBtn.remove();
    } else {
      deleteBtn.addEventListener("click", async () => {
        if (!confirm("Remove this comment?")) return;
        await apiFetch(`/admin/comments/${comment.id}/delete`, { method: "POST" });
        node.querySelector(".comment-content").textContent = "[deleted]";
        node.querySelector(".comment-content").classList.add("italic", "text-vault-500");
        deleteBtn.remove();
      });
    }

    const repliesContainer = node.querySelector(":scope > .replies-container");
    (comment.replies || []).forEach(function (reply) {
      repliesContainer.appendChild(renderComment(reply));
    });

    return frag;
  }

  async function load() {
    try {
      const post = await apiFetch(`/admin/api/posts/${postId}`);
      renderPost(post);

      if (!post.comments || post.comments.length === 0) {
        commentsEmpty.classList.remove("hidden");
      } else {
        post.comments.forEach(function (c) {
          commentsContainer.appendChild(renderComment(c));
        });
      }
    } catch (err) {
      detailEl.innerHTML = '<p class="text-vault-400 text-sm">This post could not be loaded.</p>';
    }
  }

  load();
})();
