const $=id=>document.getElementById(id), history=[];
let voiceOn=true,rec=null;
function clock(){ $('clock').textContent=new Date().toLocaleTimeString(); } setInterval(clock,1000);clock();
function say(t){if(voiceOn&&'speechSynthesis'in window){speechSynthesis.cancel();let u=new SpeechSynthesisUtterance(t);u.lang='en-IN';speechSynthesis.speak(u)}}
function message(text,who='bot'){let d=document.createElement('div');d.className='msg '+(who==='user'?'user':'bot');let b=document.createElement('b');b.textContent=who==='user'?'YOU':'J';let p=document.createElement('p');p.textContent=text;d.append(b,p);$('chat').append(d);$('chat').scrollTop=$('chat').scrollHeight}
async function send(value){let t=(value??$('prompt').value).trim();if(!t)return;$('prompt').value='';message(t,'user');
 let q=t.toLowerCase();
 let launch=q.match(/^(?:jarvis\s+)?open\s+(notepad|calculator|paint|file explorer|explorer)$/);
 if(launch){let r=await fetch('/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:launch[1]})});let d=await r.json();message(d.message||d.error);say(d.message||d.error);return}
 let weather=q.match(/weather(?:\s+in)?\s+([a-z\s]+)$/);if(weather){$('city').value=weather[1];$('weather').click();return}
 if(/what time is it|current time/.test(q)){let s='The time is '+new Date().toLocaleTimeString();message(s);say(s);return}
 if(/today.s date|what is the date/.test(q)){let s='Today is '+new Date().toLocaleDateString(undefined,{dateStyle:'full'});message(s);say(s);return}
 history.push({role:'user',content:t});$('typing').hidden=false;
 try{let r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:history})});let d=await r.json();if(!r.ok)throw Error(d.error);history.push({role:'assistant',content:d.reply});message(d.reply);say(d.reply)}
 catch(e){message(e.message)}finally{$('typing').hidden=true}
}
$('send').onclick=()=>send();$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
$('voiceToggle').onclick=()=>{voiceOn=!voiceOn;$('voiceToggle').textContent=voiceOn?'🔊 Voice on':'🔇 Voice off';if(!voiceOn)speechSynthesis.cancel()};
document.querySelectorAll('[data-launch]').forEach(b=>b.onclick=async()=>{let r=await fetch('/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:b.dataset.launch})});let d=await r.json();message(d.message||d.error);say(d.message||d.error)});
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){rec=new SR();rec.lang='en-IN';rec.onresult=e=>send(e.results[0][0].transcript);$('mic').onclick=()=>{try{rec.start()}catch(e){}}}else{$('mic').disabled=true;$('mic').title='Speech recognition unavailable in this browser'}
$('fileSearch').onclick=async()=>{let term=$('fileTerm').value.trim();if(!term)return;let r=await fetch('/api/files/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({term})});let d=await r.json();$('fileResults').replaceChildren();if(d.error){$('fileResults').textContent=d.error;return}if(!d.results.length){$('fileResults').textContent='No matching filenames found.';return}d.results.forEach(f=>{let div=document.createElement('div');div.textContent=f.name+' — '+f.folder;div.title=f.path;$('fileResults').append(div)})};
async function loadMemories(){let r=await fetch('/api/memory');let d=await r.json();$('memories').replaceChildren();d.memories.forEach(m=>{let div=document.createElement('div');div.className='memory';let s=document.createElement('span');s.textContent=m.note;let b=document.createElement('button');b.textContent='×';b.onclick=async()=>{await fetch('/api/memory/'+m.id,{method:'DELETE'});loadMemories()};div.append(s,b);$('memories').append(div)})}
$('saveMemory').onclick=async()=>{let note=$('memoryText').value.trim();if(!note)return;let r=await fetch('/api/memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note})});let d=await r.json();if(d.error){$('memories').textContent=d.error;return}$('memoryText').value='';loadMemories()};loadMemories();
$('weather').onclick=async()=>{let city=$('city').value.trim();$('weatherResult').textContent='Loading...';let r=await fetch('/api/weather?city='+encodeURIComponent(city));let d=await r.json();$('weatherResult').textContent=r.ok?`${d.city}: ${d.temperature}°C, feels like ${d.feels_like}°C · Humidity ${d.humidity}% · Wind ${d.wind} km/h`:d.error};
$('news').onclick=async()=>{$('newsResult').textContent='Loading headlines...';let r=await fetch('/api/news');let d=await r.json();$('newsResult').replaceChildren();if(!r.ok){$('newsResult').textContent=d.error;return}d.items.forEach(n=>{let div=document.createElement('div');let a=document.createElement('a');a.href=n.link;a.target='_blank';a.rel='noopener';a.textContent=n.title;div.append(a);$('newsResult').append(div)})};
fetch('/api/status').then(r=>r.json()).then(d=>$('status').textContent=d.ai_configured?'AI API CONFIGURED · DESKTOP READY':'DESKTOP READY · ADD OPENAI API KEY FOR AI CHAT');
