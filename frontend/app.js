'use strict';
const $=id=>document.getElementById(id), channel=new BroadcastChannel('image2gfont-'+location.port);
const detached=new URLSearchParams(location.search).get('panel');
let state={pages:[],accepted:{},crops:{},annotations:{},suggestions:{}},page=0,index=0,revision=-1,img=null,imagePage='',dirty=false;
let cropBox=null,cropStart=null,popups={},settingsDraft=null,draftCharacters={},draftNotes={};
const light={bg:'#ffffff',side:'#f5f5f3',stage:'#efefed',text:'#272b29',muted:'#777c79',border:'#e1e4e0',button:'#f4f5f2',buttonText:'#303b34',hover:'#e6ece6',accent:'#246b58'};
const dark={bg:'#202322',side:'#191c1b',stage:'#151817',text:'#e5e9e6',muted:'#a2aaa5',border:'#3c4540',button:'#303833',buttonText:'#e7eee9',hover:'#414d46',accent:'#387f68'};
const baseLanguage=navigator.language.startsWith('zh')?'zh-CN':navigator.language.split('-')[0];
const defaults={language:LANGUAGES[baseLanguage]?baseLanguage:'en',theme:'light',colors:{...light},font:'Segoe UI',buttonFont:'Segoe UI',glyphFont:'Microsoft YaHei',fontSize:14,borderWidth:1};
let settings=structuredClone(defaults);
const tr=k=>I18N[settings.language]?.[k]||I18N.en[k]||k;
function localize(){document.documentElement.lang=settings.language;document.querySelectorAll('[data-t]').forEach(e=>e.textContent=tr(e.dataset.t));document.querySelectorAll('[data-placeholder]').forEach(e=>e.placeholder=tr(e.dataset.placeholder));}
function safeSettings(value){
 const s={...defaults,...value,colors:{...light,...value?.colors}};
 if(!LANGUAGES[s.language])s.language='en';if(!['light','dark','custom'].includes(s.theme))s.theme='light';
 for(const key of Object.keys(light))if(!/^#[0-9a-f]{6}$/i.test(s.colors[key]))s.colors[key]=light[key];
 for(const key of ['font','buttonFont','glyphFont'])s[key]=String(s[key]).replace(/[;{}"\\]/g,'').slice(0,100)||defaults[key];
 s.fontSize=Math.min(20,Math.max(12,Number(s.fontSize)||14));s.borderWidth=Math.min(3,Math.max(0,Number(s.borderWidth)||0));return s;
}
function applyTheme(s){const root=document.documentElement;for(const [k,v] of Object.entries(s.colors))root.style.setProperty('--'+k,v);for(const k of ['font','buttonFont','glyphFont'])root.style.setProperty('--'+k,JSON.stringify(s[k]));root.style.setProperty('--size',s.fontSize+'px');root.style.setProperty('--line',s.borderWidth+'px');}
function status(text){$('status').textContent=text;}
async function request(d){const response=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-Workspace-Token':window.API_TOKEN},body:JSON.stringify(d)});const data=await response.json();if(!response.ok)throw Error(data.error);return data;}
async function action(d){try{const result=await request(d);if(['crop','accept','note','unaccept'].includes(d.op))dirty=true;if(['save','restore','load','import'].includes(d.op))dirty=false;update(result);channel.postMessage({type:'refresh'});if(result.output)status(result.output);return result;}catch(e){status(tr('error')+': '+e.message);return null;}}
function key(){return page+':'+index;}
function isDeleted(i=index,p=page){return (state.deleted||[]).includes(p+':'+i);}
function candidate(){if(isDeleted())return null;return state.pages[page]?.characters[index];}
function pendingKeys(){return Object.keys(state.review_flags||{}).filter(k=>!state.accepted[k]&&!(state.deleted||[]).includes(k));}
function boxFor(i=index){if(isDeleted(i))return null;const c=state.pages[page]?.characters[i];if(!c)return null;return state.accepted[page+':'+i]?.box||state.crops[page+':'+i]||[Math.floor(Math.min(...c.box.map(p=>p[0]))),Math.floor(Math.min(...c.box.map(p=>p[1]))),Math.ceil(Math.max(...c.box.map(p=>p[0]))),Math.ceil(Math.max(...c.box.map(p=>p[1])))];}
function select(p,i,broadcast=true){page=p;index=i;$('pages').value=String(p);render();if(broadcast)channel.postMessage({type:'select',page,index});}
function render(){
 if(isDeleted())index=(state.pages[page]?.characters||[]).findIndex((_,i)=>!isDeleted(i));
 const c=candidate(),items=state.pages[page]?.characters||[];
 $('empty').hidden=!!state.pages.length;$('imageCanvas').style.display=state.pages.length?'block':'none';
 $('count').textContent=Object.keys(state.accepted).length+' / '+(state.pages.reduce((n,p)=>n+p.characters.length,0)-(state.deleted||[]).length);
 $('glyphs').replaceChildren();const search=$('search').value;
 const pending=pendingKeys();$('pendingCount').textContent=tr('pending')+' '+pending.length;
 items.forEach((c,i)=>{if(isDeleted(i))return;const k=page+':'+i,text=state.accepted[k]?.character||c.text;if(search&&!text.includes(search))return;if($('pendingOnly').checked&&!pending.includes(k))return;const b=document.createElement('button');b.className='glyph'+(i===index?' selected':'')+(state.accepted[k]?' confirmed':'')+(pending.includes(k)?' ambiguous':'');b.textContent=text;b.title=`${i+1} · ${text} · ${pending.includes(k)?tr('pending'):state.accepted[k]?tr('resolved'):tr('unreviewed')}`;b.onclick=()=>select(page,i);$('glyphs').append(b);});
 $('character').value=c?(draftCharacters[key()]??state.accepted[key()]?.character??c.text):'';$('note').value=draftNotes[key()]??state.annotations[key()]??'';
 const s=state.suggestions[key()];$('originalText').textContent=c?.text||'—';$('modelText').textContent=s?(s.text||tr('unknown')):tr('notRequested');
 $('suggestion').textContent=s?(!s.text||s.text==='?'?tr('uncertainHint'):s.text!==c?.text?tr('disagreementHint'):tr('agreementHint')):'';
 $('reviewState').textContent=state.accepted[key()]?tr('resolved'):pending.includes(key())?tr('pending'):tr('unreviewed');$('reviewState').className=pending.includes(key())?'pendingLabel':'';
 for(const id of ['deleteCandidate','edit','recognize','accept','saveNote','unaccept','flagReview'])$(id).disabled=!c||state.job?.status==='running';
 $('useSuggestion').disabled=!s?.text||s.text==='?'||state.job?.status==='running';$('nextPending').disabled=!pending.length;
 $('undoDelete').disabled=!(state.deleted||[]).length||state.job?.status==='running';
 const imageIdentity=page+':'+(state.pages[page]?.id||'')+':'+(state.dataset||'');
 if(state.pages.length&&imageIdentity!==imagePage){imagePage=imageIdentity;img=null;$('imageCanvas').getContext('2d').clearRect(0,0,$('imageCanvas').width,$('imageCanvas').height);const next=new Image();next.onload=()=>{if(imagePage===imageIdentity){img=next;draw();}};next.onerror=()=>status(tr('error'));next.src='/api/image/'+page+'?v='+encodeURIComponent(state.dataset||'');}
 else draw();
}
function draw(){if(!img)return;const canvas=$('imageCanvas');canvas.width=img.width;canvas.height=img.height;const g=canvas.getContext('2d');g.drawImage(img,0,0);const scale=img.width/Math.max(1,canvas.clientWidth);for(let i=0;i<(state.pages[page]?.characters.length||0);i++){const b=boxFor(i);if(!b)continue;g.strokeStyle=i===index?settings.colors.accent:'#929c9777';g.lineWidth=(i===index?2.5:1)*scale;g.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1]);}}
function update(data){const changed=data.revision!==revision;if(state.dataset!==data.dataset){draftCharacters={};draftNotes={};page=0;index=0;}state=data;dirty=!!state.dirty;revision=data.revision;if(changed){$('pages').replaceChildren(...state.pages.map((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=p.id;return o;}));page=Math.min(page,Math.max(0,state.pages.length-1));index=Math.min(index,Math.max(0,(state.pages[page]?.characters.length||1)-1));$('pages').value=String(page);render();if(state.job?.status==='running')status(tr('busy'));else if(state.job?.status==='error')status(tr('error')+': '+state.job.error);else if(state.output)status(state.output);else if(state.job?.status==='done')status(tr('ready'));}}
async function refresh(){try{const response=await fetch('/api/state');update(await response.json());}catch(e){status(tr('error')+': '+e.message);}}
$('pages').onchange=e=>select(Number(e.target.value),0);$('search').oninput=render;
$('pendingOnly').onchange=render;
$('nextPending').onclick=()=>{const keys=pendingKeys(),pos=keys.indexOf(key());if(keys.length){const [p,i]=keys[(pos+1)%keys.length].split(':').map(Number);select(p,i);}};
$('useSuggestion').onclick=()=>{const text=state.suggestions[key()]?.text;if(text){draftCharacters[key()]=text;$('character').value=text;status(tr('suggestionDraft'));}};
$('flagReview').onclick=async()=>{const k=key(),note=$('note').value;if(await action({op:'flag',page,index,note})){delete draftNotes[k];render();status(tr('flagged'));}};
$('character').oninput=()=>draftCharacters[key()]=$('character').value;
$('note').oninput=()=>draftNotes[key()]=$('note').value;
$('imageCanvas').onclick=e=>{if(!img)return;const r=e.target.getBoundingClientRect(),x=(e.clientX-r.left)*img.width/r.width,y=(e.clientY-r.top)*img.height/r.height;let hits=[];state.pages[page].characters.forEach((_,i)=>{const b=boxFor(i);if(!b)return;if(x>=b[0]&&x<=b[2]&&y>=b[1]&&y<=b[3])hits.push({i,area:(b[2]-b[0])*(b[3]-b[1])});});hits.sort((a,b)=>a.area-b.area);if(hits.length)select(page,hits[0].i);};
$('accept').onclick=async()=>{const k=key();if(await action({op:'accept',page,index,text:$('character').value,box:boxFor(),note:$('note').value})){delete draftCharacters[k];delete draftNotes[k];render();}};
$('saveNote').onclick=async()=>{const k=key();if(await action({op:'note',page,index,note:$('note').value})){delete draftNotes[k];render();}};
$('unaccept').onclick=()=>action({op:'unaccept',page,index});$('recognize').onclick=()=>action({op:'recognize',page,index,box:boxFor()});
$('deleteCandidate').onclick=()=>action({op:'delete',page,index});
$('undoDelete').onclick=async()=>{const k=(state.deleted||[]).at(-1);if(k&&await action({op:'undo_delete'})){const [p,i]=k.split(':').map(Number);select(p,i);}};
$('save').onclick=async()=>{if(await action({op:'save'}))status(state.output||tr('saved'));};
for(const [id,op] of [['open','load'],['restore','restore']])$(id).onclick=()=>{if(dirty&&!confirm(tr('unsaved')))return;const path=prompt(tr('path'));if(path)action({op,path});};
for(const id of ['export','generate'])$(id).onclick=()=>{const name=prompt(tr('name'),'Image2GFont');if(name)action({op:'export',name,generate:id==='generate'});};
let importingImages=false,dragDepth=0;
async function importImages(selected){
 const chosen=Array.from(selected||[]);if(!chosen.length)return;
 if(importingImages||state.job?.status==='running'){status(tr('busy'));return;}
 const invalid=chosen.filter(f=>!(/\.(png|jpe?g|webp|bmp|tiff?)$/i.test(f.name)));
 if(invalid.length){status(tr('unsupportedImages')+': '+invalid.map(f=>f.name).join(', '));return;}
 if(chosen.reduce((sum,f)=>sum+4*Math.ceil(f.size/3)+f.name.length*6+100,100)>99*1024*1024){status(tr('imagesTooLarge'));return;}
 if(dirty&&!confirm(tr('unsaved')))return;
 importingImages=true;status(tr('busy'));
 try{
  const files=[];
  for(const f of chosen){const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(reader.error||new Error(f.name));reader.readAsDataURL(f);});files.push({name:f.name,data});}
  await action({op:'import',files});
 }catch(e){status(tr('error')+': '+e.message);}
 finally{importingImages=false;$('files').value='';}
}
$('start').onclick=$('import').onclick=()=>{if(importingImages||state.job?.status==='running'){status(tr('busy'));return;}$('files').click();};
$('files').onchange=e=>importImages(e.target.files);
function isFileDrag(e){return Array.from(e.dataTransfer?.types||[]).includes('Files');}
function clearImageDrop(){dragDepth=0;$('imagePanel').classList.remove('file-drop');}
// Suppress file navigation even when files land outside the import area.
window.addEventListener('dragover',e=>{if(isFileDrag(e)){e.preventDefault();e.dataTransfer.dropEffect='none';}});
window.addEventListener('drop',e=>{if(isFileDrag(e))e.preventDefault();clearImageDrop();});
$('imagePanel').addEventListener('dragenter',e=>{if(!isFileDrag(e))return;e.preventDefault();dragDepth++;$('imagePanel').classList.add('file-drop');});
$('imagePanel').addEventListener('dragleave',e=>{if(!isFileDrag(e))return;if(--dragDepth<=0)clearImageDrop();});
$('imagePanel').addEventListener('dragover',e=>{if(!isFileDrag(e))return;e.preventDefault();e.stopPropagation();e.dataTransfer.dropEffect=importingImages||state.job?.status==='running'?'none':'copy';});
$('imagePanel').addEventListener('drop',e=>{if(!isFileDrag(e))return;e.preventDefault();e.stopPropagation();clearImageDrop();importImages(e.dataTransfer.files);});
window.addEventListener('dragend',clearImageDrop);
// Editing uses original pixel coordinates; only saving changes review state.
function cropDraw(){if(!img||!cropBox)return;const c=$('cropCanvas');c.width=img.width;c.height=img.height;const g=c.getContext('2d');g.drawImage(img,0,0);g.fillStyle='#0004';g.fillRect(0,0,img.width,img.height);const [x0,y0,x1,y1]=cropBox;g.drawImage(img,x0,y0,x1-x0,y1-y0,x0,y0,x1-x0,y1-y0);g.strokeStyle=settings.colors.accent;g.lineWidth=2*img.width/Math.max(1,c.clientWidth);g.strokeRect(x0,y0,x1-x0,y1-y0);['x0','y0','x1','y1'].forEach((id,i)=>$(id).value=cropBox[i]);}
$('edit').onclick=()=>{if(!candidate()||!img)return;cropBox=[...boxFor()];$('cropDialog').showModal();cropDraw();};$('cropClose').onclick=()=>$('cropDialog').close();$('cropReset').onclick=()=>{cropBox=[...boxFor()];cropDraw();};
function cropPoint(e){const r=$('cropCanvas').getBoundingClientRect();return [Math.max(0,Math.min(img.width,Math.round((e.clientX-r.left)/r.width*img.width))),Math.max(0,Math.min(img.height,Math.round((e.clientY-r.top)/r.height*img.height)))];}
$('cropCanvas').onpointerdown=e=>{cropStart=cropPoint(e);e.target.setPointerCapture(e.pointerId);};$('cropCanvas').onpointermove=e=>{if(!cropStart)return;const p=cropPoint(e);cropBox=[Math.min(p[0],cropStart[0]),Math.min(p[1],cropStart[1]),Math.max(p[0],cropStart[0]),Math.max(p[1],cropStart[1])];cropDraw();};$('cropCanvas').onpointerup=()=>cropStart=null;
for(const id of ['x0','y0','x1','y1'])$(id).onchange=()=>{cropBox=['x0','y0','x1','y1'].map(id=>Number($(id).value));cropDraw();};
$('cropSave').onclick=async()=>{if(await action({op:'crop',page,index,box:cropBox}))$('cropDialog').close();};
// Pane width has both a minimum and a maximum, including keyboard operation.
function resizeText(width){const total=$('workspace').clientWidth;$('textPanel').style.width=Math.max(240,Math.min(total*.5,width))+'px';draw();}
$('splitter').onpointerdown=e=>{e.target.setPointerCapture(e.pointerId);e.target.onpointermove=ev=>resizeText($('workspace').getBoundingClientRect().right-ev.clientX-20);e.target.onpointerup=()=>e.target.onpointermove=null;};$('splitter').onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();resizeText($('textPanel').clientWidth+(e.key==='ArrowLeft'?20:-20));}};
async function detach(panel){if(window.pywebview?.api){try{if(detached){await window.pywebview.api.dock(detached);return;}await window.pywebview.api.detach(panel);document.body.dataset['hide'+panel[0].toUpperCase()+panel.slice(1)]='true';draw();}catch(e){status(e.message);}return;}if(detached){channel.postMessage({type:'dock',panel:detached});window.close();return;}const w=window.open('/?panel='+panel,'Image2GFont-'+panel,'popup,width=850,height=780');if(!w){status(tr('blocked'));return;}popups[panel]=w;document.body.dataset['hide'+panel[0].toUpperCase()+panel.slice(1)]='true';setTimeout(()=>channel.postMessage({type:'select',page,index}),700);draw();}
for(const panel of ['image','text']){const id=panel[0].toUpperCase()+panel.slice(1);$('detach'+id).onclick=()=>detach(panel);let start=null;$(panel+'Drag').onpointerdown=e=>{if(e.target.closest('button'))return;start=[e.clientX,e.clientY];e.currentTarget.setPointerCapture(e.pointerId);};$(panel+'Drag').onpointerup=e=>{if(!start)return;const r=$(panel+'Panel').getBoundingClientRect(),distance=Math.hypot(e.clientX-start[0],e.clientY-start[1]);start=null;if(distance>50&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))detach(panel);};}
function dock(panel){if(window.pywebview?.api)window.pywebview.api.dock(panel).catch(e=>status(e.message));document.body.dataset['hide'+panel[0].toUpperCase()+panel.slice(1)]='false';if(popups[panel]&&!popups[panel].closed)popups[panel].close();delete popups[panel];draw();}
$('redock').onclick=()=>{dock('image');dock('text');};
if(detached&&['image','text'].includes(detached)){document.body.classList.add('detached');document.body.dataset.panel=detached;$('splash').remove();channel.postMessage({type:'selectionRequest'});}
channel.onmessage=e=>{const m=e.data;if(m.type==='select'){select(m.page,m.index,false);}if(m.type==='refresh')refresh();if(m.type==='dock'&&!detached)dock(m.panel);if(m.type==='selectionRequest'&&!detached)channel.postMessage({type:'select',page,index});if(m.type==='settings'){settings=safeSettings(m.settings);applyTheme(settings);localize();render();}};
setInterval(()=>{if(!detached)for(const [p,w] of Object.entries(popups))if(w.closed)dock(p);},800);
// Theme previews are reversible; only Apply persists them.
function fillSettings(){const s=settingsDraft;$('language').value=s.language;$('theme').value=s.theme;for(const k of ['font','buttonFont','glyphFont','fontSize','borderWidth'])$(k).value=s[k];for(const k of Object.keys(light))$('color-'+k).value=s.colors[k];applyTheme(s);}
for(const [code,name] of Object.entries(LANGUAGES)){const o=document.createElement('option');o.value=code;o.textContent=name;$('language').append(o);}
for(const k of Object.keys(light)){const row=document.createElement('div');row.className='setting';const label=document.createElement('label');label.dataset.t=k;const input=document.createElement('input');input.type='color';input.id='color-'+k;input.oninput=()=>{settingsDraft.colors[k]=input.value;settingsDraft.theme='custom';$('theme').value='custom';applyTheme(settingsDraft);};row.append(label,input);$('colors').append(row);}
$('settings').onclick=()=>{settingsDraft=structuredClone(settings);fillSettings();$('settingsDialog').showModal();};
$('settingsClose').onclick=()=>$('settingsDialog').close();$('settingsDialog').onclose=()=>applyTheme(settings);
$('theme').onchange=e=>{settingsDraft.theme=e.target.value;if(e.target.value!=='custom')settingsDraft.colors={...(e.target.value==='dark'?dark:light)};fillSettings();};
for(const k of ['font','buttonFont','glyphFont','fontSize','borderWidth'])$(k).oninput=()=>{settingsDraft=safeSettings({...settingsDraft,[k]:$(k).value});applyTheme(settingsDraft);};
$('language').onchange=e=>settingsDraft.language=e.target.value;$('themeReset').onclick=()=>{settingsDraft=structuredClone(defaults);fillSettings();};
$('settingsApply').onclick=async()=>{const s=safeSettings(settingsDraft);if(await action({op:'settings',settings:s})){settings=s;localize();applyTheme(s);channel.postMessage({type:'settings',settings:s});$('settingsDialog').close();render();}};
$('themeExport').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(settingsDraft,null,2)],{type:'application/json'}));a.download='Image2GFont-theme.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};$('themeImport').onclick=()=>$('themeFile').click();$('themeFile').onchange=async e=>{try{settingsDraft=safeSettings(JSON.parse(await e.target.files[0].text()));fillSettings();}catch(err){status(tr('error')+': '+err.message);}e.target.value='';};
window.addEventListener('desktop-docked',e=>dock(e.detail));
window.onbeforeunload=e=>{if(window.pywebview?.api)return;if(detached){channel.postMessage({type:'dock',panel:detached});return;}if(dirty){e.preventDefault();e.returnValue='';}};
new ResizeObserver(draw).observe($('imageStage'));
(async()=>{try{settings=safeSettings(await (await fetch('/api/settings')).json());}catch{}applyTheme(settings);localize();await refresh();if(detached)channel.postMessage({type:'selectionRequest'});setInterval(refresh,1200);if($('splash'))setTimeout(()=>{$('splash').style.opacity='0';setTimeout(()=>$('splash')?.remove(),450);},900);})();
