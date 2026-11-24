export const DAY = 86400000;
export const day = stamp => String(stamp).slice(0,10);
export const dateMs = stamp => Date.parse(day(stamp)+'T00:00:00Z');
export const money = value => Number(value).toLocaleString('lt-LT',{style:'currency',currency:'EUR'});
export const ltDay = date => date.toLocaleDateString('sv-SE',{timeZone:'Europe/Vilnius'});
export const normalize = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const isoDay = value => typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value+'T00:00:00Z')) && new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
export function validRow(r) {
  const sourceOK = r && ((r.store==='Rimi' && /^rimi:/.test(r.product_id) && /^https:\/\/www\.rimi\.lt\/e-parduotuve\/lt\/produktai\//.test(r.source) && r.channel==='online') || (r.store==='Aibė' && /^aibe:/.test(r.product_id) && r.source==='https://aibe.lt/akcijos/' && r.channel==='in_store_offer' && isoDay(r.valid_from) && isoDay(r.valid_to) && r.valid_from<=r.valid_to));
  return r && typeof r.product_id==='string' && typeof r.name==='string' && typeof r.store==='string' && r.currency==='EUR' && r.status==='observed' && r.conditions==='public_without_card' && Number.isFinite(Number(r.price)) && Number(r.price)>0 && Number.isFinite(Date.parse(r.observed_at)) && sourceOK;
}
export function groupProducts(rows, now = new Date()) {
  const groups = new Map();
  for (const r of rows.filter(r=>validRow(r) && Date.parse(r.observed_at)<=+now)) {
    const key=r.product_id+'|'+r.conditions;
    if(!groups.has(key)) groups.set(key,[]);
    groups.get(key).push(r);
  }
  return [...groups.values()].map(history=>{
    history.sort((a,b)=>a.observed_at.localeCompare(b.observed_at));
    const latest=history.at(-1), prior=history.filter(r=>dateMs(r.observed_at)<dateMs(latest.observed_at) && dateMs(r.observed_at)>=dateMs(latest.observed_at)-30*DAY);
    const minimum=prior.length?Math.min(...prior.map(r=>Number(r.price))):null;
    const days=new Set(prior.map(r=>day(r.observed_at))).size;
    const advertised=Number(latest.regular_price)>Number(latest.price)?(1-Number(latest.price)/Number(latest.regular_price))*100:0;
    const expired=Boolean(latest.valid_to && latest.valid_to<ltDay(now));
    return {...latest,history,minimum,priorDays:days,advertised,drop:minimum===null?null:(1-Number(latest.price)/minimum)*100,expired,stale:+now-Date.parse(latest.observed_at)>48*3600000};
  });
}
export function selectProducts(products,{query='',store='',mode='all',sort='name'}={}) {
  const terms=normalize(query).split(/\s+/).filter(Boolean);
  const out=products.filter(p=>terms.every(t=>normalize(p.name+' '+p.store+' '+p.sku).includes(t)) && (!store||p.store===store) && (mode==='all'||mode==='radar'&&p.advertised>0&&!p.stale&&!p.expired||mode==='drops'&&p.drop>0&&!p.stale&&!p.expired||mode==='archives'&&p.monthArchives?.length>0||mode==='compared'&&Boolean(p.leafletComparison)));
  return out.sort((a,b)=>sort==='price'?Number(a.price)-Number(b.price):sort==='discount'?b.advertised-a.advertised:a.name.localeCompare(b.name,'lt'));
}
export function windowHistory(history, days, now = new Date()) {
  const end=dateMs(now.toISOString());
  return history.filter(r=>dateMs(r.observed_at)>=end-(days-1)*DAY && Date.parse(r.observed_at)<=+now).sort((a,b)=>a.observed_at.localeCompare(b.observed_at));
}
export function checkDiscount(old,current,minimum) {
  if([old,current,minimum].some(v=>v===''||v===null||!Number.isFinite(Number(v)))||Number(old)<=0||Number(minimum)<=0||Number(current)<0) return null;
  return {advertised:(1-Number(current)/Number(old))*100,observed:(1-Number(current)/Number(minimum))*100,saving:Number(minimum)-Number(current)};
}

export function previousMonthDay(now=new Date()) {
  const [year,month,date]=ltDay(now).split('-').map(Number);
  const first=new Date(Date.UTC(year,month-2,1));
  const last=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
  return new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth(),Math.min(date,last))).toISOString().slice(0,10);
}
export function monthComparison(product,archives=[],now=new Date()) {
  const target=previousMonthDay(now);
  const observations=(product.history||[]).filter(r=>validRow(r) && r.product_id===product.product_id && r.store===product.store && r.channel===product.channel && r.conditions===product.conditions && ltDay(new Date(r.observed_at))===target);
  const historical=observations.sort((a,b)=>a.observed_at.localeCompare(b.observed_at))[0]||null;
  const offers=archives.filter(r=>r && r.product_id===product.product_id && r.store===product.store && r.record_type==='published_offer' && r.currency==='EUR' && Number.isFinite(Number(r.price)) && Number(r.price)>0 && isoDay(r.valid_from) && isoDay(r.valid_to) && r.valid_from<=target && target<=r.valid_to && officialOffer(r) && r.channel==='in_store_leaflet');
  return {target,historical,offers,change:historical?(Number(product.price)/Number(historical.price)-1)*100:null};
}

export function officialOffer(r) {
  if(!r || r.store!=='Rimi' || r.record_type!=='published_offer' || r.verification!=='source_text_and_visual' || r.channel!=='in_store_leaflet' || !/^rimi:\d+$/.test(r.product_id) || r.currency!=='EUR' || !/^\d+\.\d{2}$/.test(String(r.price)) || Number(r.price)<=0 || !isoDay(r.valid_from) || !isoDay(r.valid_to) || r.valid_from>r.valid_to)return false;
  try{const u=new URL(r.source);return u.protocol==='https:' && u.hostname==='leidiniai.rimi.lt' && !u.username && !u.password && /^\/2026\/weekly\/rimi-savaitinis-leidinys-nr-\d+\/$/.test(u.pathname) && (!u.search || /^\?page=\d+$/.test(u.search));}catch{return false;}
}
export function publishedMonthComparisons(records,now=new Date()) {
  const target=previousMonthDay(now),today=ltDay(now);
  const approved=records.filter(r=>officialOffer(r) && r.source_check!=='changed_requires_review' && ['loyalty_card','public_without_card'].includes(r.conditions) && r.store_scope==='rimi_hyper_super_excluding_express' && r.quantity===1 && typeof r.package==='string' && r.package.length>0);
  const basis=r=>[r.product_id,r.store,r.channel,r.conditions,r.store_scope,r.quantity,r.package].join('|');
  const groups=new Map();for(const r of approved){const key=basis(r);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  const out=[];
  for(const group of groups.values()){
    const current=group.filter(r=>r.valid_from<=today && today<=r.valid_to);
    const previous=group.filter(r=>r.valid_from<=target && target<=r.valid_to);
    if(!current.length || !previous.length)continue;
    // Conflicting prices for the same place, period and conditions require review.
    if(new Set(current.map(r=>r.price)).size!==1 || new Set(previous.map(r=>r.price)).size!==1)continue;
    const latest=list=>[...list].sort((a,b)=>b.valid_from.localeCompare(a.valid_from)||b.retrieved_at.localeCompare(a.retrieved_at))[0];
    const a=latest(previous),b=latest(current),before=Math.round(Number(a.price)*100),after=Math.round(Number(b.price)*100);
    out.push({product_id:b.product_id,name:b.name,store:b.store,conditions:b.conditions,scope:b.store_scope,package:b.package,target,today,previous:a,current:b,differenceCents:after-before,percent:(after-before)/before*100});
  }
  return out.sort((a,b)=>a.name.localeCompare(b.name,'lt'));
}
