(function () {
  const statsRow = document.getElementById("stats-row");
  const tbody = document.getElementById("admin-posts-body");
  const loadMoreBtn = document.getElementById("admin-load-more");
  const searchInput = document.getElementById("admin-search");
  const flaggedToggle = document.getElementById("flagged-toggle");

  const STATUS_LABELS = { open: "Open", under_review: "Under Review", resolved: "Resolved" };

  let state = { page: 1, q: "", flaggedOnly: false };

  function statBlock(label, value) {
    return `
      <div class="bg-vault-900/60 border border-vault-800 rounded-xl p-4">
        <p class="text-2xl font-bold">${value}</p>
        <p class="text-xs text-vault-400 mt-1">${label}</p>
      </div>`;
  }

  async function loadStats() {
    const stats = await apiFetch("/admin/api/stats");
    statsRow.innerHTML = [
      statBlock("Total users", stats.total_users),
      statBlock("Verified users", stats.verified_users),
      statBlock("Active posts", stats.total_posts),
      statBlock("Flagged posts", stats.flagged_posts),
      statBlock("Removed posts", stats.deleted_posts),
    ].join("");
  }

  function rowHtml(post) {
    const flagBadges = [];
    if (post.ai_flagged) flagBadges.push('<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-semibold">AI</span>');
    if (post.report_count > 0) flagBadges.push(`<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-semibold">${post.report_count} report${post.report_count > 1 ? "s" : ""}</span>`);

    return `
      <tr data-post-id="${post.id}" class="hover:bg-vault-800/40 cursor-pointer">
        <td class="px-4 py-3 font-medium text-vault-200">${escapeHtml(post.author_username)}</td>
        <td class="px-4 py-3 max-w-xs truncate text-vault-300">${escapeHtml(post.title)}</td>
        <td class="px-4 py-3 text-vault-400 text-xs">${escapeHtml(post.category)}</td>
        <td class="px-4 py-3 text-vault-400 text-xs">${STATUS_LABELS[post.status] || post.status}</td>
        <td class="px-4 py-3">${flagBadges.join(" ") || '<span class="text-vault-600 text-xs">—</span>'}</td>
        <td class="px-4 py-3 text-right">
          <button class="admin-delete-btn text-rose-400 hover:text-rose-300 font-medium text-xs">Remove</button>
        </td>
      </tr>`;
  }

  async function loadPosts(reset) {
    if (reset) {
      state.page = 1;
      tbody.innerHTML = "";
    }
    const params = new URLSearchParams({ page: state.page, q: state.q, flagged_only: state.flaggedOnly });
    const data = await apiFetch(`/admin/api/posts?${params.toString()}`);
    tbody.insertAdjacentHTML("beforeend", data.posts.map(rowHtml).join(""));
    loadMoreBtn.classList.toggle("hidden", !data.has_next);
  }

  tbody.addEventListener("click", async (e) => {
    const deleteBtn = e.target.closest(".admin-delete-btn");
    const row = e.target.closest("tr");
    if (!row) return;

    if (deleteBtn) {
      if (!confirm("Remove this post from the platform?")) return;
      try {
        await apiFetch(`/admin/posts/${row.dataset.postId}/delete`, { method: "POST" });
        row.remove();
        loadStats();
      } catch (err) {
        alert(err.message);
      }
      return;
    }

    window.location.href = `/admin/posts/${row.dataset.postId}`;
  });

  searchInput.addEventListener(
    "input",
    debounce((e) => {
      state.q = e.target.value.trim();
      loadPosts(true);
    }, 350)
  );

  flaggedToggle.addEventListener("click", () => {
    state.flaggedOnly = !state.flaggedOnly;
    flaggedToggle.classList.toggle("bg-signal-500", state.flaggedOnly);
    flaggedToggle.classList.toggle("text-vault-950", state.flaggedOnly);
    flaggedToggle.classList.toggle("bg-vault-900", !state.flaggedOnly);
    flaggedToggle.classList.toggle("text-vault-300", !state.flaggedOnly);
    loadPosts(true);
  });

  loadMoreBtn.addEventListener("click", () => {
    state.page += 1;
    loadPosts(false);
  });

  loadStats();
  loadPosts(true);
})();
