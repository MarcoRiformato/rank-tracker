// Dashboard JavaScript

let allPoints = [];
let currentKeywordFilter = '';
let rankDistributionChart = null;
let rankTrendsChart = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function () {
    loadKeywords();
    loadDashboardData();

    document.getElementById('applyFilters').addEventListener('click', applyFilters);
    document.getElementById('filterKeyword').addEventListener('change', function () {
        currentKeywordFilter = this.value;
        applyFilters();
    });

    // Change Project button handler
    document.getElementById('changeProjectBtn').addEventListener('click', function () {
        window.location.href = '/projects';
    });

    // Delete Data button and modal handlers
    document.getElementById('deleteDataBtn').addEventListener('click', showDeleteModal);
    document.getElementById('cancelDeleteBtn').addEventListener('click', hideDeleteModal);
    document.getElementById('confirmDeleteBtn').addEventListener('click', showConfirmModal);
    document.getElementById('cancelFinalDeleteBtn').addEventListener('click', hideConfirmModal);
    document.getElementById('finalDeleteBtn').addEventListener('click', performDelete);
});

async function loadKeywords() {
    try {
        // Load unique keywords from the data
        const response = await fetch('/api/dashboard/keywords');
        if (response.ok) {
            const data = await response.json();
            const keywords = data.keywords || [];
            const select = document.getElementById('filterKeyword');

            // Clear existing options except "All Keywords"
            select.innerHTML = '<option value="">All Keywords</option>';

            // Add keywords to dropdown
            keywords.forEach(keyword => {
                const option = document.createElement('option');
                option.value = keyword;
                option.textContent = keyword;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading keywords:', error);
    }
}

async function loadDashboardData() {
    try {
        // Build query parameters
        const params = new URLSearchParams();
        if (currentKeywordFilter) {
            params.append('keyword', currentKeywordFilter);
        }

        // Load aggregates
        const aggUrl = '/api/dashboard/aggregates' + (params.toString() ? '?' + params.toString() : '');
        const aggResponse = await fetch(aggUrl);
        const aggData = await aggResponse.json();

        // Update summary cards with SEO metrics (always have content to prevent card collapse)
        const top3Text = aggData.top3_coverage !== undefined && aggData.top3_coverage !== null ? `${aggData.top3_coverage.toFixed(1)}%` : '0%';
        const top10Text = aggData.top10_coverage !== undefined && aggData.top10_coverage !== null ? `${aggData.top10_coverage.toFixed(1)}%` : '0%';
        const localPackText = aggData.local_pack_presence !== undefined && aggData.local_pack_presence !== null ? `${aggData.local_pack_presence.toFixed(1)}%` : '0%';
        const avgRankText = aggData.avg_rank !== undefined && aggData.avg_rank !== null ? aggData.avg_rank.toFixed(1) : '—';

        document.getElementById('top3Coverage').textContent = top3Text;
        document.getElementById('top10Coverage').textContent = top10Text;
        document.getElementById('localPackPresence').textContent = localPackText;
        document.getElementById('avgRank').textContent = avgRankText;

        // Load scheduled scans
        const scheduledResponse = await fetch('/api/scheduled-scans');
        const scheduledData = await scheduledResponse.json();
        renderScheduledScans(scheduledData.scans || []);

        // Load points
        const pointsUrl = '/api/dashboard/points' + (params.toString() ? '?' + params.toString() : '');
        const pointsResponse = await fetch(pointsUrl);
        const pointsData = await pointsResponse.json();
        allPoints = pointsData.points || [];

        // Filter points by date range and render table
        const filteredPoints = filterPointsByDate(allPoints);
        renderFilteredPointsTable(filteredPoints);

        // Render charts
        renderRankDistributionChart(aggData);
        renderRankTrendsChart(aggData);

    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function renderPointsTable() {
    const filteredPoints = filterPointsByDate(allPoints);
    renderFilteredPointsTable(filteredPoints);
}

function getRankBadge(rank) {
    if (rank === null || rank === undefined) {
        return '<span class="badge red">Not Found</span>';
    }
    if (rank >= 1 && rank <= 3) {
        return `<span class="badge gold">${rank}</span>`;
    } else if (rank >= 4 && rank <= 10) {
        return `<span class="badge green">${rank}</span>`;
    } else if (rank >= 11 && rank <= 20) {
        return `<span class="badge yellow">${rank}</span>`;
    } else if (rank >= 21 && rank <= 30) {
        return `<span class="badge orange">${rank}</span>`;
    } else {
        return `<span class="badge red">${rank}</span>`;
    }
}

function renderRankDistributionChart(data) {
    const ctx = document.getElementById('rankDistributionChart');
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (rankDistributionChart) {
        rankDistributionChart.destroy();
    }

    const distribution = data.rank_distribution || {};

    rankDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Rank 1-3', 'Rank 4-10', 'Rank 11-20', 'Rank 21-30', 'Not Found'],
            datasets: [{
                data: [
                    distribution['1-3'] || 0,
                    distribution['4-10'] || 0,
                    distribution['11-20'] || 0,
                    distribution['21-30'] || 0,
                    distribution['not_found'] || 0
                ],
                backgroundColor: ['#FFD700', '#22c55e', '#eab308', '#f97316', '#ef4444']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function renderRankTrendsChart(data) {
    const ctx = document.getElementById('rankTrendsChart');
    if (!ctx) return;

    // Destroy existing chart if it exists
    if (rankTrendsChart) {
        rankTrendsChart.destroy();
    }

    const trends = data.rank_trends || { dates: [], avg_local_pack: [], avg_organic: [] };

    rankTrendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: (trends.dates || []).map(d => new Date(d).toLocaleDateString()),
            datasets: [
                {
                    label: 'Avg Local Pack',
                    data: trends.avg_local_pack || [],
                    borderColor: '#FFD700',
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                    tension: 0.4,
                    spanGaps: true
                },
                {
                    label: 'Avg Organic',
                    data: trends.avg_organic || [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    spanGaps: true
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    reverse: true,
                    title: {
                        display: true,
                        text: 'Rank'
                    }
                }
            }
        }
    });
}

function renderScheduledScans(scans) {
    const container = document.getElementById('scheduledScansContainer');
    if (scans.length === 0) {
        container.innerHTML = '<p class="text-slate-400 text-sm">No scheduled scans yet.</p>';
        return;
    }

    let html = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;"><thead><tr>';
    html += '<th style="padding: 8px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; color: #94a3b8; background: #334155; border-bottom: 2px solid #475569;">Name</th>';
    html += '<th style="padding: 8px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; color: #94a3b8; background: #334155; border-bottom: 2px solid #475569;">Frequency</th>';
    html += '<th style="padding: 8px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; color: #94a3b8; background: #334155; border-bottom: 2px solid #475569;">Next Run</th>';
    html += '<th style="padding: 8px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; color: #94a3b8; background: #334155; border-bottom: 2px solid #475569;">Status</th>';
    html += '<th style="padding: 8px; text-align: left; font-weight: 600; font-size: 10px; text-transform: uppercase; color: #94a3b8; background: #334155; border-bottom: 2px solid #475569;">Actions</th>';
    html += '</tr></thead><tbody>';

    scans.forEach(scan => {
        const nextRun = new Date(scan.next_run_date);
        const statusBadge = scan.is_active ? '<span class="badge green">Active</span>' : '<span class="badge red">Inactive</span>';
        html += `<tr style="border-bottom: 1px solid #334155;">`;
        html += `<td style="padding: 8px; color: #cbd5e1;">${escapeHtml(scan.name)}</td>`;
        html += `<td style="padding: 8px; color: #cbd5e1;">${scan.frequency}</td>`;
        html += `<td style="padding: 8px; color: #cbd5e1;">${nextRun.toLocaleDateString()}</td>`;
        html += `<td style="padding: 8px;">${statusBadge}</td>`;
        html += `<td style="padding: 8px;"><button onclick="deleteScheduledScan(${scan.id})" class="text-red-400 hover:text-red-300 text-xs bg-transparent border-none cursor-pointer">Delete</button></td>`;
        html += `</tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

async function deleteScheduledScan(scanId) {
    if (!confirm('Are you sure you want to delete this scheduled scan?')) return;

    try {
        const response = await fetch(`/api/scheduled-scans/${scanId}`, { method: 'DELETE' });
        if (response.ok) {
            loadDashboardData();
        }
    } catch (error) {
        console.error('Error deleting scheduled scan:', error);
    }
}

function applyFilters() {
    // Get filter values
    const keyword = document.getElementById('filterKeyword').value;

    // Store keyword filter
    currentKeywordFilter = keyword;

    // Reload all data with filters applied
    loadDashboardData();
}

function filterPointsByDate(points) {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;

    let filteredPoints = points;

    if (dateFrom) {
        filteredPoints = filteredPoints.filter(point => {
            if (!point.scan_date) return false;
            const pointDate = new Date(point.scan_date); // This parses ISO string
            // Create date object from input string "YYYY-MM-DD" and set to midnight local time
            const dateFromParts = dateFrom.split('-');
            const dateFromObj = new Date(dateFromParts[0], dateFromParts[1] - 1, dateFromParts[2]);

            // Compare timestamps
            return pointDate.getTime() >= dateFromObj.getTime();
        });
    }

    if (dateTo) {
        filteredPoints = filteredPoints.filter(point => {
            const pointDate = new Date(point.scan_date);
            const toDate = new Date(dateTo);
            toDate.setHours(23, 59, 59, 999); // Include entire day
            return pointDate <= toDate;
        });
    }

    return filteredPoints;
}

function renderFilteredPointsTable(points) {
    const tbody = document.getElementById('pointsTableBody');
    tbody.innerHTML = '';

    if (points.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="6" class="text-center text-slate-400 py-4">No points found</td>';
        tbody.appendChild(row);
        return;
    }

    // Group points by city
    const groupedByCity = {};
    points.forEach(point => {
        const cityKey = point.city || `Coordinates: ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`;
        if (!groupedByCity[cityKey]) {
            groupedByCity[cityKey] = [];
        }
        groupedByCity[cityKey].push(point);
    });

    // Sort cities alphabetically
    const sortedCities = Object.keys(groupedByCity).sort();

    // Render grouped data as SINGLE ROWS per city
    sortedCities.forEach(city => {
        const cityPoints = groupedByCity[city];

        // Calculate aggregated statistics
        const pointCount = cityPoints.length;
        const keywordCount = new Set(cityPoints.map(p => p.keyword)).size;
        const keywords = [...new Set(cityPoints.map(p => p.keyword))].join(', ');

        // Calculate average ranks (only for non-null values)
        const localPackRanks = cityPoints.filter(p => p.local_pack_rank !== null).map(p => p.local_pack_rank);
        const organicRanks = cityPoints.filter(p => p.organic_rank !== null).map(p => p.organic_rank);
        const displayRanks = cityPoints.filter(p => p.display_rank !== null).map(p => p.display_rank);

        const avgLocalPack = localPackRanks.length > 0
            ? Math.round(localPackRanks.reduce((a, b) => a + b, 0) / localPackRanks.length)
            : null;
        const avgOrganic = organicRanks.length > 0
            ? Math.round(organicRanks.reduce((a, b) => a + b, 0) / organicRanks.length)
            : null;
        const avgDisplay = displayRanks.length > 0
            ? Math.round(displayRanks.reduce((a, b) => a + b, 0) / displayRanks.length)
            : null;

        // Get most recent date
        const mostRecentDate = new Date(Math.max(...cityPoints.map(p => new Date(p.scan_date))));

        // Create single aggregated row for this city
        const row = document.createElement('tr');
        row.style.cursor = 'pointer';
        row.className = 'city-group-row';

        const localPackBadge = getRankBadge(avgLocalPack);
        const organicBadge = getRankBadge(avgOrganic);
        const displayBadge = getRankBadge(avgDisplay);

        // Trend Calculation
        // distinct scan dates, sorted descending (newest first)
        const scanDates = [...new Set(cityPoints.map(p => p.scan_date.split('T')[0]))].sort().reverse();

        let trendBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">New</span>';

        if (scanDates.length >= 2) {
            const latestDate = scanDates[0];
            const previousDate = scanDates[1];

            const latestPoints = cityPoints.filter(p => p.scan_date.startsWith(latestDate) && p.display_rank !== null);
            const previousPoints = cityPoints.filter(p => p.scan_date.startsWith(previousDate) && p.display_rank !== null);

            if (latestPoints.length > 0 && previousPoints.length > 0) {
                const latestAvg = latestPoints.reduce((sum, p) => sum + p.display_rank, 0) / latestPoints.length;
                const previousAvg = previousPoints.reduce((sum, p) => sum + p.display_rank, 0) / previousPoints.length;

                const diff = previousAvg - latestAvg; // Positive means rank got smaller (better)

                if (diff > 0.1) {
                    trendBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                        <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z" clip-rule="evenodd"/></svg>
                        +${diff.toFixed(1)}
                    </span>`;
                } else if (diff < -0.1) {
                    trendBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                        <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M12 13a1 1 0 110 2H7a1 1 0 01-1-1v-5a1 1 0 112 0v2.586l4.293-4.293a1 1 0 011.414 0L16 9.586l4.293-4.293a1 1 0 011.414 1.414l-5 5a1 1 0 01-1.414 0L13 9.414 9.414 13H12z" clip-rule="evenodd"/></svg>
                        ${diff.toFixed(1)}
                    </span>`;
                } else {
                    trendBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">Stable</span>';
                }
            }
        }

        row.innerHTML = `
            <td class="text-sm font-semibold">📍 ${escapeHtml(city)} <span style="font-weight: normal; opacity: 0.7; font-size: 11px;">(${pointCount} ${pointCount === 1 ? 'pt' : 'pts'})</span></td>
            <td style="font-size: 11px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(keywords)}">${escapeHtml(keywords)}</td>
            <td>${localPackBadge}</td>
            <td>${organicBadge}</td>
            <td>${displayBadge}</td>
            <td>${trendBadge}</td>
            <td>${mostRecentDate.toLocaleDateString()}</td>
        `;

        // Add click handler to navigate to city detail page
        row.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            // Navigate to the city detail page
            window.location.href = `/city/${encodeURIComponent(city)}`;
        });

        tbody.appendChild(row);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Delete Modal Functions
function showDeleteModal() {
    const modal = document.getElementById('deleteDataModal');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';

    // Set default dates (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    document.getElementById('deleteFromDate').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('deleteToDate').value = today.toISOString().split('T')[0];
}

function hideDeleteModal() {
    const modal = document.getElementById('deleteDataModal');
    modal.classList.add('hidden');
    modal.style.display = 'none';
}

function showConfirmModal() {
    const fromDate = document.getElementById('deleteFromDate').value;
    const toDate = document.getElementById('deleteToDate').value;

    if (!fromDate || !toDate) {
        alert('Please select both from and to dates.');
        return;
    }

    if (new Date(fromDate) > new Date(toDate)) {
        alert('From date cannot be after to date.');
        return;
    }

    // Format dates for display
    const fromDisplay = new Date(fromDate).toLocaleDateString();
    const toDisplay = new Date(toDate).toLocaleDateString();

    document.getElementById('confirmDeleteMessage').textContent =
        `Are you sure you want to delete all tracked data from ${fromDisplay} to ${toDisplay}? This action cannot be undone.`;

    hideDeleteModal();

    const modal = document.getElementById('confirmDeleteModal');
    modal.classList.remove('hidden');
    modal.style.display = 'flex';
}

function hideConfirmModal() {
    const modal = document.getElementById('confirmDeleteModal');
    modal.classList.add('hidden');
    modal.style.display = 'none';
}

async function performDelete() {
    const fromDate = document.getElementById('deleteFromDate').value;
    const toDate = document.getElementById('deleteToDate').value;

    hideConfirmModal();

    try {
        const response = await fetch('/api/dashboard/delete', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                date_from: fromDate,
                date_to: toDate
            })
        });

        const result = await response.json();

        if (response.ok) {
            alert(result.message);
            // Reload dashboard data
            loadDashboardData();
        } else {
            alert('Error: ' + (result.error || 'Unknown error occurred'));
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('An error occurred while deleting data.');
    }
}
