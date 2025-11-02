// simpletix/static/js/search.js
document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ Search script loaded");

  // Get values injected from Django template (nav.html)
  const ALGOLIA_APP_ID = window.ALGOLIA_APP_ID;
  const ALGOLIA_SEARCH_KEY = window.ALGOLIA_SEARCH_KEY;
  const ALGOLIA_INDEX = window.ALGOLIA_INDEX;

  if (!ALGOLIA_APP_ID || !ALGOLIA_SEARCH_KEY || !ALGOLIA_INDEX) {
    console.error("❌ Missing Algolia credentials from template context");
    return;
  }

  if (typeof algoliasearch === "undefined" || typeof instantsearch === "undefined") {
    console.error("❌ Algolia libraries not found — check script imports");
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
      cssClasses: { input: "form-control", root: "w-100" },
      templates: {
        submit() { return ''; },
        reset() { return ''; }
      },
      render(options, isFirstRender) {
        if (isFirstRender) {
          // clear any leftover input from the DOM (fixes double bar issue)
          document.querySelector("#searchbox").innerHTML = "";
        }
        options.widgetParams.container.innerHTML = `
          <input type="search" class="form-control" placeholder="Search events..." aria-label="Search">
        `;
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

  document.addEventListener("click", (e) => {
    if (!resultsPanel) return;
    const inside =
      searchBoxEl.contains(e.target) || resultsPanel.contains(e.target);
    if (!inside) resultsPanel.style.display = "none";
  });
});
