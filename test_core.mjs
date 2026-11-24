import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {groupProducts,selectProducts,windowHistory,checkDiscount,DAY} from './core.mjs';
const actual=JSON.parse(readFileSync(new URL('./data/observations.json',import.meta.url)));
const now=new Date('2026-11-24T23:59:00Z'),base=actual[0];
const datasetNow=new Date(Math.max(...actual.map(r=>Date.parse(r.observed_at)))+1000);
// Scenario prices are isolated test inputs; they are never served as observations.
const row=(offset,price=base.price)=>({...base,price,observed_at:new Date(+now-offset*DAY).toISOString()});
test('actual shared dataset loads and has advertised offers',()=>{const p=groupProducts(actual,datasetNow);assert.equal(p.length,new Set(actual.map(r=>r.product_id)).size);assert.ok(p.length>0);const single=groupProducts([row(0)],now)[0];assert.equal(single.minimum,null);assert.equal(single.priorDays,0);});
test('30/90/365 calendar windows include boundary and exclude future',()=>{const rows=[row(0),row(29),row(30),row(89),row(90),row(364),row(365),row(-1)];assert.equal(windowHistory(rows,30,now).length,2);assert.equal(windowHistory(rows,90,now).length,4);assert.equal(windowHistory(rows,365,now).length,6);});
test('current day is excluded from prior minimum',()=>{const p=groupProducts([row(0,'1.00'),row(1,'2.00'),row(30,'1.50'),row(31,'0.50')],now)[0];assert.equal(p.minimum,1.5);assert.equal(p.priorDays,2);assert.ok(p.drop>33);});
test('unknown history never becomes a confirmed drop',()=>{const p=groupProducts([row(0)],now);assert.equal(selectProducts(p,{mode:'drops'}).length,0);});
test('conditions stay separate and invalid data is excluded',()=>{assert.equal(groupProducts([{...row(0),conditions:'card'},row(-1),{...row(0),price:'NaN'}, {...row(0),status:'requires_review'}],now).length,0);});
test('accent insensitive multiword and code search',()=>{const p=groupProducts(actual,datasetNow);const found=selectProducts(p,{query:'rokiskio pienas'});assert.ok(found.length>0);assert.ok(found.every(p=>p.name.includes('pienas')));assert.equal(selectProducts(p,{query:base.sku}).length,1);assert.equal(selectProducts(p,{query:'zzzznotfound'}).length,0);});
test('store filter and price sorting',()=>{const p=groupProducts(actual,datasetNow);assert.equal(selectProducts(p,{store:'Unknown'}).length,0);const sorted=selectProducts(p,{sort:'price'});assert.ok(sorted.every((p,i)=>i===0||Number(p.price)>=Number(sorted[i-1].price)));});
test('stale prices do not enter radar',()=>{const p=groupProducts([{...row(3),regular_price:'99.00'}],now);assert.equal(p[0].stale,true);assert.equal(selectProducts(p,{mode:'radar'}).length,0);});
test('discount calculator validates and distinguishes real minimum',()=>{assert.deepEqual(checkDiscount(10,8,8),{advertised:19.999999999999996,observed:0,saving:0});assert.equal(checkDiscount('',8,8),null);assert.equal(checkDiscount(0,8,8),null);assert.equal(checkDiscount(10,-1,8),null);assert.equal(checkDiscount('NaN',1,2),null);assert.equal(checkDiscount(10,0,8).saving,8);});
test('Aibė without-card prices are accepted with a separate store and channel',()=>{
 const a={...row(0,'2.09'),product_id:'aibe:test',store:'Aibė',channel:'in_store_offer',source:'https://aibe.lt/akcijos/',regular_price:null,valid_from:'2026-11-12',valid_to:'2026-11-24'};
 const before=groupProducts([a],new Date('2026-11-24T21:59:59Z'))[0];assert.equal(before,undefined); // Observation is still in the future.
 const active=groupProducts([{...a,observed_at:'2026-11-24T17:00:00Z'}],new Date('2026-11-24T21:59:59Z'))[0];assert.equal(active.expired,false);assert.equal(active.advertised,0);
 const expired=groupProducts([{...a,observed_at:'2026-11-24T17:00:00Z'}],new Date('2026-11-24T22:00:01Z'))[0];assert.equal(expired.expired,true);
});
test('expired offers never enter either radar',()=>{
 const a={...row(0),expired:true,advertised:20,drop:10,stale:false};assert.equal(selectProducts([a],{mode:'radar'}).length,0);assert.equal(selectProducts([a],{mode:'drops'}).length,0);assert.equal(selectProducts([a]).length,1);
});
test('source and store combinations cannot be mixed',()=>{
 assert.equal(groupProducts([{...row(0),store:'Aibė'}],now).length,0);
 assert.equal(groupProducts([{...row(0),source:'https://www.rimi.lt.evil.test/e-parduotuve/lt/produktai/'}],now).length,0);
});
test('previous calendar month clamps end dates and uses Lithuanian date',async()=>{
 const {previousMonthDay}=await import('./core.mjs');assert.equal(previousMonthDay(new Date('2026-11-24T12:00:00Z')),'2026-10-24');assert.equal(previousMonthDay(new Date('2026-03-31T12:00:00Z')),'2026-02-28');assert.equal(previousMonthDay(new Date('2024-03-31T12:00:00Z')),'2024-02-29');assert.equal(previousMonthDay(new Date('2026-12-31T22:01:00Z')),'2026-12-01');
});
test('monthly comparison uses exact day and matching conditions only',async()=>{
 const {monthComparison}=await import('./core.mjs');const reference=new Date('2026-11-24T18:00:00Z'),latest={...row(0,'2.79'),observed_at:'2026-11-24T17:00:00Z'},earlier={...latest,price:'1.99',observed_at:'2026-10-24T09:00:00Z'};
 const p={...latest,history:[earlier,latest]};const a=monthComparison(p,[],reference);assert.equal(a.historical.price,'1.99');assert.ok(a.change>40);
 for(const wrong of [{...earlier,observed_at:'2026-10-23T09:00:00Z'},{...earlier,conditions:'loyalty_card'},{...earlier,channel:'in_store_offer'}])assert.equal(monthComparison({...p,history:[wrong,latest]},[],reference).historical,null);
});
test('real archived leaflets remain separate from observed monthly price',async()=>{
 const {monthComparison}=await import('./core.mjs');const archives=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url)));const p={...actual.find(r=>r.product_id==='rimi:248955'),history:[]};const m=monthComparison(p,archives,now);assert.equal(m.historical,null);assert.equal(m.change,null);assert.equal(m.offers.length,1);assert.equal(m.offers[0].price,'1.19');assert.equal(m.offers[0].conditions,'loyalty_card');assert.equal(monthComparison(p,archives,new Date('2026-12-24T12:00:00Z')).offers[0].price,'1.29');assert.equal(monthComparison(p,archives,new Date('2027-01-24T12:00:00Z')).offers.length,0);
});
test('same-conditions published comparison uses real source prices and integer cents',async()=>{
 const {publishedMonthComparisons}=await import('./core.mjs');const records=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url)));const rows=publishedMonthComparisons(records,new Date('2026-11-24T18:00:00Z'));
 assert.equal(rows.length,1);assert.equal(rows[0].product_id,'rimi:248955');assert.equal(rows[0].previous.price,'1.19');assert.equal(rows[0].current.price,'1.29');assert.equal(rows[0].differenceCents,10);assert.equal(rows[0].percent.toFixed(1),'8.4');assert.equal(rows[0].target,'2026-10-24');
});
test('conditions, package, quantity, store scope and channels must match',async()=>{
 const {publishedMonthComparisons}=await import('./core.mjs');const records=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url))).filter(r=>r.sku==='248955');const current=records.find(r=>r.valid_from==='2026-11-24'),past=records.find(r=>r.valid_from==='2026-10-20');
 for(const patch of [{conditions:'public_without_card'},{package:'180 g'},{quantity:2},{store_scope:'express'},{channel:'online'},{store:'Aibė'},{product_id:'rimi:other'}])assert.equal(publishedMonthComparisons([past,{...current,...patch}],new Date('2026-11-24T18:00:00Z')).length,0);
});
test('expired or upcoming current leaflet does not become a present-day price',async()=>{
 const {publishedMonthComparisons}=await import('./core.mjs');const records=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url)));assert.equal(publishedMonthComparisons(records,new Date('2026-12-01T12:00:00Z')).length,0);assert.equal(publishedMonthComparisons(records,new Date('2026-11-23T12:00:00Z')).length,0);
});
test('conflicting or changed prices require review instead of choosing a convenient price',async()=>{
 const {publishedMonthComparisons}=await import('./core.mjs');const records=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url)));const current=records.find(r=>r.valid_from==='2026-11-24');assert.equal(publishedMonthComparisons([...records,{...current,price:'9.99'}],new Date('2026-11-24T18:00:00Z')).length,0);assert.equal(publishedMonthComparisons(records.map(r=>r===current?{...r,source_check:'changed_requires_review'}:r),new Date('2026-11-24T18:00:00Z')).length,0);
});
test('network failure preserves a previously reviewed published offer',async()=>{
 const {publishedMonthComparisons}=await import('./core.mjs');const records=JSON.parse(readFileSync(new URL('./data/archive_offers.json',import.meta.url))).map(r=>({...r,source_check:'unavailable'}));assert.equal(publishedMonthComparisons(records,new Date('2026-11-24T18:00:00Z')).length,1);
});
test('comparison filter never includes products that only have an old leaflet',()=>{
 const good={...base,leafletComparison:{current:{price:'1.29'}}},missing={...base,product_id:'rimi:missing',monthArchives:[{}]};assert.equal(selectProducts([good,missing],{mode:'compared'}).length,1);
});
