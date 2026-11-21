(function(){
  var store={get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},set:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
  // 首頁篩選
  var filts=[].slice.call(document.querySelectorAll('.filt'));
  filts.forEach(function(b){b.addEventListener('click',function(){var f=b.dataset.f;
    filts.forEach(function(x){x.setAttribute('aria-pressed',x===b)});
    document.querySelectorAll('.dish-card').forEach(function(c){c.hidden=!(f==='all'||c.dataset.tag===f)});});});
  var KEY=window.ZD_KEY; if(!KEY) return;
  // 份量倍數
  var FR=[[0,''],[1/6,'⅙'],[1/4,'¼'],[1/3,'⅓'],[1/2,'½'],[2/3,'⅔'],[3/4,'¾'],[5/6,'⅚']];
  var SP={piece:1,clove:1,slice:1,stalk:1,bicchiere:1,cucchiaio:1,tbsp:1,tsp:1,cup:1,pack:1};
  function fmt(v,u){
    if(SP[u]){var w=Math.floor(v+1e-9),r=v-w;for(var i=0;i<FR.length;i++){if(Math.abs(r-FR[i][0])<0.02){return w&&FR[i][1]?w+FR[i][1]:(FR[i][1]||String(w));}}
      if(Math.abs(r-1)<0.02)return String(w+1);var q=Math.round(v*4)/4;return '約 '+fmt(q,u);}
    if(v>=10)return String(Math.round(v));return String(Math.round(v*10)/10);}
  function conv(g,k){var c=window.ZD_CONV[k];if(!c)return '';
    if(c[1]){var n=g/c[1];n=n<20?Math.round(n*2)/2:Math.round(n);return '約 '+fmt(Math.max(n,0.5),'piece')+' '+c[2];}
    var tb=g/c[0];if(tb>=8){var cup=Math.round(tb/16*4)/4;if(cup>=0.25)return '約 '+fmt(cup,'cup')+' 杯（量杯）';}
    if(tb>=1)return '約 '+fmt(Math.round(tb*2)/2,'tbsp')+' 大匙';var t=tb*3;if(t>=0.249)return '約 '+fmt(Math.max(Math.round(t*4)/4,0.25),'tsp')+' 小匙';return '不到 ¼ 小匙';}
  function scale(s){
    document.querySelectorAll('.q').forEach(function(e){e.textContent=(fmt(parseFloat(e.dataset.v)*s,e.dataset.u)+' '+e.dataset.w).trim();});
    document.querySelectorAll('.cv').forEach(function(e){e.textContent='換算值：'+conv(parseFloat(e.dataset.g)*s,+e.dataset.k);});
    document.querySelectorAll('.scale-btn').forEach(function(b){b.setAttribute('aria-pressed',+b.dataset.s===s);});
    store.set('zd-scale-'+KEY,String(s));}
  document.querySelectorAll('.scale-btn').forEach(function(b){b.addEventListener('click',function(){scale(+b.dataset.s);});});
  var s0=parseFloat(store.get('zd-scale-'+KEY)||'1');if(s0!==1)scale(s0);
  // 步驟勾選
  var boxes=[].slice.call(document.querySelectorAll('.step-check input'));
  function refresh(){var n=0;boxes.forEach(function(b){if(b.checked)n++;b.closest('.step').classList.toggle('is-done',b.checked);});
    var p=document.querySelector('.progress');if(p)p.textContent='已完成 '+n+' / '+boxes.length;}
  boxes.forEach(function(b){b.checked=store.get('zd-step-'+KEY+'-'+b.dataset.step)==='1';
    b.addEventListener('change',function(){store.set('zd-step-'+KEY+'-'+b.dataset.step,b.checked?'1':'0');refresh();});});
  refresh();
  var rs=document.querySelector('.reset');if(rs)rs.addEventListener('click',function(){boxes.forEach(function(b){b.checked=false;store.set('zd-step-'+KEY+'-'+b.dataset.step,'0');});refresh();});
  // 複製購物清單
  var cp=document.querySelector('.copy-shop');
  if(cp)cp.addEventListener('click',function(){var lines=[document.querySelector('.dish-name').textContent+' 購物清單'];
    document.querySelectorAll('.shop-list li').forEach(function(li){if(!li.querySelector('input').checked)lines.push('□ '+li.querySelector('label span').textContent+'　'+li.querySelector('.ing-qty').textContent);});
    var t=lines.join('\n'),msg=document.querySelector('.shop-msg');
    function ok(){msg.textContent='已複製，可以貼到備忘錄或傳給家人。';}
    if(navigator.clipboard)navigator.clipboard.writeText(t).then(ok,function(){msg.textContent='這個瀏覽器不能自動複製，請長按選取。';});
    else msg.textContent='這個瀏覽器不能自動複製，請長按選取。';});
})();
