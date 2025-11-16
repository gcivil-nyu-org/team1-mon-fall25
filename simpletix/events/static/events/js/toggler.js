document.addEventListener('DOMContentLoaded', function() {
    
    /**
     * Handles the enabled/disabled/required state of a single formset row.
     */
    function handleRowState(checkbox) {
        // Find the parent <tr>
        const row = checkbox.closest('.ticket-formset-row');
        if (!row) return;

        // Find the inputs within that row
        const priceInput = row.querySelector('input[id$="-price"]');
        const availabilityInput = row.querySelector('input[id$="-availability"]');

        if (!priceInput || !availabilityInput) return;

        if (checkbox.checked) {
            // --- TOGGLE ON ---
            // Enable, set required, and fill default values
            priceInput.disabled = false;
            priceInput.required = true;
            // Only fill if it's empty
            if (priceInput.value === '' || parseFloat(priceInput.value) === 0) {
                priceInput.value = 0.5; // Min value
            }

            availabilityInput.disabled = false;
            availabilityInput.required = true;
            if (availabilityInput.value === '') {
                availabilityInput.value = 0; // Min value
            }

        } else {
            // --- TOGGLE OFF ---
            // Disable, clear, and remove required
            priceInput.disabled = true;
            priceInput.required = false;
            priceInput.value = ''; // Clear the value

            availabilityInput.disabled = true;
            availabilityInput.required = false;
            availabilityInput.value = ''; // Clear the value
        }
    }

    // Find all formset rows
    const allRows = document.querySelectorAll('.ticket-formset-row');
    
    allRows.forEach(function(row) {
        // Find the checkbox in this row
        const checkbox = row.querySelector('input[id$="-is_active"]');
        if (!checkbox) return;
        
        // 1. Add a listener for any "change"
        checkbox.addEventListener('change', function() {
            handleRowState(checkbox);
        });

        // 2. Run on page load to set the initial state
        // (This handles re-renders on form validation errors)
        handleRowState(checkbox);
    });
});