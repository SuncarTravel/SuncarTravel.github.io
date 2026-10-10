(function(){
  'use strict';

  const TIME_ZONE='America/Santo_Domingo';
  const DATE_RE=/^\d{4}-\d{2}-\d{2}$/;

  const dateKey=(date=new Date())=>{
    const parts=new Intl.DateTimeFormat('en-US',{
      timeZone:TIME_ZONE,year:'numeric',month:'2-digit',day:'2-digit'
    }).formatToParts(date);
    const values=Object.fromEntries(parts.map(p=>[p.type,p.value]));
    return values.year+'-'+values.month+'-'+values.day;
  };

  const today=()=>dateKey(new Date());

  const deadline=(el)=>{
    const validThrough=el.getAttribute('data-valid-through');
    if(validThrough&&DATE_RE.test(validThrough)){
      return Date.parse(validThrough+'T23:59:59-04:00');
    }
    const raw=el.getAttribute('data-expire');
    if(!raw)return Number.POSITIVE_INFINITY;
    if(DATE_RE.test(raw))return Date.parse(raw+'T00:00:00-04:00');
    const parsed=Date.parse(raw);
    return Number.isFinite(parsed)?parsed:Number.POSITIVE_INFINITY;
  };

  const isExpired=(el)=>{
    const current=today();
    const validThrough=el.getAttribute('data-valid-through');
    if(validThrough&&DATE_RE.test(validThrough))return current>validThrough;

    const raw=el.getAttribute('data-expire');
    if(!raw)return false;
    if(DATE_RE.test(raw))return current>=raw;

    const parsed=Date.parse(raw);
    return Number.isFinite(parsed)&&Date.now()>=parsed;
  };

  const prune=()=>{
    let removed=0;
    document.querySelectorAll('[data-expire],[data-valid-through]').forEach(el=>{
      if(isExpired(el)){el.remove();removed++;}
    });

    document.querySelectorAll('[data-offers-container]').forEach(box=>{
      const items=[...box.children].filter(el=>el.matches('[data-expire],[data-valid-through],.limited-offer'));
      if(box.dataset.sortOffers==='deadline'){
        items.sort((a,b)=>deadline(a)-deadline(b)).forEach(el=>box.appendChild(el));
      }
      const limit=Number(box.dataset.offersLimit||0);
      if(Number.isFinite(limit)&&limit>0){
        [...box.children].forEach((el,i)=>el.classList.toggle('is-hidden',i>=limit));
      }
      const hasOffer=[...box.children].some(el=>el.matches('.offer-card,.limited-offer,[data-expire],[data-valid-through]'));
      if(!hasOffer&&!box.querySelector('.empty')){
        const empty=document.createElement('div');
        empty.className='empty';
        empty.textContent='No hay ofertas activas publicadas en este momento. Escríbenos y te cotizamos opciones vigentes.';
        box.appendChild(empty);
      }
    });

    document.dispatchEvent(new CustomEvent('suncar:offers-pruned',{detail:{removed,today:today(),timeZone:TIME_ZONE}}));
    return removed;
  };

  window.SuncarOffers={TIME_ZONE,today,deadline,isExpired,prune};
  prune();
})();
