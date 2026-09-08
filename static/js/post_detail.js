(function () {
  const root = document.querySelector("[data-post-id]");
  const postId = root.dataset.postId;

  const detailEl = document.getElementById("post-detail");
  const commentFormRoot = document.getElementById("comment-form-root");
  const commentsContainer = document.getElementById("comments-container");
  const commentsEmpty = document.getElementById("comments-empty");

  const commentTemplate = document.getElementById("comment-template");
  const commentFormTemplate = document.getElementById("comment-form-template");

  const STATUS_STYLES = {
    open: "bg-emerald-500/15 text-emerald-300",
    under_review: "bg-amber-500/15 text-amber-300",
    resolved: "bg-vault-700 text-vault-300",
  };
  const STATUS_LABELS = { open: "Open", under_review: "Under Review", resolved: "Resolved" };
  const REPORT_REASONS = [
    "Information is not true or misleading",
    "Copyright infringement or already published elsewhere",
    "Pornographic or sexually explicit content",
    "Hate speech or abusive content",
    "Personal information or doxxing",
    "Spam or advertising",
    "Threats or illegal content",
    "Other",
  ];

  function renderPost(post) {
    const images = (post.image_urls || [])
      .map((url) => `<img src="${url}" class="rounded-lg border border-vault-800 max-h-96 w-full object-cover mb-3" alt="attachment">`)
      .join("");

    detailEl.innerHTML = `
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full bg-vault-800 text-vault-300">${escapeHtml(post.category)}</span>
        <span class="text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full ${STATUS_STYLES[post.status] || "bg-vault-800 text-vault-300"}">${STATUS_LABELS[post.status] || post.status}</span>
      </div>
      <h1 class="text-2xl font-extrabold mb-3 leading-snug">${escapeHtml(post.title)}</h1>
      ${images}
      <p class="text-sm text-vault-100 whitespace-pre-wrap break-words leading-relaxed mb-4">${escapeHtml(post.content)}</p>
      <div class="flex items-center justify-between text-xs text-vault-500 border-t border-vault-800 pt-4">
        <span>Posted ${timeAgo(post.created_at)} · views: ${post.view_count} · Anonymous</span>
        <div class="flex items-center gap-2">
          <button id="report-btn" class="px-3 py-1.5 rounded-full border border-vault-700 hover:border-rose-500 hover:text-rose-300 text-xs font-medium transition-colors">Report</button>
          <button id="bookmark-btn" class="px-3 py-1.5 rounded-full border text-xs font-semibold transition-colors ${post.bookmarked_by_viewer ? "bg-vault-600 border-vault-600 text-white" : "bg-vault-950 border-vault-700 text-vault-300 hover:border-vault-500"}">
            ${post.bookmarked_by_viewer ? "Saved" : "Save"}
          </button>
          <button id="upvote-btn" class="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold transition-colors ${post.upvoted_by_viewer ? "bg-signal-500 border-signal-500 text-vault-950" : "bg-vault-950 border-vault-700 text-vault-300 hover:border-vault-500"}">
            ▲ <span id="upvote-count">${post.upvotes}</span>
          </button>
        </div>
      </div>
    `;

    document.getElementById("upvote-btn").addEventListener("click", async () => {
      try {
        const result = await apiFetch(`/posts/${postId}/upvote`, { method: "POST" });
        document.getElementById("upvote-count").textContent = result.upvotes;
        const btn = document.getElementById("upvote-btn");
        btn.classList.toggle("bg-signal-500", result.upvoted);
        btn.classList.toggle("border-signal-500", result.upvoted);
        btn.classList.toggle("text-vault-950", result.upvoted);
        btn.classList.toggle("bg-vault-950", !result.upvoted);
        btn.classList.toggle("border-vault-700", !result.upvoted);
        btn.classList.toggle("text-vault-300", !result.upvoted);
      } catch (err) {
        window.location.href = "/auth/login";
      }
    });

    document.getElementById("bookmark-btn").addEventListener("click", async () => {
      try {
        const result = await apiFetch(`/posts/${postId}/bookmark`, { method: "POST" });
        const btn = document.getElementById("bookmark-btn");
        btn.textContent = result.bookmarked ? "Saved" : "Save";
        btn.classList.toggle("bg-vault-600", result.bookmarked);
        btn.classList.toggle("border-vault-600", result.bookmarked);
        btn.classList.toggle("text-white", result.bookmarked);
      } catch (err) {
        window.location.href = "/auth/login";
      }
    });

    document.getElementById("report-btn").addEventListener("click", async () => {
      const reason = await chooseReportReason();
      if (!reason) return;
      try {
        await apiFetch(`/posts/${postId}/report`, { method: "POST", body: { reason } });
        alert("Thanks — this has been flagged for moderator review.");
      } catch (err) {
        window.location.href = "/auth/login";
      }
    });
  }

  function chooseReportReason() {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4";
      overlay.innerHTML = `
        <div class="w-full max-w-md bg-vault-900 border border-vault-700 rounded-xl p-6 shadow-2xl">
          <h2 class="text-lg font-bold mb-1">Why are you reporting this?</h2>
          <p class="text-sm text-vault-400 mb-4">Choose the reason that best describes the problem.</p>
          <div class="space-y-2">${REPORT_REASONS.map((reason) => `
            <label class="flex items-start gap-3 p-3 rounded-lg border border-vault-800 hover:border-vault-500 cursor-pointer text-sm text-vault-200">
              <input type="radio" name="report-reason" value="${escapeHtml(reason)}" class="mt-0.5">
              <span>${escapeHtml(reason)}</span>
            </label>`).join("")}</div>
          <div class="flex justify-end gap-3 mt-5">
            <button type="button" data-report-cancel class="px-3 py-2 text-sm text-vault-300">Cancel</button>
            <button type="button" data-report-submit class="px-4 py-2 rounded-lg bg-rose-500 text-white text-sm font-semibold">Report post</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const close = (value) => { overlay.remove(); resolve(value); };
      overlay.querySelector("[data-report-cancel]").addEventListener("click", () => close(null));
      overlay.querySelector("[data-report-submit]").addEventListener("click", () => {
        const selected = overlay.querySelector('input[name="report-reason"]:checked');
        if (selected) close(selected.value);
      });
    });
  }

  // --- Comments ---

  function makeCommentForm(opts) {
    const parentId = opts.parentId || null;
    const onCancel = opts.onCancel || null;

    const frag = commentFormTemplate.content.cloneNode(true);
    const form = frag.querySelector(".comment-form");
    const cancelBtn = frag.querySelector(".cancel-btn");

    if (onCancel) {
      cancelBtn.classList.remove("hidden");
      cancelBtn.addEventListener("click", onCancel);
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const textarea = form.querySelector(".comment-textarea");
      const content = textarea.value.trim();
      if (!content) return;

      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      try {
        const comment = await apiFetch(`/posts/${postId}/comments`, {
          method: "POST",
          body: { content: content, parent_id: parentId },
        });
        const node = renderComment(comment);
        if (parentId) {
          const parentNode = document.querySelector('.comment-node[data-comment-id="' + parentId + '"]');
          parentNode.querySelector(":scope > .replies-container").appendChild(node);
          if (onCancel) onCancel();
        } else {
          commentsContainer.prepend(node);
          commentsEmpty.classList.add("hidden");
          textarea.value = "";
        }
      } catch (err) {
        if (err.message.includes("Authentication")) {
          window.location.href = "/auth/login";
        } else {
          alert(err.message);
        }
      } finally {
        submitBtn.disabled = false;
      }
    });

    return frag;
  }

  function renderComment(comment) {
    const frag = commentTemplate.content.cloneNode(true);
    const node = frag.querySelector(".comment-node");
    node.dataset.commentId = comment.id;

    node.querySelector(".comment-content").textContent = comment.content;
    node.querySelector(".comment-time").textContent = timeAgo(comment.created_at);
    if (comment.is_op) node.querySelector(".op-badge").classList.remove("hidden");

    const replyBtn = node.querySelector(".reply-btn");
    const replySlot = node.querySelector(".reply-form-slot");
    const deleteBtn = node.querySelector(".delete-comment-btn");

    if (comment.deleted) {
      node.querySelector(".comment-content").classList.add("italic", "text-vault-500");
    }
    if (comment.is_mine && !comment.deleted) {
      deleteBtn.classList.remove("hidden");
      deleteBtn.addEventListener("click", async () => {
        if (!confirm("Delete this comment?")) return;
        await apiFetch(`/posts/comments/${comment.id}/delete`, { method: "POST" });
        const contentEl = node.querySelector(".comment-content");
        contentEl.textContent = "[deleted]";
        contentEl.classList.add("italic", "text-vault-500");
        deleteBtn.remove();
      });
    }

    replyBtn.addEventListener("click", () => {
      if (replySlot.childElementCount > 0) {
        replySlot.classList.add("hidden");
        replySlot.innerHTML = "";
        return;
      }
      replySlot.innerHTML = "";
      replySlot.appendChild(
        makeCommentForm({
          parentId: comment.id,
          onCancel: function () {
            replySlot.classList.add("hidden");
            replySlot.innerHTML = "";
          },
        })
      );
      replySlot.classList.remove("hidden");
      replySlot.querySelector("textarea").focus();
    });

    const repliesContainer = node.querySelector(":scope > .replies-container");
    (comment.replies || []).forEach(function (reply) {
      repliesContainer.appendChild(renderComment(reply));
    });

    return frag;
  }

  async function loadPost() {
    try {
      const post = await apiFetch(`/posts/${postId}/api`);
      renderPost(post);

      commentFormRoot.appendChild(makeCommentForm({}));

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

  loadPost();
})();
