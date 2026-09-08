(function () {
  const MAX_IMAGES = 3;

  const form = document.getElementById("create-form");
  const attachmentsInput = document.getElementById("attachments-input");
  const previewContainer = document.getElementById("image-preview");
  const aiCheckBtn = document.getElementById("ai-check-btn");
  const aiCheckStatus = document.getElementById("ai-check-status");
  const piiWarningBox = document.getElementById("ai-pii-warning");
  const categorySelect = document.getElementById("category-select");
  const categoryHint = document.getElementById("ai-category-hint");
  const titleInput = document.getElementById("title-input");
  const contentInput = document.getElementById("content-input");

  // --- Multi-image preview, enforced client-side at MAX_IMAGES ---
  attachmentsInput.addEventListener("change", () => {
    const files = Array.from(attachmentsInput.files);
    previewContainer.innerHTML = "";

    if (files.length > MAX_IMAGES) {
      alert(`You can attach at most ${MAX_IMAGES} images. Only the first ${MAX_IMAGES} will be kept.`);
      const dt = new DataTransfer();
      files.slice(0, MAX_IMAGES).forEach((f) => dt.items.add(f));
      attachmentsInput.files = dt.files;
    }

    Array.from(attachmentsInput.files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = document.createElement("img");
        img.src = e.target.result;
        img.className = "w-full h-24 object-cover rounded-lg border border-vault-800";
        previewContainer.appendChild(img);
      };
      reader.readAsDataURL(file);
    });
  });

  // --- "Check with AI" -- pre-submit convenience only, never blocking ---
  aiCheckBtn.addEventListener("click", async () => {
    const title = titleInput.value.trim();
    const content = contentInput.value.trim();
    if (!title && !content) {
      aiCheckStatus.textContent = "Write a bit first, then check.";
      return;
    }

    aiCheckBtn.disabled = true;
    aiCheckStatus.textContent = "Analyzing…";
    piiWarningBox.classList.add("hidden");
    categoryHint.classList.add("hidden");

    try {
      const result = await apiFetch("/posts/api/analyze", { method: "POST", body: { title, content } });

      if (!result.available) {
        aiCheckStatus.textContent = "AI check is unavailable right now.";
      } else {
        aiCheckStatus.textContent = "Done.";

        if (result.category) {
          categoryHint.textContent = `AI suggests: ${result.category}. Leave category as "Auto" to use it, or pick your own above.`;
          categoryHint.classList.remove("hidden");
        }

        if (result.pii_detected && result.pii_warning) {
          piiWarningBox.textContent = `⚠️ ${result.pii_warning}`;
          piiWarningBox.classList.remove("hidden");
        }
      }
    } catch (err) {
      aiCheckStatus.textContent = "Could not run the AI check.";
    } finally {
      aiCheckBtn.disabled = false;
    }
  });
})();
