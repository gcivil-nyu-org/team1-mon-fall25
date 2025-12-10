function initAutocomplete() {
    const input = document.getElementById('id_location');
    if (!input) return;

    let isSelectingPlace = false;

    const autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.addListener('place_changed', function() {
        isSelectingPlace = true;
        const place = autocomplete.getPlace();
        document.getElementById('id_formatted_address').value = place.formatted_address || '';
        document.getElementById('id_latitude').value = place.geometry?.location?.lat() || '';
        document.getElementById('id_longitude').value = place.geometry?.location?.lng() || '';
        setTimeout(() => { isSelectingPlace = false; }, 100);
    });

    // Whenever the user types manually, clear hidden fields
    input.addEventListener("input", function () {
        if (isSelectingPlace) return; // skip clearing when selecting a suggestion

        document.getElementById("id_latitude").value = "";
        document.getElementById("id_longitude").value = "";
        document.getElementById("id_formatted_address").value = "";
    });
}
document.addEventListener("DOMContentLoaded", initAutocomplete);