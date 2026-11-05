function ude04InitLab(){
  var root=document.querySelector('[data-ude-root]');
  if(!root||!window.UDEThemeResolver)return;
  function apply(theme){
    var mode=theme==='ude-high-contrast'?'high-contrast':theme==='ude-dark-default'?'dark':'light';
    var result=UDEThemeResolver.resolve({settings:{theme:mode,contrast:mode==='high-contrast'?'high':'normal'}},{matchMedia:window.matchMedia.bind(window)});
    UDEThemeResolver.apply(result,document,root);
  }
  apply(root.getAttribute('data-ude-theme'));
  root.addEventListener('ude:theme-change',function(event){apply(event.detail.profile);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ude04InitLab);else ude04InitLab();
setTimeout(ude04InitLab,0);
window.addEventListener('load',ude04InitLab);
