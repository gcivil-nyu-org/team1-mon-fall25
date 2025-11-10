function initAutocomplete() {
    const input = document.getElementById('id_location');
    if (!input) return;

    const autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.addListener('place_changed', function() {
        const place = autocomplete.getPlace();
        document.getElementById('id_formatted_address').value = place.formatted_address || '';
        document.getElementById('id_latitude').value = place.geometry?.location?.lat() || '';
        document.getElementById('id_longitude').value = place.geometry?.location?.lng() || '';
    });
}
document.addEventListener("DOMContentLoaded", initAutocomplete);