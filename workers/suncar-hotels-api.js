const VERSION="2026-10-07.2";
const ALLOWED_ORIGINS=new Set([
  "https://suncartravel.github.io",
  "https://suncartravel.com",
  "https://www.suncartravel.com"
]);

function corsHeaders(request){
  const origin=request.headers.get("Origin")||"";
  const allow=ALLOWED_ORIGINS.has(origin)?origin:"https://suncartravel.github.io";
  return {
    "Access-Control-Allow-Origin":allow,
    "Vary":"Origin",
    "Access-Control-Allow-Methods":"GET,OPTIONS",
    "Access-Control-Allow-Headers":"Content-Type",
    "Access-Control-Max-Age":"86400"
  };
}
function json(request,data,status=200,extra={}){
  return new Response(JSON.stringify(data),{
    status,
    headers:{...corsHeaders(request),"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store",...extra}
  });
}
const clean=s=>String(s||"").trim();
const int=(v,d,min,max)=>{const n=parseInt(v,10);return Number.isFinite(n)?Math.min(max,Math.max(min,n)):d};
const arr=v=>Array.isArray(v)?v:[];
const uniq=a=>[...new Set(a.filter(Boolean))];
const numOrNull=v=>{const n=Number(v);return Number.isFinite(n)&&n>0?n:null};

function validDateString(s){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(s||""))return false;
  const d=new Date(s+"T00:00:00Z");
  return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===s;
}
function daysBetween(a,b){
  const x=Date.parse(a+"T00:00:00Z"),y=Date.parse(b+"T00:00:00Z");
  return Math.round((y-x)/86400000);
}
function todayDR(){
  const parts=new Intl.DateTimeFormat("en-CA",{
    timeZone:"America/Santo_Domingo",year:"numeric",month:"2-digit",day:"2-digit"
  }).formatToParts(new Date());
  const get=t=>parts.find(x=>x.type===t)?.value||"";
  return get("year")+"-"+get("month")+"-"+get("day");
}
function parseAges(raw){
  const s=clean(raw);
  if(!s)return [];
  return s.split(",").map(x=>parseInt(x.trim(),10)).filter(Number.isFinite);
}
function validAges(children,ages){
  if(children===0)return ages.length===0;
  return ages.length===children&&ages.every(x=>x>=1&&x<=17);
}
function normalizePrice(p){
  p=p||{};
  return {
    display:clean(p.lowest||p.display),
    amount:numOrNull(p.extracted_lowest??p.extractedLowest),
    beforeDisplay:clean(p.before_taxes_fees||p.beforeTaxesFees),
    beforeAmount:numOrNull(p.extracted_before_taxes_fees??p.extractedBeforeTaxesFees)
  };
}
function priceConsistency(night,total,nights){
  if(!night?.amount||!total?.amount||!nights)return "partial";
  const expected=night.amount*nights;
  const ratio=total.amount/expected;
  return ratio>=0.60&&ratio<=1.60?"consistent":"review";
}
function requestOriginAllowed(request){
  const origin=request.headers.get("Origin");
  return !!origin&&ALLOWED_ORIGINS.has(origin);
}

function canonicalSearchKey(u){
  const p=new URLSearchParams();
  ["q","check_in","check_out","adults","children","children_ages","rooms","currency"].forEach(k=>p.set(k,clean(u.searchParams.get(k))));
  return "https://suncar-cache.invalid/hotels/search?"+p.toString();
}
function canonicalDetailKey(u){
  const p=new URLSearchParams();
  ["property_token","q","check_in","check_out","adults","children","children_ages","rooms","currency"].forEach(k=>p.set(k,clean(u.searchParams.get(k))));
  return "https://suncar-cache.invalid/hotels/details?"+p.toString();
}
async function cacheGet(key){
  const r=await caches.default.match(new Request(key));
  if(!r)return null;
  try{return await r.json()}catch{return null}
}
async function cachePut(key,payload,ttl){
  const r=new Response(JSON.stringify(payload),{headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"public, max-age="+ttl}});
  await caches.default.put(new Request(key),r);
}
async function fetchJson(url,opts={},timeoutMs=18000){
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),timeoutMs);
  try{
    const r=await fetch(url,{...opts,signal:ctrl.signal});
    let d=null;
    try{d=await r.json()}catch{}
    return {ok:r.ok,status:r.status,data:d};
  }catch(e){
    return {ok:false,status:0,data:null,error:String(e?.message||e)};
  }finally{
    clearTimeout(timer);
  }
}

/* ---------- SerpApi / Google Hotels ---------- */
async function serpQuota(env){
  if(!env.SERPAPI_KEY)return null;
  const key="https://suncar-cache.invalid/internal/serp-quota-v2";
  const cached=await cacheGet(key);
  if(cached)return cached;
  const r=await fetchJson("https://serpapi.com/account.json?api_key="+encodeURIComponent(env.SERPAPI_KEY),{},10000);
  if(!r.ok||!r.data)return null;
  const leftRaw=Number(r.data.total_searches_left??r.data.plan_searches_left);
  const perMonthRaw=Number(r.data.searches_per_month);
  const q={
    left:Number.isFinite(leftRaw)?leftRaw:null,
    perMonth:Number.isFinite(perMonthRaw)?perMonthRaw:null,
    usage:Number(r.data.this_month_usage)||0
  };
  await cachePut(key,q,60);
  return q;
}
function serpParams(ctx,env){
  const p=new URLSearchParams({
    engine:"google_hotels",
    q:ctx.q,
    check_in_date:ctx.checkIn,
    check_out_date:ctx.checkOut,
    adults:String(ctx.adults),
    children:String(ctx.children),
    currency:ctx.currency,
    hl:"es-419",
    gl:"do",
    api_key:env.SERPAPI_KEY
  });
  if(ctx.children&&ctx.childrenAges.length)p.set("children_ages",ctx.childrenAges.join(","));
  return p;
}
function normalizeSerpProperty(p,ctx){
  const imgs=arr(p.images).map(x=>typeof x==="string"?x:(x?.thumbnail||x?.original_image||x?.original)).filter(Boolean).slice(0,8);
  const night=normalizePrice(p.rate_per_night);
  const total=normalizePrice(p.total_rate);
  return {
    id:"sp:"+clean(p.property_token),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:Number(p.extracted_hotel_class)||0,
    rating:Number(p.overall_rating)||0,
    reviews:Number(p.reviews)||0,
    amenities:arr(p.amenities).slice(0,10),
    image:imgs[0]||p.thumbnail||"",
    images:imgs,
    night,
    total,
    priceConsistency:priceConsistency(night,total,daysBetween(ctx.checkIn,ctx.checkOut)),
    freeCancellation:!!p.free_cancellation,
    checkInTime:p.check_in_time||"",
    checkOutTime:p.check_out_time||""
  };
}
function normalizeSerpRoom(room,ctx){
  const rates=arr(room.rates);
  const cheapest=rates.slice().sort((a,b)=>{
    const at=numOrNull(a?.total_rate?.extracted_lowest)??numOrNull(a?.rate_per_night?.extracted_lowest)??1e12;
    const bt=numOrNull(b?.total_rate?.extracted_lowest)??numOrNull(b?.rate_per_night?.extracted_lowest)??1e12;
    return at-bt;
  })[0]||{};
  const total=normalizePrice(room.total_rate||cheapest.total_rate);
  const night=normalizePrice(room.rate_per_night||cheapest.rate_per_night);
  const inclusions=uniq([
    ...arr(room.inclusions),
    ...arr(cheapest.inclusions),
    ...(room.breakfast_included||cheapest.breakfast_included?["Desayuno incluido"]:[])
  ]).slice(0,10);
  return {
    name:room.name||"Tarifa disponible",
    guests:Number(room.num_guests||cheapest.num_guests)||0,
    image:arr(room.images)[0]||"",
    night,
    total,
    priceConsistency:priceConsistency(night,total,daysBetween(ctx.checkIn,ctx.checkOut)),
    inclusions,
    freeCancellation:!!(room.free_cancellation||cheapest.free_cancellation)
  };
}
async function searchSerp(ctx,env){
  if(!env.SERPAPI_KEY)return null;
  const quota=await serpQuota(env);
  if(quota&&Number.isFinite(quota.left)&&quota.left<=15)return null;
  const p=serpParams(ctx,env);
  const r=await fetchJson("https://serpapi.com/search.json?"+p.toString());
  if(!r.ok||!r.data||r.data.error)return null;
  const results=arr(r.data.properties)
    .filter(x=>x.type==="hotel"||!x.type)
    .slice(0,20)
    .map(x=>normalizeSerpProperty(x,ctx));
  return results.length?results:null;
}
async function detailsSerp(token,ctx,env){
  if(!env.SERPAPI_KEY)return null;
  const quota=await serpQuota(env);
  if(quota&&quota.left<=10)return null;
  const p=serpParams(ctx,env);
  p.set("property_token",token);
  const r=await fetchJson("https://serpapi.com/search.json?"+p.toString());
  if(!r.ok||!r.data||r.data.error)return null;

  const groups=[...arr(r.data.featured_prices),...arr(r.data.prices)];
  let rawRooms=[
    ...arr(r.data.rooms),
    ...groups.flatMap(x=>arr(x?.rooms))
  ];
  if(!rawRooms.length){
    rawRooms=groups
      .filter(x=>x?.total_rate||x?.rate_per_night)
      .map(x=>({
        name:"Tarifa disponible",
        num_guests:x.num_guests,
        total_rate:x.total_rate,
        rate_per_night:x.rate_per_night,
        free_cancellation:x.free_cancellation,
        breakfast_included:x.breakfast_included,
        inclusions:arr(x.benefits).length?x.benefits:[x.benefits].filter(Boolean)
      }));
  }

  const seen=new Set();
  const rooms=rawRooms.filter(room=>{
    const total=room?.total_rate?.extracted_lowest??room?.total_rate?.lowest;
    const night=room?.rate_per_night?.extracted_lowest??room?.rate_per_night?.lowest;
    const key=[room?.name,total,night,room?.num_guests].join("|");
    if(seen.has(key))return false;
    seen.add(key);
    return true;
  }).slice(0,12).map(x=>normalizeSerpRoom(x,ctx));
  return rooms.length?rooms:null;
}

/* ---------- HasData / Google Hotels ---------- */
function hasDataOccupancyOk(ctx){
  return ctx.adults<=6&&ctx.children<=5&&(ctx.adults+ctx.children)<=6;
}
function hasDataParams(ctx){
  const p=new URLSearchParams({
    q:ctx.q,
    checkInDate:ctx.checkIn,
    checkOutDate:ctx.checkOut,
    adults:String(ctx.adults),
    currency:ctx.currency,
    hl:"es",
    gl:"do"
  });
  if(ctx.children){
    p.set("children",String(ctx.children));
    p.set("childrenAges",ctx.childrenAges.join(","));
  }
  return p;
}
function normalizeHasDataProperty(p,ctx){
  const imgs=arr(p.images).map(x=>typeof x==="string"?x:(x?.thumbnail||x?.original||x?.url)).filter(Boolean).slice(0,8);
  const night=normalizePrice(p.ratePerNight||p.rate_per_night);
  const total=normalizePrice(p.totalRate||p.total_rate);
  return {
    id:"hd:"+clean(p.propertyToken||p.property_token),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:Number(p.hotelClass||p.extractedHotelClass||p.extracted_hotel_class)||0,
    rating:Number(p.overallRating||p.overall_rating)||0,
    reviews:Number(p.reviews)||0,
    amenities:arr(p.amenities).slice(0,10),
    image:imgs[0]||p.thumbnail||"",
    images:imgs,
    night,
    total,
    priceConsistency:priceConsistency(night,total,daysBetween(ctx.checkIn,ctx.checkOut)),
    freeCancellation:!!(p.freeCancellation||p.free_cancellation),
    checkInTime:p.checkInTime||p.check_in_time||"",
    checkOutTime:p.checkOutTime||p.check_out_time||""
  };
}
function normalizeHasDataRoom(room,ctx){
  const total=normalizePrice(room.totalRate||room.total_rate);
  const night=normalizePrice(room.ratePerNight||room.rate_per_night);
  const inclusions=uniq([
    ...arr(room.inclusions),
    ...arr(room.amenities),
    ...(room.breakfastIncluded||room.breakfast_included?["Desayuno incluido"]:[])
  ]).slice(0,10);
  return {
    name:room.name||room.roomName||"Tarifa disponible",
    guests:Number(room.numGuests||room.num_guests||room.guests)||0,
    image:arr(room.images)[0]||"",
    night,
    total,
    priceConsistency:priceConsistency(night,total,daysBetween(ctx.checkIn,ctx.checkOut)),
    inclusions,
    freeCancellation:!!(room.freeCancellation||room.free_cancellation)
  };
}
async function hasDataCall(params,env){
  if(!env.HASDATA_API_KEY)return null;
  const url="https://api.hasdata.com/scrape/google/hotels?"+params.toString();
  const r=await fetchJson(url,{headers:{"x-api-key":env.HASDATA_API_KEY,"Content-Type":"application/json"}});
  if(!r.ok||!r.data||r.data.error)return null;
  return r.data;
}
async function searchHasData(ctx,env){
  if(!env.HASDATA_API_KEY||!hasDataOccupancyOk(ctx))return null;
  const d=await hasDataCall(hasDataParams(ctx),env);
  if(!d)return null;
  const results=arr(d.properties)
    .filter(x=>x.type==="hotel"||!x.type)
    .slice(0,20)
    .map(x=>normalizeHasDataProperty(x,ctx));
  return results.length?results:null;
}
async function detailsHasData(token,ctx,env){
  if(!env.HASDATA_API_KEY||!hasDataOccupancyOk(ctx))return null;
  const p=hasDataParams(ctx);
  p.set("propertyToken",token);
  const d=await hasDataCall(p,env);
  if(!d)return null;
  const candidates=arr(d.rooms).length?d.rooms:
    arr(d.property?.rooms).length?d.property.rooms:
    arr(d.properties?.[0]?.rooms);
  const rooms=arr(candidates).slice(0,12).map(x=>normalizeHasDataRoom(x,ctx));
  return rooms.length?rooms:null;
}

/* ---------- StayingAPI: optional evaluation fallback ---------- */
function ctxCurrency(currency,amount){
  const n=Number(amount);
  return Number.isFinite(n)&&n>0?(currency||"USD")+" "+n.toLocaleString("en-US"):"";
}
function normalizeStayingProperty(p,ctx){
  const price=p.price||{};
  const photos=arr(p.photos).map(x=>typeof x==="string"?x:(x?.url||x?.src)).filter(Boolean);
  const night={display:price.nightlyPrice?ctxCurrency(price.currency,price.nightlyPrice):"",amount:numOrNull(price.nightlyPrice),beforeDisplay:"",beforeAmount:null};
  const total={display:price.totalPrice?ctxCurrency(price.currency,price.totalPrice):"",amount:numOrNull(price.totalPrice),beforeDisplay:"",beforeAmount:null};
  return {
    id:"st:"+clean(p.id||p.platformListingId),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:Number(p.starRating)||0,
    rating:Number(p.guestRating)||0,
    reviews:Number(p.reviewCount)||0,
    amenities:arr(p.amenities).slice(0,10),
    image:photos[0]||p.image||"",
    images:photos.slice(0,8),
    night,
    total,
    priceConsistency:priceConsistency(night,total,daysBetween(ctx.checkIn,ctx.checkOut)),
    freeCancellation:!!p.freeCancellation,
    checkInTime:"",
    checkOutTime:""
  };
}
async function searchStaying(ctx,env){
  if(!env.STAYINGAPI_KEY||String(env.STAYINGAPI_ENABLED||"").toLowerCase()!=="true")return null;
  if(ctx.children>0)return null;
  const p=new URLSearchParams({
    location:ctx.q,checkIn:ctx.checkIn,checkOut:ctx.checkOut,adults:String(ctx.adults),
    platforms:"google",limit:"20",currency:ctx.currency
  });
  const r=await fetchJson("https://api.stayingapi.com/v1/search?"+p.toString(),{
    headers:{Authorization:"Bearer "+env.STAYINGAPI_KEY}
  },25000);
  if(!r.ok||!r.data||r.status===202)return null;
  const results=arr(r.data.data).map(x=>normalizeStayingProperty(x,ctx)).slice(0,20);
  return results.length?results:null;
}

/* ---------- Shared ---------- */
function searchContext(u){
  const children=int(u.searchParams.get("children"),0,0,5);
  return {
    q:clean(u.searchParams.get("q")).slice(0,120),
    checkIn:clean(u.searchParams.get("check_in")),
    checkOut:clean(u.searchParams.get("check_out")),
    adults:int(u.searchParams.get("adults"),2,1,8),
    children,
    childrenAges:parseAges(u.searchParams.get("children_ages")),
    rooms:int(u.searchParams.get("rooms"),1,1,6),
    currency:(clean(u.searchParams.get("currency"))||"USD").toUpperCase().slice(0,3)
  };
}
function validateCtx(c){
  if(c.q.length<2)return "Destino inválido";
  if(!validDateString(c.checkIn)||!validDateString(c.checkOut)||c.checkOut<=c.checkIn)return "Fechas inválidas";
  if(c.checkIn<todayDR())return "La entrada debe ser hoy o una fecha futura";
  const nights=daysBetween(c.checkIn,c.checkOut);
  if(nights<1||nights>45)return "La búsqueda automática admite estadías de 1 a 45 noches";
  if(c.rooms!==1)return "La búsqueda automática está disponible para 1 habitación; Suncar confirma solicitudes de varias habitaciones";
  if(!validAges(c.children,c.childrenAges))return "Indica una edad de 1 a 17 años por cada niño";
  return "";
}
async function searchWithFailover(ctx,env){
  const engines=[searchSerp,searchHasData,searchStaying];
  for(const fn of engines){
    try{
      const results=await fn(ctx,env);
      if(results?.length)return results;
    }catch{}
  }
  return null;
}
async function detailsWithRoute(rawToken,ctx,env){
  const [prefix,...rest]=rawToken.split(":");
  const token=rest.join(":");
  if(!token)return null;
  if(prefix==="sp"){
    return (await detailsSerp(token,ctx,env))||(await detailsHasData(token,ctx,env));
  }
  if(prefix==="hd"){
    return (await detailsHasData(token,ctx,env))||(await detailsSerp(token,ctx,env));
  }
  return null;
}

export default {
  async fetch(request,env){
    if(request.method==="OPTIONS"){
      if(!requestOriginAllowed(request))return new Response(null,{status:403,headers:corsHeaders(request)});
      return new Response(null,{status:204,headers:corsHeaders(request)});
    }
    if(request.method!=="GET")return json(request,{ok:false,error:"Método no permitido"},405);

    const u=new URL(request.url);
    if(u.pathname==="/"||u.pathname==="/health"){
      return json(request,{ok:true,service:"Suncar Hotels API",version:VERSION,multiSource:true});
    }

    if(!requestOriginAllowed(request)){
      return json(request,{ok:false,error:"Origen no autorizado"},403);
    }

    if(u.pathname==="/hotels/search"){
      const ctx=searchContext(u);
      const invalid=validateCtx(ctx);
      if(invalid)return json(request,{ok:false,error:invalid},422);

      const cacheKey=canonicalSearchKey(u);
      const cached=await cacheGet(cacheKey);
      if(cached)return json(request,{...cached,cached:true});

      const results=await searchWithFailover(ctx,env);
      if(!results?.length)return json(request,{ok:false,error:"No hay resultados automáticos disponibles en este momento"},503);

      const payload={
        ok:true,
        cached:false,
        observedAt:new Date().toISOString(),
        query:{q:ctx.q,checkIn:ctx.checkIn,checkOut:ctx.checkOut,adults:ctx.adults,children:ctx.children,rooms:ctx.rooms,currency:ctx.currency},
        results
      };
      await cachePut(cacheKey,payload,3600);
      return json(request,payload);
    }

    if(u.pathname==="/hotels/details"){
      const ctx=searchContext(u);
      const invalid=validateCtx(ctx);
      const rawToken=clean(u.searchParams.get("property_token"));
      if(invalid||!rawToken)return json(request,{ok:false,error:invalid||"Detalle inválido"},422);

      const cacheKey=canonicalDetailKey(u);
      const cached=await cacheGet(cacheKey);
      if(cached)return json(request,{...cached,cached:true});

      const rooms=await detailsWithRoute(rawToken,ctx,env);
      if(!rooms?.length)return json(request,{ok:false,error:"No hay detalle automático disponible para esta opción"},503);

      const payload={ok:true,cached:false,observedAt:new Date().toISOString(),rooms};
      await cachePut(cacheKey,payload,3600);
      return json(request,payload);
    }

    return json(request,{ok:false,error:"Ruta no encontrada"},404);
  }
};
