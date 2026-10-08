(function(){
  'use strict';

  const id=String(window.SUNCAR_GA4_ID||'').trim();
  const campaignKeys=['utm_source','utm_medium','utm_campaign','utm_content','utm_term','utm_id'];
  const campaign={};

  try{
    const params=new URLSearchParams(location.search);
    const incoming={};
    campaignKeys.forEach(k=>{const v=params.get(k);if(v)incoming[k]=v;});
    if(Object.keys(incoming).length){
      sessionStorage.setItem('suncar_campaign',JSON.stringify(incoming));
    }
    Object.assign(campaign,JSON.parse(sessionStorage.getItem('suncar_campaign')||'{}'));
  }catch(e){}

  window.dataLayer=window.dataLayer||[];
  window.gtag=window.gtag||function(){dataLayer.push(arguments);};

  if(/^G-[A-Z0-9]+$/i.test(id)){
    const s=document.createElement('script');
    s.async=true;
    s.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(id);
    document.head.appendChild(s);
    gtag('js',new Date());
    gtag('config',id,{
      send_page_view:true,
      allow_google_signals:false
    });
  }

  function cleanText(v){
    return String(v||'').replace(/\s+/g,' ').trim().slice(0,120);
  }
  function pageName(){
    return document.title.split('|')[0].trim()||location.pathname;
  }
  function track(name,params){
    if(!/^G-[A-Z0-9]+$/i.test(id))return;
    const base={
      page_name:pageName(),
      page_path:location.pathname,
      ...campaign
    };
    gtag('event',name,{...base,...(params||{})});
  }

  document.addEventListener('click',function(e){
    const el=e.target.closest('a,button');
    if(!el)return;
    const href=el.getAttribute('href')||'';
    const label=cleanText(el.textContent||el.getAttribute('aria-label')||'');
    if(/wa\.me|api\.whatsapp\.com/i.test(href)){
      track('whatsapp_click',{link_text:label||'WhatsApp',link_url:href.slice(0,240)});
      return;
    }
    const service=el.closest('[data-service]')?.getAttribute('data-service')||'';
    if(service)track('service_click',{service,link_text:label});
    if(el.matches('[data-track]')){
      track(el.getAttribute('data-track')||'cta_click',{link_text:label});
    }
  },true);

  document.addEventListener('submit',function(e){
    const form=e.target;
    if(!(form instanceof HTMLFormElement))return;
    track('form_submit',{form_id:form.id||'sin_id',form_name:form.getAttribute('name')||''});
  },true);

  window.SuncarAnalytics={track,enabled:/^G-[A-Z0-9]+$/i.test(id)};
})();
