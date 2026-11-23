// Get city name from URL
const pathParts = window.location.pathname.split('/');
const cityName = decodeURIComponent(pathParts[pathParts.length - 1]);

let cityData = null;
let rankTrendsChart = null;

// Load city data on page load
document.addEventListener('DOMContentLoaded', function () {
    loadCityData();

    // Add event listener for keyword filter
    document.getElementById('keywordFilter').addEventListener('change', function () {
        loadCityData(this.value);
    });
});

function loadCityData(keywordFilter = '') {
    const url = `/api/city/${encodeURIComponent(cityName)}/data${keywordFilter ? `?keyword=${encodeURIComponent(keywordFilter)}` : ''}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            cityData = data;
            updateSummaryStats(data);
            populateKeywordFilter(data.keywords);
            renderRankTrends(data.rank_trends);
            renderKeywordPerformance(data.keyword_performance);
            renderHistoricalScans(data.historical_scans);
        })
        .catch(error => {
            console.error('Error loading city data:', error);
        });
}

function updateSummaryStats(data) {
    document.getElementById('totalScans').textContent = data.total_points;
    document.getElementById('keywordCount').textContent = data.keywords.length;

    // Calculate average and best rank from historical scans
    const displayRanks = data.historical_scans
        .map(s => s.display_rank)
        .filter(r => r !== null);

    if (displayRanks.length > 0) {
        const avgRank = Math.round(displayRanks.reduce((a, b) => a + b, 0) / displayRanks.length);
        const bestRank = Math.min(...displayRanks);

        document.getElementById('avgRank').textContent = avgRank;
        document.getElementById('bestRank').textContent = bestRank;
    } else {
        document.getElementById('avgRank').textContent = 'N/A';
        document.getElementById('bestRank').textContent = 'N/A';
    }
}

function populateKeywordFilter(keywords) {
    const select = document.getElementById('keywordFilter');
    const currentValue = select.value;

    // Clear existing options except "All Keywords"
    select.innerHTML = '<option value="">All Keywords</option>';

    // Add keyword options
    keywords.forEach(keyword => {
        const option = document.createElement('option');
        option.value = keyword;
        option.textContent = keyword;
        select.appendChild(option);
    });

    // Restore previous selection if it still exists
    if (currentValue && keywords.includes(currentValue)) {
        select.value = currentValue;
    }
}

function renderRankTrends(trends) {
    const ctx = document.getElementById('rankTrendsChart').getContext('2d');

    // Destroy existing chart if it exists
    if (rankTrendsChart) {
        rankTrendsChart.destroy();
    }

    rankTrendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: trends.dates,
            datasets: [
                {
                    label: 'Display Rank',
                    data: trends.avg_display,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Local Pack Rank',
                    data: trends.avg_local_pack,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Organic Rank',
                    data: trends.avg_organic,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    tension: 0.3,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: '#e2e8f0'
                    }
                }
            },
            scales: {
                y: {
                    reverse: true,
                    beginAtZero: false,
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        color: '#334155'
                    }
                },
                x: {
                    ticks: {
                        color: '#94a3b8'
                    },
                    grid: {
                        color: '#334155'
                    }
                }
            }
        }
    });
}

function renderKeywordPerformance(performance) {
    const tbody = document.getElementById('keywordPerfTableBody');
    tbody.innerHTML = '';

    if (performance.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-slate-400">No keyword data available</td></tr>';
        return;
    }

    performance.forEach(kw => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="font-semibold">${escapeHtml(kw.keyword)}</td>
            <td>${getRankBadge(kw.avg_rank)}</td>
            <td>${getRankBadge(kw.best_rank)}</td>
            <td>${getRankBadge(kw.worst_rank)}</td>
            <td>${kw.scan_count}</td>
        `;
        tbody.appendChild(row);
    });
}

function renderHistoricalScans(scans) {
    const tbody = document.getElementById('historicalScansTableBody');
    tbody.innerHTML = '';

    if (scans.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-400">No scan data available</td></tr>';
        return;
    }

    scans.forEach(scan => {
        const row = document.createElement('tr');
        const date = new Date(scan.scan_date);
        const coords = `${scan.lat.toFixed(4)}, ${scan.lon.toFixed(4)}`;

        row.innerHTML = `
            <td>${date.toLocaleDateString()}</td>
            <td>${escapeHtml(scan.keyword)}</td>
            <td class="text-xs text-slate-400">${coords}</td>
            <td>${getRankBadge(scan.local_pack_rank)}</td>
            <td>${getRankBadge(scan.organic_rank)}</td>
            <td>${getRankBadge(scan.display_rank)}</td>
        `;
        tbody.appendChild(row);
    });
}

function getRankBadge(rank) {
    if (rank === null || rank === undefined) {
        return '<span class="rank-badge rank-not-found">Not Found</span>';
    }

    if (rank <= 3) {
        return `<span class="rank-badge rank-top3">${rank}</span>`;
    } else if (rank <= 10) {
        return `<span class="rank-badge rank-top10">${rank}</span>`;
    } else {
        return `<span class="rank-badge rank-top30">${rank}</span>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
