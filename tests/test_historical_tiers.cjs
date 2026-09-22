const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const element = { getContext() {}, querySelector() { return this; }, querySelectorAll() { return []; }, addEventListener() {}, style: {}, classList: { toggle() {}, contains() { return false; } } };
const context = vm.createContext({ URL, console, document: { baseURI: 'http://localhost/', getElementById() { return element; }, querySelectorAll() { return []; }, body: element } });
const source = fs.readFileSync('assets/js/main.js', 'utf8').replace('    bootstrap();', '');
vm.runInContext(source, context);
context.dataset = JSON.parse(fs.readFileSync('data/epa.json', 'utf8'));
vm.runInContext(`
seasonData = normalizeSeasonPayloads(dataset.seasons);
for (const mode of ['raw', 'sos']) {
  const ref = historicalReference(mode, {first: 1, last: 1});
  if (ref.combined.length < 500) throw new Error('Missing historical reference: ' + mode);
  if (ref.seasons.includes(2026)) throw new Error('Incomplete season included');
  console.log(mode, ref.combined.length, Math.min(...ref.seasons), Math.max(...ref.seasons));
}
`, context);
for (const [value, tier] of [[100,'S'], [90,'A'], [70,'B'], [50,'C'], [30,'D'], [-1,'F']]) {
  const result = vm.runInContext(`historicalTierCache.set('test:1:1:season_to_date', { combined: Array.from({length:100}, (_, i) => i), seasons: [2025] }); historicalTierBadge(${value}, 'combined', 'test', {first: 1, last: 1})`, context);
  assert.ok(result.includes(`>${tier}</span>`), result);
}
assert.equal(vm.runInContext("historicalTierBadge(null, 'combined')", context), '');
assert.equal(vm.runInContext("historicalTierBadge(NaN, 'combined')", context), '');
console.log('Historical tier checks passed.');

context.assert = assert;
vm.runInContext(`
const fixture = {weeks: {1: {off: 1, def: 0}, 3: {off: 0, def: 0}, 4: {off: 0, def: 0}, 19: {off: 1, def: 0}}};
assert.equal(JSON.stringify(historicalSample(fixture, 2025, 1, 3)), JSON.stringify({first: 1, last: 2}));
assert.equal(JSON.stringify(historicalSample(fixture, 2025, 3, 4)), JSON.stringify({first: 2, last: 3}));
assert.equal(historicalSample(fixture, 2025, 2, 2), null);
assert.equal(historicalSample(fixture, 2025, 1, 19), null);
const opening = historicalReference('raw', {first: 1, last: 1});
const five = historicalReference('raw', {first: 1, last: 5});
assert.notEqual(opening, five);
const team = seasonData['2025'].teams.find(t => t.team === 'ARI');
const firstWeek = regularGameWeeks(team, 2025)[0];
assert.ok(opening.off.includes(team.weeks[firstWeek].off));
assert.ok(historicalTierBadge(0.1, 'off', 'raw', {first: 1, last: 1}).includes('Early sample'));
assert.ok(!historicalTierBadge(0.1, 'off', 'raw', {first: 1, last: 5}).includes('Early sample'));
assert.ok(historicalTierBadge(0.1, 'off', 'raw', {first: 3, last: 5}).includes('games 3–5'));
`, context);
console.log('Matched game count, byes, custom ranges, and early sample checks passed.');

vm.runInContext(`
const splitRef = historicalReference('split', {first:1, last:1});
for (const metric of ['offPass', 'offRush', 'defPass', 'defRush']) {
  assert.ok(splitRef[metric].length > 0, metric);
  assert.ok(historicalTierBadge(0.1, metric, 'split', {first:1,last:1}).includes('historical-tier'));
  assert.equal(historicalTierBadge(null, metric, 'split', {first:1,last:1}), '');
}
const splitAri = buildSplitRows('2025', 1, 1).find(row => row.team === 'ARI');
assert.ok(splitRef.offPass.includes(splitAri.offPass));
`, context);
console.log('Pass/run historical badge checks passed.');
