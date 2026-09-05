    const TEAM_COLORS = {
      ARI: '#97233F', ATL: '#A71930', BAL: '#241773', BUF: '#00338D', CAR: '#0085CA', CHI: '#0B162A',
      CIN: '#FB4F14', CLE: '#311D00', DAL: '#003594', DEN: '#FB4F14', DET: '#0076B6', GB: '#203731',
      HOU: '#03202F', IND: '#002C5F', JAX: '#101820', KC: '#E31837', LAC: '#0080C6', LAR: '#003594',
      LV: '#000000', MIA: '#008E97', MIN: '#4F2683', NE: '#002244', NO: '#D3BC8D', NYG: '#0B2265',
      NYJ: '#125740', PHI: '#004C54', PIT: '#101820', SEA: '#002244', SF: '#AA0000', TB: '#D50A0A',
      TEN: '#4B92DB', WAS: '#5A1414'
    };

    const TEAM_DISPLAY_NAMES = {
      ARI: 'Arizona', ATL: 'Atlanta', BAL: 'Baltimore', BUF: 'Buffalo', CAR: 'Carolina', CHI: 'Chicago',
      CIN: 'Cincinnati', CLE: 'Cleveland', DAL: 'Dallas', DEN: 'Denver', DET: 'Detroit', GB: 'Green Bay',
      HOU: 'Houston', IND: 'Indianapolis', JAX: 'Jacksonville', KC: 'Kansas City', LAC: 'LA Chargers',
      LAR: 'Los Angeles Rams', LV: 'Las Vegas', MIA: 'Miami', MIN: 'Minnesota', NE: 'New England',
      NO: 'New Orleans', NYG: 'NY Giants', NYJ: 'NY Jets', PHI: 'Philadelphia', PIT: 'Pittsburgh',
      SEA: 'Seattle', SF: 'San Francisco', TB: 'Tampa Bay', TEN: 'Tennessee', WAS: 'Washington'
    };

    const TEAM_ABBR_ALIASES = { LA: 'LAR' };

    const QUADRANT_BACKGROUND_COLORS = {
      'positive-positive': 'rgba(34, 197, 94, 0.12)',
      'positive-negative': 'rgba(56, 189, 248, 0.12)',
      'negative-positive': 'rgba(168, 85, 247, 0.12)',
      'negative-negative': 'rgba(239, 68, 68, 0.12)'
    };

    const statusEl = document.getElementById('status');
    const metaEl = document.getElementById('data-meta');
    const seasonSelect = document.getElementById('season-select');
    const weekStartSelect = document.getElementById('week-start');
    const weekEndSelect = document.getElementById('week-end');
    const metricModeSelect = document.getElementById('metric-mode');
    const sosBasisSelect = document.getElementById('sos-basis');
    const updateButton = document.getElementById('update-btn');
    const scatterCtx = document.getElementById('epa-chart').getContext('2d');
    const tableSection = document.getElementById('table-section');
    const table = document.getElementById('epa-table');
    const tableBody = table.querySelector('tbody');
    const tableHeaders = table.querySelectorAll('th');
    const teamSeasonSelect = document.getElementById('team-season-select');
    const teamSelect = document.getElementById('team-select');
    const teamModeSelect = document.getElementById('team-mode');
    const trailingWindowWrap = document.getElementById('trailing-window-wrap');
    const trailingWindowInput = document.getElementById('trailing-window');
    const teamWeeklyNote = document.getElementById('team-weekly-note');
    const teamCombinedCtx = document.getElementById('team-combined-chart').getContext('2d');
    const teamOffCtx = document.getElementById('team-off-chart').getContext('2d');
    const teamDefCtx = document.getElementById('team-def-chart').getContext('2d');
    const viewSummaryBtn = document.getElementById('view-summary-btn');
    const viewSplitBtn = document.getElementById('view-split-btn');
    const summaryView = document.getElementById('summary-view');
    const splitSection = document.getElementById('split-section');
    const splitTable = document.getElementById('split-table');
    const splitTableBody = splitTable.querySelector('tbody');
    const splitTableHeaders = splitTable.querySelectorAll('th');
    const DATA_URL = new URL('data/epa.json', document.baseURI);

    let scatterChart;
    let teamCombinedChart;
    let teamOffChart;
    let teamDefChart;
    let seasonData = {};
    const sortState = { column: null, direction: 'desc' };

    const quadrantPlugin = {
      id: 'quadrantBackground',
      beforeDraw(chartInstance) {
        const { chartArea, ctx, scales } = chartInstance;
        if (!chartArea) return;
        const xScale = scales.x;
        const yScale = scales.y;
        const xZero = Math.min(Math.max(xScale.getPixelForValue(0), chartArea.left), chartArea.right);
        const yZero = Math.min(Math.max(yScale.getPixelForValue(0), chartArea.top), chartArea.bottom);

        const quadrants = [
          { key: 'positive-positive', xStart: xZero, xEnd: chartArea.right, yStart: chartArea.top, yEnd: yZero },
          { key: 'positive-negative', xStart: xZero, xEnd: chartArea.right, yStart: yZero, yEnd: chartArea.bottom },
          { key: 'negative-positive', xStart: chartArea.left, xEnd: xZero, yStart: chartArea.top, yEnd: yZero },
          { key: 'negative-negative', xStart: chartArea.left, xEnd: xZero, yStart: yZero, yEnd: chartArea.bottom },
        ];

        ctx.save();
        quadrants.forEach((quad) => {
          ctx.fillStyle = QUADRANT_BACKGROUND_COLORS[quad.key] || 'rgba(0, 0, 0, 0.03)';
          ctx.fillRect(quad.xStart, quad.yStart, quad.xEnd - quad.xStart, quad.yEnd - quad.yStart);
        });
        ctx.restore();
      }
    };

    const zeroLinePlugin = {
      id: 'zeroLine',
      afterDraw(chartInstance) {
        const { ctx, chartArea, scales } = chartInstance;
        if (!chartArea || !scales?.y) return;
        const yZero = scales.y.getPixelForValue(0);
        if (!Number.isFinite(yZero)) return;
        ctx.save();
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, yZero);
        ctx.lineTo(chartArea.right, yZero);
        ctx.stroke();
        ctx.restore();
      },
    };

    function toFiniteNumberOrNull(value) {
      if (value === null || value === undefined) return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    function normalizeTeamAbbr(abbr) {
      const value = String(abbr || '').trim().toUpperCase();
      return TEAM_ABBR_ALIASES[value] || value;
    }

    function normalizeSeasonPayloads(rawSeasons) {
      if (!rawSeasons || typeof rawSeasons !== 'object') return {};
      const normalized = {};

      Object.entries(rawSeasons).forEach(([seasonKey, season]) => {
        if (!season || typeof season !== 'object') return;
        const seasonCopy = { ...season };
        const teamsByAbbr = {};

        if (Array.isArray(season.teams)) {
          season.teams.forEach((teamEntry) => {
            if (!teamEntry || typeof teamEntry !== 'object') return;
            const abbr = normalizeTeamAbbr(teamEntry.team);
            const weeks = {};
            if (teamEntry.weeks && typeof teamEntry.weeks === 'object') {
              Object.entries(teamEntry.weeks).forEach(([weekKey, values]) => {
                weeks[weekKey] = values;
              });
            }
            if (!teamsByAbbr[abbr]) {
              teamsByAbbr[abbr] = { ...teamEntry, team: abbr, weeks };
            } else {
              teamsByAbbr[abbr].weeks = { ...teamsByAbbr[abbr].weeks, ...weeks };
            }
          });
          seasonCopy.teams = Object.values(teamsByAbbr);
        }

        if (Array.isArray(season.games)) {
          seasonCopy.games = season.games.map((game) => ({
            ...game,
            team: normalizeTeamAbbr(game.team),
            opp: normalizeTeamAbbr(game.opp),
          }));
        }

        normalized[seasonKey] = seasonCopy;
      });

      return normalized;
    }

    function showStatus(message, variant = 'info') {
      statusEl.textContent = message;
      statusEl.style.display = 'block';
      statusEl.hidden = false;
      statusEl.style.borderColor = variant === 'error' ? '#f97316' : '#fed7aa';
      statusEl.style.background = variant === 'error' ? '#fff1f2' : '#fff7ed';
      statusEl.style.color = variant === 'error' ? '#9f1239' : '#9a3412';
    }

    function hideStatus() {
      statusEl.hidden = true;
      statusEl.textContent = '';
    }

    const POSTSEASON_ORDER = ['WC', 'DIV', 'CON', 'SB'];
    const POSTSEASON_LABELS = {
      WC: 'Wild Card Round',
      DIV: 'Divisional Round',
      CON: 'Conf. Round',
      SB: 'Super Bowl',
    };

    function normalizeGameType(raw) {
      const value = String(raw ?? '').trim().toUpperCase();
      if (!value) return null;
      if (value === 'REG' || value === 'REGULAR') return 'REG';
      if (value === 'POST' || value === 'POSTSEASON' || value === '2') return 'POST';
      if (['WC', 'WILDCARD', 'WILD CARD'].includes(value)) return 'WC';
      if (['DIV', 'DIVISIONAL'].includes(value)) return 'DIV';
      if (['CON', 'CONF', 'CONFERENCE', 'CHAMP', 'CONFERENCE CHAMPIONSHIP'].includes(value)) return 'CON';
      if (['SB', 'SUPER BOWL', 'SUPERBOWL'].includes(value)) return 'SB';
      return value;
    }

    function getGameType(game) {
      if (game?.postseason === true) return 'POST';
      return normalizeGameType(
        game?.game_type ?? game?.gameType ?? game?.season_type ?? game?.seasonType ?? game?.type
      );
    }

    function buildWeekTypeMap(season) {
      const map = {};
      if (!season || !Array.isArray(season.games)) return map;
      season.games.forEach((game) => {
        const week = game?.week;
        if (week == null) return;
        const type = getGameType(game);
        if (!type) return;
        if (POSTSEASON_LABELS[type]) {
          map[String(week)] = type;
        } else if (type === 'POST') {
          map[String(week)] = 'POST';
        } else if (type === 'REG' && !map[String(week)]) {
          map[String(week)] = 'REG';
        }
      });
      return map;
    }

    function getRegSeasonMax(season) {
      const seasonNum = Number(season);
      if (!Number.isFinite(seasonNum)) return 18;
      return seasonNum >= 2021 ? 18 : 17;
    }

    function inferPostseasonLabel(week, season) {
      const regMax = getRegSeasonMax(season);
      const delta = Number(week) - regMax;
      if (!Number.isFinite(delta) || delta <= 0 || delta > POSTSEASON_ORDER.length) return null;
      const roundKey = POSTSEASON_ORDER[delta - 1];
      return POSTSEASON_LABELS[roundKey] || null;
    }

    function formatWeekLabel(week, season) {
      const weekKey = String(week ?? '');
      const typeMap = season && season.games ? buildWeekTypeMap(season) : {};
      const mappedType = typeMap[weekKey];
      if (mappedType && POSTSEASON_LABELS[mappedType]) return POSTSEASON_LABELS[mappedType];
      if (mappedType === 'POST') {
        const inferred = inferPostseasonLabel(week, season?.season || season);
        if (inferred) return inferred;
      }
      const normalized = normalizeGameType(weekKey);
      if (normalized && POSTSEASON_LABELS[normalized]) return POSTSEASON_LABELS[normalized];
      const postseasonLabel = inferPostseasonLabel(week, season?.season || season);
      return postseasonLabel || `Week ${week}`;
    }

    function fillWeekSelect(selectEl, weeks, season) {
      selectEl.innerHTML = '';
      weeks.forEach((week) => {
        const option = document.createElement('option');
        option.value = week;
        option.textContent = formatWeekLabel(week, seasonData?.[season] ?? season);
        selectEl.appendChild(option);
      });
    }

    function averageWeeks(teamWeeks, start, end) {
      let offWeighted = 0;
      let offPlays = 0;
      let offSimple = 0;
      let defWeighted = 0;
      let defPlays = 0;
      let defSimple = 0;
      let count = 0;
      for (let w = start; w <= end; w += 1) {
        const payload = teamWeeks[w];
        if (payload && typeof payload.off === 'number' && typeof payload.def === 'number') {
          count += 1;
          offSimple += payload.off;
          defSimple += payload.def;
          const offWeekPlays = Number(payload.off_plays ?? 0);
          const defWeekPlays = Number(payload.def_plays ?? 0);
          if (Number.isFinite(offWeekPlays) && offWeekPlays > 0) {
            offWeighted += payload.off * offWeekPlays;
            offPlays += offWeekPlays;
          }
          if (Number.isFinite(defWeekPlays) && defWeekPlays > 0) {
            defWeighted += payload.def * defWeekPlays;
            defPlays += defWeekPlays;
          }
        }
      }
      if (count === 0) return null;
      const off = offPlays > 0 ? offWeighted / offPlays : offSimple / count;
      const def = defPlays > 0 ? defWeighted / defPlays : defSimple / count;
      return { off, def };
    }

    function computeRecord(season, team, startWeek, endWeek) {
      if (!season || !Array.isArray(season.games)) return null;
      const games = season.games.filter((g) => g.week >= startWeek && g.week <= endWeek && g.team === team);
      let wins = 0;
      let losses = 0;
      let ties = 0;
      let counted = 0;
      games.forEach((g) => {
        const pf = Number(g.points_for);
        const pa = Number(g.points_against);
        if (!Number.isFinite(pf) || !Number.isFinite(pa) || pf < 0 || pa < 0) return;
        counted += 1;
        if (pf > pa) wins += 1;
        else if (pf < pa) losses += 1;
        else ties += 1;
      });
      if (counted === 0) return null;
      const recordStr = ties ? `${wins}-${losses}-${ties}` : `${wins}-${losses}`;
      const winPct = (wins + 0.5 * ties) / counted;
      return { wins, losses, ties, recordStr, winPct };
    }

    function solveLinearSystem(matrix, vector) {
      const n = matrix.length;
      const augmented = matrix.map((row, idx) => [...row, vector[idx]]);
      for (let i = 0; i < n; i += 1) {
        let pivot = i;
        for (let r = i + 1; r < n; r += 1) {
          if (Math.abs(augmented[r][i]) > Math.abs(augmented[pivot][i])) pivot = r;
        }
        if (Math.abs(augmented[pivot][i]) < 1e-9) {
          console.error('SOS solver encountered a near-singular pivot');
          throw new Error('SOS solver failed due to singular matrix');
        }
        if (pivot !== i) [augmented[i], augmented[pivot]] = [augmented[pivot], augmented[i]];
        const pivotVal = augmented[i][i];
        for (let c = i; c <= n; c += 1) augmented[i][c] /= pivotVal;
        for (let r = 0; r < n; r += 1) {
          if (r === i) continue;
          const factor = augmented[r][i];
          if (factor === 0) continue;
          for (let c = i; c <= n; c += 1) augmented[r][c] -= factor * augmented[i][c];
        }
      }
      return augmented.map((row) => row[n]);
    }

    function computeSosRatingsForRange(selectedSeason, startWeek, endWeek, sosBasis = 'season_to_date') {
      const season = seasonData[selectedSeason];
      if (!season || !Array.isArray(season.games) || !season.games.length) {
        return { error: `No game rows in data for season ${selectedSeason}. Re-run backfill to populate team_epa_games and re-export.` };
      }

      let ratingGames;
      if (sosBasis === 'window_only') {
        ratingGames = season.games.filter((g) => g.week >= startWeek && g.week <= endWeek);
      } else if (sosBasis === 'full_season') {
        ratingGames = season.games;
      } else {
        ratingGames = season.games.filter((g) => g.week <= endWeek);
      }
      const displayGames = season.games.filter((g) => g.week >= startWeek && g.week <= endWeek);
      if (!ratingGames.length || !displayGames.length) {
        return { error: 'No game rows available for the selected SOS window.' };
      }

      const teams = Array.from(
        new Set([...ratingGames, ...displayGames].flatMap((g) => [g.team, g.opp])),
      ).sort();
      const idx = Object.fromEntries(teams.map((t, i) => [t, i]));
      const n = teams.length;
      const totalVars = n * 2;
      const lam = 20;
      const baseRow = Array.from({ length: totalVars }, (__unused, j) => 0);
      const AtA = Array.from({ length: totalVars }, (_, i) => baseRow.map((__, j) => (i === j ? lam : 0)));
      const Atb = Array(totalVars).fill(0);

      const offIndex = (team) => idx[team];
      const defIndex = (team) => idx[team] + n;

      let equationCount = 0;
      ratingGames.forEach((g) => {
        const t = g.team;
        const o = g.opp;
        const offWeight = Number(g.off_plays);
        const defWeight = Number(g.def_plays);
        const offVal = Number(g.off_epa_pp);
        const defVal = Number(g.def_epa_pp);

        if (Number.isFinite(offWeight) && offWeight > 0 && Number.isFinite(offVal)) {
          const tIdx = offIndex(t);
          const oIdx = defIndex(o);
          AtA[tIdx][tIdx] += offWeight;
          AtA[oIdx][oIdx] += offWeight;
          AtA[tIdx][oIdx] -= offWeight;
          AtA[oIdx][tIdx] -= offWeight;
          Atb[tIdx] += offWeight * offVal;
          Atb[oIdx] -= offWeight * offVal;
          equationCount += 1;
        }

        if (Number.isFinite(defWeight) && defWeight > 0 && Number.isFinite(defVal)) {
          const tIdx = defIndex(t);
          const oIdx = offIndex(o);
          AtA[tIdx][tIdx] += defWeight;
          AtA[oIdx][oIdx] += defWeight;
          AtA[tIdx][oIdx] -= defWeight;
          AtA[oIdx][tIdx] -= defWeight;
          Atb[tIdx] += defWeight * defVal;
          Atb[oIdx] -= defWeight * defVal;
          equationCount += 1;
        }
      });

      if (equationCount === 0) {
        return { error: 'No valid plays found to compute SOS for this range.' };
      }

      let ratingsArr;
      try {
        ratingsArr = solveLinearSystem(AtA, Atb);
      } catch (err) {
        console.warn('SOS solver failed; falling back to raw EPA for this selection', err);
        return { error: 'SOS solver failed due to singular matrix.' };
      }
      const mean = ratingsArr.reduce((acc, val) => acc + val, 0) / ratingsArr.length;
      const offRatings = {};
      const defRatings = {};
      teams.forEach((team, i) => {
        offRatings[team] = ratingsArr[i] - mean;
        defRatings[team] = ratingsArr[i + n] - mean;
      });

      const sosOffSums = {};
      const sosOffWeights = {};
      const sosDefSums = {};
      const sosDefWeights = {};
      displayGames.forEach((g) => {
        const offWeight = Number(g.off_plays);
        const defWeight = Number(g.def_plays);
        const oppDefRating = defRatings[g.opp];
        const oppOffRating = offRatings[g.opp];
        if (Number.isFinite(offWeight) && offWeight > 0 && Number.isFinite(oppDefRating)) {
          sosOffSums[g.team] = (sosOffSums[g.team] || 0) + offWeight * oppDefRating;
          sosOffWeights[g.team] = (sosOffWeights[g.team] || 0) + offWeight;
        }
        if (Number.isFinite(defWeight) && defWeight > 0 && Number.isFinite(oppOffRating)) {
          sosDefSums[g.team] = (sosDefSums[g.team] || 0) + defWeight * oppOffRating;
          sosDefWeights[g.team] = (sosDefWeights[g.team] || 0) + defWeight;
        }
      });

      const sosOffFaced = {};
      const sosDefFaced = {};
      teams.forEach((team) => {
        const offTotal = sosOffWeights[team] || 0;
        const defTotal = sosDefWeights[team] || 0;
        sosOffFaced[team] = offTotal ? sosOffSums[team] / offTotal : 0;
        sosDefFaced[team] = defTotal ? sosDefSums[team] / defTotal : 0;
      });

      return { offRatings, defRatings, sosOffFaced, sosDefFaced };
    }

    function buildTeamRows(selectedSeason, startWeek, endWeek, metricMode, sosBasis, sosData) {
      const season = seasonData[selectedSeason];
      if (!season) return [];
      return season.teams
        .map((teamEntry) => {
          const weeks = {};
          Object.entries(teamEntry.weeks).forEach(([week, values]) => {
            weeks[Number(week)] = values;
          });
          const averaged = averageWeeks(weeks, startWeek, endWeek);
          if (!averaged) return null;

          const baseOff = averaged.off;
          const baseDef = averaged.def;
          const sosOff = metricMode === 'sos' ? sosData?.sosOffFaced?.[teamEntry.team] : null;
          const sosDef = metricMode === 'sos' ? sosData?.sosDefFaced?.[teamEntry.team] : null;

          const offAdj = Number.isFinite(sosOff) ? baseOff + sosOff : baseOff;
          const defAdj = Number.isFinite(sosDef) ? baseDef + sosDef : baseDef;
          const combined = offAdj + defAdj;
          const record = computeRecord(season, teamEntry.team, startWeek, endWeek);

          return {
            x: offAdj,
            y: defAdj,
            label: teamEntry.team,
            backgroundColor: TEAM_COLORS[teamEntry.team] || '#0f172a',
            borderColor: '#0f172a',
            team: teamEntry.team,
            displayName: TEAM_DISPLAY_NAMES[teamEntry.team] || teamEntry.team,
            combined,
            off: offAdj,
            def: defAdj,
            rawCombined: baseOff + baseDef,
            rawOff: baseOff,
            rawDef: baseDef,
            deltaOff: offAdj - baseOff,
            deltaDef: defAdj - baseDef,
            sosOffFaced: Number.isFinite(sosOff) ? sosOff : null,
            sosDefFaced: Number.isFinite(sosDef) ? sosDef : null,
            wins: record?.wins ?? null,
            losses: record?.losses ?? null,
            ties: record?.ties ?? null,
            record: record?.recordStr ?? null,
            winPct: record?.winPct ?? null,
          };
        })
        .filter(Boolean);
    }

    function renderScatterChart(points, seasonLabel, startWeek, endWeek, metricMode, sosBasis) {
      if (scatterChart) scatterChart.destroy();
      const subtitle = startWeek === endWeek ? `Week ${startWeek}` : `Weeks ${startWeek}\u2013${endWeek}`;
      const subtitleParts = [subtitle];
      if (metricMode === 'sos') {
        const basisLabel = sosBasis === 'full_season'
          ? 'full season'
          : sosBasis === 'window_only'
            ? 'window only'
            : `through Week ${endWeek}`;
        subtitleParts.push(`SOS-adjusted offense/defense EPA (opp basis: ${basisLabel})`);
      }
      const offenseAxisLabel = metricMode === 'sos'
        ? 'Offense EPA per play (SOS-adjusted via opponent defenses)'
        : 'Offense EPA per play (higher = better offense)';
      const defenseAxisLabel = metricMode === 'sos'
        ? 'Defense EPA per play (SOS-adjusted via opponent offenses)'
        : 'Defense EPA per play (higher = better defense)';

      scatterChart = new Chart(scatterCtx, {
        type: 'scatter',
        data: { datasets: [{
          label: 'EPA per play',
          data: points,
          pointRadius: 12,
          pointHoverRadius: 14,
          backgroundColor: points.map((p) => p.backgroundColor),
          pointBackgroundColor: points.map((p) => p.backgroundColor),
          pointBorderColor: points.map((p) => p.borderColor),
          pointBorderWidth: 1.5,
        }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: { padding: 10 },
          plugins: {
            legend: { display: false },
            title: { display: false },
            subtitle: { display: false, text: subtitleParts.join(' — ') },
            datalabels: {
              backgroundColor: null,
              borderWidth: 0,
              color: '#0f172a',
              formatter: (value) => value.label,
              font: { weight: 'bold', size: 11 },
              padding: { top: 2, bottom: 2, left: 2, right: 2 },
              textStrokeColor: '#fff',
              textStrokeWidth: 3,
            },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const { x, y, label } = ctx.raw;
                  const shiftedNote = metricMode === 'sos' ? ' (SOS-adjusted)' : '';
                  return `${label}: Off ${x.toFixed(3)}, Def ${y.toFixed(3)}${shiftedNote}`;
                },
              },
            },
          },
          scales: {
            x: {
              title: { display: true, text: offenseAxisLabel },
              grid: { color: '#e2e8f0' },
            },
            y: {
              title: { display: true, text: defenseAxisLabel },
              grid: { color: '#e2e8f0' },
            },
          },
        },
        plugins: [ChartDataLabels, quadrantPlugin],
      });
    }

    function buildTeamWeeklyRows(seasonKey, team) {
      const season = seasonData[seasonKey];
      if (!season) return { rows: [], reason: 'Season not found in dataset.' };
      const entry = season.teams.find((t) => t.team === team);
      if (!entry) return { rows: [], reason: 'Team not found for selected season.' };

      const weeksPayload = entry.weeks || {};
      const rows = Object.entries(weeksPayload)
        .map(([week, payload]) => {
          const off = toFiniteNumberOrNull(payload.off);
          const def = toFiniteNumberOrNull(payload.def);
          const offPlaysRaw = toFiniteNumberOrNull(payload.off_plays);
          const defPlaysRaw = toFiniteNumberOrNull(payload.def_plays);
          const offPlays = off === null ? null : offPlaysRaw;
          const defPlays = def === null ? null : defPlaysRaw;
          return {
            week: Number(week),
            off,
            def,
            offPlays,
            defPlays,
          };
        })
        .filter((row) => Number.isFinite(row.week) && (row.off !== null || row.def !== null))
        .sort((a, b) => a.week - b.week);

      const reason = rows.length
        ? ''
        : 'Weekly breakdown not available in this dataset export.';

      return { rows, reason };
    }

    function computeModeSeries(values, weights, mode, window) {
      const result = [];
      const hasWeights = Array.isArray(weights)
        && weights.some((w) => Number.isFinite(w) && Number(w) > 0);

      if (mode === 'weekly') {
        return values.map((v) => (Number.isFinite(v) ? v : null));
      }

      if (mode === 'season_to_date_avg') {
        if (hasWeights) {
          let numer = 0;
          let denom = 0;
          values.forEach((val, idx) => {
            const valOk = Number.isFinite(val);
            const weightRaw = Number(weights[idx]);
            const weight = valOk && Number.isFinite(weightRaw) && weightRaw > 0 ? weightRaw : 0;
            if (valOk && weight > 0) {
              numer += val * weight;
              denom += weight;
            }
            result.push(denom > 0 ? numer / denom : null);
          });
          return result;
        }
        let sum = 0;
        let count = 0;
        values.forEach((val) => {
          if (Number.isFinite(val)) {
            sum += val;
            count += 1;
          }
          result.push(count ? sum / count : null);
        });
        return result;
      }

      if (mode === 'trailing_avg') {
        if (hasWeights) {
          const windowRows = [];
          values.forEach((val, idx) => {
            const valOk = Number.isFinite(val);
            const weightRaw = Number(weights[idx]);
            const weight = valOk && Number.isFinite(weightRaw) && weightRaw > 0 ? weightRaw : 0;
            windowRows.push({ val, weight });
            if (windowRows.length > window) windowRows.shift();
            let numer = 0;
            let denom = 0;
            windowRows.forEach((row) => {
              if (Number.isFinite(row.val) && row.weight > 0) {
                numer += row.val * row.weight;
                denom += row.weight;
              }
            });
            result.push(denom > 0 ? numer / denom : null);
          });
          return result;
        }
        const windowVals = [];
        values.forEach((val) => {
          windowVals.push(val);
          if (windowVals.length > window) windowVals.shift();
          const valid = windowVals.filter((v) => Number.isFinite(v));
          const avg = valid.length ? valid.reduce((acc, v) => acc + v, 0) / valid.length : null;
          result.push(Number.isFinite(avg) ? avg : null);
        });
        return result;
      }

      return values.map(() => null);
    }

    function applyTeamEpaMode(rows, mode, window = 3) {
      const offValues = rows.map((r) => r.off);
      const defValues = rows.map((r) => r.def);
      const offWeights = rows.map((r) => r.offPlays);
      const defWeights = rows.map((r) => r.defPlays);

      const offSeries = computeModeSeries(offValues, offWeights, mode, window);
      const defSeries = computeModeSeries(defValues, defWeights, mode, window);

      return rows.map((row, idx) => {
        const offVal = offSeries[idx];
        const defVal = defSeries[idx];
        const netVal = Number.isFinite(offVal) && Number.isFinite(defVal) ? offVal + defVal : null;
        return {
          ...row,
          offMode: offVal,
          defMode: defVal,
          netMode: netVal,
        };
      });
    }

    function destroyTeamCharts() {
      if (teamCombinedChart) teamCombinedChart.destroy();
      if (teamOffChart) teamOffChart.destroy();
      if (teamDefChart) teamDefChart.destroy();
    }

    function buildLineOptions(titleText) {
      return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top' },
          title: { display: Boolean(titleText), text: titleText || '' },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const value = ctx.parsed?.y;
                return `${ctx.dataset.label}: ${Number.isFinite(value) ? value.toFixed(3) : 'N/A'}`;
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: 'Week' },
            grid: { color: '#e2e8f0' },
            ticks: { precision: 0 },
          },
          y: {
            title: { display: true, text: 'EPA per play' },
            grid: { color: '#e2e8f0' },
          },
        },
      };
    }

    function renderTeamCharts() {
      const seasonKey = teamSeasonSelect.value || seasonSelect.value;
      const team = teamSelect.value;
      if (!seasonKey || !team) return;

      const { rows, reason } = buildTeamWeeklyRows(seasonKey, team);
      if (!rows.length) {
        destroyTeamCharts();
        if (teamWeeklyNote) {
          teamWeeklyNote.textContent = reason || 'Weekly breakdown not available for this team.';
          teamWeeklyNote.style.display = '';
        }
        return;
      }

      if (teamWeeklyNote) {
        teamWeeklyNote.textContent = '';
        teamWeeklyNote.style.display = 'none';
      }

      const mode = teamModeSelect.value;
      const trailingWindow = clampTrailingWindow(trailingWindowInput.value);
      trailingWindowInput.value = trailingWindow;
      toggleTrailingWindowControl(mode);

      const transformed = applyTeamEpaMode(rows, mode, trailingWindow);
      const labels = transformed.map((row) => row.week);
      const teamColor = TEAM_COLORS[team] || '#0f172a';
      const defColor = '#0ea5e9';

      destroyTeamCharts();

      teamCombinedChart = new Chart(teamCombinedCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Net EPA (Off + Def)',
              data: transformed.map((row) => row.netMode),
              borderColor: '#0f172a',
              backgroundColor: 'transparent',
              tension: 0.15,
              borderWidth: 2.5,
              spanGaps: true,
            },
            {
              label: 'Offensive EPA',
              data: transformed.map((row) => row.offMode),
              borderColor: teamColor,
              backgroundColor: 'transparent',
              tension: 0.15,
              borderWidth: 2,
              spanGaps: true,
            },
            {
              label: 'Defensive EPA',
              data: transformed.map((row) => row.defMode),
              borderColor: defColor,
              backgroundColor: 'transparent',
              tension: 0.15,
              borderWidth: 2,
              spanGaps: true,
            },
          ],
        },
        options: buildLineOptions('Combined view'),
        plugins: [zeroLinePlugin],
      });

      teamOffChart = new Chart(teamOffCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Offensive EPA',
              data: transformed.map((row) => row.offMode),
              borderColor: teamColor,
              backgroundColor: 'transparent',
              tension: 0.15,
              borderWidth: 2.5,
              spanGaps: true,
            },
          ],
        },
        options: buildLineOptions(),
        plugins: [zeroLinePlugin],
      });

      teamDefChart = new Chart(teamDefCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Defensive EPA',
              data: transformed.map((row) => row.defMode),
              borderColor: defColor,
              backgroundColor: 'transparent',
              tension: 0.15,
              borderWidth: 2.5,
              spanGaps: true,
            },
          ],
        },
        options: buildLineOptions(),
        plugins: [zeroLinePlugin],
      });
    }

    function toggleTrailingWindowControl(mode) {
      if (!trailingWindowWrap) return;
      trailingWindowWrap.style.display = mode === 'trailing_avg' ? '' : 'none';
    }

    function clampTrailingWindow(value) {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return 3;
      return Math.min(Math.max(parsed, 2), 8);
    }

    function populateTeamOptions(seasonKey) {
      if (!teamSelect) return;
      const season = seasonData[seasonKey];
      if (!season) return;
      const teams = season.teams.map((t) => t.team).sort();
      const previous = teamSelect.value;
      teamSelect.innerHTML = '';
      teams.forEach((abbr) => {
        const opt = document.createElement('option');
        opt.value = abbr;
        const display = TEAM_DISPLAY_NAMES[abbr] || abbr;
        opt.textContent = `${display} (${abbr})`;
        teamSelect.appendChild(opt);
      });
      if (teams.includes(previous)) {
        teamSelect.value = previous;
      }
      if (!teamSelect.value && teams.length) {
        teamSelect.value = teams[0];
      }
    }

    function populateTeamSeasonControls(seasonsMap) {
      if (!teamSeasonSelect) return;
      teamSeasonSelect.innerHTML = '';
      const sortedSeasonKeys = Object.keys(seasonsMap).sort();
      sortedSeasonKeys.forEach((seasonKey) => {
        const opt = document.createElement('option');
        opt.value = seasonKey;
        opt.textContent = seasonKey;
        teamSeasonSelect.appendChild(opt);
      });
      const defaultSeason = seasonSelect.value || sortedSeasonKeys[sortedSeasonKeys.length - 1];
      teamSeasonSelect.value = defaultSeason;
      populateTeamOptions(defaultSeason);
    }

    function syncWeekRange() {
      const start = Number(weekStartSelect.value);
      const end = Number(weekEndSelect.value);
      if (start > end) {
        weekEndSelect.value = start;
        return { start, end: start };
      }
      return { start, end };
    }

    function formatNumber(value) {
      return Number.isFinite(value) ? value.toFixed(3) : 'N/A';
    }

    function hexToRgb(hex) {
      const normalized = hex.replace('#', '');
      const bigint = parseInt(normalized, 16);
      return {
        r: (bigint >> 16) & 255,
        g: (bigint >> 8) & 255,
        b: bigint & 255,
      };
    }

    function mixColors(start, end, t) {
      const startRgb = hexToRgb(start);
      const endRgb = hexToRgb(end);
      const clampT = Math.min(Math.max(t, 0), 1);
      const r = Math.round(startRgb.r + (endRgb.r - startRgb.r) * clampT);
      const g = Math.round(startRgb.g + (endRgb.g - startRgb.g) * clampT);
      const b = Math.round(startRgb.b + (endRgb.b - startRgb.b) * clampT);
      return `rgb(${r}, ${g}, ${b})`;
    }

    function getRankColor(rank, totalTeams) {
      if (!Number.isFinite(rank) || totalTeams <= 1) return '#0f172a';
      const position = 1 - ((rank - 1) / Math.max(totalTeams - 1, 1));
      const red = '#ef4444';
      const gray = '#9ca3af';
      const green = '#22c55e';
      if (position <= 0.5) {
        return mixColors(red, gray, position / 0.5);
      }
      return mixColors(gray, green, (position - 0.5) / 0.5);
    }

    function computeRanks(rows, metricKey) {
      const sorted = [...rows].sort((a, b) => {
        const aVal = Number.isFinite(a[metricKey]) ? a[metricKey] : -Infinity;
        const bVal = Number.isFinite(b[metricKey]) ? b[metricKey] : -Infinity;
        if (bVal === aVal) return a.team.localeCompare(b.team);
        return bVal - aVal;
      });
      const rankMap = {};
      sorted.forEach((row, index) => {
        rankMap[row.team] = index + 1;
      });
      return rankMap;
    }

    function renderTable(rows, ranksByMetric = { combined: {}, off: {}, def: {}, sosOff: {}, sosDef: {} }, metricMode = 'raw') {
      tableBody.innerHTML = '';
      if (!rows.length) {
        tableBody.innerHTML = '<tr><td colspan="9">No EPA data for the selected range.</td></tr>';
        return;
      }
      const totalTeams = rows.length;
      const showRaw = metricMode === 'sos' && document.body.classList.contains('sos-mode');
      rows.forEach((row, index) => {
        const tr = document.createElement('tr');
        const combinedRank = ranksByMetric.combined[row.team];
        const offRank = ranksByMetric.off[row.team];
        const defRank = ranksByMetric.def[row.team];
        const sosOffRank = ranksByMetric.sosOff?.[row.team];
        const sosDefRank = ranksByMetric.sosDef?.[row.team];
        const sosOffValue = Number.isFinite(row.sosOffFaced) ? row.sosOffFaced.toFixed(6) : 'N/A';
        const sosDefValue = Number.isFinite(row.sosDefFaced) ? row.sosDefFaced.toFixed(6) : 'N/A';
        tr.innerHTML = `
          <td class="rank-cell" data-value="${index + 1}">${index + 1}</td>
          <td data-value="${row.team}">${row.displayName} (${row.team})</td>
          <td data-type="number" data-value="${Number.isFinite(row.winPct) ? row.winPct : ''}">${row.record ?? 'N/A'}</td>
          <td data-type="number" data-value="${Number.isFinite(row.winPct) ? row.winPct : ''}">${Number.isFinite(row.winPct) ? row.winPct.toFixed(3) : 'N/A'}</td>
          <td class="metric-cell" data-value="${row.combined.toFixed(6)}">
            <span class="metric-value">${formatNumber(row.combined)}</span>
            ${showRaw ? `<span class="raw-value">(raw ${formatNumber(row.rawCombined)})</span>` : ''}
            <span class="rank-label" style="color: ${getRankColor(combinedRank, totalTeams)}">(#${combinedRank})</span>
          </td>
          <td class="metric-cell sos-only" data-value="${sosOffValue}">
            <span class="metric-value">${Number.isFinite(row.sosOffFaced) ? formatNumber(row.sosOffFaced) : 'N/A'}</span>
            ${Number.isFinite(row.sosOffFaced)
              ? `<span class="rank-label" style="color: #0f172a">(#${sosOffRank})</span>`
              : ''}
          </td>
          <td class="metric-cell sos-only" data-value="${sosDefValue}">
            <span class="metric-value">${Number.isFinite(row.sosDefFaced) ? formatNumber(row.sosDefFaced) : 'N/A'}</span>
            ${Number.isFinite(row.sosDefFaced)
              ? `<span class="rank-label" style="color: #0f172a">(#${sosDefRank})</span>`
              : ''}
          </td>
          <td class="metric-cell" data-value="${row.off.toFixed(6)}">
            <span class="metric-value">${formatNumber(row.off)}</span>
            ${showRaw ? `<span class="raw-value">(raw ${formatNumber(row.rawOff)})</span>` : ''}
            <span class="rank-label" style="color: ${getRankColor(offRank, totalTeams)}">(#${offRank})</span>
          </td>
          <td class="metric-cell" data-value="${row.def.toFixed(6)}">
            <span class="metric-value">${formatNumber(row.def)}</span>
            ${showRaw ? `<span class="raw-value">(raw ${formatNumber(row.rawDef)})</span>` : ''}
            <span class="rank-label" style="color: ${getRankColor(defRank, totalTeams)}">(#${defRank})</span>
          </td>
        `;
        tableBody.appendChild(tr);
      });
      updateRankNumbers();
    }

    function updateRankNumbers() {
      Array.from(tableBody.querySelectorAll('tr')).forEach((row, index) => {
        const rankCell = row.querySelector('.rank-cell');
        if (rankCell) {
          rankCell.textContent = index + 1;
          rankCell.dataset.value = index + 1;
        }
      });
    }

    function getCellValue(cell, type) {
      const raw = cell.dataset.value ?? cell.textContent.trim();
      if (type === 'number') {
        const parsed = parseFloat(raw);
        return Number.isNaN(parsed) ? -Infinity : parsed;
      }
      return raw.toLowerCase();
    }

    function sortTable(columnIndex, toggle = true) {
      const header = tableHeaders[columnIndex];
      if (!header) return;

      const type = header.dataset.type || 'string';
      const isSameColumn = sortState.column === columnIndex;
      const direction = toggle
        ? (isSameColumn && sortState.direction === 'asc' ? 'desc' : 'asc')
        : (sortState.direction || 'asc');

      const rows = Array.from(tableBody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const aVal = getCellValue(a.children[columnIndex], type);
        const bVal = getCellValue(b.children[columnIndex], type);
        if (aVal === bVal) return 0;
        if (direction === 'asc') return aVal > bVal ? 1 : -1;
        return aVal < bVal ? 1 : -1;
      });

      tableBody.innerHTML = '';
      rows.forEach((row) => tableBody.appendChild(row));

      updateRankNumbers();

      tableHeaders.forEach((th) => th.classList.remove('sorted-asc', 'sorted-desc'));
      header.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');

      sortState.column = columnIndex;
      sortState.direction = direction;
    }

    tableHeaders.forEach((header, index) => {
      header.addEventListener('click', () => sortTable(index));
    });

    const splitSortState = { column: null, direction: 'desc' };

    function averageWeeksSplit(teamWeeks, start, end) {
      let offPassSum = 0, offPassPlays = 0;
      let offRushSum = 0, offRushPlays = 0;
      let defPassSum = 0, defPassPlays = 0;
      let defRushSum = 0, defRushPlays = 0;
      let count = 0;

      for (let w = start; w <= end; w += 1) {
        const payload = teamWeeks[w];
        if (!payload || typeof payload.off !== 'number' || typeof payload.def !== 'number') continue;
        count += 1;
        offPassSum += Number(payload.off_pass ?? 0) * Number(payload.off_pass_plays ?? 0);
        offPassPlays += Number(payload.off_pass_plays ?? 0);
        offRushSum += Number(payload.off_rush ?? 0) * Number(payload.off_rush_plays ?? 0);
        offRushPlays += Number(payload.off_rush_plays ?? 0);
        defPassSum += Number(payload.def_pass ?? 0) * Number(payload.def_pass_plays ?? 0);
        defPassPlays += Number(payload.def_pass_plays ?? 0);
        defRushSum += Number(payload.def_rush ?? 0) * Number(payload.def_rush_plays ?? 0);
        defRushPlays += Number(payload.def_rush_plays ?? 0);
      }

      if (count === 0) return null;
      return {
        offPass: offPassPlays > 0 ? offPassSum / offPassPlays : null,
        offPassPlays,
        offRush: offRushPlays > 0 ? offRushSum / offRushPlays : null,
        offRushPlays,
        defPass: defPassPlays > 0 ? defPassSum / defPassPlays : null,
        defPassPlays,
        defRush: defRushPlays > 0 ? defRushSum / defRushPlays : null,
        defRushPlays,
      };
    }

    function buildSplitRows(selectedSeason, startWeek, endWeek) {
      const season = seasonData[selectedSeason];
      if (!season) return [];
      return season.teams
        .map((teamEntry) => {
          const weeks = {};
          Object.entries(teamEntry.weeks).forEach(([week, values]) => {
            weeks[Number(week)] = values;
          });
          const averaged = averageWeeks(weeks, startWeek, endWeek);
          const split = averageWeeksSplit(weeks, startWeek, endWeek);
          if (!averaged || !split) return null;
          const combined = averaged.off + averaged.def;
          const record = computeRecord(season, teamEntry.team, startWeek, endWeek);
          return {
            team: teamEntry.team,
            displayName: TEAM_DISPLAY_NAMES[teamEntry.team] || teamEntry.team,
            combined,
            record: record?.recordStr ?? null,
            winPct: record?.winPct ?? null,
            offPass: split.offPass,
            offRush: split.offRush,
            defPass: split.defPass,
            defRush: split.defRush,
            offPassPlays: split.offPassPlays,
            offRushPlays: split.offRushPlays,
            defPassPlays: split.defPassPlays,
            defRushPlays: split.defRushPlays,
          };
        })
        .filter(Boolean);
    }


    // --- Player drill-down -------------------------------------------------
    // The offensive pass/rush cells expand to show who produced the number.
    // Player data is split one file per season so this costs a ~0.5 MB fetch
    // for the season you are looking at, not every season ever played.

    const playerSeasonCache = new Map();

    const ROLE_GROUPS = {
      offPass: [
        { role: 'passing', title: 'Passing', unit: 'Dropbacks' },
        { role: 'receiving', title: 'Receiving', unit: 'Targets' },
      ],
      offRush: [{ role: 'rushing', title: 'Rushing', unit: 'Rushes' }],
    };

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
      ));
    }

    function loadPlayerSeason(season) {
      if (!playerSeasonCache.has(season)) {
        const url = new URL(`data/players/${season}.json`, document.baseURI);
        playerSeasonCache.set(
          season,
          fetch(url).then((res) => (res.ok ? res.json() : null)).catch(() => null)
        );
      }
      return playerSeasonCache.get(season);
    }

    function playersForTeam(payload, team, weekStart, weekEnd, role) {
      const totals = new Map();
      for (let week = weekStart; week <= weekEnd; week += 1) {
        const teams = payload.weeks[String(week)];
        const entries = teams && teams[team];
        if (!entries) continue;
        entries.forEach((entry) => {
          if (entry.r !== role) return;
          const acc = totals.get(entry.i) || { name: entry.n, epa: 0, plays: 0 };
          acc.epa += entry.e;
          acc.plays += entry.p;
          acc.name = entry.n;
          totals.set(entry.i, acc);
        });
      }
      return Array.from(totals.values()).sort((a, b) => b.epa - a.epa);
    }

    function renderPlayerGroup(group, players) {
      if (!players.length) return '';
      // Flag by share of the team's own workload rather than a fixed play count,
      // so the threshold scales with however many weeks are selected.
      const teamPlays = players.reduce((sum, p) => sum + p.plays, 0);
      const body = players.map((player) => {
        const thin = teamPlays > 0 && player.plays / teamPlays < 0.1;
        const flag = thin
          ? ` <span class="low-volume" title="Under 10% of the team's ${group.unit.toLowerCase()} in this range">low volume</span>`
          : '';
        return `<tr>
              <td>${escapeHtml(player.name)}${flag}</td>
              <td class="num">${player.epa.toFixed(1)}</td>
              <td class="num">${formatNumber(player.epa / player.plays)}</td>
              <td class="num">${player.plays}</td>
            </tr>`;
      }).join('');
      return `<div class="player-group">
            <h4>${group.title}</h4>
            <table class="player-table">
              <thead><tr><th>Player</th><th class="num">EPA</th><th class="num">EPA/play</th><th class="num">${group.unit}</th></tr></thead>
              <tbody>${body}</tbody>
            </table>
          </div>`;
    }

    async function fillPlayerDetail(cell, team, drillKey) {
      const season = seasonSelect.value;
      const weekStart = Number(weekStartSelect.value);
      const weekEnd = Number(weekEndSelect.value);
      const payload = await loadPlayerSeason(season);

      if (!payload) {
        cell.innerHTML = `<p class="player-empty">No player data for ${escapeHtml(season)} yet. Run the season backfill to populate it.</p>`;
        return;
      }

      const groups = ROLE_GROUPS[drillKey] || [];
      const html = groups
        .map((group) => renderPlayerGroup(group, playersForTeam(payload, team, weekStart, weekEnd, group.role)))
        .join('');

      cell.innerHTML = html || '<p class="player-empty">No plays for this team in the selected weeks.</p>';
      if (drillKey === 'offPass' && html) {
        cell.insertAdjacentHTML(
          'beforeend',
          '<p class="player-note">Receiving is per target. Throwaways and batted balls have no intended receiver, so they count against the passer only.</p>'
        );
      }
    }

    function collapseAllPlayerDetails() {
      splitTableBody.querySelectorAll('tr.player-detail').forEach((row) => row.remove());
      splitTableBody.querySelectorAll('.drill-toggle[aria-expanded="true"]').forEach((btn) => {
        btn.setAttribute('aria-expanded', 'false');
      });
    }

    function togglePlayerDetail(button) {
      const teamRow = button.closest('tr');
      const team = button.dataset.team;
      const drillKey = button.dataset.drill;
      const isOpen = button.getAttribute('aria-expanded') === 'true';
      collapseAllPlayerDetails();
      if (isOpen) return;

      button.setAttribute('aria-expanded', 'true');
      const detail = document.createElement('tr');
      detail.className = 'player-detail';
      const cell = document.createElement('td');
      cell.colSpan = teamRow.children.length;
      cell.innerHTML = '<p class="player-empty">Loading players…</p>';
      detail.appendChild(cell);
      teamRow.insertAdjacentElement('afterend', detail);
      fillPlayerDetail(cell, team, drillKey);
    }

    splitTableBody.addEventListener('click', (event) => {
      const cell = event.target.closest('td.drillable');
      const button = event.target.closest('.drill-toggle') || (cell && cell.querySelector('.drill-toggle'));
      if (button) togglePlayerDetail(button);
    });

    function renderSplitTable(rows) {
      splitTableBody.innerHTML = '';
      const hasData = rows.some((r) => r.offPass !== null || r.offRush !== null || r.defPass !== null || r.defRush !== null);
      if (!rows.length || !hasData) {
        splitTableBody.innerHTML = '<tr><td colspan="8">Pass/run breakdown not available — re-run data fetch to populate split columns.</td></tr>';
        return;
      }

      const totalTeams = rows.length;
      const ranksByMetric = {
        combined: computeRanks(rows, 'combined'),
        offPass: computeRanks(rows.filter((r) => r.offPass !== null), 'offPass'),
        offRush: computeRanks(rows.filter((r) => r.offRush !== null), 'offRush'),
        defPass: computeRanks(rows.filter((r) => r.defPass !== null), 'defPass'),
        defRush: computeRanks(rows.filter((r) => r.defRush !== null), 'defRush'),
      };

      rows.forEach((_row, index) => {
        const row = _row;
        const tr = document.createElement('tr');
        const combinedRank = ranksByMetric.combined[row.team];
        const offPassRank = ranksByMetric.offPass[row.team];
        const offRushRank = ranksByMetric.offRush[row.team];
        const defPassRank = ranksByMetric.defPass[row.team];
        const defRushRank = ranksByMetric.defRush[row.team];

        function metricCell(value, rank, plays, drillKey) {
          const playsHint = plays > 0 ? ` title="${plays} plays"` : '';
          if (value === null) return `<td data-value="-9999">N/A</td>`;
          // Only offence drills down: play-by-play credits defensive EPA to the
          // team, with no defender named on the play.
          const drill = drillKey
            ? `<button type="button" class="drill-toggle" aria-expanded="false" data-team="${row.team}" data-drill="${drillKey}" aria-label="Show the players behind this number"></button>`
            : '';
          const drillable = drillKey ? ' drillable' : '';
          return `<td class="metric-cell${drillable}" data-value="${value.toFixed(6)}"${playsHint}>
            <span class="metric-value">${formatNumber(value)}</span>
            <span class="rank-label" style="color: ${getRankColor(rank, totalTeams)}">(#${rank})</span>
            ${drill}
          </td>`;
        }

        tr.innerHTML = `
          <td class="rank-cell" data-value="${index + 1}">${index + 1}</td>
          <td data-value="${row.team}">${row.displayName} (${row.team})</td>
          <td class="metric-cell" data-value="${row.combined.toFixed(6)}">
            <span class="metric-value">${formatNumber(row.combined)}</span>
            <span class="rank-label" style="color: ${getRankColor(combinedRank, totalTeams)}">(#${combinedRank})</span>
          </td>
          ${metricCell(row.offPass, offPassRank, row.offPassPlays, 'offPass')}
          ${metricCell(row.offRush, offRushRank, row.offRushPlays, 'offRush')}
          ${metricCell(row.defPass, defPassRank, row.defPassPlays)}
          ${metricCell(row.defRush, defRushRank, row.defRushPlays)}
          <td data-type="number" data-value="${Number.isFinite(row.winPct) ? row.winPct : ''}">${row.record ?? 'N/A'}</td>
        `;
        splitTableBody.appendChild(tr);
      });
      updateSplitRankNumbers();
    }

    function updateSplitRankNumbers() {
      Array.from(splitTableBody.querySelectorAll('tr:not(.player-detail)')).forEach((row, index) => {
        const rankCell = row.querySelector('.rank-cell');
        if (rankCell) {
          rankCell.textContent = index + 1;
          rankCell.dataset.value = index + 1;
        }
      });
    }

    function sortSplitTable(columnIndex, toggle = true) {
      const header = splitTableHeaders[columnIndex];
      if (!header) return;
      const type = header.dataset.type || 'string';
      const isSameColumn = splitSortState.column === columnIndex;
      const direction = toggle
        ? (isSameColumn && splitSortState.direction === 'asc' ? 'desc' : 'asc')
        : (splitSortState.direction || 'asc');
      // Re-ordering rows would strand any open detail row under the wrong team.
      collapseAllPlayerDetails();
      const rows = Array.from(splitTableBody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        const aVal = getCellValue(a.children[columnIndex], type);
        const bVal = getCellValue(b.children[columnIndex], type);
        if (aVal === bVal) return 0;
        return direction === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
      });
      splitTableBody.innerHTML = '';
      rows.forEach((row) => splitTableBody.appendChild(row));
      updateSplitRankNumbers();
      splitTableHeaders.forEach((th) => th.classList.remove('sorted-asc', 'sorted-desc'));
      header.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
      splitSortState.column = columnIndex;
      splitSortState.direction = direction;
    }

    splitTableHeaders.forEach((header, index) => {
      header.addEventListener('click', () => sortSplitTable(index));
    });

    function isSplitViewActive() {
      return splitSection.style.display !== 'none';
    }

    function refreshSplitTable() {
      const season = seasonSelect.value;
      const { start, end } = syncWeekRange();
      const rows = buildSplitRows(season, start, end);
      renderSplitTable(rows);
      sortSplitTable(splitSortState.column ?? 2, false); // column 2 = Combined EPA
    }

    viewSummaryBtn.addEventListener('click', () => {
      viewSummaryBtn.classList.add('active');
      viewSplitBtn.classList.remove('active');
      summaryView.style.display = '';
      splitSection.style.display = 'none';
    });

    viewSplitBtn.addEventListener('click', () => {
      viewSplitBtn.classList.add('active');
      viewSummaryBtn.classList.remove('active');
      summaryView.style.display = 'none';
      splitSection.style.display = '';
      refreshSplitTable();
    });

    function refreshChart() {
      hideStatus();
      const season = seasonSelect.value;
      const { start, end } = syncWeekRange();
      const metricMode = metricModeSelect.value;
      const sosBasis = sosBasisSelect.value;
      const sosData = metricMode === 'sos'
        ? computeSosRatingsForRange(season, start, end, sosBasis)
        : null;
      const sosError = metricMode === 'sos' && sosData && sosData.error;
      const effectiveMetricMode = metricMode === 'sos' && (!sosData || sosError) ? 'raw' : metricMode;
      if (metricMode === 'sos' && (!sosData || sosError)) {
        const reason = sosError ? sosData.error : 'SOS metrics unavailable for this selection; showing raw EPA values instead.';
        showStatus(reason, 'error');
      }
      updateSosControlsVisibility(effectiveMetricMode);
      const rows = buildTeamRows(season, start, end, effectiveMetricMode, sosBasis, sosData);
      if (rows.length === 0) {
        showStatus('No EPA points available for that range. Try a different week selection.', 'error');
        if (scatterChart) scatterChart.destroy();
        renderTable([]);
        return;
      }
      const points = rows.map((row) => ({ x: row.x, y: row.y, label: row.label, backgroundColor: row.backgroundColor, borderColor: row.borderColor }));
      const ranksByMetric = {
        combined: computeRanks(rows, 'combined'),
        off: computeRanks(rows, 'off'),
        def: computeRanks(rows, 'def'),
        sosOff: effectiveMetricMode === 'sos' ? computeRanks(rows, 'sosOffFaced') : {},
        sosDef: effectiveMetricMode === 'sos' ? computeRanks(rows, 'sosDefFaced') : {},
      };
      renderScatterChart(points, season, start, end, effectiveMetricMode, sosBasis);
      renderTable(rows, ranksByMetric, effectiveMetricMode);
      sortTable(sortState.column ?? 4, false);
    }

    function updateSosControlsVisibility(metricMode) {
      const wrap = document.getElementById('sos-basis-wrap');
      if (wrap) {
        wrap.style.display = metricMode === 'sos' ? '' : 'none';
      }
      document.body.classList.toggle('sos-mode', metricMode === 'sos');
    }

    function populateSeasonControls(seasonsMap) {
      seasonSelect.innerHTML = '';
      const sortedSeasonKeys = Object.keys(seasonsMap).sort();
      sortedSeasonKeys.forEach((seasonKey) => {
        const opt = document.createElement('option');
        opt.value = seasonKey;
        opt.textContent = seasonKey;
        seasonSelect.appendChild(opt);
      });
      const defaultSeason = sortedSeasonKeys[sortedSeasonKeys.length - 1];
      seasonSelect.value = defaultSeason;
      const selected = seasonsMap[seasonSelect.value];
      fillWeekSelect(weekStartSelect, selected.weeks, defaultSeason);
      fillWeekSelect(weekEndSelect, selected.weeks, defaultSeason);
      weekEndSelect.value = selected.weeks[selected.weeks.length - 1];
    }

    function setMetaText(snapshot) {
      const totalSeasons = Object.keys(snapshot.seasons || {}).length;
      const generatedAt = snapshot.generated_at || 'unknown';
      const sha = snapshot.git_sha ? snapshot.git_sha.slice(0, 7) : '';
      metaEl.textContent = totalSeasons
        ? `Loaded ${totalSeasons} seasons. generated_at=${generatedAt}${sha ? ` · git=${sha}` : ''}`
        : '';
    }

    async function bootstrap() {
      try {
        const res = await fetch(DATA_URL);
        if (!res.ok) throw new Error(`Failed to load data (${res.status})`);
        const json = await res.json();
        if (!json || typeof json !== 'object' || !json.seasons) {
          throw new Error('Unexpected JSON payload: missing seasons');
        }
        seasonData = normalizeSeasonPayloads(json.seasons);
        if (!Object.keys(seasonData).length) throw new Error('No seasons found in data');
        setMetaText(json);
        populateSeasonControls(seasonData);
        populateTeamSeasonControls(seasonData);
        toggleTrailingWindowControl(teamModeSelect.value);
        refreshChart();
        renderTeamCharts();
      } catch (err) {
        console.error(err);
        showStatus(`Unable to load data: ${err.message}`, 'error');
      }
    }

    seasonSelect.addEventListener('change', () => {
      const selected = seasonData[seasonSelect.value];
      if (!selected) return;
      fillWeekSelect(weekStartSelect, selected.weeks, seasonSelect.value);
      fillWeekSelect(weekEndSelect, selected.weeks, seasonSelect.value);
      weekEndSelect.value = selected.weeks[selected.weeks.length - 1];
      refreshChart();
      if (isSplitViewActive()) refreshSplitTable();
      if (teamSeasonSelect) {
        teamSeasonSelect.value = seasonSelect.value;
        populateTeamOptions(teamSeasonSelect.value);
        renderTeamCharts();
      }
    });

    weekStartSelect.addEventListener('change', () => {
      syncWeekRange();
      if (isSplitViewActive()) refreshSplitTable();
    });
    weekEndSelect.addEventListener('change', () => {
      syncWeekRange();
      if (isSplitViewActive()) refreshSplitTable();
    });
    metricModeSelect.addEventListener('change', () => {
      updateSosControlsVisibility(metricModeSelect.value);
      refreshChart();
    });
    sosBasisSelect.addEventListener('change', refreshChart);
    updateButton.addEventListener('click', () => {
      refreshChart();
      if (isSplitViewActive()) refreshSplitTable();
    });
    if (teamSeasonSelect) {
      teamSeasonSelect.addEventListener('change', () => {
        populateTeamOptions(teamSeasonSelect.value);
        renderTeamCharts();
      });
    }
    if (teamSelect) teamSelect.addEventListener('change', renderTeamCharts);
    if (teamModeSelect) {
      teamModeSelect.addEventListener('change', () => {
        toggleTrailingWindowControl(teamModeSelect.value);
        renderTeamCharts();
      });
    }
    if (trailingWindowInput) {
      trailingWindowInput.addEventListener('change', () => {
        trailingWindowInput.value = clampTrailingWindow(trailingWindowInput.value);
        renderTeamCharts();
      });
    }
    updateSosControlsVisibility(metricModeSelect.value);
    toggleTrailingWindowControl(teamModeSelect.value);
    bootstrap();
