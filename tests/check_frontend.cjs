const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/i18n.js','utf8');
vm.runInNewContext(source+`;for(const [k,v] of Object.entries(REVIEW_WORDS)){if(v.split('|').length!==REVIEW_KEYS.length)throw Error('Review translations: '+k);}`,{});
vm.runInNewContext(source+`;for(const [k,v] of Object.entries(WORDS)){if(v.split('|').length!==KEYS.length)throw Error(k+': '+v.split('|').length+' / '+KEYS.length);if(Object.values(I18N[k]).some(x=>!x))throw Error('Missing '+k);}`,{});
const html=fs.readFileSync('frontend/index.html','utf8'),js=fs.readFileSync('frontend/app.js','utf8');
for(const [,id] of js.matchAll(/\$\('([^']+)'\)/g))assert(html.includes('id="'+id+'"'),'Missing element '+id);
console.log('Nine language dictionaries and referenced controls validated.');
