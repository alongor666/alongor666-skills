/* deck.js —— 屏幕横向翻页：一屏一页，← → / 点击左右 / 滚轮 翻页。
 * 仅屏幕生效；打印时整段不参与（@media print 已把 .slide/.page 复位）。
 * 与内容无关，配合 page-deck.css 使用。放在页尾：<script src="deck.js"></script> */
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
      SC.scrollTo({left:target(i),behavior:'smooth'});}
    function go(d){jump(cur()+d);}
    window.addEventListener('keydown',function(e){
      if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '){e.preventDefault();go(1);}
      else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();go(-1);}
      else if(e.key==='Home'){e.preventDefault();jump(0);}
      else if(e.key==='End'){e.preventDefault();jump(slides.length-1);}
    });
    document.body.addEventListener('wheel',function(e){
      if(Math.abs(e.deltaY)>Math.abs(e.deltaX)){SC.scrollLeft+=e.deltaY;}
    },{passive:true});
    var prev=document.createElement('div'); prev.className='deck-nav prev'; prev.innerHTML='<span>‹</span>';
    var next=document.createElement('div'); next.className='deck-nav next'; next.innerHTML='<span>›</span>';
    prev.addEventListener('click',function(){go(-1);});
    next.addEventListener('click',function(){go(1);});
    document.body.appendChild(prev); document.body.appendChild(next);
    var h=document.createElement('div'); h.className='deck-hint';
    h.textContent='← → / 点击左右 翻页 ·  滚轮横向 ·  Cmd/Ctrl+P 导出 PDF';
    document.body.appendChild(h);
    setTimeout(function(){h.style.transition='opacity .8s';h.style.opacity='0.35';},4000);
  }
  if(document.readyState!=='loading') build();
  else document.addEventListener('DOMContentLoaded',build);
})();
