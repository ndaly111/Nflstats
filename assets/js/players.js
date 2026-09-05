(function () {
  'use strict';

  const TEAM_NAMES = {
    ARI: 'Arizona', ATL: 'Atlanta', BAL: 'Baltimore', BUF: 'Buffalo', CAR: 'Carolina', CHI: 'Chicago',
    CIN: 'Cincinnati', CLE: 'Cleveland', DAL: 'Dallas', DEN: 'Denver', DET: 'Detroit', GB: 'Green Bay',
    HOU: 'Houston', IND: 'Indianapolis', JAX: 'Jacksonville', KC: 'Kansas City', LAC: 'LA Chargers',
    LAR: 'Los Angeles Rams', LV: 'Las Vegas', MIA: 'Miami', MIN: 'Minnesota', NE: 'New England',
    NO: 'New Orleans', NYG: 'NY Giants', NYJ: 'NY Jets', PHI: 'Philadelphia', PIT: 'Pittsburgh',
    SEA: 'Seattle', SF: 'San Francisco', TB: 'Tampa Bay', TEN: 'Tennessee', WAS: 'Washington',
    // Codes the league used before the moves; the archive spans 26 seasons.
    LA: 'Los Angeles Rams', STL: 'St. Louis', SD: 'San Diego', OAK: 'Oakland', JAC: 'Jacksonville',
  };

  // Play-by-play still writes LA for the Rams; the team pages show LAR. Match them.
  const SHORT_CODES = { LA: 'LAR', JAC: 'JAX' };

  // Minimum plays to be ranked, per week of the selected range, with a floor so
  // a one-week view still asks for a real workload. Scaling by weeks keeps the
  // bar honest whether you are looking at week 3 or a whole season.
  //
  // The notes exist because these numbers are attribution, not skill: they say
  // who produced the team's results, and how repeatable that tends to be
  // differs sharply by role (rushing efficiency barely correlates year to year).
  const ROLES = {
    passing: {
      label: 'Passing', unit: 'dropbacks', one: 'dropback', perWeek: 8, floor: 10,
      note: 'Passing numbers are part quarterback, part protection and receivers — they describe the results of his dropbacks, not the quarterback alone.',
    },
    rushing: {
      label: 'Rushing', unit: 'rushes', one: 'rush', perWeek: 4, floor: 5,
      note: 'Rushing efficiency mostly reflects blocking, scheme and game situation. It says what happened with each runner carrying, not who the better runner is — the same back barely correlates season to season.',
    },
    receiving: {
      label: 'Receiving', unit: 'targets', one: 'target', perWeek: 2, floor: 3,
      note: 'EPA per target depends heavily on role — deep threats and checkdown targets are not on the same scale, so compare players with similar jobs.',
    },
  };

  const seasonSelect = document.getElementById('season-select');
  const weekStartSelect = document.getElementById('week-start');
  const weekEndSelect = document.getElementById('week-end');
  const statusEl = document.getElementById('status');
  const summaryEl = document.getElementById('league-summary');
  const resultsEl = document.getElementById('results');
  const roleGroup = document.getElementById('role-group');
  const viewGroup = document.getElementById('view-group');
  const sortGroup = document.getElementById('sort-group');

  const seasonCache = new Map();
  let payload = null;
  let state = { role: 'passing', view: 'league', sort: 'total' };

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (ch) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
    ));
  }

  function setStatus(message, tone) {
    if (!message) {
      statusEl.hidden = true;
      return;
    }
    statusEl.hidden = false;
    statusEl.textContent = message;
    statusEl.className = tone === 'error' ? 'notice error' : 'notice';
  }

  function loadSeason(season) {
    if (!seasonCache.has(season)) {
      const url = new URL(`data/players/${season}.json`, document.baseURI);
      seasonCache.set(season, fetch(url).then((res) => {
        if (!res.ok) throw new Error(`No player data for ${season}`);
        return res.json();
      }));
    }
    return seasonCache.get(season);
  }

  function selectedWeeks() {
    const start = Number(weekStartSelect.value);
    const end = Number(weekEndSelect.value);
    return { start, end, span: Math.max(1, end - start + 1) };
  }

  /** Roll the selected weeks up into one row per player for the chosen role. */
  function collectPlayers(role, start, end) {
    const totals = new Map();
    for (let week = start; week <= end; week += 1) {
      const teams = payload.weeks[String(week)];
      if (!teams) continue;
      Object.keys(teams).forEach((team) => {
        teams[team].forEach((entry) => {
          if (entry.r !== role) return;
          const key = `${team}|${entry.i}`;
          const acc = totals.get(key) || { id: entry.i, name: entry.n, team, epa: 0, plays: 0 };
          acc.epa += entry.e;
          acc.plays += entry.p;
          acc.name = entry.n;
          totals.set(key, acc);
        });
      });
    }
    return Array.from(totals.values()).map((p) => ({ ...p, perPlay: p.epa / p.plays }));
  }

  function sortPlayers(players) {
    const key = state.sort === 'total' ? 'epa' : 'perPlay';
    return players.slice().sort((a, b) => b[key] - a[key]);
  }

  function ordinal(n) {
    const rem100 = n % 100;
    if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
    return `${n}${['th', 'st', 'nd', 'rd'][n % 10] || 'th'}`;
  }

  /**
   * League context. The average is play-weighted across every play in the role,
   * which is the real league rate; percentiles only rank qualified players,
   * because a 3-carry sample is not a season.
   */
  function leagueContext(players, role, weekSpan) {
    const cfg = ROLES[role];
    const minPlays = Math.max(cfg.floor, cfg.perWeek * weekSpan);
    const totalEpa = players.reduce((sum, p) => sum + p.epa, 0);
    const totalPlays = players.reduce((sum, p) => sum + p.plays, 0);
    const average = totalPlays > 0 ? totalEpa / totalPlays : 0;

    const qualified = players.filter((p) => p.plays >= minPlays);
    const ranked = qualified.slice().sort((a, b) => a.perPlay - b.perPlay);
    const percentile = new Map();
    ranked.forEach((p, index) => {
      const pct = ranked.length > 1 ? Math.round((index / (ranked.length - 1)) * 100) : 100;
      percentile.set(`${p.team}|${p.id}`, pct);
    });

    const spread = qualified.reduce((max, p) => Math.max(max, Math.abs(p.perPlay - average)), 0);
    return { average, minPlays, qualified: qualified.length, percentile, spread: spread || 1 };
  }

  function bar(player, ctx) {
    const deviation = player.perPlay - ctx.average;
    const width = Math.min(50, (Math.abs(deviation) / ctx.spread) * 50);
    const side = deviation >= 0 ? 'above' : 'below';
    const style = deviation >= 0
      ? `left:50%;width:${width}%`
      : `right:50%;width:${width}%`;
    const wording = `${Math.abs(deviation).toFixed(3)} ${deviation >= 0 ? 'above' : 'below'} the league average`;
    return `<div class="bar" role="img" aria-label="${wording}">
        <span class="bar-axis"></span>
        <span class="bar-fill ${side}" style="${style}"></span>
      </div>`;
  }

  function playerRow(player, ctx, rank, role, showTeam) {
    const cfg = ROLES[role];
    const key = `${player.team}|${player.id}`;
    const pct = ctx.percentile.get(key);
    const thin = player.plays < ctx.minPlays;
    // Show the number the list is ordered by, so the ranking reads as it sorts.
    const byTotal = state.sort === 'total';
    const headline = byTotal ? player.epa.toFixed(1) : player.perPlay.toFixed(3);
    const meta = [
      byTotal ? `${player.perPlay.toFixed(3)} per ${cfg.one}` : `${player.epa.toFixed(1)} EPA`,
      `${player.plays} ${cfg.unit}`,
      thin ? 'below the ranking cut' : `${ordinal(pct)} pct`,
    ].join(' · ');

    return `<li class="player${thin ? ' thin' : ''}">
        <div class="player-head">
          ${rank ? `<span class="rank">${rank}</span>` : ''}
          <span class="name">${escapeHtml(player.name)}</span>
          ${showTeam ? `<span class="team-tag">${escapeHtml(SHORT_CODES[player.team] || player.team)}</span>` : ''}
          <span class="value">${headline}</span>
        </div>
        ${bar(player, ctx)}
        <p class="meta">${meta}</p>
      </li>`;
  }

  function renderLeague(players, ctx, role) {
    const cfg = ROLES[role];
    const ranked = sortPlayers(players.filter((p) => p.plays >= ctx.minPlays));
    if (!ranked.length) {
      return '<p class="empty">No player cleared the minimum for this range.</p>';
    }
    const rows = ranked
      .map((p, i) => playerRow(p, ctx, i + 1, role, true))
      .join('');
    return `<ol class="player-list">${rows}</ol>`;
  }

  function renderByTeam(players, ctx, role) {
    const cfg = ROLES[role];
    const byTeam = new Map();
    players.forEach((p) => {
      const bucket = byTeam.get(p.team) || [];
      bucket.push(p);
      byTeam.set(p.team, bucket);
    });

    // Team rate for the role is the sum of its players' work, which is the same
    // thing the team table calls Off Pass / Off Rush.
    const teams = Array.from(byTeam.entries()).map(([team, roster]) => {
      const epa = roster.reduce((sum, p) => sum + p.epa, 0);
      const plays = roster.reduce((sum, p) => sum + p.plays, 0);
      return { team, roster, epa, plays, perPlay: plays > 0 ? epa / plays : 0 };
    }).sort((a, b) => b.perPlay - a.perPlay);

    if (!teams.length) return '<p class="empty">No plays in this range.</p>';

    return teams.map((entry, index) => {
      const name = TEAM_NAMES[entry.team] || entry.team;
      const rows = sortPlayers(entry.roster)
        .map((p) => playerRow(p, ctx, null, role, false))
        .join('');
      const delta = entry.perPlay - ctx.average;
      const sign = delta >= 0 ? '+' : '−';
      return `<details class="team">
          <summary>
            <span class="rank">${index + 1}</span>
            <span class="name">${escapeHtml(name)}</span>
            <span class="value">${entry.perPlay.toFixed(3)}</span>
            <span class="delta ${delta >= 0 ? 'above' : 'below'}">${sign}${Math.abs(delta).toFixed(3)}</span>
          </summary>
          <ul class="player-list">${rows}</ul>
        </details>`;
    }).join('');
  }

  function render() {
    if (!payload) return;
    const { start, end, span } = selectedWeeks();
    const role = state.role;
    const cfg = ROLES[role];
    const players = collectPlayers(role, start, end);

    if (!players.length) {
      summaryEl.textContent = '';
      resultsEl.innerHTML = '<p class="empty">No plays in this range.</p>';
      return;
    }

    const ctx = leagueContext(players, role, span);
    summaryEl.innerHTML = `League average <strong>${ctx.average.toFixed(3)}</strong> EPA per ${cfg.one}
      · ${ctx.qualified} players with ${ctx.minPlays}+ ${cfg.unit}
      · bars show distance from that average
      <span class="role-note">${cfg.note}</span>`;

    resultsEl.innerHTML = state.view === 'league'
      ? renderLeague(players, ctx, role)
      : renderByTeam(players, ctx, role);
  }

  function wireSegmented(group, key) {
    group.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-value]');
      if (!button) return;
      state = { ...state, [key]: button.dataset.value };
      Array.from(group.querySelectorAll('button')).forEach((b) => {
        const on = b === button;
        b.classList.toggle('active', on);
        b.setAttribute('aria-pressed', String(on));
      });
      render();
    });
  }

  function fillWeeks(weeks) {
    [weekStartSelect, weekEndSelect].forEach((select) => {
      select.innerHTML = weeks
        .map((w) => `<option value="${w}">Week ${w}</option>`)
        .join('');
    });
    weekStartSelect.value = String(weeks[0]);
    weekEndSelect.value = String(weeks[weeks.length - 1]);
  }

  async function selectSeason(season) {
    setStatus(`Loading ${season}…`);
    try {
      payload = await loadSeason(season);
    } catch (err) {
      payload = null;
      resultsEl.innerHTML = '';
      summaryEl.textContent = '';
      setStatus(
        `No player data for ${season} yet. Only seasons listed in data/players are available.`,
        'error'
      );
      return;
    }
    const weeks = Object.keys(payload.weeks).map(Number).sort((a, b) => a - b);
    fillWeeks(weeks);
    setStatus('');
    render();
  }

  async function bootstrap() {
    let seasons = [];
    try {
      const res = await fetch(new URL('data/players/index.json', document.baseURI));
      if (res.ok) seasons = (await res.json()).seasons || [];
    } catch (err) {
      seasons = [];
    }
    if (!seasons.length) {
      setStatus('No player data published yet. Run the season backfill to populate it.', 'error');
      return;
    }

    seasons.sort((a, b) => b - a);
    seasonSelect.innerHTML = seasons.map((s) => `<option value="${s}">${s}</option>`).join('');
    seasonSelect.value = String(seasons[0]);

    seasonSelect.addEventListener('change', () => selectSeason(seasonSelect.value));
    weekStartSelect.addEventListener('change', () => {
      if (Number(weekEndSelect.value) < Number(weekStartSelect.value)) {
        weekEndSelect.value = weekStartSelect.value;
      }
      render();
    });
    weekEndSelect.addEventListener('change', () => {
      if (Number(weekEndSelect.value) < Number(weekStartSelect.value)) {
        weekStartSelect.value = weekEndSelect.value;
      }
      render();
    });
    wireSegmented(roleGroup, 'role');
    wireSegmented(viewGroup, 'view');
    wireSegmented(sortGroup, 'sort');

    await selectSeason(seasonSelect.value);
  }

  bootstrap();
})();
