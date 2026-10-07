const ALLOWED_ORIGINS = new Set([
  "https://suncartravel.github.io"
]);

const cors = origin => ({
  "Access-Control-Allow-Origin": ALLOWED_ORIGINS.has(origin) ? origin : "https://suncartravel.github.io",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type,Accept",
  "Vary": "Origin",
  "Cache-Control": "no-store"
});

const json = (body, status=200, origin="") => new Response(JSON.stringify(body), {
  status,
  headers: {"Content-Type":"application/json; charset=utf-8", ...cors(origin)}
});

const clampInt = (v,min,max,def=min) => {
  const n=Number.parseInt(v,10);
  return Number.isFinite(n)?Math.max(min,Math.min(max,n)):def;
};
const validIata = v => /^[A-Z]{3}$/.test(String(v||"").toUpperCase());
const validDate = v => /^\d{4}-\d{2}-\d{2}$/.test(String(v||""));

const normalizeOffer = (item, currency, sourceGroup) => {
  const flights=Array.isArray(item?.flights)?item.flights:[];
  if(!flights.length || !Number.isFinite(Number(item?.price))) return null;
  const first=flights[0], last=flights[flights.length-1];
  const airlines=[...new Set(flights.map(x=>x?.airline).filter(Boolean))];
  const flightNumbers=flights.map(x=>x?.flight_number).filter(Boolean);
  const layovers=(Array.isArray(item?.layovers)?item.layovers:[]).map(x=>x?.id||x?.name).filter(Boolean);
  const extensions=(Array.isArray(item?.extensions)?item.extensions:[]).filter(x=>typeof x==="string").slice(0,4);
  const travelClass=flights.map(x=>x?.travel_class).find(Boolean)||"";
  return {
    source_group: sourceGroup,
    price:Number(item.price),
    currency,
    origin:first?.departure_airport?.id||"",
    destination:last?.arrival_airport?.id||"",
    departure_time:first?.departure_airport?.time||"",
    arrival_time:last?.arrival_airport?.time||"",
    airlines,
    airline_logo:item?.airline_logo || first?.airline_logo || "",
    flight_numbers:flightNumbers,
    total_duration:Number(item?.total_duration||0),
    stops:Math.max(0,flights.length-1),
    layovers,
    travel_class:travelClass,
    extensions
  };
};

const dedupeOffers = offers => {
  const seen=new Set();
  return offers.filter(x=>{
    const key=[
      x.price,
      x.departure_time,
      x.arrival_time,
      x.flight_numbers.join(",")
    ].join("|");
    if(seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export default {
  async fetch(request, env, ctx) {
    const origin=request.headers.get("Origin")||"";
    if(request.method==="OPTIONS") return new Response(null,{status:204,headers:cors(origin)});
    if(request.method!=="GET") return json({message:"Método no permitido."},405,origin);

    const reqUrl=new URL(request.url);
    if(reqUrl.pathname!=="/search" && reqUrl.pathname!=="/") {
      return json({message:"Ruta no encontrada."},404,origin);
    }

    if(!ALLOWED_ORIGINS.has(origin) && origin!=="") {
      return json({message:"Origen no autorizado."},403,origin);
    }

    if(!env.SERPAPI_KEY) {
      return json({message:"El buscador aún no tiene configurada la clave segura de tarifas."},503,origin);
    }

    const p=reqUrl.searchParams;
    const trip=p.get("trip")==="oneway"?"oneway":"roundtrip";
    const from=String(p.get("origin")||"").toUpperCase();
    const to=String(p.get("destination")||"").toUpperCase();
    const outbound=String(p.get("outbound")||"");
    const inbound=String(p.get("return")||"");

    if(!validIata(from)||!validIata(to)) return json({message:"Origen y destino deben ser códigos IATA de 3 letras."},400,origin);
    if(from===to) return json({message:"Origen y destino no pueden ser iguales."},400,origin);
    if(!validDate(outbound)) return json({message:"Fecha de ida inválida."},400,origin);
    if(trip==="roundtrip" && !validDate(inbound)) return json({message:"Fecha de regreso inválida."},400,origin);
    if(trip==="roundtrip" && inbound<outbound) return json({message:"La fecha de regreso debe ser posterior a la ida."},400,origin);

    const adults=clampInt(p.get("adults"),1,9,1);
    const children=clampInt(p.get("children"),0,8,0);
    const infants=clampInt(p.get("infants"),0,4,0);
    if(adults+children+infants>9) return json({message:"Máximo 9 pasajeros por búsqueda."},400,origin);

    const travelClass=["1","2","3","4"].includes(p.get("travel_class"))?p.get("travel_class"):"1";
    const stops=["0","1","2","3"].includes(p.get("stops"))?p.get("stops"):"0";
    const sort=["1","2","5"].includes(p.get("sort"))?p.get("sort"):"1";

    // Cachea la misma búsqueda para cuidar el cupo gratuito.
    const normalized=new URL(reqUrl.origin+reqUrl.pathname);
    [...p.entries()].sort(([a],[b])=>a.localeCompare(b)).forEach(([k,v])=>normalized.searchParams.append(k,v));
    const cacheKey=new Request(normalized.toString(),{method:"GET"});
    const cache=caches.default;
    const cached=await cache.match(cacheKey);
    if(cached) {
      const headers=new Headers(cached.headers);
      Object.entries(cors(origin)).forEach(([k,v])=>headers.set(k,v));
      headers.set("X-Suncar-Cache","HIT");
      return new Response(cached.body,{status:cached.status,headers});
    }

    const api=new URL("https://serpapi.com/search.json");
    api.searchParams.set("engine","google_flights");
    api.searchParams.set("api_key",env.SERPAPI_KEY);
    api.searchParams.set("departure_id",from);
    api.searchParams.set("arrival_id",to);
    api.searchParams.set("outbound_date",outbound);
    api.searchParams.set("type",trip==="roundtrip"?"1":"2");
    if(trip==="roundtrip") api.searchParams.set("return_date",inbound);
    api.searchParams.set("adults",String(adults));
    api.searchParams.set("children",String(children));
    api.searchParams.set("infants_on_lap",String(infants));
    api.searchParams.set("travel_class",travelClass);
    api.searchParams.set("stops",stops);
    api.searchParams.set("sort_by",sort);
    api.searchParams.set("currency","USD");
    api.searchParams.set("hl","es");
    api.searchParams.set("gl","do");
    api.searchParams.set("show_hidden","true");

    let upstream;
    try{
      upstream=await fetch(api.toString(),{headers:{"Accept":"application/json"}});
    }catch{
      return json({message:"La fuente de tarifas no respondió. Intenta de nuevo o solicita búsqueda manual."},502,origin);
    }

    let raw={};
    try{ raw=await upstream.json(); }catch{}
    if(!upstream.ok || raw?.error) {
      const msg=raw?.error || "No pudimos consultar las tarifas en este momento.";
      return json({message:msg},502,origin);
    }

    const currency=raw?.search_parameters?.currency || "USD";
    const best=(Array.isArray(raw?.best_flights)?raw.best_flights:[]).map(x=>normalizeOffer(x,currency,"best")).filter(Boolean);
    const other=(Array.isArray(raw?.other_flights)?raw.other_flights:[]).map(x=>normalizeOffer(x,currency,"other")).filter(Boolean);
    let offers=dedupeOffers([...best,...other]);

    if(sort==="2") offers.sort((a,b)=>a.price-b.price);
    else if(sort==="5") offers.sort((a,b)=>a.total_duration-b.total_duration);
    else offers.sort((a,b)=>{
      if(a.source_group!==b.source_group) return a.source_group==="best"?-1:1;
      return a.price-b.price;
    });

    offers=offers.slice(0,12);
    const cheapestValue=offers.length?Math.min(...offers.map(x=>x.price)):null;
    const cheapestIndex=cheapestValue===null?-1:offers.findIndex(x=>x.price===cheapestValue);
    const directPrices=offers.map((x,i)=>({i,price:x.stops===0?x.price:Infinity})).sort((a,b)=>a.price-b.price);
    const bestDirectIndex=directPrices.length&&Number.isFinite(directPrices[0].price)?directPrices[0].i:-1;

    const out={
      provider:"market-reference",
      currency,
      trip,
      searched_at:new Date().toISOString(),
      results:offers,
      cheapest_index:cheapestIndex,
      best_direct_index:bestDirectIndex,
      price_insights:raw?.price_insights||null,
      note:trip==="roundtrip"
        ?"El precio es una referencia para la búsqueda de ida y vuelta. La combinación exacta del regreso y las condiciones finales se confirman con Suncar."
        :"El precio es una referencia de solo ida y se confirma con Suncar."
    };

    const response=json(out,200,origin);
    const cacheable=response.clone();
    cacheable.headers.set("Cache-Control","public, max-age=1800");
    ctx.waitUntil(cache.put(cacheKey,cacheable));
    return response;
  }
};
