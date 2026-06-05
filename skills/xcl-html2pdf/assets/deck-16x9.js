/* deck-16x9.js —— PPT 16:9 演示翻页（仅屏幕生效）
 *   交互（演示导向，区别于 PDF 的 deck.js）：
 *   · 左右翻页【只认 ← → 方向键】——不再有「点击页面左右」「滚轮翻页」，避免误触。
 *   · 底部【序号条】：一排页码，点任意号一键直达；当前页高亮，滚动自动跟随。
 *   · 【缩略图总览】：按 Esc（或点序号条右端 ▦）一键切换，全部页缩成小图铺一屏；
 *     点任一缩略图进入该页；Esc 随时退出。总览为懒构建，绝不在初始 DOM 出现，
 *     不污染 .page 计数 / PDF 导出 / driver 验收。
 *   打印/导出时整段不参与（@media print 已复位 .slide/.page 并隐藏导航 chrome）。
 *   配合 deck-16x9.css + report-skin.css + skin-16x9.css 使用，置于页尾：<script src="deck-16x9.js"></script>
 *   PDF（A4）版请改用 deck.js——两套脚本互不影响。 */
(function(){
  if(window.matchMedia&&window.matchMedia('print').matches) return;
  function build(){
    var pages=[].slice.call(document.querySelectorAll('.page'));
    if(!pages.length) return;
    document.body.classList.add('deck');
    pages.forEach(function(p){
      var s=document.createElement('div'); s.className='slide';
      p.parentNode.insertBefore(s,p); s.appendChild(p);
    });
    var slides=[].slice.call(document.querySelectorAll('.slide'));

    // —— 屏幕缩放适配（与 A4 版同一套；transform 缩放不影响填充率比例）——
    function fit(){
      var pw=pages[0].offsetWidth, ph=pages[0].offsetHeight;
      var sc=Math.min((window.innerHeight*0.94)/ph,(window.innerWidth*0.86)/pw);
      slides.forEach(function(sl){
        sl.querySelector('.page').style.transform='scale('+sc+')';
        sl.style.width=document.documentElement.clientWidth+'px';
      });
    }
    fit(); window.addEventListener('resize',fit);

    var SC=document.scrollingElement||document.documentElement;
    function target(i){var s=slides[i],max=SC.scrollWidth-SC.clientWidth;
      return Math.max(0,Math.min(max,s.offsetLeft-(SC.clientWidth-s.offsetWidth)/2));}
    function cur(){var x=SC.scrollLeft,best=0,bd=1/0;
      for(var i=0;i<slides.length;i++){var d=Math.abs(target(i)-x);if(d<bd){bd=d;best=i;}}
      return best;}
    function jump(i){i=Math.max(0,Math.min(slides.length-1,i));
      SC.scrollTo({left:target(i),behavior:'smooth'}); setActive(i);}
    function go(d){jump(cur()+d);}

    // —— 底部序号条：一键直达任意页 ——
    var bar=document.createElement('div'); bar.className='deck-bar';
    var nums=[];
    pages.forEach(function(p,i){
      var b=document.createElement('button'); b.className='deck-num'; b.textContent=(i+1);
      b.addEventListener('click',function(){jump(i);});
      bar.appendChild(b); nums.push(b);
    });
    var gbtn=document.createElement('button'); gbtn.className='deck-num deck-grid-btn';
    gbtn.innerHTML='&#9638;'; gbtn.title='全部页总览（Esc）';
    gbtn.addEventListener('click',function(){toggleOverview();});
    bar.appendChild(gbtn);
    document.body.appendChild(bar);
    function setActive(i){nums.forEach(function(b,k){b.classList.toggle('on',k===i);});}

    var raf=0;
    SC.addEventListener('scroll',function(){
      if(raf) return; raf=requestAnimationFrame(function(){raf=0;setActive(cur());});
    },{passive:true});
    setActive(0);

    // —— 缩略图总览（懒构建，仅用户首次触发时才进 DOM）——
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
        var tag=document.createElement('span'); tag.className='deck-thumb-no'; tag.textContent=(i+1);
        cell.appendChild(tag);
        cell.addEventListener('click',function(){closeOverview();jump(i);});
        wrap.appendChild(cell);
      });
      ov.appendChild(hd); ov.appendChild(wrap);
      ov.addEventListener('click',function(e){if(e.target===ov||e.target===hd)closeOverview();});
      document.body.appendChild(ov);
    }
    function openOverview(){
      if(!ov) buildOverview();
      var c=cur();
      [].forEach.call(ov.querySelectorAll('.deck-thumb'),function(t,k){t.classList.toggle('on',k===c);});
      document.body.classList.add('ov-open');
    }
    function closeOverview(){document.body.classList.remove('ov-open');}
    function toggleOverview(){
      document.body.classList.contains('ov-open')?closeOverview():openOverview();
    }

    // —— 键盘：左右翻页只认方向键；Esc 切换总览 ——
    window.addEventListener('keydown',function(e){
      if(e.key==='Escape'){e.preventDefault();toggleOverview();return;}
      if(document.body.classList.contains('ov-open')) return; // 总览态不翻页
      if(e.key==='ArrowRight'){e.preventDefault();go(1);}
      else if(e.key==='ArrowLeft'){e.preventDefault();go(-1);}
      else if(e.key==='Home'){e.preventDefault();jump(0);}
      else if(e.key==='End'){e.preventDefault();jump(slides.length-1);}
    });
  }
  if(document.readyState!=='loading') build();
  else document.addEventListener('DOMContentLoaded',build);
})();
