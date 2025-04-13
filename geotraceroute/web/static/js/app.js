// Global variables
let map, markers = [], routePolylines = [], currentTraceroute = null, apiKey = null;
let showReputationScores = localStorage.getItem('showReputationScores') !== 'false';
let useDarkTheme = false;
let stopRequested = false;
let clientLocation = null;
let hops = [];
let latencies = [];
let progressInterval = null;
let hopCount = 0;
let hasReceivedValidHop = false;

// Initialize map when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM fully loaded");

    // Initialize element references
    initElementReferences();

    // Load API key from localStorage if exists
    apiKey = localStorage.getItem('ipinfoApiKey') || '';
    if (apiKeyInput) {
        apiKeyInput.value = apiKey;
    }

    // Load reputation score setting based on API key
    // Only enable reputation scores if API key exists
    const hasApiKey = apiKey && apiKey.trim().length > 0;
    showReputationScores = hasApiKey ? (localStorage.getItem('showReputationScores') === 'true') : false;

    if (showReputationScoreToggle) {
        showReputationScoreToggle.checked = showReputationScores;
        showReputationScoreToggle.disabled = !hasApiKey;
    }

    // Initialize map with a world view
    initMap();

    // Set up event listeners
    setupEventListeners();

    // Responsive layout adjustments
    window.addEventListener('resize', adjustLayout);
    adjustLayout();

    // Initialize geolocation
    initGeolocation();
});

// Initialize element references
function initElementReferences() {
    window.targetInput = document.getElementById('target');
    window.startBtn = document.getElementById('startBtn');
    window.stopBtn = document.getElementById('stopBtn');
    window.clearBtn = document.getElementById('clearBtn');
    window.settingsBtn = document.getElementById('settingsBtn');
    window.apiKeyInput = document.getElementById('apiKeyInput');
    window.saveApiKeyBtn = document.getElementById('saveApiKeyBtn');
    window.showReputationScoreToggle = document.getElementById('showReputationScore');
    window.resultsContainer = document.getElementById('resultsContainer');
    window.resultList = document.getElementById('resultList');
    window.progressBar = document.getElementById('progressBar')?.querySelector('.progress-bar') || null;
    window.progressBarContainer = document.getElementById('progressBar');
    window.statsContainer = document.getElementById('statsContainer');
    window.totalHops = document.getElementById('totalHops');
    window.averageLatency = document.getElementById('averageLatency');
    window.spinner = document.getElementById('spinner');
}

// Set up event listeners
function setupEventListeners() {
    // Only add event listeners if elements exist
    if (startBtn) startBtn.addEventListener('click', startTraceroute);
    if (stopBtn) stopBtn.addEventListener('click', stopTraceroute);
    if (clearBtn) clearBtn.addEventListener('click', clearResults);
    if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
    if (saveApiKeyBtn) saveApiKeyBtn.addEventListener('click', saveApiKey);

    if (showReputationScoreToggle) {
        showReputationScoreToggle.addEventListener('change', function () {
            showReputationScores = this.checked;
            localStorage.setItem('showReputationScores', showReputationScores);
        });
    }

    // Add input event to API key input to toggle reputation score availability
    if (apiKeyInput) {
        apiKeyInput.addEventListener('input', function () {
            const hasApiKey = this.value.trim().length > 0;
            if (showReputationScoreToggle) {
                showReputationScoreToggle.disabled = !hasApiKey;
                if (!hasApiKey) {
                    showReputationScoreToggle.checked = false;
                    showReputationScores = false;
                }
            }
        });
    }
}

// Initialize the map
function initMap() {
    console.log("Initializing map");
    try {
        // Create a new map centered on a world view
        map = L.map('map', {
            center: [20, 0],
            zoom: 2,
            minZoom: 2,
            maxZoom: 18,
            zoomControl: false,
            attributionControl: true,
            inertia: true
        });

        console.log("Map object created:", map);

        // Add the base map tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // Add zoom control to bottom right
        L.control.zoom({
            position: 'bottomright'
        }).addTo(map);

        console.log("Map initialization complete");

        // Force a resize to ensure map displays correctly
        setTimeout(() => {
            console.log("Forcing map resize");
            map.invalidateSize(true);
            const mapContainer = document.getElementById('map');
            if (mapContainer) {
                console.log("Map dimensions after resize:",
                    "Width:", mapContainer.offsetWidth,
                    "Height:", mapContainer.offsetHeight);
            }
        }, 500);

        // Add resize event listener to ensure map always fits
        window.addEventListener('resize', function () {
            if (map) {
                setTimeout(() => map.invalidateSize(true), 200);
            }
        });
    } catch (error) {
        console.error("Error initializing map:", error);
    }
}

// Adjust layout based on window size
function adjustLayout() {
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    const sidebar = document.getElementById('sidebar');
    const mapContainer = document.getElementById('mapContainer');

    if (sidebar && mapContainer) {
        if (windowWidth < 768) {
            sidebar.style.width = '100%';
            sidebar.style.height = '40%';
            mapContainer.style.width = '100%';
            mapContainer.style.height = '60%';
        } else {
            sidebar.style.width = '25%';
            sidebar.style.height = '100%';
            mapContainer.style.width = '75%';
            mapContainer.style.height = '100%';
        }
    }

    if (map) {
        // Force map to refresh its size
        map.invalidateSize(true);
    }
}

// Open settings modal
function openSettings() {
    const modal = new bootstrap.Modal(document.getElementById('apiKeyModal'));
    modal.show();
}

// Save API key
function saveApiKey() {
    if (!apiKeyInput) return;

    const newApiKey = apiKeyInput.value.trim();
    apiKey = newApiKey;
    localStorage.setItem('ipinfoApiKey', apiKey);

    // Handle reputation score setting based on API key
    const hasApiKey = apiKey.length > 0;

    if (showReputationScoreToggle) {
        // Only allow reputation scores if we have an API key
        showReputationScoreToggle.disabled = !hasApiKey;

        // If no API key, force reputation scores off
        if (!hasApiKey) {
            showReputationScoreToggle.checked = false;
            showReputationScores = false;
            localStorage.setItem('showReputationScores', 'false');
        } else {
            // Otherwise use the toggle's value
            showReputationScores = showReputationScoreToggle.checked;
            localStorage.setItem('showReputationScores', showReputationScores);
        }
    }

    const modal = bootstrap.Modal.getInstance(document.getElementById('apiKeyModal'));
    if (modal) modal.hide();

    // Show success toast
    const toastEl = document.getElementById('apiKeyToast');
    if (toastEl) {
        const toast = new bootstrap.Toast(toastEl);
        toast.show();
    }
}

// Start the traceroute process
async function startTraceroute() {
    const target = document.getElementById('target').value.trim();
    if (!target) {
        alert('Please enter a target IP or hostname');
        return;
    }

    clearResults();

    // Show loading state
    if (startBtn) startBtn.disabled = true;
    if (stopBtn) {
        stopBtn.disabled = false;
        stopBtn.classList.remove('d-none');
    }
    if (spinner) spinner.style.display = 'inline-block';

    // Show progress bar
    if (progressBarContainer) progressBarContainer.style.display = 'block';
    if (progressBar) progressBar.style.width = '0%';

    // Show containers
    if (resultsContainer) resultsContainer.style.display = 'block';
    if (statsContainer) statsContainer.style.display = 'block';

    // Reset state
    stopRequested = false;
    markers = [];
    routePolylines = [];
    hops = [];
    latencies = [];
    hasReceivedValidHop = false;

    // Add initial message
    addResultLine(`Tracing route to ${target}...`);

    let apiKey = localStorage.getItem('ipinfo_api_key') || '';

    try {
        // Build URL, including client location information
        let url = `/api/traceroute/start`;
        const params = new URLSearchParams();

        // Add target and API key
        params.append('target', target);

        if (apiKey) {
            params.append('api_key', apiKey);
        }

        // Add client location information (if available)
        if (clientLocation) {
            params.append('client_lat', clientLocation.latitude);
            params.append('client_lon', clientLocation.longitude);

            if (clientLocation.city) {
                params.append('client_city', clientLocation.city);
            }

            if (clientLocation.country) {
                params.append('client_country', clientLocation.country);
            }
        }

        const requestBody = {
            target: target,
            max_hops: 30,
            include_reputation: showReputationScores
        };

        console.log("Sending traceroute request:", {
            url: url,
            params: Object.fromEntries(params.entries()),
            body: requestBody
        });

        // Send POST request
        const response = await fetch(`${url}?${params.toString()}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }

        // Process the SSE stream
        const success = await processStream(response);

        // If no valid data was received, show error
        if (!success) {
            // Check if there's hops data, if so, don't show error message
            if (hops.length > 0) {
                addResultLine("Tracking route completed.", "info");
            } else {
                addResultLine("Traceroute completed, but no data was received. The server may be experiencing issues or the target may not be reachable.", "error");
            }
        }

    } catch (error) {
        console.error('Error starting traceroute:', error);
        addResultLine(`Error: ${error.message}`, 'error');
    } finally {
        // Reset UI state
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) {
            stopBtn.disabled = true;
            stopBtn.classList.add('d-none');
        }
        if (spinner) spinner.style.display = 'none';
        clearInterval(progressInterval);

        console.log("Traceroute completed");
    }
}

// Log debug message (only to console, not to UI)
function logDebugMessage(msg) {
    // Only output to console, not to UI
    console.log('[Debug]', msg);
}

// JSON parsing helper function - attempt to fix malformed JSON
function tryFixAndParseJSON(jsonStr) {
    try {
        return JSON.parse(jsonStr);
    } catch (e) {
        console.warn('Failed to parse JSON, attempting to fix...', jsonStr);

        // Try to fix some common JSON issues
        try {
            // Replace single quotes with double quotes
            const fixed = jsonStr.replace(/'/g, '"');
            return JSON.parse(fixed);
        } catch (e2) {
            console.error('Failed to parse JSON after attempted fix', e2);
            return null;
        }
    }
}

// Process the SSE stream
async function processStream(response) {
    try {
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        hasReceivedValidHop = false;

        // Start progress update interval
        let hopCount = 0;
        let lastLocation = null;

        // Update progress every 500ms
        progressInterval = setInterval(() => {
            if (stopRequested) {
                clearInterval(progressInterval);
                stopTraceroute();
                return;
            }

            // Increment progress slightly to show activity
            if (progressBar) {
                const currentWidth = parseFloat(progressBar.style.width) || 0;
                if (currentWidth < 90) {  // Cap at 90% until complete
                    progressBar.style.width = `${Math.min(90, currentWidth + 1)}%`;
                }
            }
        }, 500);

        while (true) {
            if (stopRequested) {
                console.log("Stop requested, breaking stream processing loop");
                break;
            }

            const { done, value } = await reader.read();
            if (done) {
                console.log("Stream complete");
                // Final update to 100%
                if (progressBar) {
                    progressBar.style.width = "100%";
                    // Remove animation effect and blue style
                    progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-primary');
                    // Add green style
                    progressBar.classList.add('bg-success');
                }
                break;
            }

            // Decode the chunk and add it to our buffer
            const chunk = decoder.decode(value, { stream: true });
            console.log("Received chunk:", chunk);
            if (chunk.includes('data:')) {
                logDebugMessage(`Received data chunk`);
            }
            buffer += chunk;

            // Process complete events from the buffer (SSE format)
            let eventsToProcess = buffer.split('\n\n');
            buffer = eventsToProcess.pop() || ''; // Keep the last incomplete event in the buffer

            if (eventsToProcess.length > 0) {
                logDebugMessage(`Processing ${eventsToProcess.length} events`);
            }

            for (const event of eventsToProcess) {
                if (event.startsWith('data: ')) {
                    const jsonData = event.substring(6).trim();
                    if (!jsonData) continue;

                    try {
                        console.log("Processing event data:", jsonData);
                        const hop = tryFixAndParseJSON(jsonData);

                        // Check if this is the completion message
                        if (hop && (hop.status === 'completed' || hop.done === true)) {
                            logDebugMessage('Traceroute completed');
                            continue;
                        }

                        // Make sure hop has necessary fields
                        if (hop && hop.hop_number !== undefined) {
                            hasReceivedValidHop = true; // Mark valid data received
                            logDebugMessage(`Processing hop #${hop.hop_number}: IP=${hop.ip || '*'}`);

                            // Process the hop and update variables
                            const result = processSingleHop(hop, hops, latencies);
                            hopCount = result.hopCount;
                            lastLocation = result.lastLocation;

                            // Update progress (assuming max 30 hops)
                            const progress = Math.min(100, (hopCount / 30) * 100);
                            if (progressBar) progressBar.style.width = `${progress}%`;

                            // Update stats
                            updateStats(hopCount, latencies);
                        } else if (hop) {
                            logDebugMessage(`Received invalid hop data: ${JSON.stringify(hop)}`);
                            console.warn('Received hop data without hop_number:', hop);
                        } else {
                            logDebugMessage(`Failed to parse JSON`);
                        }
                    } catch (e) {
                        console.error('Error parsing JSON:', e, 'Data:', jsonData);
                        logDebugMessage(`Processing event error: ${e.message}`);
                    }
                }
            }
        }

        // Update the hop count in the results header
        const resultsHeader = document.querySelector('.d-flex .badge');
        if (resultsHeader) {
            resultsHeader.textContent = `${hops.length} hops`;
            resultsHeader.classList.remove('bg-primary');
            resultsHeader.classList.add('bg-success');
        }

        // Ensure the progress bar shows completion and turns green
        if (progressBar) {
            progressBar.style.width = "100%";
            progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-primary');
            progressBar.classList.add('bg-success');
        }

    } catch (e) {
        console.error("Stream processing error:", e);
        logDebugMessage(`Stream processing error: ${e.message}`);
    }

    // Ensure hopCount is defined and has a safe default
    // This helps avoid the "hopCount is not defined" error
    hopCount = hopCount || 0;

    // Final stats update
    updateStats(hopCount, latencies);

    // Check if we've processed any hop data
    logDebugMessage(`Stream processing complete, valid hop data received: ${hasReceivedValidHop ? "yes" : "no"}`);

    // If there's data in the hops array, consider it a success even if hasReceivedValidHop is false
    if (!hasReceivedValidHop && hops.length > 0) {
        logDebugMessage(`Although marked as no valid hops received, the hops array contains ${hops.length} entries, considering as success`);
        hasReceivedValidHop = true;
    }

    // Final update of the hop count in the results header
    const resultsHeader = document.querySelector('.d-flex .badge');
    if (resultsHeader) {
        resultsHeader.textContent = `${hops.length} hops`;
        if (hops.length > 0) {
            resultsHeader.classList.remove('bg-primary');
            resultsHeader.classList.add('bg-success');
        }
    }

    return hasReceivedValidHop;
}

// Process a single hop and update UI
function processSingleHop(hop, hops, latencies) {
    console.log("Processing hop:", hop);

    if (!hop) {
        console.error("Empty hop data received");
        return { hopCount: hops.length, lastLocation: null };
    }

    // Extract data with safety checks
    const hopNumber = hop.hop_number || 0;
    const ipAddress = hop.ip || '*';
    const hostname = hop.hostname || '';
    const rttArr = Array.isArray(hop.rtt_ms) ? hop.rtt_ms : [];
    const avgRtt = rttArr.length > 0 ? rttArr.reduce((a, b) => a + b, 0) / rttArr.length : null;

    const location = {
        latitude: hop.latitude || null,
        longitude: hop.longitude || null,
        city: hop.city || null,
        country: hop.country || null
    };

    const organization = hop.organization || null;
    const reputationScore = typeof hop.reputation_score === 'number' ? hop.reputation_score : null;

    console.log(`Hop ${hopNumber}: IP=${ipAddress}, Location: lat=${location.latitude}, lng=${location.longitude}`);

    // Add to latencies array for average calculation if not a timeout
    if (avgRtt !== null) {
        latencies.push(avgRtt);
    }

    // Create and add marker if location data exists
    if (location.latitude && location.longitude) {
        console.log(`Adding marker for hop ${hopNumber} at ${location.latitude},${location.longitude}`);
        addMarker(hopNumber, ipAddress, hostname, location, avgRtt, organization, reputationScore);
    } else {
        console.log(`No location data for hop ${hopNumber}`);
    }

    // Add result to list
    addResultLine(formatHopResult(hop), hop.error ? 'error' : 'success');

    // Add to hops array
    hops.push(hop);

    // Return updated information
    return { hopCount: hops.length, lastLocation: location };
}

// Format hop result for display
function formatHopResult(hop) {
    if (!hop) return "Error: Invalid hop data";

    // If only a basic invalid hop data situation
    if (typeof hop === 'string') {
        return `Raw data: ${hop}`;
    }

    // Error message handling
    if (hop.error) {
        return `Error: ${hop.error}`;
    }

    // Completion/done message handling
    if (hop.status === 'completed' || hop.done === true) {
        return "Traceroute completed.";
    }

    const number = hop.hop_number || 0;
    const ip = hop.ip || '*';
    const host = hop.hostname || '';

    // Safely handle rtt_ms
    let rttStr = '*';
    if (Array.isArray(hop.rtt_ms) && hop.rtt_ms.length > 0) {
        const avg = hop.rtt_ms.reduce((a, b) => a + b, 0) / hop.rtt_ms.length;
        rttStr = avg.toFixed(2);
    }

    // Location info
    let locationStr = '';
    if (hop.city && hop.country) {
        locationStr = `${hop.city}, ${hop.country}`;
    } else if (hop.country) {
        locationStr = hop.country;
    }

    // Organization info
    let orgStr = '';
    if (hop.organization) {
        orgStr = hop.organization;
    }

    // Reputation score
    let reputationStr = '';
    if (showReputationScores && typeof hop.reputation_score === 'number') {
        reputationStr = `Safety: ${(hop.reputation_score * 100).toFixed(0)}/100`;
    }

    // Use template string to create more beautiful result
    let result = `<span class="hop-number">${number}.</span> `;

    // IP address part, using fixed width font
    if (ip === '*') {
        result += `<span class="hop-timeout">* * *</span>`;
    } else {
        result += `<span class="hop-ip">${ip}</span>`;
        if (host) result += ` <span class="hop-host">(${host})</span>`;
    }

    // RTT value part
    if (rttStr !== '*') {
        result += ` <span class="hop-rtt">${rttStr} ms</span>`;
    }

    // Location information and organization part
    if (locationStr) {
        result += ` <span class="hop-location"><i class="fas fa-map-marker-alt"></i> ${locationStr}</span>`;
    }

    if (orgStr) {
        result += ` <span class="hop-org"><i class="fas fa-building"></i> ${orgStr}</span>`;
    }

    // Reputation score part
    if (reputationStr) {
        result += ` <span class="hop-reputation">${reputationStr}</span>`;
    }

    // If empty result, at least show hop number
    if (result === `<span class="hop-number">${number}.</span> <span class="hop-timeout">* * *</span>`) {
        result = `<span class="hop-number">${number}.</span> <span class="hop-timeout">No response</span>`;
    }

    return result;
}

// Add a marker to the map
function addMarker(hopNumber, ip, hostname, location, latency, organization, reputationScore) {
    if (!map) return;

    const lat = location.latitude;
    const lng = location.longitude;

    if (!lat || !lng) return;

    // Create custom icon based on hop number
    const markerIcon = createMarkerIcon(hopNumber);

    // Create marker
    const marker = L.marker([lat, lng], { icon: markerIcon }).addTo(map);

    // Create popup content
    let popupContent = `<div class="marker-popup">`;
    popupContent += `<h6>Hop ${hopNumber}: ${ip}</h6>`;
    if (hostname) popupContent += `<p>Hostname: ${hostname}</p>`;
    if (latency) popupContent += `<p>Latency: ${latency.toFixed(2)}ms</p>`;
    if (location) {
        if (location.city) popupContent += `<p>City: ${location.city}</p>`;
        if (location.country) popupContent += `<p>Country: ${location.country}</p>`;
    }
    if (organization) popupContent += `<p>Organization: ${organization}</p>`;

    // Add reputation information if available and enabled
    if (showReputationScores && reputationScore !== undefined) {
        popupContent += `<p>Safety Score: ${(reputationScore * 100).toFixed(0)}/100</p>`;
    }

    popupContent += `</div>`;

    marker.bindPopup(popupContent);
    markers.push(marker);

    // Add route polyline if there are at least 2 markers
    if (markers.length > 1) {
        const prevMarker = markers[markers.length - 2];
        const prevLatLng = prevMarker.getLatLng();
        const currentLatLng = marker.getLatLng();

        const polyline = L.polyline([prevLatLng, currentLatLng], {
            color: 'red',
            weight: 2,
            opacity: 0.7,
            dashArray: '5, 10'
        }).addTo(map);

        routePolylines.push(polyline);
    }

    // Fit map to all markers if there are at least 2
    if (markers.length >= 2) {
        const markerBounds = L.latLngBounds(markers.map(m => m.getLatLng()));
        map.fitBounds(markerBounds, { padding: [50, 50] });
    } else if (markers.length === 1) {
        // If only one marker, center on it
        map.setView([lat, lng], 10);
    }
}

// Create a marker icon based on hop number
function createMarkerIcon(hopNumber) {
    return L.divIcon({
        className: 'custom-marker',
        html: `<div class="marker-icon">${hopNumber}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    });
}

// Calculate distance between two points using Haversine formula
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Radius of the Earth in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c; // Distance in km
    return distance;
}

// Update statistics
function updateStats(hopCount, latencies) {
    // Ensure hopCount has a safe default
    hopCount = hopCount || 0;

    if (totalHops) totalHops.textContent = `${hopCount} hops`;

    if (latencies && latencies.length > 0) {
        const total = latencies.reduce((sum, latency) => sum + latency, 0);
        const avg = total / latencies.length;
        if (averageLatency) averageLatency.textContent = `${avg.toFixed(2)} ms`;
    } else {
        if (averageLatency) averageLatency.textContent = '0 ms';
    }
}

// Add a single result line to the results container
function addResultLine(text, type = 'info') {
    if (!resultList) return;

    // Ensure results container is displayed
    if (resultsContainer) resultsContainer.style.display = 'block';

    const resultItem = document.createElement('div');
    resultItem.className = `result-item ${type}`;

    // Use innerHTML to support formatted HTML content
    resultItem.innerHTML = text;

    resultList.appendChild(resultItem);
    resultList.scrollTop = resultList.scrollHeight;
}

// Stop the current traceroute
async function stopTraceroute() {
    stopRequested = true;

    try {
        // Call the stop endpoint
        const response = await fetch('/api/traceroute/stop', {
            method: 'POST'
        });
        if (!response.ok) {
            console.error('Failed to stop traceroute:', await response.text());
        }
    } catch (error) {
        console.error('Error stopping traceroute:', error);
    }

    // Re-enable start button
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) {
        stopBtn.disabled = true;
        stopBtn.classList.add('d-none');
    }
}

// Clear all results and reset the UI
function clearResults() {
    // Clear result list
    if (resultList) resultList.innerHTML = '';

    // Clear map markers and polylines
    if (map) {
        markers.forEach(marker => map.removeLayer(marker));
        routePolylines.forEach(line => map.removeLayer(line));
    }
    markers = [];
    routePolylines = [];
    hops = [];
    latencies = [];

    // Reset stats
    if (totalHops) totalHops.textContent = '0 hops';
    if (averageLatency) averageLatency.textContent = '0 ms';

    // Reset results header
    const resultsHeader = document.querySelector('.d-flex .badge');
    if (resultsHeader) {
        resultsHeader.textContent = '0 hops';
        resultsHeader.classList.remove('bg-success');
        resultsHeader.classList.add('bg-primary');
    }

    // Reset progress bar style and hide it
    if (progressBarContainer) progressBarContainer.style.display = 'none';
    if (progressBar) {
        progressBar.style.width = '0%';
        // Restore animation effect and blue style
        progressBar.classList.remove('bg-success');
        progressBar.classList.add('progress-bar-striped', 'progress-bar-animated', 'bg-primary');
    }

    // Reset map view
    if (map) {
        map.setView([20, 0], 2);
    }
}

function processEvent(data) {
    console.log("Processing event data:", data);

    if (!data || data.trim() === "") {
        console.log("Empty data received, skipping");
        return;
    }

    try {
        const result = JSON.parse(data);

        // Check if this is a completion message
        if (result.done === true) {
            console.log("Traceroute completed (done flag received)");
            clearInterval(progressInterval);
            updateProgress(100);
            stopButton.style.display = "none";
            startButton.disabled = false;
            spinner.style.display = "none";
            addResultLine("Traceroute completed!");
            return;
        }

        // Check if this is a status message
        if (result.status === "completed") {
            console.log("Traceroute completed (status message received)");
            // Continue processing, but we know it's almost done
            addResultLine("Traceroute data collection complete, finalizing...");
            return;
        }

        // Check if this is an error message
        if (result.error) {
            console.error("Error in traceroute:", result.error);
            addResultLine(`Error: ${result.error}`);
            clearInterval(progressInterval);
            updateProgress(100);
            stopButton.style.display = "none";
            startButton.disabled = false;
            spinner.style.display = "none";
            return;
        }

        // Process regular hop data
        processHopData(result);
    } catch (e) {
        console.error("Error parsing event data:", e, "Raw data:", data);
        addResultLine(`Error parsing data: ${e.message}`);
    }
}

// Add new function for processing hop data
function processHopData(hopData) {
    if (!hopData || !hopData.hop) {
        console.log("Invalid hop data received:", hopData);
        return;
    }

    console.log(`Processing hop #${hopData.hop}:`, hopData);

    // Update total hop count counter (for progress bar)
    if (hopData.hop > hopCount) {
        hopCount = hopData.hop;
    }

    // Add to results list
    const formattedResult = formatHopResult(hopData);
    addResultLine(formattedResult);

    // If there's coordinate information, add to map
    if (hopData.coordinates && hopData.coordinates.length === 2) {
        addMapMarker(hopData);
    }
}

// Initialize geolocation
function initGeolocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                clientLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                console.log("User location acquired:", clientLocation);

                // Try to get city and country through reverse geocoding
                try {
                    reverseGeocode(clientLocation.latitude, clientLocation.longitude);
                } catch (e) {
                    console.warn("Reverse geocoding failed:", e);
                }
            },
            (error) => {
                console.warn("Failed to get location:", error.message);
                // Use IP-based geolocation as backup
                fetchIpBasedLocation();
            },
            {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }
        );
    } else {
        console.warn("Browser does not support geolocation");
        // Use IP-based geolocation as backup
        fetchIpBasedLocation();
    }
}

// Get approximate location via IP
function fetchIpBasedLocation() {
    fetch('https://ipapi.co/json/')
        .then(response => response.json())
        .then(data => {
            clientLocation = {
                latitude: data.latitude,
                longitude: data.longitude,
                city: data.city,
                country: data.country_name
            };
            console.log("IP location acquired:", clientLocation);
        })
        .catch(error => {
            console.error("Failed to get IP location:", error);
        });
}

// Reverse geocoding
function reverseGeocode(lat, lon) {
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`;

    fetch(url, {
        headers: {
            'User-Agent': 'GeoTraceroute/1.0'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data && data.address) {
                clientLocation.city = data.address.city || data.address.town || data.address.village;
                clientLocation.country = data.address.country;
                console.log("Location details acquired:", clientLocation);
            }
        })
        .catch(error => {
            console.error("Reverse geocoding failed:", error);
        });
}