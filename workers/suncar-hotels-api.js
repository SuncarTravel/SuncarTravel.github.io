const CORS={
  "Access-Control-Allow-Origin":"*",
  "Access-Control-Allow-Methods":"GET,OPTIONS",
  "Access-Control-Allow-Headers":"Content-Type"
};
const json=(data,status=200,extra={})=>new Response(JSON.stringify(data),{
  status,
  headers:{...CORS,"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store",...extra}
});
const clean=s=>String(s||"").trim();
const int=(v,d,min,max)=>{const n=parseInt(v,10);return Number.isFinite(n)?Math.min(max,Math.max(min,n)):d};
const dateOk=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||"");
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:0};
const arr=v=>Array.isArray(v)?v:[];
const uniq=a=>[...new Set(a.filter(Boolean))];

function canonicalSearchKey(u){
  const p=new URLSearchParams();
  ["q","check_in","check_out","adults","children","currency"].forEach(k=>p.set(k,clean(u.searchParams.get(k))));
  return "https://suncar-cache.invalid/hotels/search?"+p.toString();
}
function canonicalDetailKey(u){
  const p=new URLSearchParams();
  ["property_token","q","check_in","check_out","adults","children","currency"].forEach(k=>p.set(k,clean(u.searchParams.get(k))));
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
  }catch(e){return {ok:false,status:0,data:null,error:String(e?.message||e)}}
  finally{clearTimeout(timer)}
}

/* ---------- SerpApi ---------- */
async function serpQuota(env){
  if(!env.SERPAPI_KEY)return null;
  const key="https://suncar-cache.invalid/internal/serp-quota";
  const cached=await cacheGet(key);
  if(cached)return cached;
  const r=await fetchJson("https://serpapi.com/account.json?api_key="+encodeURIComponent(env.SERPAPI_KEY),{},10000);
  if(!r.ok||!r.data)return null;
  const q={
    left:num(r.data.total_searches_left||r.data.plan_searches_left),
    perMonth:num(r.data.searches_per_month),
    usage:num(r.data.this_month_usage)
  };
  await cachePut(key,q,900);
  return q;
}
function normalizeSerpProperty(p){
  const imgs=arr(p.images).map(x=>typeof x==="string"?x:(x?.thumbnail||x?.original_image||x?.original)).filter(Boolean).slice(0,8);
  const rate=p.rate_per_night||{};
  const total=p.total_rate||{};
  return {
    id:"sp:"+clean(p.property_token),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:num(p.extracted_hotel_class),
    rating:num(p.overall_rating),
    reviews:num(p.reviews),
    amenities:arr(p.amenities).slice(0,8),
    image:imgs[0]||p.thumbnail||"",
    images:imgs,
    night:{display:rate.lowest||"",amount:num(rate.extracted_lowest)},
    total:{display:total.lowest||"",amount:num(total.extracted_lowest)},
    freeCancellation:!!p.free_cancellation,
    checkInTime:p.check_in_time||"",
    checkOutTime:p.check_out_time||""
  };
}
function normalizeSerpRoom(room){
  const rates=arr(room.rates);
  const cheapest=rates.slice().sort((a,b)=>num(a?.total_rate?.extracted_lowest||1e12)-num(b?.total_rate?.extracted_lowest||1e12))[0]||{};
  const total=room.total_rate||cheapest.total_rate||{};
  const night=room.rate_per_night||cheapest.rate_per_night||{};
  return {
    name:room.name||"Habitación",
    guests:num(room.num_guests||cheapest.num_guests),
    image:arr(room.images)[0]||"",
    night:{display:night.lowest||"",amount:num(night.extracted_lowest)},
    total:{display:total.lowest||"",amount:num(total.extracted_lowest)},
    inclusions:uniq([...arr(room.inclusions),...arr(cheapest.inclusions)]).slice(0,8),
    freeCancellation:!!(room.free_cancellation||cheapest.free_cancellation)
  };
}
async function searchSerp(ctx,env){
  if(!env.SERPAPI_KEY)return null;
  const q=await serpQuota(env);
  if(q && q.left<=5)return null; // reserva de emergencia
  const p=new URLSearchParams({
    engine:"google_hotels",q:ctx.q,check_in_date:ctx.checkIn,check_out_date:ctx.checkOut,
    adults:String(ctx.adults),children:String(ctx.children),currency:ctx.currency,hl:"es",gl:"us",
    api_key:env.SERPAPI_KEY
  });
  const r=await fetchJson("https://serpapi.com/search.json?"+p.toString());
  if(!r.ok||!r.data||r.data.error)return null;
  const results=arr(r.data.properties).filter(x=>x.type==="hotel"||!x.type).slice(0,20).map(normalizeSerpProperty);
  return results.length?results:null;
}
async function detailsSerp(token,ctx,env){
  if(!env.SERPAPI_KEY)return null;
  const p=new URLSearchParams({
    engine:"google_hotels",q:ctx.q,property_token:token,check_in_date:ctx.checkIn,check_out_date:ctx.checkOut,
    adults:String(ctx.adults),children:String(ctx.children),currency:ctx.currency,hl:"es",gl:"us",
    api_key:env.SERPAPI_KEY
  });
  const r=await fetchJson("https://serpapi.com/search.json?"+p.toString());
  if(!r.ok||!r.data||r.data.error)return null;
  // Property Details puede devolver habitaciones en el nivel principal
  // y/o agrupadas dentro de featured_prices/prices.
  const rawRooms=[
    ...arr(r.data.rooms),
    ...arr(r.data.featured_prices).flatMap(x=>arr(x?.rooms)),
    ...arr(r.data.prices).flatMap(x=>arr(x?.rooms))
  ];
  const seen=new Set();
  const rooms=rawRooms.filter(room=>{
    const key=[room?.name,room?.total_rate?.lowest,room?.rate_per_night?.lowest].join("|");
    if(seen.has(key))return false;
    seen.add(key);return true;
  }).slice(0,12).map(normalizeSerpRoom);
  return rooms.length?rooms:null;
}

/* ---------- HasData ---------- */
function normalizeHasDataProperty(p){
  const imgs=arr(p.images).map(x=>typeof x==="string"?x:(x?.thumbnail||x?.original||x?.url)).filter(Boolean).slice(0,8);
  const rate=p.ratePerNight||p.rate_per_night||{};
  const total=p.totalRate||p.total_rate||{};
  return {
    id:"hd:"+clean(p.propertyToken||p.property_token),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:num(p.hotelClass||p.extractedHotelClass||p.extracted_hotel_class),
    rating:num(p.overallRating||p.overall_rating),
    reviews:num(p.reviews),
    amenities:arr(p.amenities).slice(0,8),
    image:imgs[0]||p.thumbnail||"",
    images:imgs,
    night:{
      display:rate.lowest||rate.display||"",
      amount:num(rate.extractedLowest||rate.extracted_lowest)
    },
    total:{
      display:total.lowest||total.display||"",
      amount:num(total.extractedLowest||total.extracted_lowest)
    },
    freeCancellation:!!(p.freeCancellation||p.free_cancellation),
    checkInTime:p.checkInTime||p.check_in_time||"",
    checkOutTime:p.checkOutTime||p.check_out_time||""
  };
}
function normalizeHasDataRoom(room){
  const total=room.totalRate||room.total_rate||{};
  const night=room.ratePerNight||room.rate_per_night||{};
  return {
    name:room.name||room.roomName||"Habitación",
    guests:num(room.numGuests||room.num_guests||room.guests),
    image:arr(room.images)[0]||"",
    night:{display:night.lowest||night.display||"",amount:num(night.extractedLowest||night.extracted_lowest)},
    total:{display:total.lowest||total.display||"",amount:num(total.extractedLowest||total.extracted_lowest)},
    inclusions:uniq([...arr(room.inclusions),...arr(room.amenities)]).slice(0,8),
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
  const p=new URLSearchParams({
    q:ctx.q,checkInDate:ctx.checkIn,checkOutDate:ctx.checkOut,
    adults:String(Math.min(6,ctx.adults)),children:String(Math.min(5,ctx.children)),
    currency:ctx.currency,hl:"es",gl:"us"
  });
  const d=await hasDataCall(p,env);
  if(!d)return null;
  const results=arr(d.properties).filter(x=>x.type==="hotel"||!x.type).slice(0,20).map(normalizeHasDataProperty);
  return results.length?results:null;
}
async function detailsHasData(token,ctx,env){
  const p=new URLSearchParams({
    q:ctx.q,checkInDate:ctx.checkIn,checkOutDate:ctx.checkOut,
    adults:String(Math.min(6,ctx.adults)),children:String(Math.min(5,ctx.children)),
    currency:ctx.currency,hl:"es",gl:"us",propertyToken:token
  });
  const d=await hasDataCall(p,env);
  if(!d)return null;
  const candidates=arr(d.rooms).length?d.rooms:
    arr(d.property?.rooms).length?d.property.rooms:
    arr(d.properties?.[0]?.rooms);
  const rooms=arr(candidates).slice(0,12).map(normalizeHasDataRoom);
  return rooms.length?rooms:null;
}

/* ---------- StayingAPI: optional last fallback; free evaluation credits only ---------- */
function normalizeStayingProperty(p){
  const price=p.price||{};
  const photos=arr(p.photos).map(x=>typeof x==="string"?x:(x?.url||x?.src)).filter(Boolean);
  return {
    id:"st:"+clean(p.id||p.platformListingId),
    name:p.name||"Hotel",
    description:p.description||"",
    stars:num(p.starRating),
    rating:num(p.guestRating),
    reviews:num(p.reviewCount),
    amenities:arr(p.amenities).slice(0,8),
    image:photos[0]||p.image||"",
    images:photos.slice(0,8),
    night:{display:price.nightlyPrice?ctxCurrency(price.currency,price.nightlyPrice):"",amount:num(price.nightlyPrice)},
    total:{display:price.totalPrice?ctxCurrency(price.currency,price.totalPrice):"",amount:num(price.totalPrice)},
    freeCancellation:!!p.freeCancellation,
    checkInTime:"",
    checkOutTime:""
  };
}
function ctxCurrency(currency,amount){return (currency||"USD")+" "+num(amount).toLocaleString("en-US")}
async function searchStaying(ctx,env){
  if(!env.STAYINGAPI_KEY || String(env.STAYINGAPI_ENABLED||"").toLowerCase()!=="true")return null;
  const p=new URLSearchParams({
    location:ctx.q,checkIn:ctx.checkIn,checkOut:ctx.checkOut,adults:String(ctx.adults),
    children:String(ctx.children),platforms:"google",limit:"20",currency:ctx.currency
  });
  const r=await fetchJson("https://api.stayingapi.com/v1/search?"+p.toString(),{
    headers:{Authorization:"Bearer "+env.STAYINGAPI_KEY}
  },25000);
  if(!r.ok||!r.data)return null;
  if(r.status===202)return null; // no hacemos polling en búsquedas web del cliente
  const results=arr(r.data.data).map(normalizeStayingProperty).slice(0,20);
  return results.length?results:null;
}

/* ---------- Shared ---------- */
function searchContext(u){
  return {
    q:clean(u.searchParams.get("q")),
    checkIn:clean(u.searchParams.get("check_in")),
    checkOut:clean(u.searchParams.get("check_out")),
    adults:int(u.searchParams.get("adults"),2,1,12),
    children:int(u.searchParams.get("children"),0,0,8),
    currency:(clean(u.searchParams.get("currency"))||"USD").toUpperCase().slice(0,3)
  };
}
function validCtx(c){return !!c.q&&dateOk(c.checkIn)&&dateOk(c.checkOut)&&c.checkOut>c.checkIn}
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
  if(prefix==="sp"){
    return (await detailsSerp(token,ctx,env)) || (await detailsHasData(token,ctx,env));
  }
  if(prefix==="hd"){
    return (await detailsHasData(token,ctx,env)) || (await detailsSerp(token,ctx,env));
  }
  return null;
}

export default {
 async fetch(request,env){
  if(request.method==="OPTIONS")return new Response(null,{headers:CORS});
  const u=new URL(request.url);

  if(u.pathname==="/"||u.pathname==="/health"){
    return json({ok:true,service:"Suncar Hotels API",multiSource:true});
  }

  if(u.pathname==="/hotels/search"){
    const ctx=searchContext(u);
    if(!validCtx(ctx))return json({ok:false,error:"Búsqueda inválida"},400);

    const cacheKey=canonicalSearchKey(u);
    const cached=await cacheGet(cacheKey);
    if(cached)return json({...cached,cached:true});

    const results=await searchWithFailover(ctx,env);
    if(!results?.length)return json({ok:false,error:"No hay resultados automáticos disponibles en este momento"},503);

    const payload={
      ok:true,cached:false,observedAt:new Date().toISOString(),
      query:{q:ctx.q,checkIn:ctx.checkIn,checkOut:ctx.checkOut,adults:ctx.adults,children:ctx.children,currency:ctx.currency},
      results
    };
    await cachePut(cacheKey,payload,21600); // 6 horas para proteger cupos gratuitos
    return json(payload);
  }

  if(u.pathname==="/hotels/details"){
    const ctx=searchContext(u);
    const rawToken=clean(u.searchParams.get("property_token"));
    if(!rawToken||!validCtx(ctx))return json({ok:false,error:"Detalle inválido"},400);

    const cacheKey=canonicalDetailKey(u);
    const cached=await cacheGet(cacheKey);
    if(cached)return json({...cached,cached:true});

    const rooms=await detailsWithRoute(rawToken,ctx,env);
    if(!rooms?.length)return json({ok:false,error:"No hay detalle automático disponible"},503);

    const payload={ok:true,cached:false,observedAt:new Date().toISOString(),rooms};
    await cachePut(cacheKey,payload,21600);
    return json(payload);
  }

  return json({ok:false,error:"Ruta no encontrada"},404);
 }
};