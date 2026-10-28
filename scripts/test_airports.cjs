const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
require('../assets/airports.js');
const api = globalThis.SuncarAirports;
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../assets/airports-iata.json')));
const rows = api.indexRows(data.airports);
assert(rows.length > 8000);
assert.equal(new Set(rows.map(row => row.code)).size, rows.length);
for (const [query, code] of [['PUJ','PUJ'], ['Punta Cana','PUJ'], ['punta cána','PUJ'], ['SDQ','SDQ'], ['Santo Domingo','SDQ'], ['Nueva York','JFK'], ['Londres','LHR'], ['Tokio','HND'], ['NRT','NRT'], ['SYD','SYD'], ['JNB','JNB'], ['GRU','GRU'], ['DXB','DXB']]) {
  assert(api.match(rows, query).some(row => row.code === code), `${query} must contain ${code}`);
}
for (const row of rows) assert.equal(api.match(rows, row.code)[0].code, row.code);
for (const value of ['Punta Cana','Madrid','Santo Domingo','PUJ unknown','PUJJ']) assert.equal(api.cleanIata(value), '');
assert.equal(api.cleanIata(' puj '), 'PUJ');
assert.equal(api.cleanIata('PUJ - Punta Cana International Airport'), 'PUJ');
for (const file of ['index.html','vuelos.html']) {
  const html = fs.readFileSync(path.join(__dirname,'..',file),'utf8');
  assert(html.includes('assets/airports.js?v=20261028a'));
  assert(html.includes("SuncarAirports.setup('origin','originSuggestions')"));
  assert(!html.includes('autocomplete.travelpayouts.com'));
}
console.log(`PASS: ${rows.length} exact IATA lookups, city/accent/alias search, strict code parsing, both forms`);
