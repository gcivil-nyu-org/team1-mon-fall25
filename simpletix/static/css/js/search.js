// simpletix/static/js/search.js
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ Search script loaded"); // debug confirmation in console

  const ALGOLIA_APP_ID = "KFIC62EZAO";
  const ALGOLIA_SEARCH_KEY = "4fe1741215a5a5ef75ed0847d66dbd64"; // Search-only API key
  const ALGOLIA_INDEX = "simpletix_simpletix_events"; // Use your exact index name from Algolia

  // Ensure Algolia libraries are present
  if (typeof algoliasearch === "undefined" || typeof instantsearch === "undefined") {
    console.error("❌ Algolia libraries not found — check script order or network load");
    return;
  }

  const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
  const resultsPanel = document.getElementById("search-results");
  const searchBoxEl = document.getElementById("searchbox");

  if (!searchBoxEl) {
    console.error("❌ #searchbox not found in DOM");
    return;
  }

  const search = instantsearch({
    indexName: ALGOLIA_INDEX,
    searchClient,
  });

  search.addWidgets([
    instantsearch.widgets.searchBox({
      container: "#searchbox",
      placeholder: "Search events...",
      showReset: false,
      showSubmit: false,
      searchAsYouType: true,
      cssClasses: { input: "form-control" },
      queryHook(query, refine) {
        if (resultsPanel) {
          resultsPanel.style.display = query.trim() ? "block" : "none";
        }
        refine(query);
      },
    }),

    instantsearch.widgets.hits({
      container: "#search-results",
      templates: {
        item(hit) {
          const desc = (hit.description || "").slice(0, 80);
          return `
            <a href="/events/${hit.objectID}/" class="text-decoration-none text-reset">
              <div class="p-2 border-bottom">
                <strong>${hit.title}</strong><br>
                <small class="text-muted">${hit.location || ""}</small><br>
                <span class="text-muted">${desc}...</span>
              </div>
            </a>
          `;
        },
        empty: `<div class="p-2 text-muted">No events found</div>`,
      },
    }),
  ]);

  search.start();

  // Hide results dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!resultsPanel) return;
    const inside =
      searchBoxEl.contains(e.target) || resultsPanel.contains(e.target);
    if (!inside) resultsPanel.style.display = "none";
  });
});
