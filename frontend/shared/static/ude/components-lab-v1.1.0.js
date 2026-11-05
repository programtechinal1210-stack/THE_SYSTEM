function ude04InitLab(){
  var root=document.querySelector('[data-ude-root]');
  if(!root||!window.UDEComponents||!window.UDEThemeResolver)return;
  var profile=JSON.parse(document.getElementById('ude-demo-profile').textContent||'{}');
  function apply(theme){
    var result=UDEThemeResolver.resolve({settings:Object.assign({},profile,{theme:theme,contrast:theme==='high-contrast'?'high':'normal'})},{matchMedia:window.matchMedia.bind(window)});
    UDEThemeResolver.apply(result,document,root);
  }
  document.querySelectorAll('[data-theme]').forEach(function(button){button.addEventListener('click',function(){apply(button.dataset.theme);});});
  document.getElementById('density').addEventListener('change',function(event){root.setAttribute('data-ude-density',event.target.value);});
  document.getElementById('motion').addEventListener('click',function(){root.setAttribute('data-ude-motion',root.getAttribute('data-ude-motion')==='reduced'?'normal':'reduced');});
  UDEComponents.init(root);
  document.getElementById('toast-button').addEventListener('click',function(){var toast=document.createElement('div');toast.className='ude-toast';toast.textContent='تم إظهار الإشعار';document.getElementById('toast-region').appendChild(toast);setTimeout(function(){toast.remove();},2500);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ude04InitLab);else ude04InitLab();
setTimeout(ude04InitLab,0);
window.addEventListener('load',ude04InitLab);
