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
});
