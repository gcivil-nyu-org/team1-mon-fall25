document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ Search script loaded");

  // your Algolia credentials
  const ALGOLIA_APP_ID = "KFIC62EZAO";
  const ALGOLIA_SEARCH_KEY = "4fe1741215a5a5ef75ed0847d66dbd64";
  const ALGOLIA_INDEX = "simpletix_simpletix_events"; // match your actual index

  // check that libraries loaded
  if (typeof algoliasearch === "undefined" || typeof instantsearch === "undefined") {
    console.error("❌ Algolia libs not loaded");
    return;
  }

  const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);

  const resultsPanel = document.getElementById("search-results");
  const searchBoxEl = document.getElementById("searchbox");

  if (!searchBoxEl || !resultsPanel) {
    console.error("❌ Searchbox or results panel not found");
    return;
  }

  // build search
  const search = instantsearch({
    indexName: ALGOLIA_INDEX,
    searchClient,
  });

  // search bar widget
  search.addWidget(
    instantsearch.widgets.searchBox({
      container: "#searchbox",
      placeholder: "Search events...",
      showReset: false,
      showSubmit: false,
      searchAsYouType: true,
      cssClasses: { input: "form-control" },
      queryHook(query, refine) {
        refine(query);
        // always show results panel while typing
        resultsPanel.style.display = "block";
      },
    })
  );

  // hits widget
  search.addWidget(
    instantsearch.widgets.hits({
      container: "#search-results",
      templates: {
        item(hit) {
          // adjust field names if your index uses different ones
          const desc = (hit.description || "").slice(0, 80);
          const loc = hit.location || "";
          return `
            <a href="/events/${hit.id || hit.objectID}/" class="text-decoration-none text-reset d-block p-2 border-bottom">
              <strong>${hit.title || "(Untitled)"}</strong><br>
              <small class="text-muted">${loc}</small><br>
              <span class="text-muted">${desc}...</span>
            </a>
          `;
        },
        empty: `<div class="p-2 text-muted">No events found</div>`,
      },
    })
  );

  // start search
  search.start();

  // optional: keep dropdown open while clicking inside, hide when clicking elsewhere
  document.addEventListener("click", (e) => {
    const inside = searchBoxEl.contains(e.target) || resultsPanel.contains(e.target);
    resultsPanel.style.display = inside ? "block" : "none";
  });
});
