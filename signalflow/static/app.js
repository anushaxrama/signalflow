'use strict';
const $ = id => document.getElementById(id);
const palette = {wind:'#74966a',solar:'#d9bf77',hydro:'#8db3ad',gas:'#c3c5ad',nuclear:'#b4a9c8',biomass:'#a9bf8b',imports:'#98aca7',coal:'#9f9b87',other:'#dbddce'};
const fmt = (v,d=0) => v === null || v === undefined ? '—' : Number(v).toLocaleString('en-GB',{maximumFractionDigits:d});
const date = s => new Date(s).toLocaleString('en-GB',{timeZone:'UTC',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const time = s => new Date(s).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false});
function text(id,value){$(id).textContent=value;}
function el(tag,cls,value){const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)node.textContent=value;return node;}
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('icon');svg.setAttribute('aria-hidden','true');const use=document.createElementNS(svg.namespaceURI,'use');use.setAttribute('href','/static/icons.svg#'+name);svg.append(use);return svg;}
async function get(url){const response=await fetch(url,{signal:AbortSignal.timeout(15000)});if(!response.ok)throw new Error(`Request failed (${response.status})`);return response.json();}
const chartState={actual:true,forecast:true,index:null};
let currentSeries=[];
function drawSpark(id,values,color){
 const svg=$(id);svg.replaceChildren();const valid=values.filter(v=>v!==null);if(!valid.length)return;
 const low=Math.min(...valid),high=Math.max(...valid),span=Math.max(high-low,1);let path='',connected=false;
 values.forEach((value,i)=>{if(value===null){connected=false;return;}const x=i/Math.max(values.length-1,1)*240,y=26-(value-low)/span*22;path+=`${connected?'L':'M'}${x.toFixed(1)},${y.toFixed(1)} `;connected=true;});
 const line=document.createElementNS(svg.namespaceURI,'path');line.setAttribute('d',path);line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width','1.5');line.setAttribute('stroke-linejoin','round');line.setAttribute('vector-effect','non-scaling-stroke');svg.append(line);
}
function drawChart(rows){
 const svg=$('chart'),tooltip=$('chart-tooltip');svg.replaceChildren();tooltip.hidden=true;$('chart-empty').hidden=rows.length>0;if(!rows.length)return;
 const ns=svg.namespaceURI;
 const node=(tag,attrs,content,parent=svg)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(content!==undefined)n.textContent=content;parent.append(n);return n;};
 const width=Math.max(svg.clientWidth,260),height=svg.clientHeight||285;svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
 const left=31,right=width-9,top=16,bottom=height-34;
 const values=rows.flatMap(r=>[chartState.forecast?r.forecast:null,chartState.actual?r.actual:null]).filter(v=>v!==null);
 const maximum=Math.max(50,Math.ceil(Math.max(...values)*1.13/50)*50);
 const start=new Date(rows[0].start).getTime(),end=new Date(rows.at(-1).start).getTime();
 const x=r=>left+(new Date(r.start).getTime()-start)/Math.max(end-start,1)*(right-left);
 const y=v=>bottom-v/maximum*(bottom-top);
 const defs=node('defs',{});const gradient=node('linearGradient',{id:'curve-fill',x1:0,y1:0,x2:0,y2:1},undefined,defs);
 node('stop',{offset:'0%','stop-color':'#a8c594','stop-opacity':'.24'},undefined,gradient);node('stop',{offset:'100%','stop-color':'#c5d6b6','stop-opacity':'.01'},undefined,gradient);
 for(let i=0;i<=4;i++){const value=maximum*i/4;node('line',{x1:left,x2:right,y1:y(value),y2:y(value),stroke:'#e8eddf','stroke-width':1,'stroke-dasharray':i===0?'none':'2 5'});node('text',{x:left-9,y:y(value)+3,fill:'#8a987e','font-size':8,'font-family':'DM Sans,sans-serif','text-anchor':'end'},fmt(value));}
 const ticks=width<470?2:4;
 for(let i=0;i<=ticks;i++){const t=start+(end-start)*i/ticks,position=left+(right-left)*i/ticks;node('text',{x:position,y:height-8,fill:'#859578','font-size':7.5,'font-family':'DM Sans,sans-serif','text-anchor':i===0?'start':i===ticks?'end':'middle'},date(new Date(t).toISOString()));}
 function segments(key){const list=[];let part=[],previous=null;for(const row of rows){const t=new Date(row.start).getTime();if(row[key]===null||previous!==null&&t-previous!==1800000){if(part.length)list.push(part);part=[];}if(row[key]!==null)part.push(row);previous=row[key]===null?null:t;}if(part.length)list.push(part);return list;}
 if(chartState.actual){for(const part of segments('actual')){if(part.length<2)continue;const path=part.map((r,i)=>`${i?'L':'M'}${x(r).toFixed(2)},${y(r.actual).toFixed(2)}`).join(' ');node('path',{d:`${path} L${x(part.at(-1))},${bottom} L${x(part[0])},${bottom} Z`,fill:'url(#curve-fill)'});}}
 for(const [key,color,dash] of [['forecast','#b7bea8','4 5'],['actual','#487c58','none']]){if(!chartState[key])continue;for(const part of segments(key)){const path=part.map((r,i)=>`${i?'L':'M'}${x(r).toFixed(2)},${y(r[key]).toFixed(2)}`).join(' ');node('path',{d:path,fill:'none',stroke:color,'stroke-width':key==='actual'?2:1.4,'stroke-dasharray':dash,'stroke-linejoin':'round','stroke-linecap':'round'});if(part.length===1)node('circle',{cx:x(part[0]),cy:y(part[0][key]),r:2,fill:color});}}
 if(chartState.actual){for(const row of rows.filter(r=>r.anomaly&&r.actual!==null)){const marker=node('circle',{cx:x(row),cy:y(row.actual),r:3,fill:'#c3a065',stroke:'#fffefa','stroke-width':1.5});node('title',{},`Statistical deviation · ${date(row.start)} UTC`,marker);}}
 const inspect=node('g',{visibility:'hidden'});const guide=node('line',{y1:top,y2:bottom,stroke:'#9cae8d','stroke-width':1,'stroke-dasharray':'3 4'},undefined,inspect);const dot=node('circle',{r:4,fill:'#487c58',stroke:'#fffefa','stroke-width':2},undefined,inspect);
 function hide(){tooltip.hidden=true;inspect.setAttribute('visibility','hidden');}
 function show(index){
  chartState.index=index;const row=rows[index],position=x(row),value=chartState.actual&&row.actual!==null?row.actual:chartState.forecast?row.forecast:null;
  inspect.setAttribute('visibility','visible');guide.setAttribute('x1',position);guide.setAttribute('x2',position);dot.setAttribute('cx',position);dot.setAttribute('cy',y(value??0));dot.setAttribute('visibility',value===null?'hidden':'visible');dot.setAttribute('fill',row.actual!==null&&chartState.actual?'#487c58':'#9aa98a');
  tooltip.replaceChildren(el('div','tooltip-date',date(row.start)+' UTC'));
  for(const [label,v] of [['Observed',row.actual],['Forecast',row.forecast]]){const line=el('div','tooltip-row');line.append(el('span','',label),v===null?el('em','','Pending'):el('strong','',fmt(v,1)));tooltip.append(line);}
  tooltip.append(el('div','tooltip-unit','gCO₂ / kWh'));tooltip.hidden=false;tooltip.style.left=Math.max(0,Math.min(position+12,width-182))+'px';tooltip.style.top=Math.max(8,Math.min(value===null?top+30:y(value)-70,bottom-122))+'px';
 }
 svg.onpointermove=event=>{const rect=svg.getBoundingClientRect(),position=event.clientX-rect.left;const target=start+Math.max(0,Math.min(1,(position-left)/(right-left)))*(end-start);let best=0;for(let i=1;i<rows.length;i++)if(Math.abs(new Date(rows[i].start).getTime()-target)<Math.abs(new Date(rows[best].start).getTime()-target))best=i;show(best);};
 svg.onpointerleave=()=>{if(document.activeElement!==svg)hide();};
 svg.onkeydown=event=>{if(event.key==='Escape'){hide();return;}if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let index=chartState.index??rows.length-1;if(event.key==='ArrowLeft')index--;if(event.key==='ArrowRight')index++;if(event.key==='Home')index=0;if(event.key==='End')index=rows.length-1;show(Math.max(0,Math.min(rows.length-1,index)));};
 svg.onblur=hide;
 text('chart-period',`${date(rows[0].start)} — ${date(rows.at(-1).end)} UTC`);
}
window.addEventListener('resize',()=>drawChart(currentSeries));
function render(data){
 const m=data.metrics,latest=m.latest,observed=data.series.filter(r=>r.actual!==null),lastActual=observed.at(-1);
 text('connection',data.status==='healthy'?'Data current':data.status==='empty'?'Awaiting data':`Data ${data.status}`);$('connection').className=`status ${data.status}`;
 text('pipeline-status',{healthy:'HEALTHY',stale:'STALE',degraded:'CHECK DATA',empty:'AWAITING DATA'}[data.status]||data.status.toUpperCase());$('pipeline-status').dataset.status=data.status;
 $('notice').closest('.notice').classList.toggle('warning',data.status!=='healthy');
 text('notice',latest?`Latest source interval: ${date(latest.start)}–${time(latest.end)} UTC. ${data.status==='healthy'?'National grid data from NESO.':'Stored data may be delayed. Review data operations below.'}`:'Waiting for the first grid signals. Source and ingestion status will appear in data operations.');
 text('last-refresh',`View updated ${time(data.generated_at)} UTC · ${fmt(m.window_intervals)} stored intervals`);
 text('intensity',fmt(lastActual?.actual));text('intensity-note',lastActual?`${time(lastActual.start)} UTC${latest?.actual===null?' · newest actual pending':' · latest observed interval'}`:'Observed values will appear here');
 const previous=observed.at(-2),delta=previous&&lastActual?lastActual.actual-previous.actual:null;
 text('intensity-delta',delta===null?'OBSERVED VALUES, NOT FORECASTS':`${delta>0?'+':delta<0?'−':''}${fmt(Math.abs(delta))} VS. PRIOR OBSERVATION`);
 text('renewables',m.renewable_percentage===null?'—':fmt(m.renewable_percentage,1)+'%');text('mae',fmt(m.forecast_mae,1));text('coverage',m.actual_coverage===null?'—':fmt(m.actual_coverage,1)+'%');text('coverage-note',`${fmt(m.window_intervals)} stored intervals in this view`);
 drawSpark('spark-intensity',data.series.slice(-48).map(r=>r.actual),'#749466');drawSpark('spark-error',data.series.slice(-48).map(r=>r.actual===null?null:Math.abs(r.actual-r.forecast)),'#b2a2c0');
 $('coverage-bars').replaceChildren(...data.series.slice(-32).map(r=>{const bar=el('i',r.actual===null?'pending':'');return bar;}));
 $('renewable-bar').replaceChildren(...data.generation.filter(r=>r.percentage>0).map(r=>{const bar=el('i');bar.style.width=r.percentage+'%';bar.style.background=palette[r.fuel]||'#dbddce';return bar;}));
 currentSeries=data.series;drawChart(data.series);
 text('mix-total',m.renewable_percentage===null?'—':fmt(m.renewable_percentage,1)+'%');
 let position=0;const positive=data.generation.filter(r=>r.percentage>0),sum=positive.reduce((n,r)=>n+r.percentage,0);const stops=[];
 for(const row of positive){const start=position;position+=row.percentage/sum*100;const gap=Math.min(.5,(position-start)/5);stops.push(`#fffefa ${start}% ${start+gap}%`,`${palette[row.fuel]||'#dbddce'} ${start+gap}% ${position}%`);}
 $('donut').style.background=stops.length?`conic-gradient(${stops.join(',')})`:'#e3e9da';
 $('mix-list').replaceChildren(...data.generation.map(row=>{const item=el('div','mix-item'),label=el('span'),swatch=el('i'),track=el('span','fuel-track'),bar=el('i');swatch.style.background=bar.style.background=palette[row.fuel]||'#dbddce';bar.style.width=row.percentage+'%';track.append(bar);track.setAttribute('aria-hidden','true');label.append(swatch,document.createTextNode(row.fuel[0].toUpperCase()+row.fuel.slice(1)));item.append(label,track,el('strong','',fmt(row.percentage,1)+'%'));return item;}));
 text('mix-time',data.generation.length?`${date(data.generation[0].start)} UTC${m.generation_freshness_seconds>5400?' · stale':''}`:'Awaiting generation data');
 text('events',fmt(m.accepted_events));text('rejected',fmt(m.rejected_events));text('freshness',m.freshness_seconds===null?'—':m.freshness_seconds<3600?Math.floor(m.freshness_seconds/60)+'m':fmt(m.freshness_seconds/3600,1)+'h');
 $('runs').replaceChildren(...data.runs.map(run=>{const tr=el('tr'),started=el('td','',date(run.started_at)),status=el('td');started.title=run.error||`Run ${run.id}`;status.append(el('span',`run-status ${run.status}`,run.status));tr.append(started,el('td','',`${fmt(run.inserted)} / ${fmt(run.fetched)}`),status);return tr;}));
 if(!data.runs.length){const tr=el('tr'),td=el('td','','No reconciliation runs yet. Streamed records are tracked in accepted events.');td.colSpan=3;tr.append(td);$('runs').append(tr);}
 const alerts=data.anomalies.slice(-5).reverse();
 $('anomalies').replaceChildren(...alerts.map(a=>{const n=el('div','anomaly'),copy=el('div');copy.append(el('strong','',`${a.severity==='high'?'High deviation':'A change worth a look'} · ${fmt(a.actual)} gCO₂/kWh`),el('p','',`${date(a.start)} UTC · baseline ${a.baseline} · z = ${a.z_score}`));n.append(el('span','alert-marker'),copy);return n;}));
 if(!alerts.length){const n=el('div','no-alerts'),mark=el('div','no-alerts-icon');mark.append(icon(observed.length>12?'check':'activity'));n.append(mark,el('strong','',observed.length>12?'A steady signal.':'Building the picture.'),el('p','',observed.length>12?'No statistical anomalies found in this view. A little less noise, a little more confidence.':'More observed intervals are needed to establish a reliable comparison baseline.'));$('anomalies').append(n);}
 $('quarantine').replaceChildren();if(data.quarantine.length)$('quarantine').append(el('div','quarantine-title','ITEMS TO REVIEW'));
 $('quarantine').append(...data.quarantine.slice(0,3).map(q=>{const n=el('div','anomaly'),copy=el('div');copy.append(el('strong','','Quarantined '+q.kind),el('p','',q.error));n.append(el('span','alert-marker'),copy);return n;}));
}
let controllerVersion=0,firstView=true;
function updateRange(){const value=$('range').value;document.querySelectorAll('[data-hours]').forEach(button=>{const selected=button.dataset.hours===value;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});}
async function refresh(){
 const version=++controllerVersion;updateRange();$('refresh').classList.add('is-loading');$('refresh').setAttribute('aria-busy','true');
 try{const hours=$('range').value,data=await get('/api/overview?hours='+hours);if(version!==controllerVersion)return;render(data);$('export').href='/api/export.csv?hours='+hours;if(firstView){firstView=false;if(data.series.length)runScenario();}}
 catch(error){if(version!==controllerVersion)return;text('connection','Connection interrupted');$('connection').className='status failed';text('notice',`We couldn’t refresh the view. Any visible values are from the last successful update. ${error.message}.`);$('notice').closest('.notice').classList.add('warning');}
 finally{if(version===controllerVersion){$('refresh').classList.remove('is-loading');$('refresh').removeAttribute('aria-busy');}}
}
$('range').addEventListener('change',refresh);document.querySelectorAll('[data-hours]').forEach(button=>button.addEventListener('click',()=>{$('range').value=button.dataset.hours;refresh();}));$('refresh').addEventListener('click',refresh);
for(const key of ['actual','forecast']){$('toggle-'+key).addEventListener('click',()=>{const other=key==='actual'?'forecast':'actual';if(chartState[key]&&!chartState[other]){chartState[other]=true;$('toggle-'+other).setAttribute('aria-pressed','true');}chartState[key]=!chartState[key];$('toggle-'+key).setAttribute('aria-pressed',String(chartState[key]));drawChart(currentSeries);});}
let scenarioVersion=0;
function scenarioPlaceholder(message){const box=el('div','scenario-placeholder');box.append(icon('spark'),el('p','',message));$('scenario-result').replaceChildren(box);}
$('scenario-form').addEventListener('input',()=>{scenarioVersion++;scenarioPlaceholder('Inputs updated. Explore again to see the difference.');});
async function runScenario(){
 const version=++scenarioVersion,form=$('scenario-form'),button=form.querySelector('button');if(!form.reportValidity())return;button.disabled=true;text('compare-label','Comparing historical windows…');form.classList.add('is-loading');
 try{const params=new URLSearchParams({power_kw:$('power').value,duration_hours:$('duration').value,pue:$('pue').value}),result=await get('/api/scenario?'+params);if(version!==scenarioVersion)return;if(!result.available){scenarioPlaceholder(result.reason);return;}
 const values=el('div','scenario-values');for(const [value,label,cls] of [[result.best_kg,'Lowest · kgCO₂',''],[result.worst_kg,'Highest · kgCO₂',''],[result.avoided_kg,'Difference · kgCO₂','saving']]){const item=el('div',cls);item.append(el('strong','',fmt(value,2)),el('span','',label));values.append(item);}
 const window=el('div','scenario-window');window.append(el('strong','','Lowest window: '),document.createTextNode(`${date(result.best.start)}–${date(result.best.end)} UTC · ${fmt(result.energy_kwh,1)} kWh facility energy`));$('scenario-result').replaceChildren(values,window);
 }catch(error){if(version===scenarioVersion)scenarioPlaceholder('Comparison is unavailable just now. Please try again.');}
 finally{button.disabled=false;form.classList.remove('is-loading');text('compare-label','Explore the difference');}
}
$('scenario-form').addEventListener('submit',event=>{event.preventDefault();runScenario();});
$('about').addEventListener('click',()=>$('about-dialog').showModal());$('close-about').addEventListener('click',()=>$('about-dialog').close());$('about-dialog').addEventListener('click',event=>{const box=$('about-dialog').getBoundingClientRect();if(event.target===$('about-dialog')&&(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom))$('about-dialog').close();});
const sectionLinks=[...document.querySelectorAll('nav a[href^="#"]')];
const observer=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top);if(!visible.length)return;const id=visible[0].target.id;sectionLinks.forEach(link=>{const active=link.getAttribute('href')==='#'+id;link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});},{rootMargin:'-15% 0px -55% 0px',threshold:0});
for(const id of ['overview','signals','workload','pipeline'])observer.observe($(id));
refresh();setInterval(refresh,60000);
