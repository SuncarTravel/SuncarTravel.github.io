/* Airport names and IATA codes: OurAirports, public domain. See airports-iata.json. */
(function (root) {
  'use strict';
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const aliases = {
    'new york': 'nueva york', london: 'londres', munich: 'munich munchen',
    frankfurt: 'francfort', rome: 'roma', milan: 'milan milano',
    lisbon: 'lisboa', athens: 'atenas', beijing: 'pekin', tokyo: 'tokio',
    moscow: 'moscu', warsaw: 'varsovia', vienna: 'viena',
    zurich: 'zurich', seoul: 'seul', brussels: 'bruselas',
    copenhagen: 'copenhague', cairo: 'el cairo'
  };
  let catalogue;
  let countries;
  try { countries = new Intl.DisplayNames(['es'], {type: 'region'}); } catch (_) {}
  function indexRows(rows) {
    return rows.map(row => {
      const [code, name, city, country, keywords, scheduled] = row;
      let countryName = country;
      try { countryName = countries ? countries.of(country) : country; } catch (_) {}
      const cityKey = normalize(city);
      const extra = Object.entries(aliases).filter(([key]) => cityKey.includes(key)).map(([, value]) => value).join(' ');
      return {code, name, city_name: city, country_name: countryName, scheduled,
        search: normalize([code, name, city, country, countryName, keywords, extra].join(' ')), cityKey};
    });
  }
  function match(items, term) {
    const query = normalize(term);
    if (query.length < 2) return [];
    const words = query.split(' ');
    return items.filter(item => words.every(word => item.search.includes(word)))
      .sort((a, b) => score(b) - score(a) || a.name.localeCompare(b.name))
      .slice(0, 12);
    function score(item) {
      return (item.code.toLowerCase() === query ? 1000 : 0) +
        (item.cityKey === query ? 100 : 0) + (item.cityKey.startsWith(query) ? 30 : 0) +
        (item.scheduled ? 10 : 0);
    }
  }
  async function search(term) {
    if (!catalogue) {
      catalogue = (async () => {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10000);
        try {
          const response = await fetch('assets/airports-iata.json?v=20261028a', {signal: controller.signal});
          if (!response.ok) throw new Error('Airport catalogue unavailable');
          const data = await response.json();
          if (!Array.isArray(data.airports) || !data.airports.length) throw new Error('Invalid airport catalogue');
          return indexRows(data.airports);
        } finally { clearTimeout(timer); }
      })().catch(error => { catalogue = null; throw error; });
    }
    return match(await catalogue, term);
  }
  function cleanIata(value) {
    const found = String(value || '').trim().toUpperCase().match(/^([A-Z]{3})(?:\s+-\s+.+)?$/);
    return found ? found[1] : '';
  }
  function setup(inputId, boxId) {
    const input = document.getElementById(inputId);
    const box = document.getElementById(boxId);
    let timer, requestId = 0;
    input.setAttribute('aria-label', inputId === 'origin' ? 'Origen' : 'Destino');
    input.setAttribute('aria-controls', boxId);
    input.setAttribute('aria-expanded', 'false');
    function close() {
      clearTimeout(timer);
      requestId++;
      box.classList.remove('show');
      box.replaceChildren();
      input.setAttribute('aria-expanded', 'false');
    }
    function message(text) {
      const element = document.createElement('div');
      element.className = 'airport-empty';
      element.setAttribute('role', 'status');
      element.textContent = text;
      box.replaceChildren(element);
      box.classList.add('show');
      input.setAttribute('aria-expanded', 'true');
    }
    input.addEventListener('input', () => {
      close();
      const term = input.value.trim();
      if (term.length < 2) return;
      const current = requestId;
      timer = setTimeout(async () => {
        message('Buscando aeropuertos…');
        try {
          const items = await search(term);
          if (current !== requestId) return;
          if (!items.length) {
            message('No encontramos coincidencias. Prueba otra ciudad o escribe el código IATA de 3 letras.');
            return;
          }
          box.replaceChildren();
          items.forEach(item => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'airport-option';
            const strong = document.createElement('strong');
            strong.textContent = item.code + ' - ' + item.name;
            const meta = document.createElement('span');
            meta.textContent = [item.city_name, item.country_name].filter(Boolean).join(' · ');
            button.append(strong, meta);
            button.addEventListener('click', () => {
              input.value = item.code + ' - ' + item.name;
              close();
              input.focus();
            });
            box.appendChild(button);
          });
        } catch (_) {
          if (current === requestId) message('No se pudo cargar el catálogo. Intenta de nuevo o escribe el código IATA de 3 letras.');
        }
      }, 150);
    });
    input.addEventListener('keydown', event => {
      if (event.key === 'Escape') close();
      if (event.key === 'ArrowDown' && box.querySelector('button')) {
        event.preventDefault();
        box.querySelector('button').focus();
      }
    });
    box.addEventListener('keydown', event => {
      const buttons = Array.from(box.querySelectorAll('button'));
      const position = buttons.indexOf(document.activeElement);
      if (event.key === 'Escape') { close(); input.focus(); }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const next = position + (event.key === 'ArrowDown' ? 1 : -1);
        if (next < 0) input.focus();
        else if (buttons[next]) buttons[next].focus();
      }
    });
    document.addEventListener('click', event => {
      if (!input.parentElement.contains(event.target)) close();
    });
  }
  root.SuncarAirports = {search, setup, cleanIata, indexRows, match};
})(typeof window === 'undefined' ? globalThis : window);
