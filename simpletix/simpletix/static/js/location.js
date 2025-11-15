// location.js
document.addEventListener("DOMContentLoaded", function() {
  const input = document.getElementById("location-input");
  const setLocationBtn = document.getElementById("set-location-btn");

  // Load saved location (if any)
  const savedLocation = localStorage.getItem("user_location");
  if (savedLocation && input) {
    input.value = savedLocation;
  }

  // Initialize Google Places Autocomplete
  if (typeof google !== "undefined" && google.maps && google.maps.places) {
    const autocomplete = new google.maps.places.Autocomplete(input, {
      types: ["(cities)"], // you can change to geocode if you prefer ZIPs
    });
    autocomplete.addListener("place_changed", function() {
      const place = autocomplete.getPlace();
      if (place && place.formatted_address) {
        input.value = place.formatted_address;
        localStorage.setItem("user_location", place.formatted_address);
      }
    });
  }

  // Optional button for auto-detect 
  if (setLocationBtn) {
    setLocationBtn.addEventListener("click", function() {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            localStorage.setItem("user_coords", JSON.stringify({ lat, lng }));
            reverseGeocode(lat, lng); // fill in the city name
          },
          () => {
            alert("Location access denied. Please enter manually.");
          }
        );
      } else {
        alert("Geolocation not supported by this browser.");
      }
    });
  }

  // Helper: reverse geocode coordinates into a readable city name
  function reverseGeocode(lat, lng) {
    const geocoder = new google.maps.Geocoder();
    const latlng = { lat, lng };
    geocoder.geocode({ location: latlng }, (results, status) => {
      if (status === "OK" && results[0]) {
        const city = results[0].formatted_address;
        input.value = city;
        localStorage.setItem("user_location", city);
      }
    });
  }

  // --- Keep hidden fields in sync for event_list filtering ---
  const hiddenLat = document.getElementById("user_lat");
  const hiddenLng = document.getElementById("user_lng");

  // 1. Load saved coords into hidden fields on page load
  const savedCoords = localStorage.getItem("user_coords");
  if (savedCoords && hiddenLat && hiddenLng) {
    const parsed = JSON.parse(savedCoords);
    hiddenLat.value = parsed.lat;
    hiddenLng.value = parsed.lng;
  }

  // 2. Manual input should overwrite auto-detect
  input.addEventListener("change", function () {
    const text = input.value.trim();
    if (!text) return;

    const geocoder = new google.maps.Geocoder();
    geocoder.geocode({ address: text }, (results, status) => {
      if (status === "OK" && results[0]) {
        const loc = results[0].geometry.location;
        const lat = loc.lat();
        const lng = loc.lng();

        // Save & overwrite auto coords
        localStorage.setItem("user_coords", JSON.stringify({ lat, lng }));
        localStorage.setItem("user_location", results[0].formatted_address);

        // Sync hidden fields
        if (hiddenLat && hiddenLng) {
          hiddenLat.value = lat;
          hiddenLng.value = lng;
        }
      }
    });
  });

  // 3. When auto-detect is used, it overwrites manual coords
  function updateHidden(lat, lng) {
    if (hiddenLat) hiddenLat.value = lat;
    if (hiddenLng) hiddenLng.value = lng;
  }

  // Patch reverseGeocode so it also updates hidden fields
  const originalReverse = reverseGeocode;
  reverseGeocode = function(lat, lng) {
    updateHidden(lat, lng);
    originalReverse(lat, lng);
  };

});
