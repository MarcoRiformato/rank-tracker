// Generic Modal Functions (replacement for alert/confirm)
function showAlert(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('genericModal');
        const titleEl = document.getElementById('genericModalTitle');
        const messageEl = document.getElementById('genericModalMessage');
        const buttonsEl = document.getElementById('genericModalButtons');

        titleEl.textContent = title || 'Alert';
        messageEl.textContent = message;

        buttonsEl.innerHTML = `
            <button class="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold" id="genericModalOkBtn">
                OK
            </button>
        `;

        modal.classList.remove('hidden');
        modal.style.display = 'flex';

        document.getElementById('genericModalOkBtn').onclick = function () {
            modal.classList.add('hidden');
            modal.style.display = 'none';
            resolve(true);
        };
    });
}

function showConfirm(title, message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('genericModal');
        const titleEl = document.getElementById('genericModalTitle');
        const messageEl = document.getElementById('genericModalMessage');
        const buttonsEl = document.getElementById('genericModalButtons');

        titleEl.textContent = title || 'Confirm';
        messageEl.textContent = message;

        buttonsEl.innerHTML = `
            <button class="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold" id="genericModalConfirmBtn">
                Confirm
            </button>
            <button class="flex-1 px-4 py-3 bg-slate-700 text-white rounded-lg hover:bg-slate-600 font-semibold" id="genericModalCancelBtn">
                Cancel
            </button>
        `;

        modal.classList.remove('hidden');
        modal.style.display = 'flex';

        document.getElementById('genericModalConfirmBtn').onclick = function () {
            modal.classList.add('hidden');
            modal.style.display = 'none';
            resolve(true);
        };

        document.getElementById('genericModalCancelBtn').onclick = function () {
            modal.classList.add('hidden');
            modal.style.display = 'none';
            resolve(false);
        };
    });
}

// Initialize map centered on Saronno, Italy
const map = L.map('map').setView([45.6251, 9.0352], 13);

let currentScanJobId = null;

// Add cancel scan listener
document.getElementById('cancelScanBtn').addEventListener('click', async function () {
    if (!currentScanJobId) return;

    const cancelBtn = this;
    cancelBtn.textContent = '⏳ Cancelling...';
    cancelBtn.disabled = true;

    try {
        const response = await fetch('/api/scan/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: currentScanJobId })
        });

        if (response.ok) {
            // Note: We don't close modal here, we wait for pollStatus to detect the cancellation
            console.log('Cancellation requested successfully');
        } else {
            cancelBtn.textContent = '⛔ Cancel Scan';
            cancelBtn.disabled = false;
            showAlert('Error', 'Failed to request cancellation');
        }
    } catch (error) {
        console.error('Error cancelling scan:', error);
        cancelBtn.textContent = '⛔ Cancel Scan';
        cancelBtn.disabled = false;
    }
});

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

// Store drawn polygon and pins
let drawnPolygon = null;
let drawnLayer = new L.FeatureGroup();
map.addLayer(drawnLayer);
let polygonPins = [];
let isPlacingPins = false;
let pinMarkers = new L.FeatureGroup();
map.addLayer(pinMarkers);
let pinMarkerMap = new Map(); // Map marker to index in polygonPins
let markers = []; // Store scan result markers

// Initialize Leaflet Draw (but don't add control to map - we'll use button instead)
const drawControl = new L.Control.Draw({
    draw: {
        polygon: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
        rectangle: {
            shapeOptions: {
                color: '#3388ff'
            }
        }
    },
    edit: {
        featureGroup: drawnLayer,
        remove: true
    }
});
// Don't add control to map - we use sidebar button instead

// Button to activate pin placement
document.getElementById('drawRectangleButton').addEventListener('click', function () {
    const button = this;

    if (!isPlacingPins) {
        // Start placing pins
        isPlacingPins = true;
        button.disabled = false;
        button.textContent = '📍 Click on map to place pins...';
        button.classList.remove('btn-draw');
        button.classList.add('bg-yellow-500', 'hover:bg-yellow-600');

        // Clear previous pins and polygon
        polygonPins = [];
        pinMarkers.clearLayers();
        drawnLayer.clearLayers();
        drawnPolygon = null;

        // Add click handler for placing pins
        map.on('click', placePin);

        // Show complete button if we have enough pins
        updateCompleteButton();
    } else {
        // Cancel pin placement
        cancelPinPlacement();
    }
});

function placePin(e) {
    if (!isPlacingPins) return;

    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // Add pin marker (draggable)
    const pin = L.marker([lat, lon], {
        icon: L.divIcon({
            className: 'pin-marker',
            html: '<div style="background: #ef4444; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); cursor: move;"></div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        }),
        draggable: true
    });

    // Store index for this pin
    const pinIndex = polygonPins.length;
    polygonPins.push([lat, lon]);
    pinMarkerMap.set(pin, pinIndex);

    // Handle drag end - update polygonPins position
    pin.on('dragend', function () {
        updatePolygonFromMarkers();
    });

    // Handle click - delete pin
    pin.on('click', function (e) {
        e.originalEvent.stopPropagation(); // Prevent map click

        // Remove marker
        pinMarkers.removeLayer(pin);

        updatePolygonFromMarkers();

        // Update status
        const statusMsg = document.getElementById('statusMessage');
        statusMsg.textContent = `${polygonPins.length} pin${polygonPins.length !== 1 ? 's' : ''} placed. ${polygonPins.length >= 3 ? 'Drag pins to adjust, click to delete.' : 'Place at least 3 pins.'}`;
        statusMsg.classList.remove('hidden');

        updateCompleteButton();
    });

    // Update polygon from current markers positions
    function updatePolygonFromMarkers() {
        // Rebuild polygonPins from all markers
        polygonPins = [];
        pinMarkerMap.clear();
        let markerIndex = 0;
        pinMarkers.eachLayer(function (marker) {
            const latlng = marker.getLatLng();
            polygonPins.push([latlng.lat, latlng.lng]);
            pinMarkerMap.set(marker, markerIndex);
            markerIndex++;
        });

        // Update polygon if it exists or if we have enough points to show it
        if (drawnPolygon || (isPlacingPins && polygonPins.length >= 3)) {
            drawnLayer.clearLayers();
            if (polygonPins.length >= 3) {
                const updatedPolygon = L.polygon(polygonPins, {
                    color: '#3388ff',
                    fillColor: '#3388ff',
                    fillOpacity: 0.2,
                    weight: 2
                });
                drawnLayer.addLayer(updatedPolygon);
                drawnPolygon = updatedPolygon;
            } else {
                drawnPolygon = null;
            }
        }
    }

    pinMarkers.addLayer(pin);

    // Update status
    const statusMsg = document.getElementById('statusMessage');
    statusMsg.textContent = `${polygonPins.length} pin${polygonPins.length !== 1 ? 's' : ''} placed. ${polygonPins.length >= 3 ? 'Click "Complete Polygon" to finish.' : 'Place at least 3 pins.'}`;
    statusMsg.classList.remove('hidden');

    updateCompleteButton();
}

function updateCompleteButton() {
    const button = document.getElementById('drawRectangleButton');
    const completeBtn = document.getElementById('completePolygonButton');

    if (polygonPins.length >= 3 && !completeBtn) {
        // Create complete button
        const btn = document.createElement('button');
        btn.id = 'completePolygonButton';
        btn.className = 'btn-primary mt-2';
        btn.textContent = '✅ Complete Polygon';
        btn.addEventListener('click', completePolygon);
        button.parentElement.insertBefore(btn, button.nextSibling);
    } else if (polygonPins.length < 3 && completeBtn) {
        completeBtn.remove();
    }
}

async function completePolygon() {
    if (polygonPins.length < 3) {
        await showAlert('Polygon Required', 'Please place at least 3 pins to create a polygon');
        return;
    }

    // Create polygon from pins
    const polygon = L.polygon(polygonPins, {
        color: '#3388ff',
        fillColor: '#3388ff',
        fillOpacity: 0.2,
        weight: 2
    });

    drawnLayer.clearLayers();
    drawnLayer.addLayer(polygon);
    drawnPolygon = polygon;

    // Remove pin placement mode
    cancelPinPlacement();

    // Update status
    const statusMsg = document.getElementById('statusMessage');
    statusMsg.textContent = `Polygon created with ${polygonPins.length} points. Click "Start Scan" to begin.`;
    statusMsg.classList.remove('hidden');
}

function cancelPinPlacement() {
    isPlacingPins = false;
    map.off('click', placePin);

    const button = document.getElementById('drawRectangleButton');
    button.textContent = '📐 Drop Pins on Map';
    button.classList.remove('bg-yellow-500', 'hover:bg-yellow-600');
    button.classList.add('btn-draw');

    const completeBtn = document.getElementById('completePolygonButton');
    if (completeBtn) {
        completeBtn.remove();
    }
}

// Handle polygon editing/deletion
map.on(L.Draw.Event.DELETED, function (e) {
    drawnPolygon = null;
    polygonPins = [];
    pinMarkers.clearLayers();
    const statusMsg = document.getElementById('statusMessage');
    statusMsg.textContent = 'Polygon removed. Draw a new polygon to scan.';
    statusMsg.classList.remove('hidden');
});

// Tag system for business names and keywords
const businessNameTags = [];
const keywordTags = [];

function addBusinessNameTag(name) {
    const trimmed = name.trim();
    if (trimmed && !businessNameTags.includes(trimmed)) {
        businessNameTags.push(trimmed);
        renderBusinessNameTags();
        document.getElementById('businessNameInput').value = '';
    }
}

function removeBusinessNameTag(name) {
    const index = businessNameTags.indexOf(name);
    if (index > -1) {
        businessNameTags.splice(index, 1);
        renderBusinessNameTags();
    }
}

function renderBusinessNameTags() {
    const container = document.getElementById('businessNameTags');
    container.innerHTML = '';

    businessNameTags.forEach(name => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.innerHTML = `${escapeHtml(name)} <span class="tag-delete">×</span>`;

        const deleteBtn = tag.querySelector('.tag-delete');
        deleteBtn.addEventListener('click', () => removeBusinessNameTag(name));

        container.appendChild(tag);
    });
}

function addKeywordTag(keyword) {
    const trimmed = keyword.trim();
    if (trimmed && !keywordTags.includes(trimmed) && keywordTags.length < 25) {
        keywordTags.push(trimmed);
        renderKeywordTags();
        document.getElementById('keywordInput').value = '';
    } else if (keywordTags.length >= 25) {
        showAlert('Limit Reached', 'Maximum 25 keywords allowed');
    }
}

function removeKeywordTag(keyword) {
    const index = keywordTags.indexOf(keyword);
    if (index > -1) {
        keywordTags.splice(index, 1);
        renderKeywordTags();
    }
}

function renderKeywordTags() {
    const container = document.getElementById('keywordTags');
    container.innerHTML = '';

    keywordTags.forEach(keyword => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.innerHTML = `${escapeHtml(keyword)} <span class="tag-delete">×</span>`;

        const deleteBtn = tag.querySelector('.tag-delete');
        deleteBtn.addEventListener('click', () => removeKeywordTag(keyword));

        container.appendChild(tag);
    });

    // Update counter
    const counter = document.getElementById('keywordCount');
    if (counter) {
        counter.textContent = `(${keywordTags.length}/25)`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Business name input handler
document.getElementById('businessNameInput').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        addBusinessNameTag(this.value);
    }
});

// Keyword input handler
document.getElementById('keywordInput').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        addKeywordTag(this.value);
    }
});

// Update spacing value display
document.getElementById('gridSpacing').addEventListener('input', function (e) {
    document.getElementById('spacingValue').textContent = e.target.value;
});

// Color coding function
function getMarkerColor(displayRank) {
    if (displayRank === null || displayRank === undefined) {
        return '#ef4444'; // Red for Not Found
    }

    if (displayRank >= 1 && displayRank <= 3) {
        return '#FFD700'; // Gold
    } else if (displayRank >= 4 && displayRank <= 10) {
        return '#22c55e'; // Green
    } else if (displayRank >= 11 && displayRank <= 20) {
        return '#eab308'; // Yellow
    } else if (displayRank >= 21 && displayRank <= 30) {
        return '#f97316'; // Orange
    } else {
        return '#ef4444'; // Red
    }
}

// Markers layer for scan results
let markersLayer = new L.FeatureGroup();
map.addLayer(markersLayer);

// Scan button handler
document.getElementById('scanButton').addEventListener('click', async function () {
    // Get business names and keywords from tags
    const businessNames = [...businessNameTags];
    const keywords = [...keywordTags];

    const gridSpacing = parseFloat(document.getElementById('gridSpacing').value);

    // Validate inputs
    if (businessNames.length === 0) {
        await showAlert('Business Name Required', 'Please add at least one business name variation (type and press Enter)');
        return;
    }

    if (keywords.length === 0) {
        await showAlert('Keyword Required', 'Please add at least one keyword (type and press Enter)');
        return;
    }

    if (!drawnPolygon || polygonPins.length < 3) {
        await showAlert('Polygon Required', 'Please draw a polygon on the map first. Click "Drop Pins on Map" and place at least 3 pins.');
        return;
    }

    // Get polygon coordinates
    const polygonCoords = polygonPins.map(pin => [pin[0], pin[1]]);

    // Also calculate bbox for backward compatibility
    const bounds = drawnPolygon.getBounds();
    const bbox = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest()
    };

    // Show loading modal
    const scanModal = document.getElementById('scanLoadingModal');
    const scanButton = document.getElementById('scanButton');
    const progressFill = document.getElementById('scanProgressFill');
    const progressText = document.getElementById('scanProgressText');
    const loadingMessage = document.getElementById('scanLoadingMessage');
    const completeSection = document.getElementById('scanCompleteSection');
    const viewResultsBtn = document.getElementById('viewResultsBtn');

    scanButton.disabled = true;
    scanModal.style.display = 'flex';
    scanModal.classList.remove('hidden');
    completeSection.style.display = 'none';
    viewResultsBtn.disabled = true;

    // Estimate total points (grid calculation is done on server)
    const estimatedPoints = Math.ceil(Math.pow(bounds.getNorth() - bounds.getSouth(), 2) / Math.pow(gridSpacing, 2)) * keywords.length;
    const totalPoints = estimatedPoints;

    // Clear previous markers
    markersLayer.clearLayers();

    try {
        // Phase 1: Starting scan
        loadingMessage.textContent = `Preparing scan: ${businessNames.length} business names × ${keywords.length} keywords`;
        progressFill.style.width = '5%';
        progressText.textContent = 'Initializing scan...';

        // Small delay to show initial phase
        await new Promise(resolve => setTimeout(resolve, 300));

        // Phase 2: Start scan job
        progressFill.style.width = '5%';
        progressText.textContent = 'Starting scan...';
        loadingMessage.textContent = 'Initializing scan job...';

        // Start the scan request
        const scanResponse = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                business_names: businessNames,
                keywords: keywords,
                grid_spacing: gridSpacing,
                bbox: bbox,
                polygon_coords: polygonCoords
            })
        });

        if (!scanResponse.ok) {
            const error = await scanResponse.json();
            throw new Error(error.error || 'Scan failed to start');
        }

        const scanData = await scanResponse.json();
        const jobId = scanData.job_id;
        currentScanJobId = jobId;

        // Reset cancel button
        const cancelBtn = document.getElementById('cancelScanBtn');
        cancelBtn.textContent = '⛔ Cancel Scan';
        cancelBtn.disabled = false;
        cancelBtn.style.display = 'inline-block';

        const totalWorkUnits = scanData.total_work_units;
        const totalSerperCalls = scanData.total_serper_calls;

        // Update initial progress
        progressFill.style.width = '5%';
        progressText.textContent = '0%';
        loadingMessage.textContent = `Scanning ${totalWorkUnits} locations (${totalSerperCalls} API calls)...`;

        // Helper function to process results (defined before use)
        const processScanResults = (results) => {
            // Phase 7: Processing results
            progressFill.style.width = '95%';
            progressText.textContent = '95%';
            loadingMessage.textContent = `Processing ${results.length} results and preparing display...`;

            // Add markers for each result
            results.forEach(result => {
                const color = result.status === 'success'
                    ? getMarkerColor(result.display_rank)
                    : '#6b7280'; // Grey for API errors

                const marker = L.circleMarker([result.lat, result.lon], {
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                });

                // Store result data on marker for later use
                marker.resultData = result;

                // Create detailed popup card
                const popupId = `popup-${result.lat}-${result.lon}-${result.keyword}`.replace(/[^a-zA-Z0-9-]/g, '-');
                const rankColor = getMarkerColor(result.display_rank);
                const rankLabel = result.display_rank ? `Rank ${result.display_rank}` : 'Not Found';

                // Landing page status display
                const landingPageExists = result.landing_page_exists || false;
                const landingPageIcon = landingPageExists ? '✓' : '✗';
                const landingPageColor = landingPageExists ? '#22c55e' : '#ef4444';
                const landingPageText = landingPageExists ? 'Exists' : 'Missing';
                const landingPageUrl = result.landing_page_url || '';

                const cityName = result.city || 'Unknown Location';

                let popupContent = `
                    <div class="popup-card" style="min-width: 320px; max-width: 400px;">
                        <div class="popup-header" style="background: ${rankColor}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
                            <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 700;">${escapeHtml(cityName)}</h3>
                            <div style="margin-top: 8px; font-size: 14px; opacity: 0.9;">${rankLabel}</div>
                        </div>
                        <div class="popup-body" style="padding: 16px; background: #f8fafc;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                                <div style="background: white; padding: 12px; border-radius: 8px; text-align: center;">
                                    <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">LOCAL PACK</div>
                                    <div style="font-size: 24px; font-weight: 700; color: ${rankColor};">${result.local_pack_rank || '—'}</div>
                                </div>
                                <div style="background: white; padding: 12px; border-radius: 8px; text-align: center;">
                                    <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">ORGANIC</div>
                                    <div style="font-size: 24px; font-weight: 700; color: ${result.organic_rank ? '#3b82f6' : '#94a3b8'};">
                                        ${result.organic_rank || '—'}
                                    </div>
                                </div>
                            </div>
                            <div style="background: white; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                                <div style="font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 8px;">Landing Page Status</div>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-size: 20px; color: ${landingPageColor};">${landingPageIcon}</span>
                                    <span style="font-size: 13px; color: #475569;">Landing Page: ${landingPageText}</span>
                                    ${landingPageUrl ? `<a href="${escapeHtml(landingPageUrl)}" target="_blank" style="font-size: 11px; color: #3b82f6; margin-left: auto;">View</a>` : ''}
                                </div>
                            </div>
                            <div style="background: white; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                                <div style="font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 8px;">Top 5 Competitors</div>
                                <div id="competitors-${popupId}" style="font-size: 12px; color: #64748b;">
                                    <div style="text-align: center; padding: 8px; color: #94a3b8;">Loading...</div>
                                </div>
                            </div>
                            <div style="background: white; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                                <div style="font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 8px;">Ranking History</div>
                                <canvas id="chart-${popupId}" style="max-height: 200px;"></canvas>
                            </div>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 400,
                    className: 'custom-popup'
                });

                // Load history, competitors, and create chart when popup opens
                marker.on('popupopen', function () {
                    loadPointHistoryAndChart(result.lat, result.lon, result.keyword, popupId);
                    loadPointCompetitors(result.lat, result.lon, result.keyword, popupId);
                });

                markersLayer.addLayer(marker);
            });

            // Show complete section
            progressFill.style.width = '100%';
            progressText.textContent = `Complete! ${results.length} points scanned.`;
            loadingMessage.textContent = `Successfully scanned ${results.length} locations.`;

            // Hide spinner, show complete section
            document.getElementById('scanLoadingSpinner').style.display = 'none';
            document.getElementById('cancelScanBtn').style.display = 'none'; // Hide cancel button
            completeSection.style.display = 'block';
            viewResultsBtn.disabled = false;

            // View results button - close modal and show map
            viewResultsBtn.onclick = function () {
                scanModal.style.display = 'none';
                scanModal.classList.add('hidden');
                scanButton.disabled = false;
                scanButton.textContent = '🔄 New Scan';
            };
        };

        // Poll for status updates until complete
        let scanComplete = false;
        let scanResults = null;
        let scanError = null;

        const pollStatus = async () => {
            while (!scanComplete && !scanError) {
                try {
                    const statusResponse = await fetch(`/api/scan/status?job_id=${jobId}`);
                    if (!statusResponse.ok) {
                        await new Promise(resolve => setTimeout(resolve, 500));
                        continue;
                    }

                    const statusData = await statusResponse.json();

                    // Update progress bar with REAL progress
                    const progressPercent = Math.max(5, Math.min(95, statusData.progress || 0));
                    progressFill.style.width = progressPercent + '%';
                    progressText.textContent = Math.round(progressPercent) + '%';

                    // Build status message with real data
                    let statusMsg = `Scanning: ${statusData.completed}/${statusData.total} points`;
                    if (statusData.completed_serper_calls && statusData.total_serper_calls) {
                        statusMsg += ` (${statusData.completed_serper_calls}/${statusData.total_serper_calls} API calls)`;
                    }

                    // Add ETA if available
                    if (statusData.eta_seconds !== null && statusData.eta_seconds !== undefined && statusData.eta_seconds > 0) {
                        const etaMinutes = Math.floor(statusData.eta_seconds / 60);
                        const etaSeconds = Math.floor(statusData.eta_seconds % 60);
                        if (etaMinutes > 0) {
                            statusMsg += ` • ETA: ~${etaMinutes}m ${etaSeconds}s`;
                        } else if (etaSeconds > 0) {
                            statusMsg += ` • ETA: ~${etaSeconds}s`;
                        }
                    }

                    // Add current keyword if available
                    if (statusData.current_keyword) {
                        statusMsg += ` • Keyword: ${statusData.current_keyword}`;
                    }

                    loadingMessage.textContent = statusMsg;

                    // Check if complete or error
                    if (statusData.status === 'complete') {
                        // Fetch results
                        const resultsResponse = await fetch(`/api/scan/results?job_id=${jobId}`);
                        if (!resultsResponse.ok) {
                            scanError = new Error('Failed to fetch results');
                            break;
                        }
                        const resultsData = await resultsResponse.json();
                        scanResults = resultsData.results;
                        scanComplete = true;
                        break;
                    } else if (statusData.status === 'error') {
                        scanError = new Error(statusData.error || 'Scan failed');
                        break;
                    } else if (statusData.status === 'cancelled') {
                        scanError = new Error('Scan cancelled by user');
                        break;
                    }

                    // Wait before next poll
                    await new Promise(resolve => setTimeout(resolve, 500));
                } catch (error) {
                    console.error('Error polling scan status:', error);
                    // Wait and retry on network errors
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
        };

        // Start polling (don't await, let it run in background)
        pollStatus();

        // Wait for completion (with timeout)
        const maxWaitTime = 30 * 60 * 1000; // 30 minutes max
        const startTime = Date.now();
        while (!scanComplete && !scanError && (Date.now() - startTime) < maxWaitTime) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        if (scanError) {
            throw scanError;
        }

        if (!scanComplete) {
            throw new Error('Scan timed out');
        }

        // Process results
        processScanResults(scanResults);

    } catch (error) {
        console.error('Scan error:', error);
        loadingMessage.textContent = `Error: ${error.message}`;
        progressText.textContent = 'Scan failed';
        showAlert('Scan Failed', `Scan failed: ${error.message}`);

        // Close modal on error
        scanModal.style.display = 'none';
        scanModal.classList.add('hidden');
        scanButton.disabled = false;
    }
});

// Load point history and create chart
async function loadPointHistoryAndChart(lat, lon, keyword, popupId) {
    try {
        const response = await fetch(`/api/point-history?lat=${lat}&lon=${lon}&keyword=${encodeURIComponent(keyword)}`);
        if (!response.ok) return;

        const data = await response.json();
        const history = data.history || [];

        if (history.length === 0) return;

        // Prepare chart data
        const labels = history.map(h => {
            const date = new Date(h.date);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });

        const localPackData = history.map(h => h.local_pack_rank || null);
        const organicData = history.map(h => h.organic_rank || null);

        // Create chart
        const ctx = document.getElementById(`chart-${popupId}`);
        if (!ctx) return;

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Local Pack',
                        data: localPackData,
                        borderColor: '#FFD700',
                        backgroundColor: 'rgba(255, 215, 0, 0.1)',
                        tension: 0.4,
                        spanGaps: true
                    },
                    {
                        label: 'Organic',
                        data: organicData,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        spanGaps: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            font: { size: 11 },
                            padding: 8
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        reverse: true, // Lower rank is better
                        title: {
                            display: true,
                            text: 'Rank',
                            font: { size: 11 }
                        },
                        ticks: {
                            font: { size: 10 }
                        }
                    },
                    x: {
                        ticks: {
                            font: { size: 10 },
                            maxRotation: 45
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Load point competitors and display in popup
async function loadPointCompetitors(lat, lon, keyword, popupId) {
    try {
        const response = await fetch(`/api/point-competitors?lat=${lat}&lon=${lon}&keyword=${encodeURIComponent(keyword)}`);
        if (!response.ok) {
            const competitorsContainer = document.getElementById(`competitors-${popupId}`);
            if (competitorsContainer) {
                competitorsContainer.innerHTML = '<div style="text-align: center; padding: 8px; color: #94a3b8; font-size: 11px;">No competitor data available</div>';
            }
            return;
        }

        const data = await response.json();
        const competitors = data.competitors || [];

        const competitorsContainer = document.getElementById(`competitors-${popupId}`);
        if (!competitorsContainer) return;

        if (competitors.length === 0) {
            competitorsContainer.innerHTML = '<div style="text-align: center; padding: 8px; color: #94a3b8; font-size: 11px;">No competitors found</div>';
            return;
        }

        let competitorsHtml = '<div style="display: flex; flex-direction: column; gap: 6px;">';
        competitors.forEach(competitor => {
            const reviewText = competitor.review_count
                ? ` (${competitor.review_count} ${competitor.review_count === 1 ? 'review' : 'reviews'})`
                : '';
            const ratingText = competitor.rating_stars
                ? ` ⭐ ${competitor.rating_stars.toFixed(1)}`
                : '';

            competitorsHtml += `
                <div style="display: flex; align-items: center; gap: 8px; padding: 6px; background: #f1f5f9; border-radius: 4px;">
                    <span style="font-weight: 600; color: #475569; min-width: 20px;">${competitor.rank}.</span>
                    <span style="flex: 1; color: #334155; font-size: 12px;">${escapeHtml(competitor.name)}</span>
                    ${ratingText ? `<span style="color: #f59e0b; font-size: 11px;">${ratingText}</span>` : ''}
                    ${reviewText ? `<span style="color: #64748b; font-size: 11px;">${reviewText}</span>` : ''}
                </div>
            `;
        });
        competitorsHtml += '</div>';

        competitorsContainer.innerHTML = competitorsHtml;
    } catch (error) {
        console.error('Error loading competitors:', error);
        const competitorsContainer = document.getElementById(`competitors-${popupId}`);
        if (competitorsContainer) {
            competitorsContainer.innerHTML = '<div style="text-align: center; padding: 8px; color: #94a3b8; font-size: 11px;">Error loading competitors</div>';
        }
    }
}

// Load project data on page load
async function loadProjectData() {
    try {
        const response = await fetch('/api/projects/current');
        if (response.ok) {
            const project = await response.json();

            // Load business names
            if (project.business_names && project.business_names.length > 0) {
                businessNameTags.length = 0;
                project.business_names.forEach(name => {
                    businessNameTags.push(name);
                });
                renderBusinessNameTags();
            }

            // Load keywords
            if (project.keywords && project.keywords.length > 0) {
                keywordTags.length = 0;
                project.keywords.forEach(keyword => {
                    keywordTags.push(keyword);
                });
                renderKeywordTags();
            }
        }
    } catch (error) {
        console.error('Error loading project data:', error);
    }
}

// Modal for business names settings
const businessNameTagsModal = [];

function addBusinessNameTagModal(name) {
    const trimmed = name.trim();
    if (trimmed && !businessNameTagsModal.includes(trimmed)) {
        businessNameTagsModal.push(trimmed);
        renderBusinessNameTagsModal();
        document.getElementById('businessNameInputModal').value = '';
    }
}

function removeBusinessNameTagModal(name) {
    const index = businessNameTagsModal.indexOf(name);
    if (index > -1) {
        businessNameTagsModal.splice(index, 1);
        renderBusinessNameTagsModal();
    }
}

function renderBusinessNameTagsModal() {
    const container = document.getElementById('businessNameTagsModal');
    container.innerHTML = '';

    businessNameTagsModal.forEach(name => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.innerHTML = `${escapeHtml(name)} <span class="tag-delete">×</span>`;

        const deleteBtn = tag.querySelector('.tag-delete');
        deleteBtn.addEventListener('click', () => removeBusinessNameTagModal(name));

        container.appendChild(tag);
    });
}

// Settings button handler
document.getElementById('businessNameSettingsBtn').addEventListener('click', function () {
    // Copy current tags to modal
    businessNameTagsModal.length = 0;
    businessNameTags.forEach(tag => businessNameTagsModal.push(tag));
    renderBusinessNameTagsModal();

    // Show modal
    document.getElementById('businessNameModal').classList.remove('hidden');
    document.getElementById('businessNameModal').style.display = 'flex';
});

// Modal input handler
document.getElementById('businessNameInputModal').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        addBusinessNameTagModal(this.value);
    }
});

// Save business names
document.getElementById('saveBusinessNamesBtn').addEventListener('click', async function () {
    const projectId = null; // We'll get this from session via API
    try {
        const response = await fetch('/api/projects/current');
        const project = await response.json();

        const updateResponse = await fetch(`/api/projects/${project.id}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                business_names: businessNameTagsModal,
                keywords: keywordTags // Keep existing keywords
            })
        });

        if (updateResponse.ok) {
            // Update main tags
            businessNameTags.length = 0;
            businessNameTagsModal.forEach(tag => businessNameTags.push(tag));
            renderBusinessNameTags();

            // Close modal
            document.getElementById('businessNameModal').classList.add('hidden');
            document.getElementById('businessNameModal').style.display = 'none';
        }
    } catch (error) {
        console.error('Error saving business names:', error);
        showAlert('Save Failed', 'Failed to save business names: ' + error.message);
    }
});

// Cancel business names modal
document.getElementById('cancelBusinessNamesBtn').addEventListener('click', function () {
    document.getElementById('businessNameModal').classList.add('hidden');
    document.getElementById('businessNameModal').style.display = 'none';
});

// Load project data when page loads
loadProjectData();

// Change Project button handler
document.getElementById('changeProjectBtn').addEventListener('click', function () {
    window.location.href = '/projects';
});

// Testing Mode button handler
async function loadTestingModeStatus() {
    try {
        const response = await fetch('/api/testing-mode-status');
        if (response.ok) {
            const data = await response.json();
            updateTestingModeButton(data.testing_mode);
        }
    } catch (error) {
        console.error('Error loading testing mode status:', error);
    }
}

function updateTestingModeButton(isEnabled) {
    const btn = document.getElementById('testingModeBtn');
    const status = document.getElementById('testingModeStatus');
    if (isEnabled) {
        btn.style.background = '#22c55e';
        status.textContent = 'ON';
    } else {
        btn.style.background = '#f59e0b';
        status.textContent = 'OFF';
    }
}

document.getElementById('testingModeBtn').addEventListener('click', async function () {
    // Check current status
    try {
        const response = await fetch('/api/testing-mode-status');
        if (response.ok) {
            const data = await response.json();
            if (data.testing_mode) {
                // Currently enabled, ask to disable
                const confirmed = await showConfirm('Disable Testing Mode?', 'This will use real API calls for scans.');
                if (confirmed) {
                    const toggleResponse = await fetch('/api/toggle-testing-mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enable: false })
                    });
                    if (toggleResponse.ok) {
                        updateTestingModeButton(false);
                    }
                }
            } else {
                // Currently disabled, show confirmation modal
                document.getElementById('testingModeModal').classList.remove('hidden');
                document.getElementById('testingModeModal').style.display = 'flex';
            }
        }
    } catch (error) {
        console.error('Error checking testing mode status:', error);
    }
});

// Testing Mode Modal handlers
document.getElementById('confirmTestingModeBtn').addEventListener('click', async function () {
    try {
        const response = await fetch('/api/toggle-testing-mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: true })
        });
        if (response.ok) {
            updateTestingModeButton(true);
            document.getElementById('testingModeModal').classList.add('hidden');
            document.getElementById('testingModeModal').style.display = 'none';
        }
    } catch (error) {
        console.error('Error enabling testing mode:', error);
        showAlert('Error', 'Failed to enable testing mode: ' + error.message);
    }
});

document.getElementById('cancelTestingModeBtn').addEventListener('click', function () {
    document.getElementById('testingModeModal').classList.add('hidden');
    document.getElementById('testingModeModal').style.display = 'none';
});

// Load testing mode status on page load
loadTestingModeStatus();

// Cleanup Dummy Data button handler
document.getElementById('cleanupDummyDataBtn').addEventListener('click', async function () {
    const confirmed = await showConfirm(
        'Cleanup Dummy Data?',
        'This will remove all dummy/test data from the current project.\n\nKnown patterns:\n- Keywords: "pizza delivery", "italian restaurant", "food near me"\n- Business names: "My Business", "My Business Inc", "My Business LLC"\n\nContinue?'
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch('/api/cleanup-dummy-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            await showAlert('Success', `Cleanup complete!\n\nDeleted:\n- ${data.deleted.scans} scans\n- ${data.deleted.scan_points} scan points\n- ${data.deleted.point_history} point history entries\n- ${data.deleted.competitor_snapshots} competitor snapshots\n- ${data.deleted.competitor_history} competitor history entries`);

            // Reload the page to refresh data
            window.location.reload();
        } else {
            const error = await response.json();
            showAlert('Error', 'Failed to cleanup dummy data: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error cleaning up dummy data:', error);
        showAlert('Error', 'Failed to cleanup dummy data: ' + error.message);
    }
});

// Periodic frequency handler - show/hide Save button
document.getElementById('periodicFrequency').addEventListener('change', function () {
    const saveBtn = document.getElementById('savePeriodicScanBtn');
    const frequency = this.value;
    const startDate = document.getElementById('periodicStartDate').value;
    if (frequency && startDate) {
        saveBtn.style.display = 'block';
    } else {
        saveBtn.style.display = 'none';
    }
});

document.getElementById('periodicStartDate').addEventListener('change', function () {
    const saveBtn = document.getElementById('savePeriodicScanBtn');
    const frequency = document.getElementById('periodicFrequency').value;
    if (frequency && this.value) {
        saveBtn.style.display = 'block';
    } else {
        saveBtn.style.display = 'none';
    }
});

// Save Periodic Scan button handler  
document.getElementById('savePeriodicScanBtn').addEventListener('click', async function () {
    const frequency = document.getElementById('periodicFrequency').value;
    const startDate = document.getElementById('periodicStartDate').value;

    if (!frequency || !startDate) {
        await showAlert('Missing Information', 'Please select both frequency and start date');
        return;
    }

    if (!drawnPolygon || polygonPins.length < 3) {
        await showAlert('Polygon Required', 'Please draw a polygon on the map first');
        return;
    }

    if (businessNameTags.length === 0 || keywordTags.length === 0) {
        await showAlert('Configuration Required', 'Please add business names and keywords first');
        return;
    }

    const polygonCoords = polygonPins.map(pin => [pin[0], pin[1]]);
    const bounds = drawnPolygon.getBounds();
    const bbox = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest()
    };

    try {
        const response = await fetch('/api/scheduled-scans', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: `Periodic Scan - ${frequency}`,
                frequency: frequency,
                start_date: startDate,
                business_names: businessNameTags,
                keywords: keywordTags,
                grid_spacing: parseFloat(document.getElementById('gridSpacing').value),
                polygon_coords: polygonCoords,
                bbox: bbox
            })
        });

        if (response.ok) {
            await showAlert('Success', 'Periodic scan saved successfully!');
            // Reset form
            document.getElementById('periodicFrequency').value = '';
            document.getElementById('periodicStartDate').value = '';
            document.getElementById('savePeriodicScanBtn').style.display = 'none';
        } else {
            const error = await response.json();
            showAlert('Save Failed', 'Failed to save periodic scan: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving periodic scan:', error);
        showAlert('Error', 'Failed to save periodic scan: ' + error.message);
    }
});

// Cache-only scan button handler
document.getElementById('cacheScanButton').addEventListener('click', async function () {
    // Get business names and keywords from tags
    const businessNames = [...businessNameTags];
    const keywords = [...keywordTags];

    const gridSpacing = parseFloat(document.getElementById('gridSpacing').value);

    // Validate inputs
    if (businessNames.length === 0) {
        await showAlert('Business Name Required', 'Please add at least one business name variation (type and press Enter)');
        return;
    }

    if (keywords.length === 0) {
        await showAlert('Keyword Required', 'Please add at least one keyword (type and press Enter)');
        return;
    }

    if (!drawnPolygon || polygonPins.length < 3) {
        await showAlert('Polygon Required', 'Please draw a polygon on the map first. Click "Drop Pins on Map" and place at least 3 pins.');
        return;
    }

    // Get polygon coordinates
    const polygonCoords = polygonPins.map(pin => [pin[0], pin[1]]);

    // Also calculate bbox for backward compatibility
    const bounds = drawnPolygon.getBounds();
    const bbox = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest()
    };

    // Show loading modal
    const scanModal = document.getElementById('scanLoadingModal');
    const cacheScanButton = document.getElementById('cacheScanButton');
    const progressFill = document.getElementById('scanProgressFill');
    const progressText = document.getElementById('scanProgressText');
    const loadingMessage = document.getElementById('scanLoadingMessage');
    const completeSection = document.getElementById('scanCompleteSection');
    const viewResultsBtn = document.getElementById('viewResultsBtn');

    scanModal.classList.remove('hidden');
    scanModal.style.display = 'flex';
    completeSection.style.display = 'none';
    viewResultsBtn.disabled = true;
    cacheScanButton.disabled = true;
    cacheScanButton.textContent = '⏳ Scanning Cache...';

    progressFill.style.width = '0%';
    progressText.textContent = 'Starting cached scan...';

    try {
        // Make API call to cache-only scan endpoint
        const response = await fetch('/api/scan-cache-only', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                business_names: businessNames,
                keywords: keywords,
                grid_spacing: gridSpacing,
                bbox: bbox,
                polygon_coords: polygonCoords
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Scan failed');
        }

        const data = await response.json();
        const jobId = data.job_id;
        currentScanJobId = jobId;

        // Reset cancel button
        const cancelBtn = document.getElementById('cancelScanBtn');
        cancelBtn.textContent = '⛔ Cancel Scan';
        cancelBtn.disabled = false;
        cancelBtn.style.display = 'inline-block';

        // Helper function to process results (defined before use)
        const processScanResults = (results) => {
            // Phase 7: Processing results
            progressFill.style.width = '95%';
            progressText.textContent = '95%';
            loadingMessage.textContent = `Processing ${results.length} results and preparing display...`;

            // Add markers for each result
            results.forEach(result => {
                const color = result.status === 'success'
                    ? getMarkerColor(result.display_rank)
                    : '#6b7280'; // Grey for API errors

                const marker = L.circleMarker([result.lat, result.lon], {
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                });

                // Store result data on marker for later use
                marker.resultData = result;

                // Create detailed popup card
                const popupId = `popup-${result.lat}-${result.lon}-${result.keyword}`.replace(/[^a-zA-Z0-9-]/g, '-');
                const rankColor = getMarkerColor(result.display_rank);
                const rankLabel = result.display_rank ? `Rank ${result.display_rank}` : 'Not Found';

                // Landing page status display
                const landingPageExists = result.landing_page_exists || false;
                const landingPageIcon = landingPageExists ? '✓' : '✗';
                const landingPageColor = landingPageExists ? '#22c55e' : '#ef4444';
                const landingPageText = landingPageExists ? 'Exists' : 'Missing';
                const landingPageUrl = result.landing_page_url || '';

                const cityName = result.city || 'Unknown Location';

                let popupContent = `
                    <div class="popup-card" style="min-width: 320px; max-width: 400px;">
                        <div class="popup-header" style="background: ${rankColor}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
                            <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 700;">${escapeHtml(cityName)}</h3>
                            <div style="margin-top: 8px; font-size: 14px; opacity: 0.9;">${rankLabel}</div>
                        </div>
                        <div class="popup-body" style="padding: 16px; background: #f8fafc;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                                <div style="background: white; padding: 12px; border-radius: 8px; text-align: center;">
                                    <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">LOCAL PACK</div>
                                    <div style="font-size: 24px; font-weight: 700; color: ${rankColor};">${result.local_pack_rank || '—'}</div>
                                </div>
                                <div style="background: white; padding: 12px; border-radius: 8px; text-align: center;">
                                    <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">ORGANIC</div>
                                    <div style="font-size: 24px; font-weight: 700; color: ${rankColor};">${result.organic_rank || '—'}</div>
                                </div>
                            </div>
                            <div style="background: white; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                                <div style="font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px;">📍 ${escapeHtml(result.keyword)}</div>
                                <div style="font-size: 12px; color: #6b7280;">Business: ${escapeHtml(result.matched_business_name || 'Not found')}</div>
                            </div>
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="font-size: 12px; color: #6b7280;">
                                    <span style="color: ${landingPageColor};">${landingPageIcon}</span> Landing page ${landingPageText.toLowerCase()}
                                </div>
                                <button id="competitors-btn-${popupId}" style="background: #3b82f6; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer;">
                                    👥 Competitors
                                </button>
                            </div>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent);

                // Add click handler for competitors button
                marker.on('popupopen', function () {
                    const btn = document.getElementById(`competitors-btn-${popupId}`);
                    if (btn) {
                        btn.onclick = () => loadPointCompetitors(result.lat, result.lon, result.keyword, popupId);
                    }
                });

                markersLayer.addLayer(marker);
            });

            // Phase 8: Complete
            setTimeout(() => {
                progressFill.style.width = '100%';
                progressText.textContent = '100%';
                loadingMessage.textContent = `Scan complete! Found ${results.length} locations.`;

                // Show completion section after a delay
                setTimeout(() => {
                    completeSection.style.display = 'block';
                    viewResultsBtn.disabled = false;

                    // View results button - close modal and show map
                    viewResultsBtn.onclick = function () {
                        scanModal.style.display = 'none';
                        scanModal.classList.add('hidden');
                        cacheScanButton.disabled = false;
                        cacheScanButton.textContent = '📦 Scan with Cached Data Only';
                    };
                }, 1000);
            }, 500);
        };

        // Poll for progress
        const pollCacheScanProgress = async () => {
            let scanComplete = false;
            let scanError = null;

            while (!scanComplete && !scanError) {
                try {
                    const statusResponse = await fetch(`/api/scan/status?job_id=${jobId}`);
                    if (!statusResponse.ok) {
                        await new Promise(resolve => setTimeout(resolve, 1000));
                        continue;
                    }

                    const statusData = await statusResponse.json();

                    // Update progress bar
                    const progressPercent = Math.max(5, Math.min(95, statusData.progress || 0));
                    progressFill.style.width = progressPercent + '%';
                    progressText.textContent = Math.round(progressPercent) + '%';

                    // Build status message
                    let statusMsg = `Cache scan: ${statusData.completed || 0}/${statusData.total || 0} points`;

                    // Add current keyword if available
                    if (statusData.current_keyword) {
                        statusMsg += ` • Keyword: ${statusData.current_keyword}`;
                    }

                    loadingMessage.textContent = statusMsg;

                    // Check if complete or error
                    if (statusData.status === 'complete') {
                        scanComplete = true;

                        // Fetch results
                        const resultsResponse = await fetch(`/api/scan/results?job_id=${jobId}`);
                        if (resultsResponse.ok) {
                            const resultsData = await resultsResponse.json();

                            // Show completion
                            progressFill.style.width = '100%';
                            progressText.textContent = '100%';
                            loadingMessage.textContent = 'Cache scan complete! Processing results...';

                            // Small delay to show 100%
                            await new Promise(resolve => setTimeout(resolve, 500));

                            // Process results and show map
                            if (resultsData.results && resultsData.results.length > 0) {
                                processScanResults(resultsData.results);
                            }

                            // Show completion section
                            document.getElementById('cancelScanBtn').style.display = 'none'; // Hide cancel button
                            completeSection.style.display = 'block';
                            viewResultsBtn.disabled = false;

                            // Reset button
                            cacheScanButton.disabled = false;
                            cacheScanButton.textContent = '📦 Scan with Cached Data Only';
                        } else {
                            throw new Error('Failed to fetch results');
                        }
                    } else if (statusData.status === 'error') {
                        scanError = statusData.error || 'Unknown error';
                        throw new Error(scanError);
                    } else if (statusData.status === 'cancelled') {
                        throw new Error('Scan cancelled by user');
                    }

                    // Wait before next poll
                    await new Promise(resolve => setTimeout(resolve, 1000));

                } catch (error) {
                    console.error('Cache scan polling error:', error);
                    scanError = error.message;

                    // Show error
                    await showAlert('Scan Failed', `Cache scan failed: ${error.message}`);
                    scanModal.classList.add('hidden');
                    cacheScanButton.disabled = false;
                    cacheScanButton.textContent = '📦 Scan with Cached Data Only';
                    break;
                }
            }
        };

        // Start polling
        pollCacheScanProgress();

    } catch (error) {
        console.error('Cache scan error:', error);
        await showAlert('Scan Failed', error.message);
        scanModal.classList.add('hidden');
        cacheScanButton.disabled = false;
        cacheScanButton.textContent = '📦 Scan with Cached Data Only';
    }
});

// Polygon Management Functions
document.addEventListener('DOMContentLoaded', function () {
    loadSavedPolygons();

    // Show/hide save polygon controls when polygon is created/completed
    const observer = new MutationObserver(function (mutations) {
        const saveBtn = document.getElementById('savePolygonBtn');
        const nameInput = document.getElementById('polygonNameInput');

        if (drawnPolygon && polygonPins.length >= 3) {
            saveBtn.style.display = 'inline-block';
        } else {
            saveBtn.style.display = 'none';
            nameInput.style.display = 'none';
        }
    });

    observer.observe(document.getElementById('statusMessage'), {
        childList: true,
        subtree: true
    });
});

document.getElementById('savePolygonBtn').addEventListener('click', function () {
    const nameInput = document.getElementById('polygonNameInput');
    if (nameInput.style.display === 'none') {
        nameInput.style.display = 'block';
        nameInput.focus();
    } else {
        saveCurrentPolygon();
    }
});

document.getElementById('polygonNameInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        saveCurrentPolygon();
    }
});

async function loadSavedPolygons() {
    try {
        const response = await fetch('/api/polygons');
        if (response.ok) {
            const data = await response.json();
            displaySavedPolygons(data.polygons);
        }
    } catch (error) {
        console.error('Error loading saved polygons:', error);
    }
}

function displaySavedPolygons(polygons) {
    const container = document.getElementById('savedPolygonsList');

    if (polygons.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500 italic">No saved polygons yet</p>';
        return;
    }

    container.innerHTML = polygons.map(polygon => `
        <div class="flex items-center justify-between bg-slate-800 rounded px-3 py-2">
            <span class="text-sm text-slate-300 flex-1">${polygon.name}</span>
            <div class="flex gap-1">
                <button class="text-xs bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded text-white"
                        onclick="loadPolygon(${polygon.id}, '${polygon.name}')">
                    📥
                </button>
                <button class="text-xs bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-white"
                        onclick="deletePolygon(${polygon.id}, '${polygon.name}')">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

async function saveCurrentPolygon() {
    const nameInput = document.getElementById('polygonNameInput');
    const name = nameInput.value.trim();

    if (!name) {
        await showAlert('Name Required', 'Please enter a name for the polygon');
        return;
    }

    if (!drawnPolygon || polygonPins.length < 3) {
        await showAlert('Polygon Required', 'Please draw a polygon first');
        return;
    }

    const coordinates = polygonPins.map(pin => [pin[0], pin[1]]);

    try {
        const response = await fetch('/api/polygons', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                coordinates: coordinates
            })
        });

        if (response.ok) {
            await showAlert('Success', `Polygon "${name}" saved successfully!`);
            nameInput.value = '';
            nameInput.style.display = 'none';
            loadSavedPolygons(); // Refresh the list
        } else {
            const error = await response.json();
            await showAlert('Save Failed', 'Failed to save polygon: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving polygon:', error);
        await showAlert('Error', 'Failed to save polygon: ' + error.message);
    }
}

async function loadPolygon(polygonId, name) {
    try {
        const response = await fetch('/api/polygons');
        if (!response.ok) return;

        const data = await response.json();
        const polygon = data.polygons.find(p => p.id === polygonId);

        if (!polygon) {
            await showAlert('Error', 'Polygon not found');
            return;
        }

        // Clear current polygon and pins
        clearCurrentPolygon();

        // Load the saved coordinates as pins
        polygonPins = polygon.coordinates.map(coord => [coord[0], coord[1]]);

        // Add markers to pinMarkers group (same as original pin placement)
        polygonPins.forEach((pin, index) => {
            const marker = L.marker(pin, {
                draggable: true,
                icon: L.divIcon({
                    className: 'pin-marker',
                    html: `<div style="background: #3b82f6; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-weight: bold; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${index + 1}</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                })
            });

            // Handle drag end - same logic as original
            marker.on('dragend', function () {
                // Rebuild polygonPins from all markers (after drag)
                polygonPins = [];
                pinMarkerMap.clear();
                let markerIndex = 0;
                pinMarkers.eachLayer(function (marker) {
                    const latlng = marker.getLatLng();
                    polygonPins.push([latlng.lat, latlng.lng]);
                    pinMarkerMap.set(marker, markerIndex);
                    markerIndex++;
                });

                // Update polygon if it exists
                if (drawnPolygon && polygonPins.length >= 3) {
                    drawnLayer.clearLayers();
                    const updatedPolygon = L.polygon(polygonPins, {
                        color: '#3b82f6',
                        weight: 2,
                        opacity: 1,
                        fillColor: '#3b82f6',
                        fillOpacity: 0.1
                    });
                    drawnLayer.addLayer(updatedPolygon);
                    drawnPolygon = updatedPolygon;
                }
            });

            // Handle click to remove pin
            marker.on('click', function () {
                removePin(marker);
            });

            pinMarkers.addLayer(marker);
            pinMarkerMap.set(marker, index);
        });

        // Create polygon
        if (polygonPins.length >= 3) {
            const leafletPolygon = L.polygon(polygonPins, {
                color: '#3b82f6',
                weight: 2,
                opacity: 1,
                fillColor: '#3b82f6',
                fillOpacity: 0.1
            });
            drawnLayer.addLayer(leafletPolygon);
            drawnPolygon = leafletPolygon;
        }

        // Update UI
        const statusMsg = document.getElementById('statusMessage');
        statusMsg.textContent = `Polygon "${name}" loaded with ${polygonPins.length} points. Click "Start Scan" to begin.`;
        statusMsg.classList.remove('hidden');

        // Show scan button
        document.getElementById('scanButton').style.display = 'block';

        await showAlert('Success', `Polygon "${name}" loaded successfully!`);

    } catch (error) {
        console.error('Error loading polygon:', error);
        await showAlert('Error', 'Failed to load polygon: ' + error.message);
    }
}

async function deletePolygon(polygonId, name) {
    const confirmed = await showConfirm(
        'Delete Polygon',
        `Are you sure you want to delete the polygon "${name}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
        const response = await fetch(`/api/polygons/${polygonId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await showAlert('Success', `Polygon "${name}" deleted successfully!`);
            loadSavedPolygons(); // Refresh the list
        } else {
            const error = await response.json();
            await showAlert('Delete Failed', 'Failed to delete polygon: ' + (error.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting polygon:', error);
        await showAlert('Error', 'Failed to delete polygon: ' + error.message);
    }
}

function clearCurrentPolygon() {
    // Clear existing polygon and pins
    if (drawnPolygon) {
        drawnLayer.removeLayer(drawnPolygon);
        drawnPolygon = null;
    }

    // Remove all markers
    drawnLayer.eachLayer(layer => {
        if (layer instanceof L.Marker) {
            drawnLayer.removeLayer(layer);
        }
    });

    polygonPins = [];
    pinMarkerMap.clear();

    // Hide complete button if it exists
    const completeBtn = document.querySelector('button[style*="Complete Polygon"]');
    if (completeBtn) {
        completeBtn.style.display = 'none';
    }

    // Hide save button
    document.getElementById('savePolygonBtn').style.display = 'none';
    document.getElementById('polygonNameInput').style.display = 'none';
    document.getElementById('polygonNameInput').value = '';
}

// Load latest scan points to populate the map on refresh
document.addEventListener('DOMContentLoaded', () => {
    // Determine if we should load points (only if map is present)
    if (document.getElementById('map')) {
        loadLatestScanPoints();
    }
});

async function loadLatestScanPoints() {
    try {
        const response = await fetch('/api/dashboard/points?limit=1000');
        if (response.ok) {
            const data = await response.json();
            const points = data.points || [];
            if (points.length > 0) {
                // Add markers to map
                points.forEach(point => {
                    // Determine color based on rank
                    let color = '#ef4444'; // Red for > 10 or not found
                    if (point.display_rank) {
                        if (point.display_rank <= 3) color = '#facc15'; // Gold
                        else if (point.display_rank <= 10) color = '#22c55e'; // Green
                    } else if (point.status === 'not_found' || !point.display_rank) {
                        color = '#94a3b8'; // Grey for valid search but no rank
                    } else if (point.status === 'error') {
                        color = '#ef4444'; // Red for error
                    }

                    const marker = L.circleMarker([point.lat, point.lon], {
                        radius: 8,
                        fillColor: color,
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    }).addTo(map);

                    // Add popup
                    const rankText = point.display_rank ? `#${point.display_rank}` : (point.status === 'error' ? 'Error' : 'Not Found');
                    const popupContent = `
                         <div class="p-2">
                             <div class="font-bold mb-1">${point.keyword}</div>
                             <div class="text-sm mb-1">${point.city || ''}</div>
                             <div class="text-sm">Rank: <span class="font-bold" style="color: ${color}">${rankText}</span></div>
                             <div class="text-xs text-gray-500 mt-1">${new Date(point.scan_date).toLocaleDateString()}</div>
                         </div>
                     `;
                    marker.bindPopup(popupContent);

                    markers.push(marker);
                });

                // Fit bounds to show all markers
                if (markers.length > 0) {
                    const group = new L.featureGroup(markers);
                    map.fitBounds(group.getBounds().pad(0.1));
                }
            }
        }
    } catch (error) {
        console.error('Error loading latest points:', error);
    }
}
