import {useState} from 'react';
import {KpiCards} from './KpiCards';
export function Dashboard(){
 const d=(window as any).__FIELDWORK__ || {orders:[],result:null};
 const r=d.result; const [zone,setZone]=useState('drive');
 const o=r?.observation||{};
 const zones:any={drive:{title:'Drive / spindle',values:[['Rotational speed',o.speed,'RPM'],['Torque',o.torque,'Nm']]},process:{title:'Process chamber',values:[['Air temperature',o.air,'K'],['Process temperature',o.process,'K']]},tool:{title:'Tool head',values:[['Tool wear',o.wear,'min']]}};
 const decision=!r?'Not assessed':r.predicted_failure===null?'Abstained':r.predicted_failure?'Review flagged':'Below threshold';
 const complete=d.orders.filter((x:any)=>x.review==='Review completed').length;
 const kpis=[{label:'Current observation',value:r?.record_id||'None',sub:'Same assessment as technician console'}, {label:'Classifier score',value:r?.score==null?'—':r.score.toFixed(4),sub:'Uncalibrated score, not failure probability'}, {label:'Open reviews',value:String(d.orders.length-complete),sub:'Recorded local simulated orders'}, {label:'Completed reviews',value:String(complete),sub:'Review completed, not repair verified'}];
 return <div className="shell"><div className="wrap">
 <div className="mono" style={{fontSize:12,color:'#3DD6C3'}}>FIELDWORK / MACHINING CELL / OPERATIONS</div>
 <h1 style={{margin:'4px 0 20px',fontSize:26,fontWeight:600}}>Maintenance overview</h1>
 <div className="sub" style={{marginBottom:18}}>Synchronized assessment and ledger snapshot · Synthetic observations · Simulated actions</div>
 <KpiCards kpis={kpis}/>
 <div className="grid"><div className="card"><div className="lbl">Assembly evidence map</div>
 <div className="sub">Select a zone. The decision applies to the entire observation, not an identified failed part.</div>
 <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12,margin:'24px 0'}}>{Object.entries(zones).map(([id,z]:any)=><button className={zone===id?'btn':'btn2'} onClick={()=>setZone(id)} key={id}>{z.title}</button>)}</div>
 <h2>{zones[zone].title}</h2>{zones[zone].values.map(([label,value,unit]:any)=><div key={label} style={{padding:'12px 0',borderBottom:'1px solid #263344'}}><span className="sub">{label}</span><strong className="mono" style={{float:'right'}}>{value??'—'} {unit}</strong></div>)}
 <p className="sub">Product type: {o.kind||'—'}. No confirmed component diagnosis or replacement recommendation.</p></div>
 <div className="card"><div className="lbl">Current decision</div><h2 style={{color:r?.predicted_failure?'#FFB3AB':'#3DD6C3'}}>{decision}</h2>
 <p>Threshold: {r?.threshold??'—'}</p><p>Explanation mode: {r?.explanation_mode||'Not requested'}</p>
 <p className="sub">Bedrock selects supporting evidence in live mode. Classification and order policy remain separate. No remaining-life estimate is available.</p>
 {(r?.statements||[]).map((s:string)=><p className="sub" key={s}>{s}</p>)}
 {!r&&<p>Assess a record in Technician console, then return here.</p>}
 <a className="btn" href="/" target="_top">Open technician review →</a></div></div>
 <div className="card" style={{marginTop:18}}><div className="lbl">Review and remediation register</div>
 {d.orders.length===0?<p className="sub">No orders recorded in this ledger.</p>:d.orders.map((x:any)=><div key={x.id} style={{padding:'15px 0',borderBottom:'1px solid #263344'}}><strong>{x.asset}</strong><span className="mono" style={{float:'right'}}>{x.review}</span><p className="sub">{x.id} · {x.status}</p><p>{x.note||x.reason}</p></div>)}
 <p className="sub">Propose inspection first; verify the fault and appropriate repair before parts, inventory, specialist, or scheduling decisions. No dispatch or purchase is executed here.</p></div>
 </div></div>;
}
