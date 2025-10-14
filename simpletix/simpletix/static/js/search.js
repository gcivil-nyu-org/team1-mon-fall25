// simpletix/static/js/search.js
const ALGOLIA_APP_ID = "KFIC62EZAO";
const ALGOLIA_SEARCH_KEY = "4fe1741215a5a5ef75ed0847d66dbd64"; // Search-only API key
const ALGOLIA_INDEX = "simpletix_events"; // Use your exact index name from Algolia

const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);
const resultsPanel = document.getElementById("search-results");

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
    queryHook(query, refine) {
      resultsPanel.style.display = query.trim() ? "block" : "none";
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
              <small class="text-muted">${hit.location}</small><br>
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

// Hide results when clicking outside
document.addEventListener("click", (e) => {
  const box = document.getElementById("searchbox");
  const inside = box.contains(e.target) || resultsPanel.contains(e.target);
  if (!inside) resultsPanel.style.display = "none";
});

