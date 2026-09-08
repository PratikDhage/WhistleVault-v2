(function () {
  const container = document.getElementById("feed-container");
  const emptyState = document.getElementById("feed-empty");
  const loadMoreBtn = document.getElementById("load-more");
  const searchInput = document.getElementById("search-input");
  const categorySelect = document.getElementById("category-select");
  const sortBtns = document.querySelectorAll(".sort-btn");
  const cardTemplate = document.getElementById("post-card-template");

  const STATUS_STYLES = {
    open: "bg-emerald-500/15 text-emerald-300",
    under_review: "bg-amber-500/15 text-amber-300",
    resolved: "bg-vault-700 text-vault-300",
  };
  const STATUS_LABELS = { open: "Open", under_review: "Under Review", resolved: "Resolved" };

  let state = { page: 1, q: "", category: "", sort: "recent", hasNext: false, loading: false };

  function buildCard(post) {
    const node = cardTemplate.content.cloneNode(true);
    const article = node.querySelector(".post-card");
    article.dataset.postId = post.id;

    if (post.thumbnail_url) {
      const wrap = node.querySelector(".card-thumb-wrap");
      wrap.classList.remove("hidden");
      node.querySelector(".card-thumb").src = post.thumbnail_url;
    }

    node.querySelector(".card-category").textContent = post.category;
    const statusEl = node.querySelector(".card-status");
    statusEl.textContent = STATUS_LABELS[post.status] || post.status;
    statusEl.className = "card-status text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full " + (STATUS_STYLES[post.status] || "bg-vault-800 text-vault-300");

    node.querySelector(".card-title").textContent = post.title;
    node.querySelector(".card-meta").textContent = `${timeAgo(post.created_at)} · 👁 ${post.view_count}`;
    node.querySelector(".card-comment-count").textContent = post.comment_count;

    const upvoteBtn = node.querySelector(".upvote-btn");
    upvoteBtn.dataset.postId = post.id;
    upvoteBtn.querySelector(".upvote-count").textContent = post.upvotes;
    if (post.upvoted_by_viewer) {
      upvoteBtn.classList.add("bg-signal-500", "text-vault-950", "border-signal-500");
      upvoteBtn.classList.remove("bg-vault-950", "border-vault-700", "text-vault-300");
    }

    return node;
  }

  async function loadFeed(reset) {
    if (state.loading) return;
    state.loading = true;
    if (reset) {
      state.page = 1;
      container.innerHTML = "";
    }
    try {
      const params = new URLSearchParams({
        page: state.page, q: state.q, sort: state.sort, category: state.category,
      });
      const data = await apiFetch(`/api/feed?${params.toString()}`);
      if (reset && data.posts.length === 0) {
        emptyState.classList.remove("hidden");
      } else {
        emptyState.classList.add("hidden");
      }
      data.posts.forEach((post) => container.appendChild(buildCard(post)));
      state.hasNext = data.has_next;
      loadMoreBtn.classList.toggle("hidden", !state.hasNext);
    } catch (err) {
      console.error(err);
    } finally {
      state.loading = false;
    }
  }

  container.addEventListener("click", async (e) => {
    const upvoteBtn = e.target.closest(".upvote-btn");
    const card = e.target.closest(".post-card");
    if (upvoteBtn) {
      e.stopPropagation();
      try {
        const result = await apiFetch(`/posts/${upvoteBtn.dataset.postId}/upvote`, { method: "POST" });
        upvoteBtn.querySelector(".upvote-count").textContent = result.upvotes;
        upvoteBtn.classList.toggle("bg-signal-500", result.upvoted);
        upvoteBtn.classList.toggle("text-vault-950", result.upvoted);
        upvoteBtn.classList.toggle("border-signal-500", result.upvoted);
        upvoteBtn.classList.toggle("bg-vault-950", !result.upvoted);
        upvoteBtn.classList.toggle("text-vault-300", !result.upvoted);
        upvoteBtn.classList.toggle("border-vault-700", !result.upvoted);
      } catch (err) {
        window.location.href = "/auth/login";
      }
      return;
    }
    if (card) {
      window.location.href = `/posts/${card.dataset.postId}`;
    }
  });

  searchInput.addEventListener(
    "input",
    debounce((e) => {
      state.q = e.target.value.trim();
      loadFeed(true);
    }, 350)
  );

  categorySelect.addEventListener("change", (e) => {
    state.category = e.target.value;
    loadFeed(true);
  });

  sortBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      sortBtns.forEach((b) => {
        b.classList.remove("bg-vault-600", "text-white");
        b.classList.add("bg-vault-900", "border", "border-vault-800", "text-vault-300");
      });
      btn.classList.add("bg-vault-600", "text-white");
      btn.classList.remove("bg-vault-900", "border", "border-vault-800", "text-vault-300");
      state.sort = btn.dataset.sort;
      loadFeed(true);
    });
  });

  loadMoreBtn.addEventListener("click", () => {
    state.page += 1;
    loadFeed(false);
  });

  loadFeed(true);
})();
