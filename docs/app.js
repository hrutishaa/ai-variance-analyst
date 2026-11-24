// Mirrors variance_analyst/core.py + runrate.py + commentary.py (+ pvm.py via pvm.js) (keep in sync; covered by Python tests).
const REQ = ["month","department","account","account_type","budget","actual"];
const DRIVERS = {salaries:"headcount timing (hires landing earlier/later than plan) or merit/bonus accruals",
  contractors:"use of contractors to backfill open roles or accelerate projects",cloud:"usage growth, untagged resources, or reserved-instance coverage gaps",
  software:"new SaaS seats or annual renewals hitting earlier than phased",marketing:"campaign spend timing or a shift between paid channels",
  travel:"event and customer-visit volume",events:"conference sponsorships or event costs landing in a different month than planned",
  subscription:"new-logo bookings, expansion, or churn versus plan",services:"implementation project timing and utilization",
  rent:"facility changes or lease escalations",commission:"bookings mix and accelerators tied to revenue performance"};
let rows = [], lines = [], sortKey = "variance", sortDir = 1, charts = {};
const $ = id => document.getElementById(id);

function parseCSV(text){
  const out=[]; let row=[], f="", q=false;
  for(let i=0;i<text.length;i++){const c=text[i];
    if(q){ if(c=='"'&&text[i+1]=='"'){f+='"';i++;} else if(c=='"') q=false; else f+=c; }
    else if(c=='"') q=true; else if(c==','){row.push(f);f="";}
    else if(c=='\n'||c=='\r'){ if(c=='\r'&&text[i+1]=='\n') i++; row.push(f); f=""; if(row.some(x=>x.trim()!=="")) out.push(row); row=[]; }
    else f+=c;}
  if(f!==""||row.length){row.push(f); if(row.some(x=>x.trim()!=="")) out.push(row);}
  return out;
}
function load(text){
  const t=parseCSV(text); const hdr=t[0].map(h=>h.trim().toLowerCase());
  const miss=REQ.filter(c=>!hdr.includes(c)); if(miss.length) throw new Error("CSV is missing required columns: "+miss.join(", "));
  const hu=["budget_units","actual_units"].map(c=>hdr.includes(c)); if(hu[0]!==hu[1]) throw new Error("unit columns come as a pair: add both budget_units and actual_units, or neither");
  return t.slice(1).map((r,i)=>{const o={}; hdr.forEach((h,j)=>o[h]=(r[j]||"").trim());
    o.account_type=o.account_type.toLowerCase(); if(!["revenue","expense"].includes(o.account_type)) throw new Error(`line ${i+2}: account_type must be revenue or expense`);
    o.budget=parseFloat(o.budget.replace(/,/g,"")); o.actual=parseFloat(o.actual.replace(/,/g,""));
    if(isNaN(o.budget)||isNaN(o.actual)) throw new Error(`line ${i+2}: budget/actual must be numeric`);
    const bu=hu[0]?o.budget_units:"", au=hu[0]?o.actual_units:"";
    if(!bu&&!au){o.budget_units=null;o.actual_units=null;}
    else { if(!bu||!au) throw new Error(`line ${i+2}: fill both budget_units and actual_units, or leave both blank`);
      o.budget_units=Number(bu.replace(/,/g,"")); o.actual_units=Number(au.replace(/,/g,""));
      if(isNaN(o.budget_units)||isNaN(o.actual_units)) throw new Error(`line ${i+2}: budget_units/actual_units must be numeric`);
      if(o.budget_units<0||o.actual_units<0) throw new Error(`line ${i+2}: units cannot be negative`); }
    return o;});
}
function compute(rows,pct,abs){
  return rows.map(r=>{const v=r.actual-r.budget, p=r.budget===0?null:v/Math.abs(r.budget);
    const fav=r.account_type==="revenue"?v>=0:v<=0; const hit=(p===null&&v!==0)||(p!==null&&Math.abs(p)>=pct);
    return {...r,variance:v,variance_pct:p,favorable:fav,material:hit&&Math.abs(v)>=abs};});
}
const money=x=>{const s=x<0?"-":"";x=Math.abs(x);return x>=1e6?`${s}$${(x/1e6).toFixed(2)}M`:x>=1e3?`${s}$${(x/1e3).toFixed(1)}K`:`${s}$${Math.round(x).toLocaleString()}`};
const pctf=p=>p===null?"n/a":(p>=0?"+":"")+(p*100).toFixed(1)+"%";
const driver=a=>{a=a.toLowerCase();for(const k in DRIVERS) if(a.includes(k)) return DRIVERS[k];return "volume, price/rate, or timing differences versus the plan phasing";};
function summarize(ls){const s=(t,k)=>ls.filter(l=>l.account_type===t).reduce((a,l)=>a+l[k],0);
  const rb=s("revenue","budget"),ra=s("revenue","actual"),eb=s("expense","budget"),ea=s("expense","actual");
  return {rb,ra,eb,ea,pb:rb-eb,pa:ra-ea,pv:(ra-ea)-(rb-eb),mat:ls.filter(l=>l.material).length,n:ls.length};}
function rollup(ls,by){const m={};ls.forEach(l=>{const k=l[by];m[k]=m[k]||{key:k,budget:0,actual:0,net:0};m[k].budget+=l.budget;m[k].actual+=l.actual;m[k].net+=l.favorable?Math.abs(l.variance):-Math.abs(l.variance);});
  return Object.values(m).sort((a,b)=>a.net-b.net);}
// Run-rate vs timing (mirrors runrate.py): a month extends a streak when material and same sign;
// a non-material month, a sign flip or a missing month breaks it.
function groupItems(ls){const months=[...new Set(ls.map(l=>l.month))].sort(), items=new Map();
  ls.forEach(l=>{const k=l.department+"\u0000"+l.account; if(!items.has(k)) items.set(k,new Map()); const m=items.get(k);
    if(m.has(l.month)) throw new Error(`duplicate line item ${l.department} / ${l.account} in ${l.month}; aggregate rows before run-rate detection`);
    m.set(l.month,l);});
  return {months,items};}
const dir=l=>!l||!l.material||l.variance===0?0:l.variance>0?1:-1;
function runs(months,byMonth){const out=[];let cur=[],cs=0;
  months.forEach(m=>{const l=byMonth.get(m),s=dir(l); if(s&&s===cs){cur.push(l);return;} if(cur.length) out.push(cur); cur=s?[l]:[]; cs=s;});
  if(cur.length) out.push(cur); return out;}
function runLengths(ls){const {months,items}=groupItems(ls),out=new Map();
  items.forEach(bm=>runs(months,bm).forEach(r=>r.forEach(l=>out.set(l,r.length)))); return out;}
function detectRunRate(ls,n){const {months,items}=groupItems(ls); if(!months.length) return [];
  const latest=months[months.length-1],out=[];
  items.forEach(bm=>{const rs=runs(months,bm), last=rs.length?rs[rs.length-1]:null;
    const tr=last&&last[last.length-1].month===latest?last:[], lm=last?last[last.length-1]:null, any=[...bm.values()][0];
    out.push({department:any.department,account:any.account,pattern:tr.length>=n?"run-rate":rs.length?"timing":"none",
      streak:tr.length,streak_months:tr.map(l=>l.month),streak_variance:tr.reduce((a,l)=>a+l.variance,0),
      favorable:tr.length?tr[0].favorable:null,last_material_month:lm?lm.month:null,last_material_variance:lm?lm.variance:0});});
  const ord={"run-rate":0,timing:1,none:2}, mag=p=>Math.abs(p.pattern==="run-rate"?p.streak_variance:p.last_material_variance);
  return out.sort((a,b)=>ord[a.pattern]-ord[b.pattern]||mag(b)-mag(a)||(a.department+a.account<b.department+b.account?-1:1));}
function runRateSection(ls,n){
  const months=new Set(ls.map(l=>l.month)); if(months.size<n) return "";
  const ps=detectRunRate(ls,n), latest=[...months].sort().pop();
  const rr=ps.filter(p=>p.pattern==="run-rate"), tm=ps.filter(p=>p.pattern==="timing");
  const out=[`Run-rate vs timing (material in the same direction for ${n}+ consecutive months through ${latest}):`];
  rr.slice(0,5).forEach(p=>out.push(`• ${p.department} ${p.account}: ${p.favorable?"favorable":"unfavorable"} for ${p.streak} months running (${p.streak_months[0]} to ${p.streak_months[p.streak-1]}, ${money(Math.abs(p.streak_variance))} cumulative); likely run-rate, consider re-forecast.`));
  if(!rr.length) out.push("• No run-rate variances; no material variance has repeated through the latest month.");
  const rev=tm.filter(p=>p.streak===0), fresh=tm.filter(p=>p.streak>0);
  if(rev.length) out.push(`• Timing (did not repeat): ${rev.slice(0,5).map(p=>`${p.department} ${p.account} (${p.last_material_month})`).join(", ")}. Likely phasing; confirm with budget owners.`);
  if(fresh.length) out.push(`• New in ${latest}: ${fresh.slice(0,5).map(p=>`${p.department} ${p.account}`).join(", ")}. Watch next month; a repeat makes it run-rate.`);
  return out.join("\n");}
const signed=x=>Math.round(x)===0?"$0":(x>0?"+":"")+money(x);
const price2=x=>"$"+x.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
function pvmDetail(g){const e={price:g.price_effect,volume:g.volume_effect,mix:g.mix_effect};
  const big=Object.keys(e).reduce((a,k)=>Math.abs(e[k])>Math.abs(e[a])?k:a,"price"), top=k=>g.products.reduce((a,p)=>Math.abs(p[k])>Math.abs(a[k])?p:a);
  let why; if(big==="price"){const p=top("price_effect"); why=`${p.account} averaged ${price2(p.actual_price)} per unit vs ${price2(p.budget_price)} budget`;}
  else if(big==="volume") why=`${Math.round(g.actual_units).toLocaleString()} units sold vs ${Math.round(g.budget_units).toLocaleString()} budget`;
  else {const p=top("mix_effect"); why=`${p.account} was ${Math.round(100*(g.actual_units?p.actual_units/g.actual_units:0))}% of units vs ${Math.round(100*(g.budget_units?p.budget_units/g.budget_units:0))}% in budget`;}
  return `Largest effect: ${big} (${why}).`;}
function pvmSection(groups){ if(!groups.length) return "";
  return [`Price / volume / mix (revenue lines with units, ${groups[0].period}):`].concat(groups.slice(0,5).map(g=>
    `• ${g.department}: revenue ${money(g.actual)} vs budget ${money(g.budget)} (${signed(g.variance)}). Price ${signed(g.price_effect)}, volume ${signed(g.volume_effect)}, mix ${signed(g.mix_effect)}. ${pvmDetail(g)}`)).join("\n");}
function commentary(ls,n,pvm){
  const s=summarize(ls);
  let t=`Operating profit was ${money(s.pa)} vs budget ${money(s.pb)}, ${s.pv>=0?"a favorable":"an unfavorable"} variance of ${money(Math.abs(s.pv))}. `+
    `Revenue landed at ${money(s.ra)} (${money(s.ra-s.rb)} vs plan) and expenses at ${money(s.ea)} (${money(s.ea-s.eb)} vs plan). `+
    `${s.mat} of ${s.n} lines breached the materiality threshold.\n\nTop material variances:\n`;
  const top=ls.filter(l=>l.material).sort((a,b)=>Math.abs(b.variance)-Math.abs(a.variance)).slice(0,5);
  t+= top.length? top.map(l=>`• ${l.department} ${l.account} (${l.month}) came in ${money(Math.abs(l.variance))} ${l.variance>0?"over":"under"} budget (${pctf(l.variance_pct)}), ${l.favorable?"favorable":"unfavorable"}. Likely driver: ${driver(l.account)}.`).join("\n") : "• No material variances.";
  const rrs=runRateSection(ls,n); if(rrs) t+="\n\n"+rrs;
  const pv=pvmSection(pvm||[]); if(pv) t+="\n\n"+pv;
  const d=rollup(ls,"department"); if(d.length){const w=d[0],b=d[d.length-1];
  t+=`\n\nBy department, ${w.key} had the largest net drag on profit (${money(w.net)}) and ${b.key} the largest net help (${money(b.net)}). Recommended follow-ups: confirm timing items with budget owners, and re-forecast lines whose variance repeats for ${n}+ months.`;}
  return t;
}
function render(){
  $("err").hidden=true;
  const dept=$("dept").value;
  lines=compute(rows.filter(r=>!dept||r.department===dept),+$("pct").value/100,+$("abs").value);
  const n=Math.max(2,Math.round(+$("runN").value)||2), lens=runLengths(lines);
  lines.forEach(l=>{const len=lens.get(l)||0; l.run=len; l.pattern=!l.material?"":len>=n?"run-rate":"timing";});
  const s=summarize(lines), rrCount=detectRunRate(lines,n).filter(p=>p.pattern==="run-rate").length;
  const k=(l,v,d,good)=>`<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="d ${good===undefined?"":good?"good":"bad"}">${d}</div></div>`;
  $("kpis").innerHTML=k("Revenue (actual)",money(s.ra),`${money(s.ra-s.rb)} vs budget`,s.ra>=s.rb)+k("Expenses (actual)",money(s.ea),`${money(s.ea-s.eb)} vs budget`,s.ea<=s.eb)+
    k("Operating profit",money(s.pa),`${money(s.pv)} vs budget`,s.pv>=0)+k("Material variances",s.mat,`of ${s.n} lines`)+
    k("Run-rate items",rrCount,`material ${n}+ months running`,rrCount===0);
  const pvm=decomposePVM(lines,false);
  $("commentary").textContent=commentary(lines,n,pvm);
  renderPVM(pvm);
  const d=rollup(lines,"department");
  draw("deptChart",{type:"bar",data:{labels:d.map(x=>x.key),datasets:[{label:"Net profit impact ($)",data:d.map(x=>Math.round(x.net)),backgroundColor:d.map(x=>x.net>=0?"#2ecc8f":"#ff6b6b")}]},options:{indexAxis:"y",plugins:{legend:{display:false}}}});
  const months=[...new Set(lines.map(l=>l.month))].sort();
  const prof=(m,k)=>lines.filter(l=>l.month===m).reduce((a,l)=>a+(l.account_type==="revenue"?l[k]:-l[k]),0);
  draw("monthChart",{type:"line",data:{labels:months,datasets:[{label:"Budget",data:months.map(m=>prof(m,"budget")),borderColor:"#93a0bd",borderDash:[5,5]},{label:"Actual",data:months.map(m=>prof(m,"actual")),borderColor:"#5b8cff",backgroundColor:"#5b8cff"}]}});
  table();
}
function renderPVM(groups){
  $("pvmCard").hidden=!groups.length; if(!groups.length){ if(charts.pvmChart){charts.pvmChart.destroy();delete charts.pvmChart;} return; }
  $("pvmPeriod").textContent=groups[0].period;
  const tot=k=>groups.reduce((a,g)=>a+g[k],0), b=tot("budget"), steps=[["Price",tot("price_effect")],["Volume",tot("volume_effect")],["Mix",tot("mix_effect")]];
  let run=b; const bars=[[0,b]].concat(steps.map(([,v])=>{const bar=[run,run+v]; run+=v; return bar;})).concat([[0,tot("actual")]]);
  const pts=bars.flat().filter(v=>v!==0), lo=Math.min(...pts), hi=Math.max(...pts), yMin=Math.max(0,Math.floor(lo-Math.max((hi-lo)*0.5,Math.abs(lo)*0.01)));
  draw("pvmChart",{type:"bar",data:{labels:["Budget revenue"].concat(steps.map(s=>s[0])).concat(["Actual revenue"]),
    datasets:[{label:"$",data:bars,backgroundColor:["#93a0bd"].concat(steps.map(([,v])=>v>=0?"#2ecc8f":"#ff6b6b")).concat(["#5b8cff"])}]},
    options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>{const [x,y]=c.raw;return c.dataIndex===0||c.dataIndex===4?money(y):signed(y-x);}}}},scales:{y:{min:yMin}}}});
  const cell=(v)=>`<td class="num ${v>=0?"good":"bad"}">${signed(v)}</td>`;
  document.querySelector("#pvmTbl tbody").innerHTML=groups.map(g=>
    `<tr class="grp"><td>${esc(g.department)}</td><td class="num">${Math.round(g.budget_units).toLocaleString()} → ${Math.round(g.actual_units).toLocaleString()}</td><td></td><td class="num">${money(g.budget)}</td>${cell(g.price_effect)}${cell(g.volume_effect)}${cell(g.mix_effect)}<td class="num">${money(g.actual)}</td></tr>`+
    g.products.map(p=>`<tr><td class="ind">${esc(p.account)}</td><td class="num">${Math.round(p.budget_units).toLocaleString()} → ${Math.round(p.actual_units).toLocaleString()}</td><td class="num">${price2(p.budget_price)} → ${price2(p.actual_price)}</td><td class="num">${money(p.budget)}</td>${cell(p.price_effect)}${cell(p.volume_effect)}${cell(p.mix_effect)}<td class="num">${money(p.actual)}</td></tr>`).join("")).join("");
}
function draw(id,cfg){ if(!window.Chart) return; Chart.defaults.color="#93a0bd"; Chart.defaults.borderColor="#24304d"; if(charts[id]) charts[id].destroy(); charts[id]=new Chart($(id),cfg);}
function table(){
  const only=$("onlyMat").checked;
  const ls=lines.filter(l=>!only||l.material).sort((a,b)=>{let x=a[sortKey],y=b[sortKey];
    if(sortKey==="variance"||sortKey==="variance_pct"){x=Math.abs(x??0);y=Math.abs(y??0);return (y-x)*sortDir;}
    if(sortKey==="pattern"){x=a.pattern?a.pattern==="run-rate"?1000+a.run:a.run:0;y=b.pattern?b.pattern==="run-rate"?1000+b.run:b.run:0;return (y-x)*sortDir;}
    return (x>y?1:x<y?-1:0)*sortDir;});
  document.querySelector("#tbl tbody").innerHTML=ls.map(l=>`<tr class="${l.material?"mat":""}"><td>${l.month}</td><td>${esc(l.department)}</td><td>${esc(l.account)}</td><td>${l.account_type}</td>
    <td class="num">${money(l.budget)}</td><td class="num">${money(l.actual)}</td><td class="num ${l.favorable?"good":"bad"}">${money(l.variance)}</td><td class="num ${l.favorable?"good":"bad"}">${pctf(l.variance_pct)}</td>
    <td class="${l.favorable?"good":"bad"}">${l.favorable?"F":"U"}</td><td>${l.material?'<span class="tag">material</span>':""}</td>
    <td>${l.pattern==="run-rate"?`<span class="tag rr" title="material in the same direction for ${l.run} consecutive months">run-rate ×${l.run}</span>`:l.pattern==="timing"?'<span class="tag tm" title="material, but did not repeat in the same direction">timing</span>':""}</td></tr>`).join("");
}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function setData(text){ try{ rows=load(text); const ds=[...new Set(rows.map(r=>r.department))].sort();
  $("dept").innerHTML='<option value="">All</option>'+ds.map(d=>`<option>${esc(d)}</option>`).join(""); render(); }
  catch(e){ $("err").textContent=e.message; $("err").hidden=false; } }
document.querySelectorAll("#tbl th").forEach(th=>th.onclick=()=>{const k=th.dataset.k; sortDir=sortKey===k?-sortDir:1; sortKey=k; table();});
["pct","abs","dept","runN"].forEach(id=>$(id).oninput=render); $("onlyMat").onchange=table;
$("file").onchange=e=>{const f=e.target.files[0]; if(f) f.text().then(setData);};
$("sample").onclick=()=>fetch("sample.csv").then(r=>r.text()).then(setData);
$("samplePvm").onclick=()=>fetch("sample_pvm.csv").then(r=>r.text()).then(setData);
$("copy").onclick=()=>navigator.clipboard.writeText($("commentary").textContent);
fetch("sample.csv").then(r=>r.text()).then(setData);
