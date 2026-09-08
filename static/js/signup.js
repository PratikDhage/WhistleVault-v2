(function () {
    const form = document.querySelector('form[action$="/signup"]');
    if (!form) return;

    const fields = [
        { name: "username", input: form.elements.username, pattern: /^[a-zA-Z0-9_]{3,32}$/ },
        { name: "email", input: form.elements.email, pattern: /^[^@\s]+@[^@\s]+\.[^@\s]+$/ },
    ];
    const timers = {};

    fields.forEach(({ name, input, pattern }) => {
        const message = form.querySelector(`[data-availability="${name}"]`);
        input.addEventListener("input", () => {
            clearTimeout(timers[name]);
            const value = input.value.trim();
            message.classList.add("hidden");
            input.setCustomValidity("");
            if (!pattern.test(value)) return;

            timers[name] = setTimeout(async () => {
                try {
                    const response = await fetch(`/auth/api/check-availability?field=${name}&value=${encodeURIComponent(value)}`, {
                        headers: { Accept: "application/json" },
                        credentials: "same-origin",
                    });
                    const result = await response.json();
                    message.textContent = result.available ? `${name[0].toUpperCase() + name.slice(1)} is available.` : `${name[0].toUpperCase() + name.slice(1)} already exists.`;
                    message.className = `text-xs mt-1 ${result.available ? "text-emerald-300" : "text-rose-300"}`;
                    input.setCustomValidity(result.available ? "" : `${name} already exists.`);
                } catch (_) {
                    message.classList.add("hidden");
                    input.setCustomValidity("");
                }
            }, 250);
        });
    });
})();