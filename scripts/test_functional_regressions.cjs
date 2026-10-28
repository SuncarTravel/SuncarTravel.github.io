const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const root = require('node:path').resolve(__dirname, '..');
process.chdir(root);

function mscCheck(source) {
  const normalize = source.match(/^const normalize=.*$/m)[0].split(';const laRomanaExitTax=')[0] + ';';
  const search = source.slice(source.indexOf('const monthNames='), source.indexOf('const findDeparture=q=>'));
  const departures = [
    { ship: 'MSC Seaside', port: 'Miami', region: 'Caribe', start: '2026-12-07', route: 'Miami -> Nassau' },
    { ship: 'MSC Seaside', port: 'Miami', region: 'Caribe', start: '2027-12-07', route: 'Miami -> Nassau' },
    { ship: 'MSC Seaside', port: 'Miami', region: 'Caribe', start: '2026-11-07', route: 'Miami -> Nassau' }
  ];
  const context = vm.createContext({ departures });
  vm.runInContext(`const mscData={fleet:[],regionAliases:{}}; const availableDepartures=()=>departures; ${normalize}${search}`, context);
  assert.equal(vm.runInContext('normalize("diciembre 2026")', context), 'diciembre 2026');
  assert.equal(vm.runInContext('normalize("Sudamérica")', context), 'sudamerica');
  assert.equal(vm.runInContext('findDepartureMatches("Miami diciembre 2026").length', context), 1);
  assert.equal(vm.runInContext('findDepartureMatches("Miami diciembre 2026")[0].start', context), '2026-12-07');
  assert.equal(vm.runInContext('findDepartureMatches("Miami diciembre 2027")[0].start', context), '2027-12-07');
}

for (const file of ['index.html', 'assets/msc-assistant-widget.js']) {
  const before = cp.execFileSync('git', ['show', '43751e4aa110009a60164980ee30d189475b4519:' + file], { encoding: 'utf8' });
  assert.throws(() => mscCheck(before), 'Original must reproduce the MSC defect');
  mscCheck(fs.readFileSync(file, 'utf8'));
  console.log('PASS MSC baseline fails, correction passes:', file);
}

const insurance = fs.readFileSync('seguros-viaje.html', 'utf8');
const code = insurance.slice(insurance.indexOf('const parseAges='), insurance.indexOf('function updateEstimate'));
const field = { value: '', message: '', setCustomValidity(value) { this.message = value; } };
const form = { elements: { edades: field, pasajeros: { value: '2' } } };
const context = vm.createContext({ form });
vm.runInContext(code, context);
for (const [ages, expected] of [['35, 40', true], ['35', false], ['35, -1', false], ['35, abc', false], ['35, 4.5', false], ['0, 75', true], ['35; 76', true], ['', false]]) {
  field.value = ages;
  assert.equal(vm.runInContext('validateAges()', context), expected, ages);
}
field.value = '35, 76';
assert.equal(vm.runInContext('maxAge(form.elements.edades.value)', context), 76);
assert.match(insurance, /if\(!validateAges\(\)\)return;/);
console.log('PASS insurance: complete ages, mismatch, invalid formats, zero and special age');
