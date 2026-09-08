(function () {
  const profileCard = document.getElementById("profile-card");

  function statBlock(label, value) {
    return `
      <div class="bg-vault-900/60 border border-vault-800 rounded-xl p-4">
        <p class="text-2xl font-bold">${value}</p>
        <p class="text-xs text-vault-400 mt-1">${label}</p>
      </div>`;
  }

  async function loadProfile() {
    const profile = await apiFetch("/api/profile");
    profileCard.innerHTML = [
      statBlock("Username", escapeHtml(profile.username)),
      statBlock("Member since", profile.member_since),
      statBlock("Posts", profile.post_count),
      statBlock("Upvotes received", profile.total_upvotes_received),
    ].join("");
  }

  function postCardHtml(post, opts) {
    opts = opts || {};
    const img = post.thumbnail_url
      ? `<img src="${post.thumbnail_url}" alt="attachment" class="rounded-lg mt-3 max-h-48 w-full object-cover border border-vault-800">`
      : "";
    const deleteBtn = opts.allowDelete
      ? `<form method="POST" action="/posts/${post.id}/delete" onsubmit="return confirm('Delete this post permanently?');" class="inline">
           <input type="hidden" name="csrf_token" value="${window.CSRF_TOKEN}">
           <button type="submit" class="text-rose-400 hover:text-rose-300 font-medium">Delete</button>
         </form>`
      : "";
    return `
      <article class="post-card bg-vault-900/60 border border-vault-800 rounded-xl p-5 flex flex-col">
        <a href="/posts/${post.id}" class="hover:underline">
          <h3 class="text-sm font-bold text-vault-100 leading-snug">${escapeHtml(post.title)}</h3>
        </a>
        ${img}
        <div class="mt-4 flex items-center justify-between text-xs text-vault-500">
          <span>Posted ${timeAgo(post.created_at)} · ▲ ${post.upvotes} · 💬 ${post.comment_count}</span>
          ${deleteBtn}
        </div>
      </article>`;
  }

  function makeListLoader({ endpoint, containerId, emptyId, loadMoreId, allowDelete }) {
    const container = document.getElementById(containerId);
    const emptyState = document.getElementById(emptyId);
    const loadMoreBtn = document.getElementById(loadMoreId);
    let page = 1;

    async function load(reset) {
      if (reset) {
        page = 1;
        container.innerHTML = "";
      }
      const data = await apiFetch(`${endpoint}?page=${page}`);
      if (reset && data.posts.length === 0) {
        emptyState.classList.remove("hidden");
      } else {
        emptyState.classList.add("hidden");
      }
      container.insertAdjacentHTML("beforeend", data.posts.map((p) => postCardHtml(p, { allowDelete })).join(""));
      loadMoreBtn.classList.toggle("hidden", !data.has_next);
    }

    loadMoreBtn.addEventListener("click", () => {
      page += 1;
      load(false);
    });

    load(true);
  }

  loadProfile();

  makeListLoader({
    endpoint: "/posts/mine",
    containerId: "my-posts-container",
    emptyId: "my-posts-empty",
    loadMoreId: "my-posts-load-more",
    allowDelete: true,
  });

  makeListLoader({
    endpoint: "/posts/bookmarked",
    containerId: "bookmarks-container",
    emptyId: "bookmarks-empty",
    loadMoreId: "bookmarks-load-more",
    allowDelete: false,
  });
})();
