// Competitors Dashboard JavaScript

let allCompetitors = [];
let selectedCompetitor = null;
let currentSortColumn = 'dominance';
let currentSortDirection = 'desc';
let currentFilterType = 'all';
let currentCity = '';
let competitorChart = null;

// Escape HTML helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Convert dominance score to text label
function dominanceScoreToLabel(score) {
    if (score === undefined || score === null) return '—';

    if (score >= 2.0) return 'Strong';
    if (score >= 1.5) return 'Moderate-Strong';
    if (score >= 1.0) return 'Moderate';
    if (score >= 0.5) return 'Present';
    return 'Weak';
}

// Create tooltip HTML
function createTooltip(label, explanation) {
    return `
        <span class="tooltip">
            ${escapeHtml(label)}
            <span class="help-icon" title="Click for help">?</span>
            <span class="tooltip-content">${escapeHtml(explanation)}</span>
        </span>
    `;
}

// Metric explanations
const metricExplanations = {
    'avg_rank': 'Average ranking position when the competitor appears in results. Lower is better (1 = best position, 30 = worst).',
    'dominance': 'Dominance: Measures competitive strength (Strong, Moderate-Strong, Moderate, Present, Weak). Formula: (Top 3 appearances × 3 + Top 10 × 2 + Top 30 × 1) ÷ Total appearances.',
    'consistency': 'Standard deviation of ranks. Lower values mean more stable rankings. A consistency of 2.0 means ranks typically vary by ±2 positions.',
    'trend': 'Growth trend comparing recent vs older rankings: ↑ Improving (ranks getting better), ↓ Declining (ranks worsening), → Stable (little change).',
    'classification': 'Competitor classification: Falling Giant (high dominance, declining), Growing Giant (high dominance, improving), Emerging (low dominance but improving), Stable Leader (high dominance, stable, consistent).',
    'coverage': 'Percentage of scanned locations where this competitor appears at least once in the top 30 search results.',
    'best_worst_rank': 'Best and worst ranking positions for this competitor in the selected city. Format: Best / Worst',
    'keywords': 'Number of different keywords where this competitor appears in the selected city.',
    'total_locations': 'Total number of unique scanned locations where this competitor appears across all keywords and cities.',
    'dominance_score': 'Dominance: Measures how well a competitor ranks (Strong ≥2.0, Moderate-Strong ≥1.5, Moderate ≥1.0, Present ≥0.5, Weak <0.5). Higher values indicate better average positioning.'
};

// Load project keywords and display them
async function loadProjectKeywords() {
    try {
        const response = await fetch('/api/projects/current');
        if (response.ok) {
            const project = await response.json();
            const keywords = project.keywords || [];

            const keywordsDisplay = document.getElementById('keywordsDisplay');
            const keywordsList = document.getElementById('keywordsList');

            if (keywords.length > 0) {
                keywordsList.innerHTML = '';
                keywords.forEach(keyword => {
                    const badge = document.createElement('span');
                    badge.className = 'badge';
                    badge.style.background = '#3b82f6';
                    badge.style.color = 'white';
                    badge.textContent = keyword;
                    keywordsList.appendChild(badge);
                });
                keywordsDisplay.style.display = 'block';
            } else {
                keywordsDisplay.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading project keywords:', error);
    }
}

// Load available cities
async function loadCities() {
    try {
        const response = await fetch('/api/competitors/cities');
        if (!response.ok) {
            throw new Error('Failed to load cities');
        }

        const data = await response.json();
        const cities = data.cities || [];

        const citySelect = document.getElementById('filterCity');
        // Keep the "All Cities" option
        citySelect.innerHTML = '<option value="">All Cities (Global View)</option>';

        cities.forEach(city => {
            const option = document.createElement('option');
            option.value = city;
            option.textContent = city;
            citySelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading cities:', error);
    }
}

// Load competitors overview
async function loadCompetitorsOverview(filterType = 'all', city = '') {
    try {
        let url;
        let data;

        // If city is selected, load city-specific data
        if (city) {
            url = `/api/competitors/by-city?city=${encodeURIComponent(city)}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to load city competitors');
            }
            data = await response.json();
            allCompetitors = data.competitors || [];

            // Update title
            document.getElementById('cityFilterLabel').textContent = `in ${city}`;

            // Apply filter type if not 'all'
            if (filterType !== 'all') {
                // For city view, we'll show all but indicate classification
                // (classification is global, so we show all competitors in city)
            }
        } else {
            // Global view
            url = '/api/competitors/overview';
            if (filterType !== 'all') {
                url = `/api/competitors/by-type?type=${encodeURIComponent(filterType)}`;
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to load competitors');
            }

            data = await response.json();
            allCompetitors = data.competitors || [];

            // Update title
            document.getElementById('cityFilterLabel').textContent = '';
        }

        // Apply sorting
        sortCompetitors(currentSortColumn, currentSortDirection);

        // Update count and table headers
        const isCityView = city !== '';
        document.getElementById('competitorCount').textContent = `${allCompetitors.length} competitors`;

        // Ensure table headers are updated with tooltips
        updateTableHeaders(isCityView);

        // Render table with correct view mode
        renderCompetitorsTable(isCityView);
    } catch (error) {
        console.error('Error loading competitors:', error);
        const colspan = currentCity ? 8 : 10;
        document.getElementById('competitorsTableBody').innerHTML =
            `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: #ef4444;">Error loading competitors: ${escapeHtml(error.message)}</td></tr>`;
    }
}

// Sort competitors
function sortCompetitors(column, direction) {
    const sortFunctions = {
        'name': (a, b) => a.name.localeCompare(b.name),
        'avg_rank': (a, b) => (a.avg_rank || 999) - (b.avg_rank || 999),
        'dominance': (a, b) => a.dominance_score - b.dominance_score,
        'consistency': (a, b) => a.consistency - b.consistency,
        'coverage': (a, b) => a.coverage - b.coverage
    };

    const sortFunc = sortFunctions[column] || sortFunctions['dominance'];

    allCompetitors.sort((a, b) => {
        const result = sortFunc(a, b);
        return direction === 'asc' ? result : -result;
    });
}

// Render competitors table
function renderCompetitorsTable(isCityView = false) {
    const tbody = document.getElementById('competitorsTableBody');
    tbody.innerHTML = '';

    if (allCompetitors.length === 0) {
        const colspan = isCityView ? 8 : 10;
        tbody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: #94a3b8;">No competitors found</td></tr>`;
        return;
    }

    allCompetitors.forEach((competitor, index) => {
        const row = document.createElement('tr');

        // Trend indicator (only in global view)
        let trendCell = '—';
        if (!isCityView && competitor.growth_trend) {
            const trendIcon = competitor.growth_trend === 'improving' ? '↑' :
                competitor.growth_trend === 'declining' ? '↓' : '→';
            const trendClass = competitor.growth_trend === 'improving' ? 'trend-up' :
                competitor.growth_trend === 'declining' ? 'trend-down' : 'trend-stable';
            trendCell = `<span class="${trendClass}">${trendIcon} ${competitor.trend_change > 0 ? '+' : ''}${competitor.trend_change ? competitor.trend_change.toFixed(2) : '0.00'}</span>`;
        }

        // Classification badge (only in global view)
        let classificationCell = '—';
        if (!isCityView && competitor.classification) {
            const classificationLabels = {
                'falling-giant': 'Falling Giant',
                'growing-giant': 'Growing Giant',
                'emerging': 'Emerging',
                'stable-leader': 'Stable Leader',
                'other': 'Other'
            };
            const classificationClass = competitor.classification || 'other';
            const classificationLabel = classificationLabels[classificationClass] || 'Other';
            classificationCell = `<span class="badge ${classificationClass}">${classificationLabel}</span>`;
        }

        // Consistency (only in global view)
        let consistencyCell = '—';
        if (!isCityView && competitor.consistency !== undefined) {
            consistencyCell = competitor.consistency.toFixed(2);
        }

        // Coverage (only in global view)
        let coverageCell = '—';
        if (!isCityView && competitor.coverage !== undefined) {
            coverageCell = competitor.coverage.toFixed(1) + '%';
        }

        // Best/Worst rank (only in city view)
        let bestWorstCell = '';
        if (isCityView) {
            if (competitor.best_rank && competitor.worst_rank) {
                bestWorstCell = `${competitor.best_rank} / ${competitor.worst_rank}`;
            } else if (competitor.best_rank) {
                bestWorstCell = competitor.best_rank.toString();
            } else {
                bestWorstCell = '—';
            }
        }

        if (isCityView) {
            // City view: different columns
            row.innerHTML = `
                <td style="font-weight: 600;">${escapeHtml(competitor.name)}</td>
                <td>${competitor.avg_rank ? competitor.avg_rank.toFixed(1) : '—'}</td>
                <td>${bestWorstCell}</td>
                <td>${dominanceScoreToLabel(competitor.dominance_score)}</td>
                <td>${competitor.category ? escapeHtml(competitor.category) : '<span style="color:#94a3b8">—</span>'}</td>
                <td>${competitor.address ? escapeHtml(competitor.address) : '<span style="color:#94a3b8">—</span>'}</td>
                <td>
                    ${competitor.phone_number ? `<div>📞 ${escapeHtml(competitor.phone_number)}</div>` : ''}
                    ${competitor.website ? `<div>🌐 <a href="${competitor.website}" target="_blank" style="color:#3b82f6;text-decoration:none;">Website</a></div>` : ''}
                    ${!competitor.phone_number && !competitor.website ? '<span style="color:#94a3b8">—</span>' : ''}
                </td>
            `;
        } else {
            // Global view: original columns
            row.innerHTML = `
                <td style="font-weight: 600;">${escapeHtml(competitor.name)}</td>
                <td>${competitor.avg_rank ? competitor.avg_rank.toFixed(1) : '—'}</td>
                <td>${dominanceScoreToLabel(competitor.dominance_score)}</td>
                <td>${consistencyCell}</td>
                <td>${trendCell}</td>
                <td>${classificationCell}</td>
                <td>${coverageCell}</td>
            `;
        }

        // Click handler to show details
        row.addEventListener('click', () => {
            selectedCompetitor = competitor.name;
            loadCompetitorDetails(competitor.name);
        });

        tbody.appendChild(row);
    });
}

// Load competitor trends
async function loadCompetitorTrends(competitorName) {
    try {
        const response = await fetch(`/api/competitors/${encodeURIComponent(competitorName)}/trends`);
        if (!response.ok) {
            throw new Error('Failed to load trends');
        }

        const data = await response.json();
        const trends = data.trends || [];

        if (trends.length === 0) {
            return null;
        }

        return trends;
    } catch (error) {
        console.error('Error loading trends:', error);
        return null;
    }
}

// Load competitor details
async function loadCompetitorDetails(competitorName) {
    try {
        // Show detail section
        const detailSection = document.getElementById('competitorDetailSection');
        detailSection.style.display = 'block';
        document.getElementById('selectedCompetitorName').textContent = competitorName;

        // Load trends
        const trends = await loadCompetitorTrends(competitorName);
        if (trends) {
            renderTrendChart(competitorName, trends);
        }

        // Load detailed breakdown
        const response = await fetch(`/api/competitors/${encodeURIComponent(competitorName)}/details`);
        if (!response.ok) {
            throw new Error('Failed to load details');
        }

        const data = await response.json();

        // Update metrics
        const metricsDiv = document.getElementById('competitorMetrics');
        const competitor = allCompetitors.find(c => c.name === competitorName);

        // Safely format values
        const dominanceDisplay = dominanceScoreToLabel(competitor ? competitor.dominance_score : undefined);
        const consistencyDisplay = (competitor && competitor.consistency !== undefined) ? competitor.consistency.toFixed(2) : '—';
        const coverageDisplay = (competitor && competitor.coverage !== undefined) ? competitor.coverage.toFixed(1) + '%' : '—';

        metricsDiv.innerHTML = `
            <div style="padding: 8px; background: #334155; border-radius: 6px;">
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;">
                    ${createTooltip('Dominance', metricExplanations.dominance_score)}
                </div>
                <div style="font-size: 20px; font-weight: 700; color: #3b82f6;">${dominanceDisplay}</div>
            </div>
            <div style="padding: 8px; background: #334155; border-radius: 6px;">
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;">
                    ${createTooltip('Consistency', metricExplanations.consistency)}
                </div>
                <div style="font-size: 20px; font-weight: 700; color: #f59e0b;">${consistencyDisplay}</div>
            </div>
            <div style="padding: 8px; background: #334155; border-radius: 6px;">
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;">
                    ${createTooltip('Coverage', metricExplanations.coverage)}
                </div>
                <div style="font-size: 20px; font-weight: 700; color: #8b5cf6;">${coverageDisplay}</div>
            </div>
        `;

        // Setup tooltip handlers for newly added metrics
        setTimeout(() => setupTooltipHandlers(), 100);

        // Render keyword breakdown
        const keywordBody = document.getElementById('keywordBreakdownBody');
        keywordBody.innerHTML = '';

        if (data.keyword_breakdown && data.keyword_breakdown.length > 0) {
            data.keyword_breakdown.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${escapeHtml(item.keyword)}</td>
                    <td>${item.avg_rank ? item.avg_rank.toFixed(1) : '—'}</td>
                    <td>${item.appearances}</td>
                    <td>${item.unique_locations}</td>
                `;
                keywordBody.appendChild(row);
            });
        } else {
            keywordBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #94a3b8;">No keyword data available</td></tr>';
        }

        // Render city breakdown
        const cityBody = document.getElementById('cityBreakdownBody');
        cityBody.innerHTML = '';

        if (data.city_breakdown && data.city_breakdown.length > 0) {
            data.city_breakdown.forEach(item => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${escapeHtml(item.city)}</td>
                    <td>${item.avg_rank ? item.avg_rank.toFixed(1) : '—'}</td>
                    <td>${item.appearances}</td>
                    <td>${item.unique_locations}</td>
                `;
                cityBody.appendChild(row);
            });
        } else {
            cityBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #94a3b8;">No city data available</td></tr>';
        }

        // Scroll to detail section
        detailSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (error) {
        console.error('Error loading competitor details:', error);
        const tbody = document.getElementById('competitorDetailSection');
        if (tbody) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'card';
            errorDiv.style.background = '#7f1d1d';
            errorDiv.style.color = '#fca5a5';
            errorDiv.style.padding = '16px';
            errorDiv.textContent = 'Failed to load competitor details: ' + error.message;
            document.getElementById('competitorDetailSection').appendChild(errorDiv);
        }
    }
}

// Render trend chart
function renderTrendChart(competitorName, trends) {
    const ctx = document.getElementById('competitorTrendChart');
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (competitorChart) {
        competitorChart.destroy();
    }

    const labels = trends.map(t => {
        const date = new Date(t.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const rankData = trends.map(t => t.avg_rank);

    competitorChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Average Rank',
                data: rankData,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4,
                spanGaps: true,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
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
}

// Update table headers based on view mode
function updateTableHeaders(isCityView) {
    const thead = document.getElementById('competitorsTableHead');
    if (!thead) return;

    const tr = thead.querySelector('tr');
    if (!tr) return;

    if (isCityView) {
        tr.innerHTML = `
            <th data-sort="name">Name</th>
            <th data-sort="avg_rank">${createTooltip('Avg Rank', metricExplanations.avg_rank)}</th>
            <th>${createTooltip('Best / Worst Rank', metricExplanations.best_worst_rank)}</th>
            <th data-sort="dominance">${createTooltip('Dominance', metricExplanations.dominance)}</th>
            <th>Category</th>
            <th>Address</th>
            <th>Contact</th>
        `;
    } else {
        tr.innerHTML = `
            <th data-sort="name">Name</th>
            <th data-sort="avg_rank">${createTooltip('Avg Rank', metricExplanations.avg_rank)}</th>
            <th data-sort="dominance">${createTooltip('Dominance', metricExplanations.dominance)}</th>
            <th data-sort="consistency">${createTooltip('Consistency', metricExplanations.consistency)}</th>
            <th data-sort="trend">${createTooltip('Trend', metricExplanations.trend)}</th>
            <th data-sort="classification">${createTooltip('Type', metricExplanations.classification)}</th>
            <th data-sort="coverage">${createTooltip('Coverage', metricExplanations.coverage)}</th>
        `;
    }

    // Re-attach sort handlers and tooltip handlers
    attachSortHandlers();
    // Need to call setupTooltipHandlers after a small delay to ensure DOM is ready
    setTimeout(() => setupTooltipHandlers(), 0);
}

// Apply filters
function applyFilters() {
    const filterType = document.getElementById('filterType').value;
    const sortBy = document.getElementById('sortBy').value;
    const city = document.getElementById('filterCity').value;

    currentFilterType = filterType;
    currentSortColumn = sortBy;
    currentCity = city;

    // Update table headers based on view (before loading data)
    const isCityView = !!city;
    updateTableHeaders(isCityView);

    loadCompetitorsOverview(filterType, city);
}

// Create or get tooltip content element in body (outside overflow containers)
let activeTooltipContent = null;
let activeTooltipTrigger = null;

function showTooltip(tooltip, explanation) {
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:showTooltip-entry', message: 'showTooltip called', data: { hasTooltip: !!tooltip, hasExplanation: !!explanation, explanationLength: explanation?.length }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch(() => { });
    // #endregion
    // Hide any existing tooltip
    hideTooltip();

    // Get trigger element position
    const rect = tooltip.getBoundingClientRect();
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:showTooltip-rect', message: 'Trigger rect calculated', data: { top: rect.top, left: rect.left, width: rect.width, height: rect.height, bottom: rect.bottom }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'D' }) }).catch(() => { });
    // #endregion

    // Create tooltip content element
    activeTooltipContent = document.createElement('div');
    activeTooltipContent.className = 'tooltip-content';
    activeTooltipContent.style.position = 'fixed';
    activeTooltipContent.style.zIndex = '99999';
    activeTooltipContent.style.visibility = 'visible';
    activeTooltipContent.style.opacity = '1';
    activeTooltipContent.style.width = '280px';
    activeTooltipContent.style.background = '#1e293b';
    activeTooltipContent.style.color = '#e2e8f0';
    activeTooltipContent.style.textAlign = 'left';
    activeTooltipContent.style.padding = '8px 12px';
    activeTooltipContent.style.borderRadius = '6px';
    activeTooltipContent.style.border = '1px solid #475569';
    activeTooltipContent.style.fontSize = '11px';
    activeTooltipContent.style.lineHeight = '1.5';
    activeTooltipContent.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.5)';
    activeTooltipContent.style.pointerEvents = 'none';
    activeTooltipContent.textContent = explanation;

    // Append to body (outside all overflow containers)
    document.body.appendChild(activeTooltipContent);
    activeTooltipTrigger = tooltip;
    // #region agent log
    fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:showTooltip-append', message: 'Tooltip appended to body', data: { parentTagName: activeTooltipContent.parentElement?.tagName, inBody: activeTooltipContent.parentElement === document.body, hasStyle: !!activeTooltipContent.style }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'B' }) }).catch(() => { });
    // #endregion

    // Position tooltip above the trigger
    const tooltipRect = activeTooltipContent.getBoundingClientRect();
    let top = rect.top - tooltipRect.height - 8; // 8px gap above
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

    // Adjust if tooltip goes off screen
    if (left < 10) left = 10; // Left edge
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10; // Right edge
    }

    // If tooltip would go above viewport, show below instead
    if (top < 10) {
        top = rect.bottom + 8;
    }

    activeTooltipContent.style.top = top + 'px';
    activeTooltipContent.style.left = left + 'px';
    // #region agent log
    const computedStyle = window.getComputedStyle(activeTooltipContent);
    fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:showTooltip-positioned', message: 'Tooltip positioned', data: { calculatedTop: top, calculatedLeft: left, computedPosition: computedStyle.position, computedZIndex: computedStyle.zIndex, computedVisibility: computedStyle.visibility, computedOpacity: computedStyle.opacity, computedDisplay: computedStyle.display, offsetParent: activeTooltipContent.offsetParent?.tagName }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'C,D' }) }).catch(() => { });
    // #endregion
}

function hideTooltip() {
    if (activeTooltipContent) {
        // #region agent log
        fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:hideTooltip', message: 'Hiding tooltip', data: { wasInBody: activeTooltipContent.parentElement === document.body }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'E' }) }).catch(() => { });
        // #endregion
        activeTooltipContent.remove();
        activeTooltipContent = null;
        activeTooltipTrigger = null;
    }
}

function positionTooltip(tooltip) {
    const tooltipContent = tooltip.querySelector('.tooltip-content');
    if (!tooltipContent) return;

    // Get explanation text
    const explanation = tooltipContent.textContent || tooltipContent.innerText;

    // Show tooltip using body-append method
    showTooltip(tooltip, explanation);
}

// Setup tooltip click handlers (use event delegation to avoid duplicate listeners)
let tooltipClickHandler = null;
let tooltipHoverHandler = null;

function setupTooltipHandlers() {
    // Remove old handlers if they exist
    if (tooltipClickHandler) {
        document.removeEventListener('click', tooltipClickHandler);
    }
    if (tooltipHoverHandler) {
        document.removeEventListener('mouseenter', tooltipHoverHandler, true);
    }

    // Position tooltips on hover for desktop
    document.querySelectorAll('.tooltip').forEach(tooltip => {
        const hoverHandler = function () {
            positionTooltip(tooltip);
        };
        tooltip.addEventListener('mouseenter', hoverHandler);
    });

    // Click handler for closing tooltips when clicking outside
    tooltipClickHandler = function (e) {
        if (!e.target.closest('.tooltip') && !e.target.closest('.tooltip-content')) {
            hideTooltip();
        }
    };

    if (tooltipClickHandler) {
        document.addEventListener('click', tooltipClickHandler);
    }

    // Setup hover and click handlers for tooltips
    document.querySelectorAll('.tooltip').forEach(tooltip => {
        const tooltipContent = tooltip.querySelector('.tooltip-content');
        if (!tooltipContent) return;

        const explanation = tooltipContent.textContent || tooltipContent.innerText;

        // Hover (desktop) - show tooltip
        tooltip.addEventListener('mouseenter', function () {
            // #region agent log
            fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:mouseenter', message: 'Mouseenter event fired', data: { tooltipExists: !!tooltip, hasExplanation: !!explanation }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch(() => { });
            // #endregion
            showTooltip(tooltip, explanation);
        });

        // Mouse leave - hide tooltip
        tooltip.addEventListener('mouseleave', function () {
            hideTooltip();
        });

        // Click (mobile) - toggle tooltip
        tooltip.querySelector('.help-icon')?.addEventListener('click', function (e) {
            e.stopPropagation();
            // #region agent log
            fetch('http://127.0.0.1:7245/ingest/e8f6d52f-48d2-46ac-ac77-f5c4a8315b3c', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ location: 'competitors.js:help-icon-click', message: 'Help icon clicked', data: { tooltipExists: !!tooltip, isActive: activeTooltipTrigger === tooltip }, timestamp: Date.now(), sessionId: 'debug-session', runId: 'run1', hypothesisId: 'A' }) }).catch(() => { });
            // #endregion
            if (activeTooltipTrigger === tooltip) {
                hideTooltip();
            } else {
                showTooltip(tooltip, explanation);
            }
        });
    });
}

// Table header click handler for sorting (will be re-attached by updateTableHeaders)
function attachSortHandlers() {
    const headers = document.querySelectorAll('#competitorsTable th[data-sort]');
    headers.forEach(header => {
        // Remove existing listeners by cloning
        const newHeader = header.cloneNode(true);
        header.parentNode.replaceChild(newHeader, header);

        // Add new listener
        newHeader.addEventListener('click', () => {
            const column = newHeader.getAttribute('data-sort');

            if (currentSortColumn === column) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortColumn = column;
                currentSortDirection = 'desc';
            }

            // Update sort dropdown
            const sortSelect = document.getElementById('sortBy');
            if (sortSelect) {
                sortSelect.value = column;
            }

            sortCompetitors(currentSortColumn, currentSortDirection);
            renderCompetitorsTable(currentCity !== '');
        });
    });
}

// Table header click handler for sorting
document.addEventListener('DOMContentLoaded', function () {
    attachSortHandlers();

    // Filter change handlers
    document.getElementById('filterType').addEventListener('change', applyFilters);
    document.getElementById('sortBy').addEventListener('change', applyFilters);
    document.getElementById('filterCity').addEventListener('change', applyFilters);

    // Close detail button
    document.getElementById('closeDetailBtn').addEventListener('click', () => {
        document.getElementById('competitorDetailSection').style.display = 'none';
        selectedCompetitor = null;
        if (competitorChart) {
            competitorChart.destroy();
            competitorChart = null;
        }
    });

    // Change project button
    document.getElementById('changeProjectBtn').addEventListener('click', () => {
        window.location.href = '/projects';
    });

    // Setup tooltip handlers
    setupTooltipHandlers();

    // Load keywords, cities and initial data
    loadProjectKeywords();
    loadCities().then(() => {
        loadCompetitorsOverview('all', '');
    });
});
