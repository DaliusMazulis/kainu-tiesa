export const DAY = 86400000;
export const day = stamp => String(stamp).slice(0,10);
export const dateMs = stamp => Date.parse(day(stamp)+'T00:00:00Z');
export const money = value => Number(value).toLocaleString('lt-LT',{style:'currency',currency:'EUR'});
export const normalize = text => String(text).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
export function validRow(r) {
  return r && typeof r.product_id==='string' && typeof r.name==='string' && typeof r.store==='string' && r.currency==='EUR' && r.status==='observed' && r.conditions==='public_without_card' && Number.isFinite(Number(r.price)) && Number(r.price)>0 && Number.isFinite(Date.parse(r.observed_at)) && /^https:\/\/www\.rimi\.lt\/e-parduotuve\/lt\/produktai\//.test(r.source);
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
    return {...latest,history,minimum,priorDays:days,advertised,drop:minimum===null?null:(1-Number(latest.price)/minimum)*100,stale:+now-Date.parse(latest.observed_at)>48*3600000};
  });
}
export function selectProducts(products,{query='',store='',mode='all',sort='name'}={}) {
  const terms=normalize(query).split(/\s+/).filter(Boolean);
  const out=products.filter(p=>terms.every(t=>normalize(p.name+' '+p.store+' '+p.sku).includes(t)) && (!store||p.store===store) && (mode==='all'||mode==='radar'&&p.advertised>0&&!p.stale||mode==='drops'&&p.drop>0&&!p.stale));
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
