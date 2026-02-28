    const TEAM_ALIASES = { WSH: 'WAS', JAC: 'JAX', OAK: 'LV', SD: 'LAC', STL: 'LAR', LA: 'LAR' };

    function normalizeTeam(code) {
      const value = String(code || '').trim().toUpperCase();
      return TEAM_ALIASES[value] || value;
    }

    function parseGameId(gameId) {
      const parts = String(gameId ?? '').split('_');
      if (parts.length < 4) return null;
      const season = Number(parts[0]);
      const weekToken = parts[1];
      const weekNumber = Number(weekToken);
      const away = parts[2];
      const home = parts[3];
      if (!away || !home) return null;
      return {
        season: Number.isFinite(season) ? season : null,
        weekToken,
        weekNumber: Number.isFinite(weekNumber) ? weekNumber : null,
        away,
        home
      };
    }

    const teamSelect = document.getElementById('team-select');
    const regularBtn = document.getElementById('regular-btn');
    const playoffsBtn = document.getElementById('playoffs-btn');
    const sortDescBtn = document.getElementById('sort-desc');
    const sortAscBtn = document.getElementById('sort-asc');
    const tableBody = document.querySelector('#season-table tbody');
    const metaEl = document.getElementById('data-meta');

    let dataPayload = null;
    let includePlayoffs = localStorage.getItem('teamHistoryIncludePlayoffs') === '1';
    let sortOrder = localStorage.getItem('teamHistorySeasonSort') || 'desc';
    if (!['asc', 'desc'].includes(sortOrder)) sortOrder = 'desc';

    const urlParams = new URLSearchParams(window.location.search);
    const urlTeam = normalizeTeam(urlParams.get('team'));
    let selectedTeam = urlTeam || normalizeTeam(localStorage.getItem('teamHistoryTeam')) || '';

    let seasonChart = null;

    function setToggleState(button, active) {
      button.classList.toggle('active', active);
    }

    function formatNumber(value, digits = 3) {
      if (!Number.isFinite(value)) return '—';
      return value.toFixed(digits);
    }

    function formatSigned(value, digits = 2) {
      if (!Number.isFinite(value)) return '—';
      const sign = value > 0 ? '+' : value < 0 ? '−' : '';
      return `${sign}${Math.abs(value).toFixed(digits)}`;
    }

    function getWeekNumber(row) {
      const numeric = Number(row.week);
      if (Number.isFinite(numeric)) return numeric;
      const parsed = parseGameId(row.game_id);
      return parsed && Number.isFinite(parsed.weekNumber) ? parsed.weekNumber : null;
    }

    function getWeekLabel(row) {
      const numeric = getWeekNumber(row);
      if (Number.isFinite(numeric)) return `WK ${numeric}`;
      const parsed = parseGameId(row.game_id);
      const token = parsed?.weekToken || row.week;
      return token ? String(token).toUpperCase() : 'WK ?';
    }

    function isRegularSeason(row, season) {
      const regMax = season >= 2021 ? 18 : 17;
      const weekNum = getWeekNumber(row);
      if (!Number.isFinite(weekNum)) return false;
      return weekNum <= regMax;
    }

    function buildGameSummary(row) {
      if (!row) return { summary: '—', details: null };
      const parsed = parseGameId(row.game_id);
      const away = normalizeTeam(parsed?.away || row.away);
      const home = normalizeTeam(parsed?.home || row.home);
      const opponent = normalizeTeam(row.opp || (away && home ? (normalizeTeam(row.team) === away ? home : away) : ''));
      const location = away && home && normalizeTeam(row.team) === away ? `@ ${home}` : `vs ${away || opponent}`;
      const weekLabel = getWeekLabel(row);
      const pointsFor = Number(row.points_for);
      const pointsAgainst = Number(row.points_against);
      const hasScore = Number.isFinite(pointsFor) && Number.isFinite(pointsAgainst);
      const result = hasScore
        ? pointsFor > pointsAgainst ? 'W' : pointsFor < pointsAgainst ? 'L' : 'T'
        : '';
      const scoreText = hasScore ? `${result} ${pointsFor}–${pointsAgainst}` : 'Score N/A';
      const net = Number(row.net_epa_pp);
      const summary = `${weekLabel} ${location} (${scoreText}) · Net ${formatSigned(net, 2)}`;

      const off = Number(row.off_epa_pp);
      const def = Number(row.def_epa_pp);
      const netPoints = Number.isFinite(net) ? net * 65 : null;
      const margin = hasScore ? pointsFor - pointsAgainst : null;

      const details = {
        opponent: opponent || 'Unknown',
        location,
        scoreText,
        margin,
        off,
        def,
        net,
        netPoints
      };

      return { summary, details };
    }

    function buildGameCell(row) {
      const cell = document.createElement('td');
      cell.className = 'game-cell';
      if (!row) {
        cell.textContent = '—';
        return cell;
      }
      const { summary, details } = buildGameSummary(row);
      const summarySpan = document.createElement('span');
      summarySpan.className = 'game-summary';
      summarySpan.textContent = summary;
      cell.appendChild(summarySpan);

      if (details) {
        const detailEl = document.createElement('details');
        const summaryEl = document.createElement('summary');
        summaryEl.textContent = 'Details';
        detailEl.appendChild(summaryEl);

        const detailGrid = document.createElement('div');
        detailGrid.className = 'detail-grid';
        detailGrid.innerHTML = `
          <span><strong>Opponent:</strong> ${details.opponent}</span>
          <span><strong>Location:</strong> ${details.location}</span>
          <span><strong>Score:</strong> ${details.scoreText}</span>
          <span><strong>Margin:</strong> ${Number.isFinite(details.margin) ? details.margin : '—'}</span>
          <span><strong>Off EPA/play:</strong> ${formatNumber(details.off, 3)}</span>
          <span><strong>Def EPA/play:</strong> ${formatNumber(details.def, 3)}</span>
          <span><strong>Net EPA/play:</strong> ${formatNumber(details.net, 3)}</span>
          <span><strong>EPA×65:</strong> ${Number.isFinite(details.netPoints) ? details.netPoints.toFixed(1) : '—'}</span>
        `;
        detailEl.appendChild(detailGrid);
        cell.appendChild(detailEl);
      }

      return cell;
    }

    function computeSeasonSummary(seasonKey, rows) {
      const season = Number(seasonKey);
      let offSum = 0;
      let offPlays = 0;
      let defSum = 0;
      let defPlays = 0;
      let wins = 0;
      let losses = 0;
      let ties = 0;
      let bestRow = null;
      let worstRow = null;
      let bestNet = -Infinity;
      let worstNet = Infinity;

      rows.forEach((row) => {
        const off = Number(row.off_epa_pp);
        const def = Number(row.def_epa_pp);
        const net = Number(row.net_epa_pp);
        const offPlaysRow = Number(row.off_plays);
        const defPlaysRow = Number(row.def_plays);
        if (Number.isFinite(off) && Number.isFinite(offPlaysRow) && offPlaysRow > 0) {
          offSum += off * offPlaysRow;
          offPlays += offPlaysRow;
        }
        if (Number.isFinite(def) && Number.isFinite(defPlaysRow) && defPlaysRow > 0) {
          defSum += def * defPlaysRow;
          defPlays += defPlaysRow;
        }

        const pointsFor = Number(row.points_for);
        const pointsAgainst = Number(row.points_against);
        const hasScore = Number.isFinite(pointsFor) && Number.isFinite(pointsAgainst) && pointsFor >= 0 && pointsAgainst >= 0;
        if (hasScore) {
          if (pointsFor > pointsAgainst) wins += 1;
          else if (pointsFor < pointsAgainst) losses += 1;
          else ties += 1;
        }

        if (hasScore && Number.isFinite(net)) {
          if (net > bestNet) {
            bestNet = net;
            bestRow = row;
          }
          if (net < worstNet) {
            worstNet = net;
            worstRow = row;
          }
        }
      });

      const offAvg = offPlays > 0 ? offSum / offPlays : null;
      const defAvg = defPlays > 0 ? defSum / defPlays : null;
      const netAvg = Number.isFinite(offAvg) && Number.isFinite(defAvg) ? offAvg + defAvg : null;
      const record = `${wins}-${losses}${ties ? `-${ties}` : ''}`;

      return {
        season,
        record,
        offAvg,
        defAvg,
        netAvg,
        bestRow,
        worstRow
      };
    }

    function getSeasonRows(seasonKey, team) {
      const games = dataPayload?.seasons?.[seasonKey]?.games || [];
      const normalizedTeam = normalizeTeam(team);
      const filtered = games.filter((row) => normalizeTeam(row.team) === normalizedTeam);
      const seasonNumber = Number(seasonKey);

      return filtered.filter((row) => {
        if (includePlayoffs) return true;
        return isRegularSeason(row, seasonNumber);
      });
    }

    function updateChart(seasonSummaries) {
      const labels = seasonSummaries.map((s) => s.season);
      const offData = seasonSummaries.map((s) => s.offAvg);
      const defData = seasonSummaries.map((s) => s.defAvg);
      const netData = seasonSummaries.map((s) => s.netAvg);

      if (seasonChart) {
        seasonChart.destroy();
      }

      const ctx = document.getElementById('season-chart');
      seasonChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Off EPA/play',
              data: offData,
              borderColor: '#2563eb',
              backgroundColor: 'rgba(37, 99, 235, 0.15)',
              tension: 0.25
            },
            {
              label: 'Def EPA/play',
              data: defData,
              borderColor: '#f97316',
              backgroundColor: 'rgba(249, 115, 22, 0.15)',
              tension: 0.25
            },
            {
              label: 'Net EPA/play',
              data: netData,
              borderColor: '#16a34a',
              backgroundColor: 'rgba(22, 163, 74, 0.15)',
              tension: 0.25
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top'
            },
            tooltip: {
              callbacks: {
                label: (context) => `${context.dataset.label}: ${formatNumber(context.parsed.y, 3)}`
              }
            }
          },
          scales: {
            y: {
              title: {
                display: true,
                text: 'EPA/play'
              }
            }
          }
        }
      });
    }

    function renderTable(seasonSummaries) {
      tableBody.textContent = '';
      seasonSummaries.forEach((summary) => {
        const row = document.createElement('tr');
        const seasonCell = document.createElement('td');
        seasonCell.textContent = summary.season;
        row.appendChild(seasonCell);

        const recordCell = document.createElement('td');
        recordCell.textContent = summary.record;
        row.appendChild(recordCell);

        const offCell = document.createElement('td');
        offCell.textContent = formatNumber(summary.offAvg, 3);
        row.appendChild(offCell);

        const defCell = document.createElement('td');
        defCell.textContent = formatNumber(summary.defAvg, 3);
        row.appendChild(defCell);

        const netCell = document.createElement('td');
        netCell.textContent = formatNumber(summary.netAvg, 3);
        row.appendChild(netCell);

        row.appendChild(buildGameCell(summary.bestRow));
        row.appendChild(buildGameCell(summary.worstRow));

        tableBody.appendChild(row);
      });
    }

    function render() {
      if (!dataPayload) return;
      setToggleState(regularBtn, !includePlayoffs);
      setToggleState(playoffsBtn, includePlayoffs);
      setToggleState(sortDescBtn, sortOrder === 'desc');
      setToggleState(sortAscBtn, sortOrder === 'asc');

      const seasons = Object.keys(dataPayload.seasons || {});
      const summaries = seasons
        .map((seasonKey) => {
          const rows = getSeasonRows(seasonKey, selectedTeam);
          if (!rows.length) return null;
          return computeSeasonSummary(seasonKey, rows);
        })
        .filter(Boolean);

      const summariesForChart = [...summaries].sort((a, b) => a.season - b.season);
      const summariesForTable = [...summaries].sort((a, b) =>
        sortOrder === 'asc' ? a.season - b.season : b.season - a.season
      );
      updateChart(summariesForChart);
      renderTable(summariesForTable);
    }

    function updateQueryParam(team) {
      const url = new URL(window.location.href);
      if (team) {
        url.searchParams.set('team', team);
      } else {
        url.searchParams.delete('team');
      }
      window.history.replaceState({}, '', url);
    }

    function setSelectedTeam(team) {
      selectedTeam = normalizeTeam(team);
      teamSelect.value = selectedTeam;
      localStorage.setItem('teamHistoryTeam', selectedTeam);
      updateQueryParam(selectedTeam);
      render();
    }

    function initTeams() {
      const teamSet = new Set();
      Object.values(dataPayload.seasons || {}).forEach((season) => {
        season.games?.forEach((row) => {
          const team = normalizeTeam(row.team);
          if (team) teamSet.add(team);
        });
      });

      const teams = Array.from(teamSet).sort();
      teamSelect.textContent = '';
      teams.forEach((team) => {
        const option = document.createElement('option');
        option.value = team;
        option.textContent = team;
        teamSelect.appendChild(option);
      });

      if (!selectedTeam || !teamSet.has(selectedTeam)) {
        selectedTeam = teams[0] || '';
      }
      teamSelect.value = selectedTeam;
    }

    async function init() {
      try {
        const response = await fetch('data/epa.json');
        dataPayload = await response.json();
        const seasonKeys = Object.keys(dataPayload.seasons || {});
        const stamp = dataPayload.generated_at ? `Updated ${dataPayload.generated_at}` : '';
        const sha = dataPayload.git_sha ? ` · ${dataPayload.git_sha.slice(0, 7)}` : '';
        metaEl.textContent = seasonKeys.length
          ? `Loaded ${seasonKeys.length} seasons of EPA data. ${stamp}${sha}`.trim()
          : 'No season data found.';
        initTeams();
        setSelectedTeam(selectedTeam);
      } catch (error) {
        metaEl.textContent = 'Failed to load EPA data.';
        console.error(error);
      }
    }

    teamSelect.addEventListener('change', (event) => {
      setSelectedTeam(event.target.value);
    });

    regularBtn.addEventListener('click', () => {
      includePlayoffs = false;
      localStorage.setItem('teamHistoryIncludePlayoffs', '0');
      render();
    });

    playoffsBtn.addEventListener('click', () => {
      includePlayoffs = true;
      localStorage.setItem('teamHistoryIncludePlayoffs', '1');
      render();
    });

    sortDescBtn.addEventListener('click', () => {
      sortOrder = 'desc';
      localStorage.setItem('teamHistorySeasonSort', sortOrder);
      render();
    });

    sortAscBtn.addEventListener('click', () => {
      sortOrder = 'asc';
      localStorage.setItem('teamHistorySeasonSort', sortOrder);
      render();
    });

    init();
