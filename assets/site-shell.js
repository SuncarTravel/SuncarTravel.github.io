(function(){
  'use strict';

  const nav=document.querySelector('header nav');
  const links=nav?.querySelector(':scope > .links, :scope > .navlinks');

  function closeMenu(){
    if(!links)return;
    links.classList.remove('open');
    const btn=nav?.querySelector('.site-menu-toggle');
    if(btn){
      btn.setAttribute('aria-expanded','false');
      btn.setAttribute('aria-label','Abrir menú');
      btn.textContent='Menú';
    }
  }

  if(nav&&links&&!nav.querySelector('.site-menu-toggle')){
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='site-menu-toggle';
    btn.setAttribute('aria-expanded','false');
    btn.setAttribute('aria-label','Abrir menú');
    btn.textContent='Menú';

    btn.addEventListener('click',()=>{
      const open=links.classList.toggle('open');
      btn.setAttribute('aria-expanded',String(open));
      btn.setAttribute('aria-label',open?'Cerrar menú':'Abrir menú');
      btn.textContent=open?'Cerrar':'Menú';
    });

    nav.insertBefore(btn,links);

    links.addEventListener('click',e=>{
      if(e.target.closest('a')) closeMenu();
    });

    document.addEventListener('click',e=>{
      if(!nav.contains(e.target)) closeMenu();
    });

    document.addEventListener('keydown',e=>{
      if(e.key==='Escape') closeMenu();
    });

    window.addEventListener('resize',()=>{
      if(window.innerWidth>940) closeMenu();
    },{passive:true});
  }

  const current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
  document.querySelectorAll('nav a[href]').forEach(a=>{
    const raw=(a.getAttribute('href')||'').split('#')[0].split('?')[0];
    if(!raw)return;
    const target=(raw.split('/').pop()||'index.html').toLowerCase();
    if(target===current)a.setAttribute('aria-current','page');
  });

  const footer=document.querySelector('footer');
  if(footer&&!footer.classList.contains('suncar-footer')){
    const container=footer.querySelector('.container');
    if(container){
      footer.classList.remove('foot');
      footer.classList.add('suncar-footer');
      container.innerHTML=
        '<div class="footer-grid">'+
          '<div><img class="footer-logo" src="assets/logo.svg?v=7" alt="Suncar Tours & Travel"><p>Cruceros, hoteles, vuelos, seguros y escapadas con atención personalizada desde República Dominicana.</p></div>'+
          '<div><h4>Contacto</h4><p><a href="tel:+18093161070">809-316-1070</a><br><a href="mailto:suncartravel@gmail.com">suncartravel@gmail.com</a><br>Calle Trinitaria No. 5, San Carlos, Santo Domingo</p></div>'+
          '<div><h4>Información</h4><p><a href="ofertas.html">Ofertas</a><br><a href="politica-privacidad.html">Privacidad</a><br><a href="terminos-condiciones.html">Términos y Condiciones</a><br><a href="cambios-cancelaciones-reembolsos.html">Cambios y reembolsos</a></p></div>'+
        '</div>'+
        '<div class="copy">© 2026 Suncar Tours & Travel. Una solicitud enviada desde la web no confirma una reserva ni genera un cargo automático.</div>';
    }
  }
})();
