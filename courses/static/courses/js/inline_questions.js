/* inline_questions.js — drag-to-reorder for inline question lists.
 * Adding / editing / deleting uses standard server-side forms that POST
 * and reload the page; this script only handles reorder.
 */
(function () {
  "use strict";

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function initList(container) {
    const reorderUrl = container.dataset.reorderUrl;
    if (!reorderUrl || !window.Sortable) return;

    const rowsUl = container.querySelector(".qlist__rows");
    if (!rowsUl) return;

    Sortable.create(rowsUl, {
      handle: ".qrow__handle",
      animation: 150,
      ghostClass: "sortable-ghost",
      onEnd: async () => {
        const ids = Array.from(rowsUl.querySelectorAll(".qrow")).map((r) => r.dataset.questionId);
        rowsUl.querySelectorAll(".qrow").forEach((r, idx) => {
          const num = r.querySelector(".qrow__num");
          if (num) num.textContent = "Q" + (idx + 1);
        });
        try {
          const res = await fetch(reorderUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrfToken(), "Content-Type": "application/json" },
            body: JSON.stringify({ order: ids }),
          });
          if (!res.ok) console.warn("Reorder failed:", res.status);
        } catch (e) { console.warn("Reorder error:", e); }
      },
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".qlist").forEach(initList);
  });
})();