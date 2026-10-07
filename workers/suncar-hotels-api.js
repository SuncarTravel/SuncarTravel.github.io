const CORS={
  "Access-Control-Allow-Origin":"*",
  "Access-Control-Allow-Methods":"GET,OPTIONS",
  "Access-Control-Allow-Headers":"Content-Type"
};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{...CORS,"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"}});
const clean=s=>String(s||"").trim();
const int=(v,d,min,max)=>{const n=parseInt(v,10);return Number.isFinite(n)?Math.min(max,Math.max(min,n)):d};
const dateOk=s=>/^\d{4}-\d{2}-\d{2}$/.test(s||"");
async function cachedFetch(url,ttl=3600){
  const cache=caches.default;
  const key=new Request(url,{method:"GET"});
  let r=await cache.match(key);
  if(r)return r;
  r=await fetch(url);
  if(r.ok){const copy=new Response(r.body,{status:r.status,headers:r.headers});copy.headers.set("Cache-Control","public, max-age="+ttl);await cache.put(key,copy.clone());return copy}
  return r;
}
function normalizeProperty(p){
  const images=Array.isArray(p.images)?p.images.slice(0,8).map(x=>x.thumbnail||x.original_image).filter(Boolean):[];
  const rate=p.rate_per_night||{};
  const total=p.total_rate||{};
  return {
    id:p.property_token||"",
    name:p.name||"Hotel",
    description:p.description||"",
    stars:Number(p.extracted_hotel_class||0),
    rating:Number(p.overall_rating||0),
    reviews:Number(p.reviews||0),
    amenities:Array.isArray(p.amenities)?p.amenities.slice(0,8):[],
    image:images[0]||p.thumbnail||"",
    images,
    night:{display:rate.lowest||"",amount:Number(rate.extracted_lowest||0)},
    total:{display:total.lowest||"",amount:Number(total.extracted_lowest||0)},
    freeCancellation:!!p.free_cancellation,
    checkInTime:p.check_in_time||"",
    checkOutTime:p.check_out_time||""
  };
}
function normalizeRoom(room){
  const rates=Array.isArray(room.rates)?room.rates:[];
  const cheapest=rates.slice().sort((a,b)=>(a.total_rate?.extracted_lowest||1e12)-(b.total_rate?.extracted_lowest||1e12))[0]||{};
  const total=room.total_rate||cheapest.total_rate||{};
  const night=room.rate_per_night||cheapest.rate_per_night||{};
  const inclusions=[...(room.inclusions||[]),...(cheapest.inclusions||[])].filter(Boolean);
  return {
    name:room.name||"Habitación",
    guests:Number(room.num_guests||cheapest.num_guests||0),
    image:Array.isArray(room.images)?room.images[0]||"": "",
    night:{display:night.lowest||"",amount:Number(night.extracted_lowest||0)},
    total:{display:total.lowest||"",amount:Number(total.extracted_lowest||0)},
    inclusions:[...new Set(inclusions)].slice(0,8),
    freeCancellation:!!(room.free_cancellation||cheapest.free_cancellation)
  };
}
export default {
 async fetch(request,env){
  if(request.method==="OPTIONS")return new Response(null,{headers:CORS});
  const u=new URL(request.url);
  if(!env.SERPAPI_KEY)return json({ok:false,error:"SERPAPI_KEY no configurada"},500);
  if(u.pathname==="/"||u.pathname==="/health")return json({ok:true,service:"Suncar Hotels API"});
  if(u.pathname==="/hotels/search"){
    const q=clean(u.searchParams.get("q"));
    const checkIn=clean(u.searchParams.get("check_in"));
    const checkOut=clean(u.searchParams.get("check_out"));
    const adults=int(u.searchParams.get("adults"),2,1,12);
    const children=int(u.searchParams.get("children"),0,0,8);
    const currency=(clean(u.searchParams.get("currency"))||"USD").toUpperCase().slice(0,3);
    if(!q||!dateOk(checkIn)||!dateOk(checkOut)||checkOut<=checkIn)return json({ok:false,error:"Búsqueda inválida"},400);
    const params=new URLSearchParams({engine:"google_hotels",q,check_in_date:checkIn,check_out_date:checkOut,adults:String(adults),children:String(children),currency,hl:"es",gl:"us",api_key:env.SERPAPI_KEY});
    const r=await cachedFetch("https://serpapi.com/search.json?"+params.toString(),3600);
    const d=await r.json();
    if(!r.ok||d.error)return json({ok:false,error:d.error||"No se pudo consultar hoteles"},502);
    const properties=(d.properties||[]).filter(x=>x.type==="hotel"||!x.type).slice(0,20).map(normalizeProperty);
    return json({ok:true,query:{q,checkIn,checkOut,adults,children,currency},results:properties});
  }
  if(u.pathname==="/hotels/details"){
    const token=clean(u.searchParams.get("property_token"));
    const q=clean(u.searchParams.get("q"));
    const checkIn=clean(u.searchParams.get("check_in"));
    const checkOut=clean(u.searchParams.get("check_out"));
    const adults=int(u.searchParams.get("adults"),2,1,12);
    const children=int(u.searchParams.get("children"),0,0,8);
    const currency=(clean(u.searchParams.get("currency"))||"USD").toUpperCase().slice(0,3);
    if(!token||!q||!dateOk(checkIn)||!dateOk(checkOut))return json({ok:false,error:"Detalle inválido"},400);
    const params=new URLSearchParams({engine:"google_hotels",q,property_token:token,check_in_date:checkIn,check_out_date:checkOut,adults:String(adults),children:String(children),currency,hl:"es",gl:"us",api_key:env.SERPAPI_KEY});
    const r=await cachedFetch("https://serpapi.com/search.json?"+params.toString(),3600);
    const d=await r.json();
    if(!r.ok||d.error)return json({ok:false,error:d.error||"No se pudo consultar detalle"},502);
    const rooms=(d.rooms||[]).slice(0,12).map(normalizeRoom);
    return json({ok:true,rooms});
  }
  return json({ok:false,error:"Ruta no encontrada"},404);
 }
};