import {
  calculate_nakshatra,
  calculate_planets,
  get_ayanamsha,
  get_swisseph_version,
  p_julday,
} from "@fusionstrings/panchangam";

const SIGNS = [
  ["Mesha","Aries","♈"],["Vrishabha","Taurus","♉"],["Mithuna","Gemini","♊"],
  ["Karka","Cancer","♋"],["Simha","Leo","♌"],["Kanya","Virgo","♍"],
  ["Tula","Libra","♎"],["Vrishchika","Scorpio","♏"],["Dhanu","Sagittarius","♐"],
  ["Makara","Capricorn","♑"],["Kumbha","Aquarius","♒"],["Meena","Pisces","♓"]
];

const NAKSHATRAS = [
  "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
  "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
  "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
  "Uttara Ashadha","Shravana","Dhanishtha","Shatabhisha","Purva Bhadrapada",
  "Uttara Bhadrapada","Revati"
];

function cors(origin: string | null) {
  const allowed = origin === "https://astrolaab.com" || origin === "https://www.astrolaab.com" || !!origin?.endsWith(".astrolaab.com");
  return {
    "Access-Control-Allow-Origin": allowed ? origin! : "https://astrolaab.com",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin"
  };
}
function json(data: unknown, status=200, req?: Request) {
  return new Response(JSON.stringify(data), {status, headers: {"Content-Type":"application/json; charset=utf-8", ...cors(req?.headers.get("Origin") ?? null)}});
}
function err(message:string, req:Request, status=400){ return json({ok:false,error:message},status,req); }

function parseDate(v:string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new Error("date must be YYYY-MM-DD");
  const [y,m,d]=v.split("-").map(Number);
  const x=new Date(Date.UTC(y,m-1,d));
  if(x.getUTCFullYear()!==y||x.getUTCMonth()!==m-1||x.getUTCDate()!==d) throw new Error("invalid date");
  return {y,m,d};
}
function parseTime(v:string) {
  if(!/^\d{2}:\d{2}(:\d{2})?$/.test(v)) throw new Error("time must be HH:MM or HH:MM:SS");
  const [h,mi,s=0]=v.split(":").map(Number);
  if(h>23||mi>59||s>59) throw new Error("invalid time");
  return {h,mi,s};
}
function offsetFor(date:Date,tz:string){
  const parts=new Intl.DateTimeFormat("en-US",{timeZone:tz,timeZoneName:"longOffset",hour:"2-digit",hourCycle:"h23"}).formatToParts(date);
  const v=parts.find(p=>p.type==="timeZoneName")?.value ?? "GMT";
  if(v==="GMT"||v==="UTC") return 0;
  const m=v.match(/^GMT([+-])(\d{1,2})(?::?(\d{2}))?$/);
  if(!m) throw new Error("invalid IANA timezone or unavailable historical offset");
  return (m[1]==="+"?1:-1)*(Number(m[2])*60+Number(m[3]||0));
}
function localToUtc(date:string,time:string,tz:string,explicit?:number){
  const {y,m,d}=parseDate(date),{h,mi,s}=parseTime(time);
  let off=explicit;
  const guess=Date.UTC(y,m-1,d,h,mi,s);
  if(off==null){
    off=offsetFor(new Date(guess),tz);
    const adjusted=new Date(guess-off*60000);
    off=offsetFor(adjusted,tz);
  }
  if(!Number.isFinite(off)||Math.abs(off)>14*60) throw new Error("invalid UTC offset");
  return {date:new Date(guess-off*60000),offsetMinutes:off};
}
function norm(x:number){return ((x%360)+360)%360;}
function dms(x:number){
  const total=Math.round((x%30)*3600);
  const deg=Math.floor(total/3600), min=Math.floor((total%3600)/60), sec=total%60;
  return {degrees:deg,minutes:min,seconds:sec,text:`${deg}° ${String(min).padStart(2,"0")}′ ${String(sec).padStart(2,"0")}″`};
}
function moonOf(planets:any[]){
  const m=planets.find(p=>Number(p.id)===1||String(p.name).toLowerCase()==="moon");
  if(!m) throw new Error("Moon position unavailable");
  return m;
}

function calculate(body:any){
  if(!body?.date||!body?.time||!body?.timeZone) throw new Error("date, time and timeZone are required");
  const u=localToUtc(body.date,body.time,body.timeZone,body.utcOffsetMinutes);
  const x=u.date;
  const hour=x.getUTCHours()+x.getUTCMinutes()/60+x.getUTCSeconds()/3600+x.getUTCMilliseconds()/3600000;
  const jd=p_julday(x.getUTCFullYear(),x.getUTCMonth()+1,x.getUTCDate(),hour,1);
  const ay=get_ayanamsha(1,jd);
  const planets=calculate_planets(jd,1) as any[];
  const moon=moonOf(planets);
  const longitude=norm(Number(moon.longitude));
  const si=Math.floor(longitude/30), deg=longitude-si*30;
  const ni=Math.floor(longitude/(360/27)), pada=Math.floor((longitude%(360/27))/((360/27)/4))+1;
  return {
    ok:true,engine:"Swiss Ephemeris",swissephVersion:get_swisseph_version(),
    ayanamsha:{name:"Lahiri (Chitrapaksha)",mode:1,degrees:Number(ay)},
    birth:{localDate:body.date,localTime:body.time,timeZone:body.timeZone,utcOffsetMinutes:u.offsetMinutes,utc:x.toISOString(),julianDayUT:jd},
    location:body.place?{name:body.place.name??null,country:body.place.country??null,latitude:Number(body.place.latitude),longitude:Number(body.place.longitude)}:null,
    moon:{siderealLongitude:longitude,sign:{name:SIGNS[si][0],english:SIGNS[si][1],symbol:SIGNS[si][2]},degreeInSign:deg,degreeInSignDms:dms(deg),nakshatra:{name:NAKSHATRAS[ni],index:ni+1,pada}},
    boundaryWarning:deg<0.1||deg>29.9?"Moon is very close to a Rashi boundary. Recheck birth time and timezone.":null
  };
}
async function locations(q:string,req:Request){
  if(q.trim().length<2||q.length>100) return err("location query must be 2–100 characters",req);
  const u=new URL("https://photon.komoot.io/api/"); u.searchParams.set("q",q.trim());u.searchParams.set("limit","6");u.searchParams.set("lang","en");
  const r=await fetch(u,{headers:{"Accept":"application/json","User-Agent":"AstroLaab/1.0 (https://astrolaab.com)"}});
  if(!r.ok) return err("location service unavailable",req,502);
  const data:any=await r.json();
  const results=(data.features??[]).map((f:any)=>{
    const p=f.properties??{}, [lon,lat]=f.geometry?.coordinates??[];
    return {id:`${p.osm_type??"place"}:${p.osm_id??`${lat},${lon}`}`,name:p.name??p.city??p.state??p.country??q,city:p.city??p.name??null,state:p.state??null,country:p.country??null,countryCode:p.countrycode??null,latitude:lat,longitude:lon,label:[p.name??p.city,p.state,p.country].filter(Boolean).join(", ")};
  }).filter((x:any)=>Number.isFinite(x.latitude)&&Number.isFinite(x.longitude));
  return json({ok:true,source:"Photon / OpenStreetMap",attribution:"Location data © OpenStreetMap contributors",results},200,req);
}
export default {async fetch(req:Request){
  if(req.method==="OPTIONS") return new Response(null,{status:204,headers:cors(req.headers.get("Origin"))});
  const u=new URL(req.url);
  try{
    if(req.method==="GET"&&u.pathname==="/health") return json({ok:true,service:"astrolaab-moon-sign",engine:"Swiss Ephemeris",swissephVersion:get_swisseph_version(),ayanamsha:"Lahiri (Chitrapaksha)"},200,req);
    if(req.method==="GET"&&u.pathname==="/location") return locations(u.searchParams.get("q")??"",req);
    if(req.method==="POST"&&u.pathname==="/moon-sign"){
      const body=await req.json();
      if(!body||typeof body!=="object") return err("invalid JSON body",req);
      if(body.place && (!Number.isFinite(Number(body.place.latitude))||!Number.isFinite(Number(body.place.longitude)))) return err("invalid selected location",req);
      return json(calculate(body),200,req);
    }
    return err("not found",req,404);
  }catch(e){return err(e instanceof Error?e.message:"unexpected error",req,400);}
}};
