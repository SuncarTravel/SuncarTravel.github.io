(function(){
  function clean(text){
    return String(text == null ? '' : text)
      .normalize('NFC')
      .replace(/\uFFFD/g,'')
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/gu,'')
      .replace(/→/g,'->')
      .replace(/[•·]/g,'-')
      .replace(/[–—]/g,'-')
      .replace(/[ \t]+\n/g,'\n')
      .replace(/\n{3,}/g,'\n\n')
      .replace(/[ \t]{2,}/g,' ')
      .trim();
  }
  function url(number,message){
    const phone=String(number||'18093161070').replace(/\D/g,'');
    return 'https://wa.me/'+phone+'?text='+encodeURIComponent(clean(message));
  }
  window.SuncarWhatsApp={clean,url};
})();