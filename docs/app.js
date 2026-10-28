// Mirrors variance_analyst/core.py + commentary.py (keep in sync; covered by Python tests).
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
  return t.slice(1).map((r,i)=>{const o={}; hdr.forEach((h,j)=>o[h]=(r[j]||"").trim());
    o.account_type=o.account_type.toLowerCase(); if(!["revenue","expense"].includes(o.account_type)) throw new Error(`line ${i+2}: account_type must be revenue or expense`);
    o.budget=parseFloat(o.budget.replace(/,/g,"")); o.actual=parseFloat(o.actual.replace(/,/g,""));
    if(isNaN(o.budget)||isNaN(o.actual)) throw new Error(`line ${i+2}: budget/actual must be numeric`); return o;});
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
function commentary(ls){
  const s=summarize(ls);
  let t=`Operating profit was ${money(s.pa)} vs budget ${money(s.pb)}, ${s.pv>=0?"a favorable":"an unfavorable"} variance of ${money(Math.abs(s.pv))}. `+
    `Revenue landed at ${money(s.ra)} (${money(s.ra-s.rb)} vs plan) and expenses at ${money(s.ea)} (${money(s.ea-s.eb)} vs plan). `+
    `${s.mat} of ${s.n} lines breached the materiality threshold.\n\nTop material variances:\n`;
  const top=ls.filter(l=>l.material).sort((a,b)=>Math.abs(b.variance)-Math.abs(a.variance)).slice(0,5);
  t+= top.length? top.map(l=>`• ${l.department} ${l.account} (${l.month}) came in ${money(Math.abs(l.variance))} ${l.variance>0?"over":"under"} budget (${pctf(l.variance_pct)}), ${l.favorable?"favorable":"unfavorable"}. Likely driver: ${driver(l.account)}.`).join("\n") : "• No material variances.";
  const d=rollup(ls,"department"); if(d.length){const w=d[0],b=d[d.length-1];
  t+=`\n\nBy department, ${w.key} had the largest net drag on profit (${money(w.net)}) and ${b.key} the largest net help (${money(b.net)}). Recommended follow-ups: confirm timing vs permanent items with budget owners, and re-forecast lines whose variance repeats for 2+ months.`;}
  return t;
}
function render(){
  $("err").hidden=true;
  const dept=$("dept").value;
  lines=compute(rows.filter(r=>!dept||r.department===dept),+$("pct").value/100,+$("abs").value);
  const s=summarize(lines);
  const k=(l,v,d,good)=>`<div class="kpi"><div class="l">${l}</div><div class="v">${v}</div><div class="d ${good===undefined?"":good?"good":"bad"}">${d}</div></div>`;
  $("kpis").innerHTML=k("Revenue (actual)",money(s.ra),`${money(s.ra-s.rb)} vs budget`,s.ra>=s.rb)+k("Expenses (actual)",money(s.ea),`${money(s.ea-s.eb)} vs budget`,s.ea<=s.eb)+
    k("Operating profit",money(s.pa),`${money(s.pv)} vs budget`,s.pv>=0)+k("Material variances",s.mat,`of ${s.n} lines`);
  $("commentary").textContent=commentary(lines);
  const d=rollup(lines,"department");
  draw("deptChart",{type:"bar",data:{labels:d.map(x=>x.key),datasets:[{label:"Net profit impact ($)",data:d.map(x=>Math.round(x.net)),backgroundColor:d.map(x=>x.net>=0?"#2ecc8f":"#ff6b6b")}]},options:{indexAxis:"y",plugins:{legend:{display:false}}}});
  const months=[...new Set(lines.map(l=>l.month))].sort();
  const prof=(m,k)=>lines.filter(l=>l.month===m).reduce((a,l)=>a+(l.account_type==="revenue"?l[k]:-l[k]),0);
  draw("monthChart",{type:"line",data:{labels:months,datasets:[{label:"Budget",data:months.map(m=>prof(m,"budget")),borderColor:"#93a0bd",borderDash:[5,5]},{label:"Actual",data:months.map(m=>prof(m,"actual")),borderColor:"#5b8cff",backgroundColor:"#5b8cff"}]}});
  table();
}
function draw(id,cfg){ if(!window.Chart) return; Chart.defaults.color="#93a0bd"; Chart.defaults.borderColor="#24304d"; if(charts[id]) charts[id].destroy(); charts[id]=new Chart($(id),cfg);}
function table(){
  const only=$("onlyMat").checked;
  const ls=lines.filter(l=>!only||l.material).sort((a,b)=>{let x=a[sortKey],y=b[sortKey];
    if(sortKey==="variance"||sortKey==="variance_pct"){x=Math.abs(x??0);y=Math.abs(y??0);return (y-x)*sortDir;}
    return (x>y?1:x<y?-1:0)*sortDir;});
  document.querySelector("#tbl tbody").innerHTML=ls.map(l=>`<tr class="${l.material?"mat":""}"><td>${l.month}</td><td>${esc(l.department)}</td><td>${esc(l.account)}</td><td>${l.account_type}</td>
    <td class="num">${money(l.budget)}</td><td class="num">${money(l.actual)}</td><td class="num ${l.favorable?"good":"bad"}">${money(l.variance)}</td><td class="num ${l.favorable?"good":"bad"}">${pctf(l.variance_pct)}</td>
    <td class="${l.favorable?"good":"bad"}">${l.favorable?"F":"U"}</td><td>${l.material?'<span class="tag">material</span>':""}</td></tr>`).join("");
}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function setData(text){ try{ rows=load(text); const ds=[...new Set(rows.map(r=>r.department))].sort();
  $("dept").innerHTML='<option value="">All</option>'+ds.map(d=>`<option>${esc(d)}</option>`).join(""); render(); }
  catch(e){ $("err").textContent=e.message; $("err").hidden=false; } }
document.querySelectorAll("th").forEach(th=>th.onclick=()=>{const k=th.dataset.k; sortDir=sortKey===k?-sortDir:1; sortKey=k; table();});
["pct","abs","dept"].forEach(id=>$(id).oninput=render); $("onlyMat").onchange=table;
$("file").onchange=e=>{const f=e.target.files[0]; if(f) f.text().then(setData);};
$("sample").onclick=()=>fetch("sample.csv").then(r=>r.text()).then(setData);
$("copy").onclick=()=>navigator.clipboard.writeText($("commentary").textContent);
fetch("sample.csv").then(r=>r.text()).then(setData);
