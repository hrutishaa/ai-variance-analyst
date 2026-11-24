// Price / volume / mix decomposition. Mirrors variance_analyst/pvm.py (CI checks parity on the sample).
// Lines need: month, department, account, account_type, budget, actual, budget_units, actual_units (null = no units).
(function(root){
function unitPrice(amount,units,what,dept,acct){
  if(units===0){ if(amount!==0) throw new Error(`${dept} / ${acct}: ${what} is ${amount.toFixed(2)} but ${what} units are 0, so the average price is undefined`); return null; }
  return amount/units;}
function decomposeGroup(period,dept,items){
  const vals=[...items.values()], bqt=vals.reduce((a,v)=>a+v[0],0), aqt=vals.reduce((a,v)=>a+v[1],0);
  const products=[...items.entries()].sort((x,y)=>x[0]<y[0]?-1:x[0]>y[0]?1:0).map(([acct,[bq,aq,b,a]])=>{
    let bp=unitPrice(b,bq,"budget",dept,acct), ap=unitPrice(a,aq,"actual",dept,acct);
    if(bp===null) bp=ap!==null?ap:0; if(ap===null) ap=bp;
    const price=(ap-bp)*aq; let volume,mix;
    if(bqt>0){const bmix=bq/bqt; volume=(aqt-bqt)*bmix*bp; mix=(aq-aqt*bmix)*bp;} else {volume=(aq-bq)*bp; mix=0;}
    return {department:dept,account:acct,budget_units:bq,actual_units:aq,budget_price:bp,actual_price:ap,budget:b,actual:a,variance:a-b,price_effect:price,volume_effect:volume,mix_effect:mix};});
  const s=k=>products.reduce((t,p)=>t+p[k],0), b=s("budget"), a=s("actual");
  return {period,department:dept,budget:b,actual:a,variance:a-b,budget_units:bqt,actual_units:aqt,
    price_effect:s("price_effect"),volume_effect:s("volume_effect"),mix_effect:s("mix_effect"),products};}
function decomposePVM(lines,byMonth){
  const el=lines.filter(l=>l.account_type==="revenue"&&l.budget_units!=null&&l.actual_units!=null);
  if(!el.length) return [];
  const months=[...new Set(el.map(l=>l.month))].sort(), whole=months.length===1?months[0]:`${months[0]} to ${months[months.length-1]}`;
  const groups=new Map();
  el.forEach(l=>{const period=byMonth?l.month:whole, gk=period+"\u0000"+l.department;
    if(!groups.has(gk)) groups.set(gk,{period,dept:l.department,items:new Map()});
    const items=groups.get(gk).items; if(!items.has(l.account)) items.set(l.account,[0,0,0,0]);
    const acc=items.get(l.account); acc[0]+=l.budget_units; acc[1]+=l.actual_units; acc[2]+=l.budget; acc[3]+=l.actual;});
  return [...groups.values()].map(g=>decomposeGroup(g.period,g.dept,g.items))
    .sort((x,y)=>(x.period<y.period?-1:x.period>y.period?1:0)||Math.abs(y.variance)-Math.abs(x.variance)||(x.department<y.department?-1:1));}
const api={decomposePVM};
if(typeof module!=="undefined"&&module.exports) module.exports=api; else Object.assign(root,api);
})(this);
