import {DAY,dateMs,day,money,groupProducts,selectProducts,windowHistory,checkDiscount,monthComparison} from './core.mjs';
const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
const fmtDate=stamp=>new Date(stamp).toLocaleDateString('lt-LT');
let products=[],selected=null,mode='all',period=30;
function link(url,label){const a=node('a',label);try{const u=new URL(url);if(u.protocol==='https:'){a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}}catch{}return a;}
function badge(text,cls=''){return node('span',text,'badge '+cls);}
function renderList(){
  const filtered=selectProducts(products,{query:$('search').value,store:$('store-filter').value,mode,sort:$('sort').value});
  $('count').textContent=`Rasta prekių: ${filtered.length}`;
  $('radar-note').textContent=mode==='archives'?'Prekės, kurioms yra oficialaus leidinio kainų, galiojusių prieš mėnesį. Leidinio ir internetinės kainos sąlygos gali skirtis.':mode==='radar'?'Parduotuvės skelbiamos akcijos be kortelės. Kol nėra ankstesnių stebėjimų, nuolaida istorija nepatvirtinta.':mode==='drops'?'Tik prekės, kurių naujausia kaina mažesnė už ankstesnių 30 dienų stebėjimų minimumą. Trūkstamos dienos nevertinamos.':'Kainos be lojalumo kortelės: „Rimi“ internetu, „Aibė“ – vieši parduotuvių pasiūlymai. Skirtingų parduotuvių prekės automatiškai nesutapatinamos.';
  const container=$('products');container.replaceChildren();
  for(const p of filtered){
    const b=node('button',undefined,'product');b.type='button';b.setAttribute('aria-pressed',String(p.product_id===selected));
    const top=node('span',undefined,'topline');top.append(node('span',p.store+(p.channel==='online'?' · internetu':' · parduotuvių pasiūlymas')),node('span',fmtDate(p.observed_at)));
    const line=node('span',undefined,'price-line'),price=node('span',money(p.price),'price');
    if(p.monthArchives?.length)top.append(badge('Yra ankstesnis leidinys','gray'));
    if(p.advertised>0)price.append(node('del',money(p.regular_price)));
    line.append(price,p.expired?badge('Pasiūlymas pasibaigė','amber'):p.stale?badge('Kaina pasenusi','amber'):p.advertised>0?badge('Skelbiama −'+p.advertised.toFixed(0)+' %'):badge('Stebima kaina','gray'));
    b.append(top,node('strong',p.name),line);
    b.onclick=()=>{selected=p.product_id;renderList();renderDetail();if(matchMedia('(max-width:640px)').matches)$('detail').scrollIntoView({behavior:'smooth',block:'start'});};container.append(b);
  }
  if(!filtered.length)container.append(node('p',mode==='drops'?'Patvirtintam atpigimui dar nėra pakankamai ankstesnių stebėjimų arba pagal filtrus atpigusių prekių nerasta.':'Pagal pasirinktus filtrus prekių nerasta.','empty'));
  if(!filtered.some(p=>p.product_id===selected)){selected=filtered[0]?.product_id||null;renderDetail();for(const b of container.children)if(b.tagName==='BUTTON'){b.setAttribute('aria-pressed','true');break;}}
}
const SVG='http://www.w3.org/2000/svg';
function svgEl(tag,attrs={},text){const e=document.createElementNS(SVG,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
function chart(rows,days){
  const svg=svgEl('svg',{viewBox:'0 0 480 230',class:'chart',role:'img','aria-label':`Kainų grafikas: ${days} dienų, ${rows.length} stebėjimų. Išsami lentelė žemiau.`});
  svg.append(svgEl('title',{},`Tik užfiksuotos kainos per ${days} dienų`));
  if(!rows.length){svg.append(svgEl('text',{x:80,y:110},'Šiuo laikotarpiu stebėjimų nėra.'));return svg;}
  const end=dateMs(new Date().toISOString()),start=end-(days-1)*DAY;
  const values=rows.map(r=>Number(r.price)),min=Math.min(...values),max=Math.max(...values),pad=Math.max((max-min)*.2,.10),lo=Math.max(0,min-pad),hi=max+pad;
  const x=r=>65+(dateMs(r.observed_at)-start)/(end-start)*390,y=r=>185-(Number(r.price)-lo)/(hi-lo)*155;
  for(let i=0;i<4;i++){const v=lo+(hi-lo)*i/3,yy=185-155*i/3;svg.append(svgEl('line',{x1:60,x2:460,y1:yy,y2:yy,class:'grid'}),svgEl('text',{x:6,y:yy+4},money(v)));}
  svg.append(svgEl('text',{x:62,y:215},fmtDate(new Date(start).toISOString())),svgEl('text',{x:455,y:215,'text-anchor':'end'},fmtDate(new Date(end).toISOString())));
  for(let i=0;i<rows.length;i++){const r=rows[i],prev=rows[i-1];if(prev&&dateMs(r.observed_at)-dateMs(prev.observed_at)===DAY)svg.append(svgEl('line',{x1:x(prev),x2:x(r),y1:y(prev),y2:y(r),class:'connector'}));const c=svgEl('circle',{cx:x(r),cy:y(r),r:5});c.append(svgEl('title',{},fmtDate(r.observed_at)+' · '+money(r.price)));svg.append(c);}
  return svg;
}
function renderDetail(){
  const box=$('detail');box.replaceChildren();const p=products.find(p=>p.product_id===selected);
  if(!p){box.append(node('p','Pasirink prekę, kad pamatytum kainų istoriją.'));return;}
  box.append(badge(p.store+' · be kortelės','gray'),node('h3',p.name),node('div',money(p.price),'detail-price'));
  if(p.advertised>0)box.append(node('p','Parduotuvės nurodyta įprasta kaina: '+money(p.regular_price),'muted'));
  if(p.unit_price)box.append(node('p',p.unit_price,'muted'));
  if(p.stale)box.append(node('p','Ši kaina senesnė nei 48 valandos. Prieš pirkdamas patikrink šaltinį.','notice error'));
  if(p.valid_to)box.append(node('p',`Pasiūlymas galioja: ${p.valid_from} – ${p.valid_to}.`,'muted'));
  if(p.expired)box.append(node('p','Pasiūlymo galiojimas pasibaigė. Rodoma istorinė kaina.','notice error'));
  if(p.identity_method==='exact_name_and_package')box.append(node('p','Prekė sekama pagal tikslų pavadinimą ir pakuotę, EAN kodas nepateiktas. Šaltinyje ieškok šio pavadinimo.','muted'));
  box.append(link(p.source,'Patikrinti kainą parduotuvėje'));
  const month=p.month;
  const monthBox=node('section',undefined,'month-comparison');
  monthBox.append(node('h4','Prieš mėnesį · '+month.target));
  if(month.historical){monthBox.append(node('div',money(month.historical.price),'detail-price'),node('p',`Tos pačios parduotuvės, kanalo ir kainos sąlygų stebėjimas. Pokytis: ${month.change>0?'+':''}${month.change.toFixed(1)} %.`,'muted'));}
  else monthBox.append(node('p','Tos pačios kainos sąlygų stebėjimo tą dieną neturime.','muted'));
  for(const offer of month.offers){const item=node('div',undefined,'archive-offer');item.append(badge('Oficiali leidinio kaina','gray'),node('p',money(offer.price)+(offer.conditions==='loyalty_card'?' · su kortele':' · sąlygos leidinyje'),'archive-price'),node('p',`Galiojo ${offer.valid_from} – ${offer.valid_to} · ${offer.page} psl.`,'muted'),node('p',offer.conditions_note,'muted'),link(offer.source,'Atidaryti ankstesnį leidinį'));monthBox.append(item);}
  if(month.offers.length)monthBox.append(node('p','Tai fizinių parduotuvių leidinio pasiūlymas. Jo nesuplakame su dabartine internetine kaina ir neskaičiuojame nuolaidos tarp skirtingų sąlygų.','muted'));
  box.append(monthBox);
  const periods=node('div',undefined,'periods');periods.setAttribute('role','group');periods.setAttribute('aria-label','Grafiko laikotarpis');
  for(const d of [30,90,365]){const b=node('button',d+' d.');b.setAttribute('aria-pressed',String(period===d));b.onclick=()=>{period=d;renderDetail();};periods.append(b);}
  const rows=windowHistory(p.history,period);box.append(periods,chart(rows,period));
  box.append(node('p',`${new Set(rows.map(r=>day(r.observed_at))).size} užfiksuota (-os) diena (-os) iš ${period}. Trūkstamų dienų kainos nežinomos.`,'muted'));
  const dl=node('dl');for(const [title,value] of [['Ankstesnių 30 d. minimumas',p.minimum===null?'Dar nėra stebėjimų':money(p.minimum)],['Ankstesnių dienų aprėptis',p.priorDays+' iš 30'],['Pirmas stebėjimas',fmtDate(p.history[0].observed_at)],['Naujausias stebėjimas',new Date(p.observed_at).toLocaleString('lt-LT')]]){const group=node('div');group.append(node('dt',title),node('dd',value));dl.append(group);}box.append(dl);
  const explanation=p.minimum===null?'Istorija dar per trumpa: negalime patvirtinti, ar tai tikras atpigimas.':p.drop>0?`Kaina ${p.drop.toFixed(1)} % mažesnė už ankstesnių 30 dienų stebėjimų minimumą.`:'Kaina nėra mažesnė už ankstesnių 30 dienų stebėjimų minimumą.';
  box.append(node('p',explanation+(p.priorDays<30?' Turime ne visų 30 dienų duomenis.':''),'notice'));
  const details=node('details'),table=node('table',undefined,'observations'),thead=node('thead'),head=node('tr');head.append(node('th','Data'),node('th','Kaina'));thead.append(head);table.append(thead);const tbody=node('tbody');for(const r of [...rows].reverse()){const tr=node('tr');tr.append(node('td',fmtDate(r.observed_at)),node('td',money(r.price)));tbody.append(tr);}table.append(tbody);details.append(node('summary','Stebėjimų lentelė ('+rows.length+')'),table);box.append(details);
}
async function load(){
  $('refresh').disabled=true;
  try{
    const responses=await Promise.all(['data/observations.json','data/status.json','data/archive_offers.json'].map(u=>fetch(u,{cache:'no-store'})));
    if(responses.some(r=>!r.ok))throw Error('Duomenų failas nepasiekiamas');
    const [rows,status,archives]=await Promise.all(responses.map(r=>r.json()));if(!Array.isArray(rows)||!Array.isArray(status.sources)||!Array.isArray(archives))throw Error('Netinkamas duomenų formatas');
    products=groupProducts(rows).map(p=>{const month=monthComparison(p,archives);return {...p,month,monthArchives:month.offers};});const previousStore=$('store-filter').value;$('store-filter').replaceChildren();const allOption=node('option','Visos palaikomos');allOption.value='';$('store-filter').append(allOption);for(const store of [...new Set(products.map(p=>p.store))].sort()){const option=node('option',store);option.value=store;$('store-filter').append(option);}$('store-filter').value=previousStore; $('products-count').textContent=products.length;$('offers-count').textContent=products.filter(p=>p.advertised>0&&!p.stale&&!p.expired).length;
    $('days-count').textContent=new Set(products.flatMap(p=>p.history.map(r=>day(r.observed_at)))).size;
    $('updated').textContent=new Date(status.updated_at).toLocaleString('lt-LT',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
    $('data-message').className='notice';$('data-message').textContent=products.length?`Bendra istorija prijungta · ${products.length} prekių · ${rows.length} kainų stebėjimų. Istorija kaupiama nuo ${fmtDate(rows.reduce((a,b)=>a.observed_at<b.observed_at?a:b).observed_at)}. Kainos renkamos kasdien. Prieš mėnesį tos pačios kainos sąlygomis: ${products.filter(p=>p.month.historical).length} prekių; ankstesnių leidinių šaltiniai: ${products.filter(p=>p.monthArchives.length).length} prekėms.`:'Kainų stebėjimų dar nėra. Šaltinių būsenos pateiktos žemiau.';
    if(Date.now()-Date.parse(status.updated_at)>48*3600000){$('data-message').className='notice error';$('data-message').textContent+=' Rinkimas vėluoja: duomenys senesni nei 48 val.';}
    $('sources').replaceChildren();for(const s of status.sources){const card=node('div',undefined,'source-card');card.append(node('strong',s.store),badge(s.status==='ok'?'Renkama':s.status==='partial'?'Dalis duomenų':s.status==='no_data'?'Pasiūlymų nerasta':s.status==='unavailable'?'Nepasiekiama':'Neprijungta',s.status==='ok'?'':'amber'));card.append(node('p',s.observations?`${s.observations} stebėjimų per rinkimą`:'Kainos į istoriją nepateko.'));if(s.errors?.length)card.append(node('p',s.errors.join('; ')));$('sources').append(card);}
    renderList();renderDetail();
  }catch(e){$('data-message').className='notice error';$('data-message').textContent='Bendros istorijos nepavyko atnaujinti. '+(products.length?'Palikti ankstesni šiame lange įkelti duomenys. ':'')+'Bandyk dar kartą. '+e.message;}
  finally{$('refresh').disabled=false;}
}
for(const id of ['search','store-filter','sort'])$(id).addEventListener(id==='search'?'input':'change',renderList);
for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>{mode=b.dataset.mode;for(const other of document.querySelectorAll('[data-mode]'))other.setAttribute('aria-pressed',String(other===b));renderList();renderDetail();};
$('refresh').onclick=load;
$('check-form').onsubmit=e=>{e.preventDefault();const r=checkDiscount($('old').value,$('current').value,$('minimum').value);$('result').textContent=r?`Skelbiama nuolaida: ${r.advertised.toFixed(1)} %. Pokytis pagal įvestą istoriją: ${r.observed.toFixed(1)} %. `+(r.saving>0?'Sutaupymas: '+money(r.saving):'Kaina nėra mažesnė už žinomą minimumą.'):'Įvesk tinkamas kainas.';};
let local=[];try{const stored=JSON.parse(localStorage.getItem('kt-prices')||'[]');if(Array.isArray(stored))local=stored.filter(r=>r&&typeof r.product==='string'&&typeof r.store==='string'&&typeof r.date==='string'&&Number.isFinite(Number(r.price)));else throw Error();}catch{$('local-status').textContent='Vietinių įrašų nepavyko perskaityti. Nauji įrašai galės būti saugomi, jei naršyklė tai leidžia.';}
const today=new Date().toLocaleDateString('sv-SE');$('date').value=today;$('date').max=today;
function renderLocal(){$('history').replaceChildren();for(const r of [...local].sort((a,b)=>b.date.localeCompare(a.date))){$('history').append(node('article',`${r.product} · ${r.store} · ${money(r.price)} · ${r.date} · Šaltinis: ${r.source}`));}if(!local.length)$('history').append(node('p','Asmeninių įrašų dar nėra.','muted'));}
$('form').onsubmit=e=>{e.preventDefault();const r={product:$('product').value.trim(),store:$('store').value.trim(),price:Number($('price').value),date:$('date').value,source:$('source').value.trim()};if(!r.product||!r.store||!r.source||!Number.isFinite(r.price)||r.price<=0||r.date>today)return;const next=[...local,r];try{localStorage.setItem('kt-prices',JSON.stringify(next));local=next;$('local-status').textContent='Kaina išsaugota šiame įrenginyje.';renderLocal();}catch{$('local-status').textContent='Naršyklė neleido išsaugoti. Įrašas neišsaugotas.';}};
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(local,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='kainos.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
renderLocal();load();
