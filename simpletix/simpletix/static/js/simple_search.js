window.addEventListener("load", () => {
  const input = document.getElementById("search-input");
  const resultsBox = document.getElementById("search-results");

  // connect to algolia
  const client = algoliasearch(window.ALGOLIA_APP_ID, window.ALGOLIA_SEARCH_KEY);
  const index = client.initIndex(window.ALGOLIA_INDEX);

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    if (!query) {
      resultsBox.style.display = "none";
      resultsBox.innerHTML = "";
      return;
    }

    try {
      const res = await index.search(query);
      if (res.hits.length === 0) {
        resultsBox.innerHTML = `<div class="p-2 text-muted">No results found</div>`;
      } else {
        resultsBox.innerHTML = res.hits
          .map(
            (hit) => `
            <a href="/events/${hit.objectID}/" class="text-decoration-none text-reset">
              <div class="p-2 border-bottom">
                <strong>${hit.title}</strong><br>
                <small class="text-muted">${hit.location || ""}</small><br>
                <span class="text-muted">${(hit.description || "").slice(0, 60)}...</span>
              </div>
            </a>
          `
          )
          .join("");
      }
      resultsBox.style.display = "block";
    } catch (err) {
      console.error("Algolia search error:", err);
    }
  });

  document.addEventListener("click", (e) => {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      resultsBox.style.display = "none";
    }
  });
});
