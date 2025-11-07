// frontend/app.js

document.addEventListener('DOMContentLoaded', () => {
    App.initialize();
});

const App = {
    // 1. Configuration and State
    // FIX: Corrected API_BASE_URL to match main.py's host and port (7070)
    API_BASE_URL: 'http://127.0.0.1:7070/api',
    BUILD_PAGE_SIZE: 100, // Used for the building card list display
    allBuildings: [],
    selectedBuildingId: null,

    // 2. Cached DOM Elements
    elements: {},

    // 3. Initialization Function
    initialize() {
        // Cache all DOM elements from your index.html
        this.elements.buildingsContainer = document.getElementById('deviceList');
        this.elements.loader = document.getElementById('loader');
        this.elements.notification = document.getElementById('notification');
        this.elements.buildingSearch = document.querySelector('.building-search');
        this.elements.buildingDropdown = document.querySelector('.building-dropdown');
        this.elements.clearFilter = document.querySelector('.clear-filter');
        this.elements.ignoreModal = document.getElementById('ignoreModal');
        this.elements.modalTitle = document.getElementById('modalTitle');
        this.elements.modalItemList = document.getElementById('modalItemList');
        this.elements.modalConfirmBtn = document.getElementById('modalConfirmBtn');
        this.elements.modalCancelBtn = document.getElementById('modalCancelBtn');
        this.elements.closeButton = document.querySelector('.close-button');
        this.elements.modalSearch = document.getElementById('modalSearch');
        this.elements.modalSelectAllBtn = document.getElementById('modalSelectAllBtn');

        // Setup event listeners and load initial data
        this.setupBuildingSelector();
        this.loadAllBuildings();
    },

    // 4. Utility Methods (Child Functions)
    
    showNotification(text, isError = false, timeout = 3000) {
        // Ensure notification element exists before using it
        if (!this.elements.notification) return;
        const { notification } = this.elements;
        notification.textContent = text;
        notification.style.backgroundColor = isError ? '#ef4444' : '#333';
        notification.classList.add('show');
        
        // Clear previous timeout if exists to prevent overlapping messages
        if (notification.timeoutId) {
            clearTimeout(notification.timeoutId);
        }
        notification.timeoutId = setTimeout(() => {
             notification.classList.remove('show');
             notification.timeoutId = null; // Clear the stored timeout ID
        }, timeout);
    },

    async apiRequest(endpoint, options = {}) {
        const url = `${this.API_BASE_URL}/${endpoint}`;
        try {
            // Show loader for all requests (moved here for central control)
            if(this.elements.loader) this.elements.loader.style.display = 'block'; 
            const response = await fetch(url, options);
            if (!response.ok) {
                // Try to get error detail from JSON, provide fallback
                const errorData = await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` }));
                throw new Error(errorData.detail || `Request failed: ${response.status}`);
            }
            // Check content type before parsing JSON
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            }
            // Return empty object for non-JSON responses (like maybe a 204 No Content)
            return {};
        } catch (error) {
            console.error(`API request error for ${endpoint}:`, error);
            // Show user-friendly error from the API or a generic one
            this.showNotification(error.message || 'An unexpected error occurred', true);
            throw error; // Re-throw to allow calling functions to handle it if needed
        } finally {
             // Hide loader after all requests, success or failure
             if(this.elements.loader) this.elements.loader.style.display = 'none';
        }
    },

    // Simple HTML escaping utility
    escapeHtml(str) {
        return String(str || '').replace(/[&<>"']/g, s => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;',
            '"': '&quot;', "'": '&#39;'
        }[s]));
    },

    // 5. Building List & Search Logic
    
    setupBuildingSelector() {
        const { buildingSearch, buildingDropdown, clearFilter } = this.elements;
        // Add null checks for safety
        if (!buildingSearch || !buildingDropdown || !clearFilter) {
            console.error("Building selector elements not found!");
            return;
        }


        buildingSearch.addEventListener('input', () => {
            const query = buildingSearch.value.toLowerCase();
            buildingDropdown.innerHTML = ''; // Clear previous results

            if (query.length === 0) {
                buildingDropdown.style.display = 'none';
                clearFilter.style.display = 'none';
                 // If query is cleared, reset view to all buildings
                 if (this.selectedBuildingId !== null) {
                     this.selectedBuildingId = null;
                     this.loadAllBuildings(); // Reload all buildings view
                 }
                return;
            }

            // Filter buildings based on search query
            const filtered = this.allBuildings.filter(b =>
                b.name.toLowerCase().includes(query)
            );

            if (filtered.length > 0) {
                filtered.forEach(building => {
                    const option = document.createElement('div');
                    option.className = 'building-option';
                    option.textContent = this.escapeHtml(building.name); // Escape name
                    option.addEventListener('click', () => this.selectBuilding(building));
                    buildingDropdown.appendChild(option);
                });
                buildingDropdown.style.display = 'block'; // Show dropdown
            } else {
                 // Show 'No results' message
                 const noResult = document.createElement('div');
                 noResult.className = 'building-option muted';
                 noResult.textContent = 'No buildings found';
                 buildingDropdown.appendChild(noResult);
                 buildingDropdown.style.display = 'block';
            }
            clearFilter.style.display = 'block'; // Show clear button if there's text
        });

        clearFilter.addEventListener('click', () => {
            buildingSearch.value = ''; // Clear search input
            buildingDropdown.innerHTML = ''; // Clear dropdown content
            buildingDropdown.style.display = 'none'; // Hide dropdown
            clearFilter.style.display = 'none'; // Hide clear button
            this.selectedBuildingId = null; // Clear selection state
            this.loadAllBuildings(); // Reload the list to show all buildings
        });

        // Close dropdown if clicked outside
        document.addEventListener('click', (e) => {
            if (!buildingSearch.contains(e.target) && !buildingDropdown.contains(e.target)) {
                buildingDropdown.style.display = 'none';
            }
        });
    },

    // Handles selecting a building from the dropdown
    selectBuilding(building) {
        const { buildingSearch, buildingDropdown, clearFilter } = this.elements;
        if (!buildingSearch || !buildingDropdown || !clearFilter) return; // Safety check

        buildingSearch.value = this.escapeHtml(building.name); // Set input value
        buildingDropdown.style.display = 'none'; // Hide dropdown
        this.selectedBuildingId = building.id; // Store selected ID
        clearFilter.style.display = 'block'; // Ensure clear button is visible
        this.loadFilteredBuilding(building); // Load only the selected building's card
    },

    // Loads and displays only the card for the selected building
    async loadFilteredBuilding(building) {
        const { buildingsContainer } = this.elements;
        if (!buildingsContainer) return; // Safety check

        buildingsContainer.innerHTML = ''; // Clear existing cards
        const card = this.createBuildingCard(building); // Create card
        buildingsContainer.appendChild(card); // Add card to the container
        
        // Automatically expand and load items for the selected building
        try {
            await this.loadItemsForBuilding(card); // Load items
            const body = card.querySelector('.building-body');
            const toggleBtn = card.querySelector('.toggle-btn');
            if (body && toggleBtn) { // Check elements exist
                body.style.display = 'block'; // Ensure body is visible
                toggleBtn.textContent = '-'; // Set toggle button state
                // Mark items list as loaded after successful load
                const itemsList = card.querySelector('.items-list');
                if (itemsList) itemsList.dataset.loaded = 'true';
            }
        } catch (error) {
             console.error("Error auto-loading items for filtered building:", error);
             // Show error within the card body
             const itemsList = card.querySelector('.items-list');
             if (itemsList) itemsList.innerHTML = '<li class="muted">Error loading items.</li>';
             // Still attempt to show the card body so error is visible
             const body = card.querySelector('.building-body');
             const toggleBtn = card.querySelector('.toggle-btn');
             if (body && toggleBtn) {
                 body.style.display = 'block';
                 toggleBtn.textContent = '-';
             }
        }
    },


    // Fetches all buildings and renders their cards
    async loadAllBuildings() {
        const { buildingsContainer } = this.elements;
        if (!buildingsContainer) return; // Safety check

        buildingsContainer.innerHTML = ''; // Clear current buildings
        this.selectedBuildingId = null; // Reset selection state

        try {
            this.allBuildings = await this.apiRequest('buildings'); // Fetch all buildings
            if (this.allBuildings.length === 0) {
                 buildingsContainer.innerHTML = '<p class="muted">No buildings found.</p>';
            } else {
                 this.allBuildings.forEach(building => { // Create and append card for each
                     buildingsContainer.appendChild(this.createBuildingCard(building));
                 });
            }
        } catch (error) {
             // Error shown by apiRequest, just display message here
             buildingsContainer.innerHTML = '<p class="muted">Failed to load buildings. Please try again later.</p>';
        } finally {
            // Loader handling moved to apiRequest
        }
    },

    // 6. Building Card Logic
    
    createBuildingCard(building) {
        const card = document.createElement('div');
        card.className = 'building-card';
        card.dataset.buildingId = building.id;
        // Use default times if API doesn't provide them
        const startTime = building.start_time || '09:00'; 
        const endTime = building.end_time || '17:00';

        // *** THIS IS THE FIX: Corrected 'class=' for building-actions ***
        card.innerHTML = `
            <div class="building-header">
                <button class="toggle-btn">+</button>
                <h2 class="building-title">${this.escapeHtml(building.name)} (ID: ${building.id})</h2>
                <div class="building-actions">
                    <button class="bulk-btn bulk-disarm">Set Ignore Flags</button>
                </div>
                <div class="building-time-control">
                    <label>Start:</label>
                    <input type="time" class="time-input start-time-input" value="${startTime}" required />
                    <label>End:</label>
                    <input type="time" class="time-input end-time-input" value="${endTime}" required />
                    <button class="time-save-btn">Save</button>
                </div>
                <div class="building-status"></div>
            </div>
            <div class="building-body" style="display:none;">
                <div class="building-controls">
                    <input type="text" class="item-search" placeholder="Search proevents..."/>
                </div>
                <ul class="items-list"></ul>
                <div class="building-loader" style="display:none;">Loading...</div>
            </div>
        `;
        this.setupBuildingCardEvents(card); // Attach event listeners
        return card;
    },

    // Sets up event listeners for a single building card
    setupBuildingCardEvents(card) {
        // Get references to elements within the card
        const buildingId = card.dataset.buildingId;
        const itemsList = card.querySelector('.items-list');
        const header = card.querySelector('.building-header');
        const body = card.querySelector('.building-body');
        const toggleBtn = card.querySelector('.toggle-btn');
        const startTimeInput = card.querySelector('.start-time-input');
        const endTimeInput = card.querySelector('.end-time-input');
        const timeSaveBtn = card.querySelector('.time-save-btn');
        // Use the correct selector from your original HTML/CSS
        const ignoreFlagsBtn = card.querySelector('.bulk-disarm'); 
        const itemSearch = card.querySelector('.item-search');

        // Add null checks for all queried elements for robustness
        if (!itemsList || !header || !body || !toggleBtn || !startTimeInput || !endTimeInput || !timeSaveBtn || !ignoreFlagsBtn || !itemSearch) {
             console.error("Failed to find all elements within building card for ID:", buildingId);
             // Optionally disable card interactions or show an error state
             card.style.opacity = '0.5';
             card.style.pointerEvents = 'none';
             return; // Stop setting up events if elements are missing
        }


        // Function to toggle the visibility of the card body (device list)
        const toggleVisibility = async () => {
            const isHidden = body.style.display === 'none';
            if (isHidden) {
                // If expanding, load items *before* showing the body
                try {
                    // Only load if the list hasn't been successfully loaded before or is empty
                    if (!itemsList.dataset.loaded || itemsList.children.length === 0 || itemsList.children[0].classList.contains('muted')) {
                         await this.loadItemsForBuilding(card);
                         itemsList.dataset.loaded = 'true'; // Mark as loaded on success
                    }
                    // Show body and update button only after successful load (or if already loaded)
                    body.style.display = 'block';
                    toggleBtn.textContent = '-';
                } catch (error) {
                     console.error(`Error loading items for building ${buildingId} on toggle:`, error);
                     // Show error message, still expand the body to show it
                     itemsList.innerHTML = '<li class="muted">Error loading proevents.</li>';
                     body.style.display = 'block';
                     toggleBtn.textContent = '-'; // Keep button state consistent
                     itemsList.dataset.loaded = 'false'; // Allow retry on next click
                }
            } else {
                // If collapsing, just hide the body
                body.style.display = 'none';
                toggleBtn.textContent = '+';
            }
        };

        // Click on header (excluding controls) toggles visibility
        header.addEventListener('click', (e) => {
            // Check if the click target is NOT within the controls areas or the button itself
            if (!e.target.closest('.building-time-control') && !e.target.closest('.building-actions') && !e.target.closest('.toggle-btn')) {
                toggleVisibility();
            }
        });
        
        // Also allow clicking the toggle button directly
        toggleBtn.addEventListener('click', (e) => {
             e.stopPropagation(); // Prevent the header click listener from firing too
             toggleVisibility();
        });


        // Save updated start/end times
        timeSaveBtn.addEventListener('click', async (e) => {
            e.stopPropagation(); // Prevent header click event
            const startTime = startTimeInput.value;
            const endTime = endTimeInput.value;

            // Basic time validation
            if (!startTime || !endTime) {
                this.showNotification('Both start and end times are required.', true);
                return;
            }
            // Optional: More complex validation (e.g., start < end) could go here

            try {
                // Send API request to update schedule
                await this.apiRequest(`buildings/${buildingId}/time`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        building_id: parseInt(buildingId), // Required by backend pydantic model for validation
                        start_time: startTime,
                        end_time: endTime
                    })
                });
                this.showNotification('Building schedule updated successfully');
                // Update the local data cache
                 const buildingIndex = this.allBuildings.findIndex(b => b.id === parseInt(buildingId));
                 if (buildingIndex > -1) {
                     this.allBuildings[buildingIndex].start_time = startTime;
                     this.allBuildings[buildingIndex].end_time = endTime;
                 }
            } catch (error) {
                 // Error already handled and shown by apiRequest
                 console.error("Failed to save building schedule:", error);
            }
        });

        // Debounced search for items within the building card
        let searchDebounceTimer;
        itemSearch.addEventListener('input', () => {
            clearTimeout(searchDebounceTimer); // Clear previous timer
            searchDebounceTimer = setTimeout(() => { // Set new timer
                 itemsList.dataset.loaded = 'false'; // Mark list as needing reload on search
                 this.loadItemsForBuilding(card, true, itemSearch.value.trim()); // Reload items
            }, 400); // Wait 400ms after last input
        });

        // Open the ignore flags modal
        ignoreFlagsBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent header click event
            // Pass only buildingId, 'action' parameter isn't used anymore
            this.showIgnoreSelectionModal(buildingId); 
        });
    },

    // 7. Item/Device Logic
    
    // Loads devices for a specific building card
    async loadItemsForBuilding(card, reset = false, search = '') {
        const buildingId = card.dataset.buildingId;
        const itemsList = card.querySelector('.items-list');
        const loader = card.querySelector('.building-loader');

        // Safety checks for elements
        if (!itemsList || !loader) {
             console.error("Missing itemsList or loader element in card for building:", buildingId);
             throw new Error("Card structure incomplete."); // Throw to prevent UI issues
        }

        if (reset) itemsList.innerHTML = ''; // Clear list if resetting (e.g., for search)
        loader.style.display = 'block'; // Show loading indicator
        itemsList.style.display = 'none'; // Hide list while loading for smoother UI

        try {
            // Fetch devices for the building, using BUILD_PAGE_SIZE for list view
            const items = await this.apiRequest(`devices?building=${buildingId}&limit=${this.BUILD_PAGE_SIZE}&search=${encodeURIComponent(search)}`);
            
            itemsList.innerHTML = ''; // Clear previous content (loader/error messages)

            if (items.length === 0) {
                 // Show appropriate message if no items found
                 itemsList.innerHTML = `<li class="muted">${search ? 'No proevents found matching search.' : 'No proevents found.'}</li>`;
            } else {
                 items.forEach(item => {
                     const itemElement = this.createItem(item);
                     // Append only if createItem returned a valid element
                     if (itemElement) {
                         itemsList.appendChild(itemElement);
                     }
                 });
            }
        } catch(error) {
             console.error(`Error loading items for building ${buildingId}:`, error);
             itemsList.innerHTML = '<li class="muted">Error loading proevents. Please try again.</li>';
             // Re-throw the error so the caller (like toggleVisibility) knows loading failed
             throw error; 
        }
        finally {
            // Always hide loader and show the list container (even if it shows an error message)
            loader.style.display = 'none';
            itemsList.style.display = ''; // Use default display (block/list-item)
            this.updateBuildingStatus(card); // Update the overall status indicator
        }
    },

    // Creates the HTML element for a single device item
    createItem(item) {
        // Basic validation of item data
        if (!item || typeof item.id === 'undefined' || typeof item.name === 'undefined') {
             console.warn("Received invalid item data:", item);
             return null; // Return null if data is bad, preventing element creation
        }

        const li = document.createElement('li');
        const state = (item.state || 'unknown').toLowerCase();
        const isIgnored = item.is_ignored; // Get ignored status from API response

        li.className = 'device-item'; // Use 'device-item' class (matches your CSS)
        li.dataset.itemId = item.id; // Store item ID
        li.dataset.state = state; // Store current state

        // Determine state color and class
        const isArmed = state === 'armed';
        const stateColor = isArmed ? '#ef4444' : '#22c55e'; // Red (Armed) or Green (Disarmed)
        const stateClass = isArmed ? 'status-all-armed' : 'state-unknown'; // Use existing CSS classes

        // Add visual indicator if the item is ignored
        const ignoredIndicator = isIgnored ? '<span style="color: #9ca3af; font-style: italic;"> (Ignored)</span>' : '';

        // *** THIS HTML IS NOW CORRECT ***
        li.innerHTML = `
            <span class="device-state-indicator ${stateClass}" style="background-color: ${stateColor};"></span>
            <div class="device-name">
                ${this.escapeHtml(item.name)} (ID: ${item.id})${ignoredIndicator}
            </div>
        `;
        return li;
    },

    // Updates the "All Armed", "Partially Armed", etc. status text in the card header
    updateBuildingStatus(card) {
        const items = card.querySelectorAll('.device-item'); // Find all device items
        const statusEl = card.querySelector('.building-status'); // Find the status display element

        if (!statusEl) return; // Exit if status element not found

        // Check if the list contains only the "muted" message (error or no items)
        const firstItemIsMuted = items.length === 1 && items[0].classList.contains('muted');

        if (items.length === 0 || firstItemIsMuted) {
            statusEl.textContent = 'No ProEvents';
            statusEl.className = 'building-status status-none-armed'; // Use gray style
            return;
        }

        // Count armed devices
        const armedCount = Array.from(items).filter(d => d.dataset.state === 'armed').length;

        // Update status text and class based on counts
        if (armedCount === items.length) {
            statusEl.textContent = 'All Armed';
            statusEl.className = 'building-status status-all-armed'; // Green
        } else if (armedCount > 0) {
            statusEl.textContent = 'Partially Armed';
            statusEl.className = 'building-status status-partial-armed'; // Orange
        } else {
            statusEl.textContent = 'All Disarmed';
            statusEl.className = 'building-status status-none-armed'; // Gray
        }
    },

    // 8. Modal Logic (Ignore Flags)
    
    async showIgnoreSelectionModal(buildingId) {
        // Ensure modal elements exist
        if (!this.elements.ignoreModal || !this.elements.modalTitle || !this.elements.modalItemList ||
            !this.elements.modalConfirmBtn || !this.elements.modalCancelBtn || !this.elements.closeButton ||
            !this.elements.modalSearch || !this.elements.modalSelectAllBtn) {
            console.error("Modal elements not found!");
            this.showNotification("Error: Could not open ignore settings.", true);
            return;
        }

        const { 
            modalTitle, modalItemList, ignoreModal, modalSearch, 
            modalSelectAllBtn, modalConfirmBtn, modalCancelBtn, closeButton 
        } = this.elements;

        // --- Prepare Modal ---
        modalTitle.textContent = `Select ProEvents to Ignore on Disarm`;
        modalItemList.innerHTML = '<div class="loader">Loading...</div>'; // Show loading state
        ignoreModal.style.display = 'block'; // Make modal visible
        
        modalSearch.value = ''; // Clear previous search
        modalSelectAllBtn.textContent = 'Select All'; // Reset button text
        modalConfirmBtn.disabled = true; // Disable confirm until items load
        modalCancelBtn.disabled = false; // Ensure cancel is enabled

        let allModalItems = []; // Array to hold fetched items for filtering

        // --- Clean up previous modal listeners to prevent duplicates ---
        // Store handler references directly on the elements to easily remove them
        const oldConfirmHandler = modalConfirmBtn.__currentClickHandler__; 
        if (oldConfirmHandler) modalConfirmBtn.removeEventListener('click', oldConfirmHandler);
        const oldCancelHandler = modalCancelBtn.__currentClickHandler__;
        if (oldCancelHandler) modalCancelBtn.removeEventListener('click', oldCancelHandler);
        const oldCloseHandler = closeButton.__currentClickHandler__;
        if (oldCloseHandler) closeButton.removeEventListener('click', oldCloseHandler);
        modalSearch.oninput = null; // Clear inline handler
        modalSelectAllBtn.onclick = null; // Clear inline handler


        // --- Load Items into Modal ---
        try {
            // Fetch ALL proevents for this building (limit 10000)
            allModalItems = await this.apiRequest(`devices?building=${buildingId}&limit=10000`);
            modalItemList.innerHTML = ''; // Clear loader/previous content

            if (allModalItems.length === 0) {
                 modalItemList.innerHTML = '<p class="muted">No proevents found in this building.</p>';
                 // Keep confirm disabled
            } else {
                 allModalItems.forEach(item => {
                     // Basic validation before creating element
                     if (item && typeof item.id !== 'undefined' && typeof item.name !== 'undefined') {
                         const div = document.createElement('div');
                         div.className = 'device-item'; // Use same class as main list for consistency
                         // Store necessary data on the element for saving later
                         div.dataset.itemId = item.id;
                         div.dataset.buildingFrk = buildingId; 
                         div.dataset.devicePrk = item.id; // Assuming device_prk is the same as item id

                         div.innerHTML = `
                             <div class="device-name">${this.escapeHtml(item.name)} (ID: ${item.id})</div>
                             <label class="ignore-alarm-label">
                                 <input type="checkbox" class="ignore-item-checkbox" ${item.is_ignored ? 'checked' : ''} />
                                 Ignore on Disarm
                             </label>
                         `;
                         modalItemList.appendChild(div);
                     } else {
                          console.warn("Skipping invalid item data in modal:", item);
                     }
                 });
                 modalConfirmBtn.disabled = false; // Enable confirm button now that items are loaded
            }
        } catch (error) {
             console.error("Error loading items into ignore modal:", error);
             modalItemList.innerHTML = '<p class="muted">Error loading proevents. Please try again.</p>';
             // Keep confirm disabled on error
        }
        
        // --- Setup Modal Event Listeners ---
        
        // Live search/filter within the modal
        modalSearch.oninput = () => {
            const query = modalSearch.value.toLowerCase();
            const modalItems = modalItemList.querySelectorAll('.device-item');
            let allVisibleChecked = true;
            let visibleCount = 0;
            
            modalItems.forEach(item => {
                const nameElement = item.querySelector('.device-name');
                // Basic check to prevent errors if item structure is unexpected
                if (!nameElement) return; 
                
                const name = nameElement.textContent.toLowerCase();
                const isVisible = name.includes(query);
                item.style.display = isVisible ? 'flex' : 'none'; // Show/hide based on match

                 // Update logic for Select/Deselect All button based on *visible* items
                 if (isVisible) {
                     visibleCount++;
                     const checkbox = item.querySelector('.ignore-item-checkbox');
                     if (checkbox && !checkbox.checked) {
                         allVisibleChecked = false;
                     }
                 }
            });
            // Set button text based on whether all *visible* items are checked
             modalSelectAllBtn.textContent = (allVisibleChecked && visibleCount > 0) ? 'Deselect All' : 'Select All';
        };
        
        // Select/Deselect All button functionality
        modalSelectAllBtn.onclick = () => {
            const isSelectAll = modalSelectAllBtn.textContent === 'Select All';
            const modalItems = modalItemList.querySelectorAll('.device-item');
            modalItems.forEach(item => {
                // Only affect items currently visible (matching search filter)
                if (item.style.display !== 'none') { 
                    const checkbox = item.querySelector('.ignore-item-checkbox');
                    if (checkbox) checkbox.checked = isSelectAll; // Set checked state
                }
            });
            // Toggle button text
            modalSelectAllBtn.textContent = isSelectAll ? 'Deselect All' : 'Select All';
        };

        // Define the confirm action handler separately to allow removal
        const confirmHandler = async () => {
            const itemsToUpdate = [];
            const itemElements = modalItemList.querySelectorAll('.device-item');
            
            itemElements.forEach(itemEl => {
                const checkbox = itemEl.querySelector('.ignore-item-checkbox');
                // Retrieve data stored on the element, ensuring they are numbers
                const itemId = parseInt(itemEl.dataset.itemId, 10);
                const buildingFrk = parseInt(itemEl.dataset.buildingFrk, 10);
                const devicePrk = parseInt(itemEl.dataset.devicePrk, 10);

                 // Validate data before adding to the update list
                 if (!isNaN(itemId) && !isNaN(buildingFrk) && !isNaN(devicePrk) && checkbox) {
                     itemsToUpdate.push({
                         item_id: itemId,
                         building_frk: buildingFrk,
                         device_prk: devicePrk, 
                         ignore: checkbox.checked // Send current checked state
                     });
                 } else {
                      console.warn("Skipping item with invalid data attributes during save:", itemEl);
                 }
            });

            // If no items were loaded initially, itemsToUpdate might be empty.
            // Check against allModalItems length to see if items *should* have been there.
            if (itemsToUpdate.length === 0 && allModalItems.length > 0) {
                 this.showNotification("No changes detected or no items to update.", false); // Use non-error message
                 closeModal(); // Close silently if no changes made
                 return;
            } else if (allModalItems.length === 0 && itemsToUpdate.length === 0) {
                 // If no items were loaded at all, just close
                 closeModal();
                 return;
            }


            // Disable buttons during API calls
            modalConfirmBtn.disabled = true;
            modalCancelBtn.disabled = true; 
            
            try {
                // 1. Send bulk update request to save ignore statuses
                await this.apiRequest('proevents/ignore/bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items: itemsToUpdate })
                });
                this.showNotification('Ignore settings saved. Applying changes...');
                
                // 2. Trigger backend re-evaluation for the affected building
                await this.apiRequest(`buildings/${buildingId}/reevaluate`, {
                    method: 'POST'
                });
                this.showNotification('Changes applied successfully.');

                // 3. Refresh the main building card view to reflect changes
                const card = document.querySelector(`.building-card[data-building-id='${buildingId}']`);
                if (card) {
                    const itemSearchInput = card.querySelector('.item-search');
                    const cardItemsList = card.querySelector('.items-list');
                    // Mark list as needing refresh
                    if (cardItemsList) cardItemsList.dataset.loaded = 'false'; 
                    
                    // Only reload if the card body is currently visible
                    const cardBody = card.querySelector('.building-body');
                    if (cardBody && cardBody.style.display !== 'none') {
                         await this.loadItemsForBuilding(card, true, itemSearchInput ? itemSearchInput.value.trim() : '');
                         if (cardItemsList) cardItemsList.dataset.loaded = 'true'; // Mark loaded after refresh
                    } else {
                         // If collapsed, clear list content so it reloads on next expand
                         if(cardItemsList) cardItemsList.innerHTML = ''; 
                    }
                }
                
                closeModal(); // Close modal only on successful completion

            } catch (error) {
                console.error("Failed to save ignore settings or re-evaluate:", error);
                // apiRequest should have shown an error notification
                // Re-enable buttons to allow retry
                modalConfirmBtn.disabled = false;
                modalCancelBtn.disabled = false;
            }
            // 'finally' block removed as closeModal should only happen on success
        };
        
        // Function to close the modal and clean up listeners
        const closeModal = () => {
             // Check if modal exists before trying to hide/modify
             if (!ignoreModal) return; 
            
            ignoreModal.style.display = 'none'; // Hide the modal

            // --- Remove event listeners to prevent memory leaks/duplicates ---
            modalSearch.oninput = null;
            modalSelectAllBtn.onclick = null;
            
            // Remove specific handlers using stored references
            const confirmHandlerToRemove = modalConfirmBtn.__currentClickHandler__;
            if (confirmHandlerToRemove) {
                 modalConfirmBtn.removeEventListener('click', confirmHandlerToRemove);
                 modalConfirmBtn.__currentClickHandler__ = null; // Clear reference
            }
            modalConfirmBtn.disabled = false; // Re-enable confirm button

            const cancelHandlerToRemove = modalCancelBtn.__currentClickHandler__;
            if (cancelHandlerToRemove) {
                modalCancelBtn.removeEventListener('click', cancelHandlerToRemove);
                modalCancelBtn.__currentClickHandler__ = null;
            }
             modalCancelBtn.disabled = false; // Re-enable cancel button

            const closeHandlerToRemove = closeButton.__currentClickHandler__;
             if (closeHandlerToRemove) {
                closeButton.removeEventListener('click', closeHandlerToRemove);
                closeButton.__currentClickHandler__ = null;
            }

            // Clear modal content
            if (modalItemList) modalItemList.innerHTML = '';
        };

        // Attach listeners using addEventListener and store references
        modalConfirmBtn.__currentClickHandler__ = confirmHandler; 
        modalConfirmBtn.addEventListener('click', confirmHandler);
        
        modalCancelBtn.__currentClickHandler__ = closeModal;
        modalCancelBtn.addEventListener('click', closeModal);
        
        closeButton.__currentClickHandler__ = closeModal;
        closeButton.addEventListener('click', closeModal);
    }
};