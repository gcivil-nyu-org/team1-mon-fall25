// Algolia InstantSearch setup
const searchClient = algoliasearch(ALGOLIA_APP_ID, ALGOLIA_SEARCH_KEY);

const search = instantsearch({
  indexName: ALGOLIA_INDEX_NAME,
  searchClient,
});

// Configure the search box & hits
search.addWidgets([
  instantsearch.widgets.searchBox({
    container: '#searchbox',
    placeholder: 'Search events...',
    showReset: false,
    showSubmit: false,
    showLoadingIndicator: false,
    queryHook(query, refine) {
      refine(query);
    },
  }),

  instantsearch.widgets.hits({
    container: '#hits-container',
    templates: {
      empty: '<div class="no-results">No events found.</div>',
      item: (hit) => `
        <a href="/events/${hit.objectID}/" class="hit-item">
          <div class="hit-title">${instantsearch.highlight({ attribute: 'title', hit })}</div>
          <div class="hit-date">${hit.date_str || ''}</div>
        </a>
      `,
    },
  }),
]);

search.start();

// Handle dropdown visibility
const searchInput = document.getElementById('searchbox');
const dropdown = document.getElementById('hits-container');

searchInput.addEventListener('input', () => {
  if (searchInput.value.trim() === '') dropdown.style.display = 'none';
  else dropdown.style.display = 'block';
});

searchInput.addEventListener('blur', () => {
  setTimeout(() => (dropdown.style.display = 'none'), 200);
});

searchInput.addEventListener('focus', () => {
  if (searchInput.value.trim() !== '') dropdown.style.display = 'block';
});
