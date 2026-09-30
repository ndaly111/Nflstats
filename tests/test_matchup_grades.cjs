const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const element = {
  getContext() {}, querySelector() { return this; }, querySelectorAll() { return []; },
  addEventListener() {}, appendChild() {}, setAttribute() {}, style: { setProperty() {} }, dataset: {},
  classList: { toggle() {}, contains() { return false; }, add() {}, remove() {} },
};
const context = vm.createContext({
  URL, console, URLSearchParams,
  window: { location: { search: '' } },
  localStorage: { getItem() { return null; }, setItem() {} },
  document: {
    baseURI: 'http://localhost/',
    getElementById() { return element; },
    querySelectorAll() { return []; },
    createElement() { return { ...element, style: { setProperty() {} }, classList: { ...element.classList } }; },
    createElementNS() { return element; },
    body: element,
  },
});
const source = fs.readFileSync('assets/js/matchups.js', 'utf8').replace(/\n\s*init\(\);\s*$/, '\n');
vm.runInContext(source, context);
context.assert = assert;
context.dataset = JSON.parse(fs.readFileSync('data/epa.json', 'utf8'));

// Grade cutoffs mirror the front-page tiers (S top 5%, A 80-95, B 60-80, C 40-60, D 20-40, F bottom 20)
// applied to a 32-team league rank.
vm.runInContext(`
{
  const expect = { 1: 'S', 2: 'S', 3: 'A', 6: 'A', 7: 'B', 13: 'B', 14: 'C', 19: 'C', 20: 'D', 26: 'D', 27: 'F', 32: 'F' };
  for (const [rank, grade] of Object.entries(expect)) {
    assert.equal(rankToGrade(Number(rank), 32), grade, 'rank ' + rank);
  }
  assert.equal(rankToGrade(null, 32), null);
  assert.equal(rankToGrade(3, 0), null);
}
`, context);

// Pass/rush splits are play-weighted means of the team-week data for weeks before the target week.
vm.runInContext(`
{
  const season = dataset.seasons['2026'];
  const ratings = computeTeamAggregates(season, 3, '2026');
  const ari = season.teams.find((t) => t.team === 'ARI');
  const wk = ['1', '2'].map((k) => ari.weeks[k]).filter(Boolean);
  const wmean = (key, playsKey) => {
    const plays = wk.reduce((a, w) => a + w[playsKey], 0);
    return wk.reduce((a, w) => a + w[key] * w[playsKey], 0) / plays;
  };
  assert.ok(Math.abs(ratings.ARI.offPassEPA - wmean('off_pass', 'off_pass_plays')) < 1e-9, 'offPass');
  assert.ok(Math.abs(ratings.ARI.offRushEPA - wmean('off_rush', 'off_rush_plays')) < 1e-9, 'offRush');
  assert.ok(Math.abs(ratings.ARI.defPassEPA - wmean('def_pass', 'def_pass_plays')) < 1e-9, 'defPass');
  assert.ok(Math.abs(ratings.ARI.defRushEPA - wmean('def_rush', 'def_rush_plays')) < 1e-9, 'defRush');
  // Week 1 has no prior games: no splits at all.
  const empty = computeTeamAggregates(season, 1, '2026');
  assert.equal(Object.keys(empty).length, 0);
}
`, context);

// League ranks: every metric ranks all 32 teams 1..32, higher EPA (or defense strength) = better rank.
vm.runInContext(`
{
  const season = dataset.seasons['2026'];
  const ratings = computeTeamAggregates(season, 3, '2026');
  const ranks = computeLeagueRanks(ratings, 'raw');
  for (const metric of ['off', 'def', 'offPass', 'offRush', 'defPass', 'defRush']) {
    const list = Object.values(ranks).map((r) => r[metric].rank).sort((a, b) => a - b);
    assert.deepEqual(list, Array.from({ length: 32 }, (_, i) => i + 1), metric + ' ranks must be 1..32');
    assert.ok(Object.values(ranks).every((r) => r[metric].total === 32), metric + ' total');
  }
  const bestOff = Object.entries(ratings).sort((a, b) => b[1].offEPA - a[1].offEPA)[0][0];
  assert.equal(ranks[bestOff].off.rank, 1);
  assert.equal(ranks[bestOff].off.grade, 'S');
  // Opponent-adjusted mode ranks the adjusted overall numbers but the raw splits.
  const adjusted = computeSOSAdjustedRatings(season, 3, ratings, '2026');
  const sosRanks = computeLeagueRanks(adjusted, 'sos');
  const bestAdj = Object.entries(adjusted).sort((a, b) => b[1].adjOffEPA - a[1].adjOffEPA)[0][0];
  assert.equal(sosRanks[bestAdj].off.rank, 1);
  assert.equal(sosRanks[bestOff].offPass.rank, ranks[bestOff].offPass.rank);
}
`, context);

// Momentum mode carries the last-N split numbers too.
vm.runInContext(`
{
  const season = dataset.seasons['2026'];
  const base = computeTeamAggregates(season, 3, '2026');
  const mom = applyMomentumRatings(base, season, 3, '2026');
  assert.ok(Number.isFinite(mom.ARI.offPassEPA), 'momentum keeps offPass');
  assert.ok(Number.isFinite(mom.ARI.defRushEPA), 'momentum keeps defRush');
}
`, context);

// Lanes carry three matchup rows: overall, passing, rushing, each with grades on both sides.
vm.runInContext(`
{
  const season = dataset.seasons['2026'];
  const week = 2;
  const games = groupGamesForWeek(season, week, '2026');
  const ratings = computeTeamAggregates(season, week, '2026');
  const { lanes } = buildGameEntries(games, ratings, { noRatings: false, week, seasonKey: '2026' });
  assert.ok(lanes.length > 0);
  for (const lane of lanes) {
    assert.deepEqual(lane.rows.map((r) => r.key), ['overall', 'pass', 'rush'], lane.off + ' rows');
    for (const row of lane.rows) {
      assert.ok(['S', 'A', 'B', 'C', 'D', 'F'].includes(row.offGrade), lane.off + ' ' + row.key + ' off grade');
      assert.ok(['S', 'A', 'B', 'C', 'D', 'F'].includes(row.defGrade), lane.def + ' ' + row.key + ' def grade');
      assert.ok(Number.isFinite(row.edge), row.key + ' edge');
    }
    assert.equal(lane.rows[0].edge, lane.edge, 'overall row edge equals lane edge');
  }
}
`, context);

console.log('test_matchup_grades: ok');
