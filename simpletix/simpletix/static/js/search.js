// simpletix/static/js/search.js
document.addEventListener("DOMContentLoaded", () => {
  const ALGOLIA_APP_ID = "KFIC62EZAO";
  const ALGOLIA_SEARCH_KEY = "4fe1741215a5a5ef75ed0847d66dbd64"; // Search-only API key
  const ALGOLIA_INDEX = "simpletix_events"; // Your index name

  // Verify Algolia libraries are loaded
  if (typeof algoliasearch === "undefined" || typeof instantsearch === "undefined") {
    console.error("Algolia libraries not found — check script order");
    return;
  }

  const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
  const resultsPanel = document.getElementById("search-results");

  const search = instantsearch({
    indexName: ALGOLIA_INDEX,
    searchClient,
  });

  // ✅ This uses your existing <div id="searchbox"> (not <input>)
  search.addWidgets([
    instantsearch.widgets.searchBox({
      container: "#searchbox",
      placeholder: "Search events...",
      showReset: false,
      showSubmit: false,
      searchAsYouType: true,
      cssClasses: {
        input: "form-control", // Bootstrap styling
      },
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
          const loc = hit.location ? `<small class="text-muted">${hit.location}</small><br>` : "";
          const date = hit.date_str ? `<small class="text-muted">${hit.date_str}</small><br>` : "";
          return `
            <a href="/events/${hit.objectID}/" class="text-decoration-none text-reset">
              <div class="p-2 border-bottom">
                <strong>${hit.title}</strong><br>
                ${loc}${date}
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

  // Hide dropdown when clicking outside
  document.addEventListener("click", (e) => {
    const box = document.getElementById("searchbox");
    const inside = box.contains(e.target) || resultsPanel.contains(e.target);
    if (!inside && resultsPanel) resultsPanel.style.display = "none";
  });
});
