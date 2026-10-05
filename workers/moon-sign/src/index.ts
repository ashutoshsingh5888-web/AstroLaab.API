import {
  calculate_nakshatra,
  calculate_houses,
  calculate_planets,
  calc_ut,
  get_ayanamsha,
  get_swisseph_version,
  p_julday,
} from "@fusionstrings/panchangam/browser";

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
function signOf(longitude:number){
  const i=Math.floor(norm(longitude)/30);
  return {index:i+1,name:SIGNS[i][0],english:SIGNS[i][1],symbol:SIGNS[i][2],degreeInSign:norm(longitude)-i*30,degreeInSignDms:dms(norm(longitude)-i*30)};
}
function divisionalSign(longitude:number, division:number){
  const x=norm(longitude), rashi=Math.floor(x/30), part=Math.floor((x%30)/(30/division));
  // Generic varga mapping. D9 is the primary public chart; this follows the classical movable/fixed/dual navamsa rule.
  if(division===9){
    const navamsaIndex = ((rashi%3===0 ? rashi : rashi%3===1 ? (rashi+8)%12 : (rashi+4)%12) + part) % 12;
    return signOf(navamsaIndex*30);
  }
  return signOf(((rashi*division+part)%12)*30);
}
function deltaT(year:number){
  let t:number;
  if(year<1920){t=year-1900;return -2.79+1.494119*t-0.0598939*t**2+0.0061966*t**3-0.000197*t**4;}
  if(year<1941){t=year-1920;return 21.20+0.84493*t-0.0761*t**2+0.0020936*t**3;}
  if(year<1961){t=year-1950;return 29.07+0.407*t-t**2/233+t**3/2547;}
  if(year<1986){t=year-1975;return 45.45+1.067*t-t**2/260-t**3/718;}
  if(year<2005){t=year-2000;return 63.86+0.3345*t-0.060374*t**2+0.0017275*t**3+0.000651814*t**4+0.00002373599*t**5;}
  if(year<2050){t=year-2000;return 62.92+0.32217*t+0.005589*t**2;}
  return -20+32*((year-1820)/100)**2-0.5628*(2150-year);
}

function planetId(name:string){
  const n=name.toLowerCase();
  if(n.includes("sun")) return 0; if(n.includes("moon")) return 1; if(n.includes("mercury")) return 2;
  if(n.includes("venus")) return 3; if(n.includes("mars")) return 4; if(n.includes("jupiter")) return 5;
  if(n.includes("saturn")) return 6; if(n.includes("uranus")) return 7; if(n.includes("neptune")) return 8;
  if(n.includes("pluto")) return 9; return -1;
}

function calculate(body:any){
  if(!body?.date||!body?.time||!body?.timeZone) throw new Error("date, time and timeZone are required");
  const u=localToUtc(body.date,body.time,body.timeZone,body.utcOffsetMinutes);
  const x=u.date;
  const hour=x.getUTCHours()+x.getUTCMinutes()/60+x.getUTCSeconds()/3600+x.getUTCMilliseconds()/3600000;
  const jd=p_julday(x.getUTCFullYear(),x.getUTCMonth()+1,x.getUTCDate(),hour,1);
  const decimalYear=x.getUTCFullYear()+(x.getUTCMonth()+0.5)/12;
  const jdTT=jd+deltaT(decimalYear)/86400;
  const ay=get_ayanamsha(1,jdTT);
  // The panchangam wrapper's calculate_planets() is its canonical Swiss Ephemeris
  // sidereal path: it calculates with Swiss Ephemeris and subtracts the requested
  // ayanamsha consistently for all supported Vedic planets.
  const planetsRaw=calculate_planets(jdTT,1) as any[];
  const planets=planetsRaw.map((p:any)=>{
    const longitude=norm(Number(p.longitude));
    const s=signOf(longitude);
    return {id:Number(p.id),name:p.name,longitude,latitude:Number(p.latitude??0),speed:Number(p.speed??0),retrograde:Boolean(p.is_retrograde),sign:s,navamsa:divisionalSign(longitude,9)};
  });
  const moon=planets.find((p:any)=>p.id===1);
  if(!moon) throw new Error("Moon position unavailable");
  const ni=Math.floor(moon.longitude/(360/27)), pada=Math.floor((moon.longitude%(360/27))/((360/27)/4))+1;
  let houses:any=null;
  if(body.place){
    const lat=Number(body.place.latitude), lon=Number(body.place.longitude);
    if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180) throw new Error("invalid selected location");
    const hs=String(body.houseSystem??"P").toUpperCase();
    if(!["P","W","E"].includes(hs)) throw new Error("houseSystem must be P, W or E");
    const h=calculate_houses(jd,lat,lon,hs,1) as any;
    houses={system:hs,ascendant:signOf(Number(h.ascendant)),cusps:Array.from(h.cusps??[]).map((v:number,i:number)=>({house:i+1,longitude:norm(Number(v)),sign:signOf(norm(Number(v)))}))};
  }
  const ayanamsaDeg=Number(ay);
  return {
    ok:true,engine:"Swiss Ephemeris",swissephVersion:get_swisseph_version(),calculationProfile:{zodiac:"sidereal",ayanamsha:"Lahiri (Chitrapaksha)",ayanamshaMode:1,houseSystem:houses?.system??null,ephemeris:"Swiss Ephemeris",timeScales:{planets:"TT",houses:"UT",ayanamsha:"TT",deltaTSeconds:deltaT(decimalYear)}},
    ayanamsha:{name:"Lahiri (Chitrapaksha)",mode:1,degrees:ayanamsaDeg},
    birth:{localDate:body.date,localTime:body.time,timeZone:body.timeZone,utcOffsetMinutes:u.offsetMinutes,utc:x.toISOString(),julianDayUT:jd,julianDayTT:jdTT},
    location:body.place?{name:body.place.name??null,country:body.place.country??null,latitude:Number(body.place.latitude),longitude:Number(body.place.longitude)}:null,
    moon:{siderealLongitude:moon.longitude,sign:moon.sign,degreeInSign:moon.sign.degreeInSign,degreeInSignDms:moon.sign.degreeInSignDms,nakshatra:{name:NAKSHATRAS[ni],index:ni+1,pada},navamsa:moon.navamsa},
    planets,
    houses,
    boundaryWarning:moon.sign.degreeInSign<0.1||moon.sign.degreeInSign>29.9?"Moon is very close to a Rashi boundary. Recheck birth time and timezone.":null
  };
}
const SELF_TESTS:any[] = [
  {id:"india-mumbai-1990",date:"1990-05-15",time:"14:30:00",timeZone:"Asia/Kolkata",place:{name:"Mumbai",country:"India",latitude:19.076,longitude:72.8777},expected:{moonSign:"Makara",moonLongitude:271.8935490396424}},
  {id:"india-delhi-2024",date:"2024-01-01",time:"12:00:00",timeZone:"Asia/Kolkata",place:{name:"New Delhi",country:"India",latitude:28.6139,longitude:77.209}},
  {id:"india-kolkata-2000",date:"2000-01-01",time:"00:00:00",timeZone:"Asia/Kolkata",place:{name:"Kolkata",country:"India",latitude:22.5726,longitude:88.3639}},
  {id:"usa-new-york-dst",date:"2020-07-15",time:"12:00:00",timeZone:"America/New_York",place:{name:"New York",country:"United States",latitude:40.7128,longitude:-74.006}},
  {id:"australia-sydney-dst",date:"2021-01-15",time:"12:00:00",timeZone:"Australia/Sydney",place:{name:"Sydney",country:"Australia",latitude:-33.8688,longitude:151.2093}},
  {id:"equator-singapore",date:"2010-06-21",time:"06:30:00",timeZone:"Asia/Singapore",place:{name:"Singapore",country:"Singapore",latitude:1.3521,longitude:103.8198}},
  {id:"southern-hemisphere-sao-paulo",date:"1985-11-03",time:"18:45:30",timeZone:"America/Sao_Paulo",place:{name:"Sao Paulo",country:"Brazil",latitude:-23.5505,longitude:-46.6333}},
  {id:"europe-london",date:"1975-03-30",time:"09:15:00",timeZone:"Europe/London",place:{name:"London",country:"United Kingdom",latitude:51.5074,longitude:-0.1278}}
];

async function runAccuracyTest(){
  // Independent public reference: AstroSage Brihat Horoscope sample, Pooja Sharma.
  // Birth: 23 Aug 1978, 23:53:18, Delhi (28N40, 77E13), TZ +5.5.
  // AstroSage reports Lahiri ayanamsha 23-33-30 and rounded sidereal longitudes to 1 arcsec.
  const ref:any={
    id:"astrosage-pooja-sharma-1978",
    date:"1978-08-23",time:"23:53:18",timeZone:"Asia/Kolkata",
    place:{latitude:28+40/60,longitude:77+13/60},
    expected:{
      Ascendant:45+30/60+14/3600,
      Sun:120+6+42/60+30/3600,
      Moon:16+23/60+10/3600,
      Mars:150+18+40/60+48/3600,
      Mercury:90+28+16/60+43/3600,
      Jupiter:90+3+54/60+40/3600,
      Venus:150+22+40/60+42/3600,
      Saturn:120+9+57/60+57/3600,
      Rahu:150+4+33/60+40/3600,
      Ketu:330+4+33/60+40/3600,
      Uranus:180+19+15/60+30/3600,
      Neptune:210+21+58/3600+28/3600,
      Pluto:150+21+19/60+34/3600,
      Ayanamsha:23+33/60+30/3600
    }
  };
  const out=calculate({date:ref.date,time:ref.time,timeZone:ref.timeZone,place:ref.place,houseSystem:"P"});
  const arcsec=(a:number,b:number)=>{const d=Math.abs(norm(a-b));return (d>180?360-d:d)*3600;};
  const errors:any={};
  for(const name of ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu","Uranus","Neptune","Pluto"]){
    const p=out.planets.find((x:any)=>x.name===name);
    errors[name]=p?arcsec(p.longitude,ref.expected[name]):null;
  }
  const ascLon=Number(out.houses?.ascendant?.index?((out.houses.ascendant.index-1)*30+out.houses.ascendant.degreeInSign):NaN);
  errors.Ascendant=arcsec(ascLon,ref.expected.Ascendant);
  errors.Ayanamsha=Math.abs(out.ayanamsha.degrees-ref.expected.Ayanamsha)*3600;
  const maxArcsec=Math.max(...Object.values(errors).map(Number));
  return {
    ok:maxArcsec<=2,
    reference:ref.id,
    source:"AstroSage Brihat Horoscope public sample",
    thresholdArcsec:2,
    note:"AstroSage reference longitudes are rounded to 1 arcsecond; this is an independent reference test, not a proof of absolute accuracy.",
    errorsArcsec:errors,
    maxArcsec,
    calculated:{birth:out.birth,ayanamsha:out.ayanamsha,ascendant:ascLon}
  };
}

function runSelfTest(){
  const results:any[]=[];
  for(const t of SELF_TESTS){
    try{
      const b={...t,houseSystem:"W"};
      const out=calculate(b);
      const checks:any[]=[
        ["engine",out.engine==="Swiss Ephemeris"],
        ["Lahiri",out.calculationProfile?.ayanamsha==="Lahiri (Chitrapaksha)"],
        ["Moon longitude",Number.isFinite(out.moon?.siderealLongitude)],
        ["Rashi",typeof out.moon?.sign?.english==="string"],
        ["Nakshatra",Number.isInteger(out.moon?.nakshatra?.index)&&out.moon.nakshatra.index>=1&&out.moon.nakshatra.index<=27],
        ["Pada",Number.isInteger(out.moon?.nakshatra?.pada)&&out.moon.nakshatra.pada>=1&&out.moon.nakshatra.pada<=4],
        ["D9",typeof out.moon?.navamsa?.english==="string"],
        ["Planets",Array.isArray(out.planets)&&out.planets.length>=7],
        ["Houses",Array.isArray(out.houses?.cusps)&&out.houses.cusps.length>=12],
        ["Ascendant",Number.isFinite(out.houses?.ascendant?.degreeInSign)]
      ];
      if(t.expected?.moonSign) checks.push(["golden Moon sign",out.moon.sign.name===t.expected.moonSign]);
      if(Number.isFinite(t.expected?.moonLongitude)) checks.push(["golden Moon longitude",Math.abs(out.moon.siderealLongitude-t.expected.moonLongitude)<(1/3600)]);
      const failed=checks.filter((x:any)=>!x[1]).map((x:any)=>x[0]);
      results.push({id:t.id,status:failed.length?"FAIL":"PASS",failed});
    }catch(e){
      results.push({id:t.id,status:"ERROR",error:e instanceof Error?e.message:String(e)});
    }
  }
  const passed=results.filter(x=>x.status==="PASS").length;
  return {ok:passed===results.length,service:"astrolaab-moon-sign",engine:"Swiss Ephemeris",tests:results,passed,failed:results.length-passed,total:results.length};
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
    if(req.method==="GET"&&u.pathname==="/self-test") return json(runSelfTest(),200,req);
    if(req.method==="GET"&&u.pathname==="/accuracy-test") return json(await runAccuracyTest(),200,req);
    if(req.method==="POST"&&(u.pathname==="/moon-sign"||u.pathname==="/birth-chart")){
      const body=await req.json();
      if(!body||typeof body!=="object") return err("invalid JSON body",req);
      if(body.place && (!Number.isFinite(Number(body.place.latitude))||!Number.isFinite(Number(body.place.longitude)))) return err("invalid selected location",req);
      return json(calculate(body),200,req);
    }
    return err("not found",req,404);
  }catch(e){return err(e instanceof Error?e.message:"unexpected error",req,400);}
}};
