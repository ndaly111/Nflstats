const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const element = {
  getContext() {}, querySelector() { return this; }, querySelectorAll() { return []; },
  addEventListener() {}, appendChild() {}, setAttribute() {}, style: {}, dataset: {},
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
    createElement() { return element; },
    createElementNS() { return element; },
    body: element,
  },
});
const source = fs.readFileSync('assets/js/matchups.js', 'utf8').replace(/\n\s*init\(\);\s*$/, '\n');
vm.runInContext(source, context);
context.assert = assert;

// Picks the week that is in progress, or the next one up when the last is finished.
vm.runInContext(`
{
  // Week 3 ends Mon Sep 21; week 4 ends Mon Sep 28.
  const weekDates = { 1: '2026-09-14', 2: '2026-09-15', 3: '2026-09-21', 4: '2026-09-28', 5: '2026-10-05' };

  // Sunday inside week 3 -> week 3, the slate being played.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2026-09-20'), 3);
  // Monday night of week 3 -> still week 3.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2026-09-21'), 3);
  // Tuesday, week 3 done -> week 4 is next up.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2026-09-22'), 4);
  // Today.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2026-09-23'), 4);
  // Before the season starts -> week 1.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2026-08-01'), 1);
  // After every week has finished -> the last week, not null.
  assert.equal(pickCurrentWeekFromDates(weekDates, '2027-01-15'), 5);
  // Out-of-order and malformed entries are tolerated.
  assert.equal(pickCurrentWeekFromDates({ 5: '2026-10-05', 3: '2026-09-21', 4: null }, '2026-09-23'), 5);
  // Nothing usable -> null, so the caller can fall back.
  assert.equal(pickCurrentWeekFromDates({}, '2026-09-23'), null);
  assert.equal(pickCurrentWeekFromDates(null, '2026-09-23'), null);
}
`, context);

// The last kickoff in a week defines when that week is over.
vm.runInContext(`
{
  const games = [
    { week: 3, gameday: '2026-09-17' },
    { week: 3, gameday: '2026-09-21' },
    { week: 3, gameday: '2026-09-20' },
    { week: 4, gameday: '2026-09-24' },
    { week: 4, gameday: null },
    { week: null, gameday: '2026-09-25' },
  ];
  const dates = weekEndDatesFromGames(games);
  assert.equal(dates[3], '2026-09-21', 'week 3 ends on its latest kickoff');
  assert.equal(dates[4], '2026-09-24');
  assert.ok(!('null' in dates), 'games without a week are skipped');
  assert.deepEqual(weekEndDatesFromGames([]), {});
  assert.deepEqual(weekEndDatesFromGames(null), {});
}
`, context);

// Real schedule data: whatever week we land on must exist and be sane.
vm.runInContext(`
{
  const sched = ${fs.readFileSync('data/schedule.json', 'utf8')};
  const games = sched.seasons['2026'].games;
  const dates = weekEndDatesFromGames(games);
  const picked = pickCurrentWeekFromDates(dates, '2026-09-23');
  if (Object.keys(dates).length === 0) {
    // schedule.json has no gameday yet; the caller falls back to odds.
    assert.equal(picked, null);
  } else {
    assert.ok(picked >= 1 && picked <= 18, 'picked week in range: ' + picked);
  }
}
`, context);

console.log('Current week checks passed.');
