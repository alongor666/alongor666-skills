/* deck-16x9.js —— PPT 16:9 演示翻页（仅屏幕生效）
 *   丝滑演示引擎：一屏一页、GPU transform 横向「推入」过渡（类 PowerPoint Push），无滚动条、无惯性回弹。
 *   交互（演示导向，区别于 PDF 的 deck.js）：
 *   · 左右翻页【只认 ← → 方向键】（Home/End 跳首末）——不再有「点击页面左右」「滚轮翻页」。
 *   · 底部【序号条】：点页码一键直达；远跳也只做一次单步推入（不论距离），当前页高亮。
 *   · 【缩略图总览】：点 ▦ 或在页面上按 Esc 打开（无序号、纯缩略图，淡入上浮），点缩略图进入该页。
 *   · 【Esc 两级退出】页面 → 缩略图总览；缩略图 → 退出全屏（关总览 + 退浏览器全屏）。⛶ 进入/退出全屏演示。
 *     注：真·浏览器全屏态下，首个 Esc 由浏览器强制退出全屏（JS 拦不住）——此时总览改用 ▦ 打开。
 *   打印/导出时整段不参与（@media print 已复位 .slide/.page 并隐藏导航 chrome）。
 *   配合 deck-16x9.css + report-skin.css + skin-16x9.css 使用，置于页尾：<script src="deck-16x9.js"></script>
 *   PDF（A4）版请改用 deck.js——两套脚本互不影响。 */
(function(){
  if(window.matchMedia&&window.matchMedia('print').matches) return;
  function build(){
    var pages=[].slice.call(document.querySelectorAll('.page'));
    if(!pages.length) return;
    document.body.classList.add('deck','deck-no-anim');
    pages.forEach(function(p){
      var s=document.createElement('div'); s.className='slide';
      p.parentNode.insertBefore(s,p); s.appendChild(p);
    });
    var slides=[].slice.call(document.querySelectorAll('.slide'));

    // —— 屏幕缩放适配：把 1280×720 的 .page 等比缩到视口（transform 不影响填充率比例）——
    function fit(){
      var pw=pages[0].offsetWidth, ph=pages[0].offsetHeight;
      var sc=Math.min((window.innerHeight*0.94)/ph,(window.innerWidth*0.86)/pw);
      pages.forEach(function(p){ p.style.transform='scale('+sc+')'; });
    }
    fit(); window.addEventListener('resize',fit);

    // —— 序号条（先建，jump 要用 setActive）——
    var bar=document.createElement('div'); bar.className='deck-bar';
    var nums=[];
    pages.forEach(function(p,i){
      var b=document.createElement('button'); b.className='deck-num'; b.textContent=(i+1);
      b.addEventListener('click',function(){jump(i);});
      bar.appendChild(b); nums.push(b);
    });
    var fbtn=document.createElement('button'); fbtn.className='deck-num deck-fs-btn';
    fbtn.innerHTML='&#9974;'; fbtn.title='全屏演示 / 退出（Esc）';
    fbtn.addEventListener('click',function(){toggleFs();});
    bar.appendChild(fbtn);
    var gbtn=document.createElement('button'); gbtn.className='deck-num deck-grid-btn';
    gbtn.innerHTML='&#9638;'; gbtn.title='全部页总览（页面里按 Esc 也可）';
    gbtn.addEventListener('click',function(){toggleOverview();});
    bar.appendChild(gbtn);
    document.body.appendChild(bar);
    function setActive(i){nums.forEach(function(b,k){b.classList.toggle('on',k===i);});}

    // —— 单步推入引擎：每次翻页都只做一次相邻推进，远跳也不例外 ——
    var idx=0;
    function place(active){ // 按 active 把每页摆到 左(-100%)/中(0)/右(100%)
      slides.forEach(function(sl,k){
        sl.style.transform='translateX('+(k<active?-100:k>active?100:0)+'%)';
        sl.classList.toggle('active',k===active);
      });
    }
    function jump(i){
      i=Math.max(0,Math.min(slides.length-1,i));
      if(i===idx) return;
      var dir=i>idx?1:-1;
      // 1) 无动画：目标贴到相邻一侧、当前留中，其余按最终侧远置（都在视口外、不可见）
      document.body.classList.add('deck-no-anim');
      slides.forEach(function(sl,k){
        var pos = k===idx?0 : k===i?dir*100 : (k<i?-100:100);
        sl.style.transform='translateX('+pos+'%)';
      });
      void document.body.offsetWidth;                 // 强制 reflow，让预置位置即时落定
      document.body.classList.remove('deck-no-anim');
      // 2) 带动画：单步推进——目标入场到 0，当前推出到另一侧
      idx=i; place(idx); setActive(idx);
    }
    function go(d){ jump(idx+d); }

    // —— 全屏（演示态）——
    function isFs(){ return document.fullscreenElement||document.webkitFullscreenElement; }
    function enterFs(){ var el=document.documentElement;
      (el.requestFullscreen||el.webkitRequestFullscreen||function(){}).call(el); }
    function exitFs(){ if(document.fullscreenElement&&document.exitFullscreen) document.exitFullscreen();
      else if(document.webkitFullscreenElement&&document.webkitExitFullscreen) document.webkitExitFullscreen(); }
    function toggleFs(){ isFs()?exitFs():enterFs(); }

    // —— 缩略图总览（懒构建，仅用户首次触发时才进 DOM，避免污染 .page 计数/导出）——
    var ov=null;
    function buildOverview(){
      ov=document.createElement('div'); ov.className='deck-overview';
      var hd=document.createElement('div'); hd.className='deck-ov-hd';
      hd.textContent='全部页 · 点击进入 · Esc 退出';
      var wrap=document.createElement('div'); wrap.className='deck-overview-grid';
      var pw=pages[0].offsetWidth, ph=pages[0].offsetHeight, TW=300, scale=TW/pw;
      pages.forEach(function(p,i){
        var cell=document.createElement('div'); cell.className='deck-thumb';
        cell.style.width=TW+'px'; cell.style.height=(TW*ph/pw)+'px';
        var clone=p.cloneNode(true);
        clone.style.transform='scale('+scale+')';
        clone.style.transformOrigin='top left'; clone.style.margin='0';
        cell.appendChild(clone);
        cell.addEventListener('click',function(){closeOverview();jump(i);});
        wrap.appendChild(cell);
      });
      ov.appendChild(hd); ov.appendChild(wrap);
      ov.addEventListener('click',function(e){if(e.target===ov||e.target===hd)closeOverview();});
      document.body.appendChild(ov);
    }
    function openOverview(){
      if(!ov) buildOverview();
      [].forEach.call(ov.querySelectorAll('.deck-thumb'),function(t,k){t.classList.toggle('on',k===idx);});
      requestAnimationFrame(function(){document.body.classList.add('ov-open');}); // 下一帧加类 → 淡入动画
    }
    function closeOverview(){document.body.classList.remove('ov-open');}
    function toggleOverview(){
      document.body.classList.contains('ov-open')?closeOverview():openOverview();
    }

    // —— 键盘：左右翻页只认方向键；Esc 只负责退出 ——
    window.addEventListener('keydown',function(e){
      if(e.key==='Escape'){
        // Esc 两级退出：① 页面 → 缩略图总览 ② 缩略图 → 退出全屏（关总览 + 退浏览器全屏）
        if(document.body.classList.contains('ov-open')){
          e.preventDefault(); closeOverview(); exitFs();
        } else if(!isFs()){
          e.preventDefault(); openOverview();            // 窗口态：页面 → 缩略图
        } // else 真全屏 + 未开总览：不拦截，让浏览器原生退出全屏（总览改用 ▦）
        return;
      }
      if(document.body.classList.contains('ov-open')) return; // 总览态不翻页
      if(e.key==='ArrowRight'){e.preventDefault();go(1);}
      else if(e.key==='ArrowLeft'){e.preventDefault();go(-1);}
      else if(e.key==='Home'){e.preventDefault();jump(0);}
      else if(e.key==='End'){e.preventDefault();jump(slides.length-1);}
    });

    // —— 初始：无动画摆位，下一帧再开过渡，避免加载时整排滑动 ——
    place(0); setActive(0);
    requestAnimationFrame(function(){requestAnimationFrame(function(){
      document.body.classList.remove('deck-no-anim');
    });});
  }
  if(document.readyState!=='loading') build();
  else document.addEventListener('DOMContentLoaded',build);
})();
