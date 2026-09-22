const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const element = { getContext() {}, querySelector() { return this; }, querySelectorAll() { return []; }, addEventListener() {}, style: {}, classList: { toggle() {}, contains() { return false; }, add() {}, remove() {} } };
const context = vm.createContext({ URL, console, document: { baseURI: 'http://localhost/', getElementById() { return element; }, querySelectorAll() { return []; }, body: element } });
const source = fs.readFileSync('assets/js/main.js', 'utf8').replace('    bootstrap();', '');
vm.runInContext(source, context);
context.dataset = JSON.parse(fs.readFileSync('data/epa.json', 'utf8'));
context.assert = assert;
vm.runInContext('seasonData = normalizeSeasonPayloads(dataset.seasons);', context);

// A single week has no prior week to compare against.
vm.runInContext(`
{
  const single = computeRankMovement('2025', 3, 3, 'raw', 'season_to_date');
  assert.ok(single.error, 'expected an error when the range is one week');
  assert.equal(single.rows.length, 0);
}
`, context);

// Ranks through week N vs through week N-1, for every metric.
vm.runInContext(`
{
  const result = computeRankMovement('2025', 1, 4, 'raw', 'season_to_date');
  assert.equal(result.error, null, String(result.error));
  assert.equal(result.priorEnd, 3);
  assert.equal(result.rows.length, 32);

  for (const metric of ['combined', 'off', 'def']) {
    const ranks = result.rows.map((row) => row.movement[metric].rank).sort((a, b) => a - b);
    assert.deepEqual(ranks, Array.from({ length: 32 }, (_, i) => i + 1), metric + ' ranks must be 1..32');

    for (const row of result.rows) {
      const move = row.movement[metric];
      assert.equal(move.delta, move.prevRank - move.rank, row.team + ' ' + metric + ' delta');
    }

    // Both windows rank the same 32 teams, so the moves must cancel out exactly.
    const total = result.rows.reduce((sum, row) => sum + row.movement[metric].delta, 0);
    assert.equal(total, 0, metric + ' deltas must sum to zero');

    // A positive delta means the team climbed: its rank number got smaller.
    for (const row of result.rows) {
      const move = row.movement[metric];
      if (move.delta > 0) assert.ok(move.rank < move.prevRank, row.team + ' climbed');
      if (move.delta < 0) assert.ok(move.rank > move.prevRank, row.team + ' fell');
    }
  }
}
`, context);

// The current-week ranks must agree with what the EPA Summary table shows.
vm.runInContext(`
{
  const result = computeRankMovement('2025', 1, 4, 'raw', 'season_to_date');
  const summaryRows = buildTeamRows('2025', 1, 4, 'raw', 'season_to_date', null);
  const summaryRanks = computeRanks(summaryRows, 'off');
  for (const row of result.rows) {
    assert.equal(row.movement.off.rank, summaryRanks[row.team], row.team + ' must match the summary table');
  }
}
`, context);

// A team on bye is flagged, because it can still move while sitting out.
vm.runInContext(`
{
  const result = computeRankMovement('2025', 1, 8, 'raw', 'season_to_date');
  const ari = result.rows.find((row) => row.team === 'ARI');
  assert.ok(ari.onBye, 'ARI has no week 8 game and should be flagged');
  const played = result.rows.find((row) => row.team !== 'ARI' && !row.onBye);
  assert.ok(played, 'expected at least one team to have played week 8');
}
`, context);

// SOS-adjusted mode ranks both windows on the same basis.
vm.runInContext(`
{
  const result = computeRankMovement('2025', 1, 6, 'sos', 'season_to_date');
  assert.equal(result.error, null, String(result.error));
  assert.equal(result.rows.length, 32);
  const total = result.rows.reduce((sum, row) => sum + row.movement.combined.delta, 0);
  assert.equal(total, 0, 'sos deltas must sum to zero');
  const raw = computeRankMovement('2025', 1, 6, 'raw', 'season_to_date');
  const sosOrder = result.rows.map((row) => row.movement.combined.rank).join(',');
  const rawOrder = raw.rows.map((row) => row.movement.combined.rank).join(',');
  assert.notEqual(sosOrder, rawOrder, 'sos ranks should differ from raw ranks');
}
`, context);

console.log('Rank movement checks passed.');
