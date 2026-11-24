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
