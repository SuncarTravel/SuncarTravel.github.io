(function(){
  'use strict';
  const now=Date.now();
  document.querySelectorAll('[data-expire]').forEach(el=>{
    const t=Date.parse(el.getAttribute('data-expire')||'');
    if(Number.isFinite(t)&&now>=t)el.remove();
  });
  document.querySelectorAll('[data-offers-container]').forEach(box=>{
    if(!box.querySelector('[data-expire], .offer-card, .card')){
      const empty=document.createElement('div');
      empty.className='empty';
      empty.textContent='No hay ofertas activas publicadas en este momento. Escríbenos y te cotizamos opciones vigentes.';
      box.appendChild(empty);
    }
  });
})();
