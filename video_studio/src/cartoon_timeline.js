// Chức năng: Canvas playback and deterministic export of shared action frames.
// Lý do: Keep preview and MP4 on the same timeline; source: https://github.com/heygen-com/hyperframes
const canvas = document.getElementById('stage');
canvas.width = CFG.width;
canvas.height = CFG.height;
const ctx = canvas.getContext('2d');
function drawBackground(t) {
  const index = Math.max(0, Math.min(CFG.frames.length - 1, Math.floor(t * CFG.fps + 1e-7)));
  ctx.setTransform(1,0,0,1,0,0);
  ctx.fillStyle = '#b9e4ef'; ctx.fillRect(0,0,canvas.width,canvas.height);
  const scale = Math.min(canvas.width/CFG.vw,canvas.height/CFG.vh);
  ctx.translate((canvas.width-CFG.vw*scale)/2,(canvas.height-CFG.vh*scale)/2);
  ctx.scale(scale,scale);
  CFG.frames[index].forEach(c => {
    ctx.beginPath();
    if(c[0]==='ellipse') {
      ctx.fillStyle=c[5];ctx.ellipse(c[1],c[2],c[3],c[4],0,0,Math.PI*2);ctx.fill();
    } else {
      c[1].forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));
      if(c[0]==='poly'){ctx.fillStyle=c[2];ctx.closePath();ctx.fill();}
      else {ctx.strokeStyle=c[2];ctx.lineWidth=c[3];ctx.lineCap='round';ctx.lineJoin='round';ctx.stroke();}
    }
  });
  return canvas;
}
let renderSequence=0;
async function sceneryAt(t) {
  if(!CFG.nature) return [];
  return Promise.all(CFG.nature.objects.map(async object=> {
    const svg=new DOMParser().parseFromString(object.svg,'image/svg+xml').documentElement;
    const style=document.createElementNS('http://www.w3.org/2000/svg','style');
    style.textContent=CFG.nature.css+`\n*{animation-play-state:paused!important;animation-delay:${-t}s!important;transition:none!important}`;
    svg.prepend(style);
    const box=svg.getAttribute('viewBox').split(/\s+/).map(Number);
    const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'}));
    try {
      const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=url;});
      const drift=['turtle','duck','butterfly','bee'].includes(object.id)?Math.sin(t*.3)*12:0;
      const x=object.id==='bird'?((t*28+40)%(CFG.vw+100)-60):object.x*CFG.vw+drift;
      const width=object.width*CFG.vw;
      return {image,x,y:object.y*CFG.vh,width,height:width*box[3]/box[2]};
    } finally {URL.revokeObjectURL(url);}
  }));
}
window.renderFrameAt = async function(t) {
  const sequence=++renderSequence;
  const p=Math.max(0,Math.min(1,t/CFG.duration));
  const smooth=v=>{const x=Math.max(0,Math.min(1,v));return x*x*(3-2*x);};
  const walking=p<.42;
  const gesture=smooth((p-.42)/.18)*(1-smooth((p-.82)/.18));
  let actor=null;
  const scenery=await sceneryAt(t);
  if(CFG.lumi) {
    const svg=new DOMParser().parseFromString(CFG.lumi,'image/svg+xml').documentElement;
    const rotate=(name,angle,x,y)=>svg.querySelector('.'+name)?.setAttribute('transform',`rotate(${angle} ${x} ${y})`);
    const phase=t*(CFG.plan.action==='run'?15:10);
    const stride=walking?Math.sin(phase)*13:0;
    rotate('legL',stride,111,246);rotate('legR',-stride,149,246);
    rotate('armL',-stride,80,166);
    rotate('armRup',stride+gesture*(CFG.plan.action==='wave'?-152:-84),180,166);
    if(CFG.plan.action==='wave') rotate('armRfore',Math.sin(t*9)*gesture*18,198,208);
    if(CFG.plan.action==='raiseL') {rotate('armL',148*gesture,80,166);rotate('armRup',0,180,166);}
    if(CFG.plan.action==='raiseR') rotate('armRup',-152*gesture,180,166);
    if(CFG.plan.action==='think') {
      rotate('headG',7*gesture,130,148);
      rotate('armRup',-18*gesture,180,166);
      rotate('armRfore',-148*gesture,198,208);
      svg.querySelector('.pupils').setAttribute('transform',`translate(${4*gesture} ${-5*gesture})`);
      if(gesture>.5) {svg.querySelector('.mouthSmile').style.display='none';svg.querySelector('.mouthThink').style.display='block';}
    }
    if(CFG.plan.action==='pick') {
      rotate('whole',gesture*22,130,285);
      rotate('armRup',-gesture*30,180,166);
    }
    rotate('hairSway',Math.sin(t*2)*.7,130,40);
    rotate('starClip',Math.sin(t*2.5)*4,90,62);
    if((t%3.6)>3.43) svg.querySelector('.blink').setAttribute('transform','translate(0 104) scale(1 .08) translate(0 -104)');
    const amp=CFG.envelope?.[Math.min(CFG.envelope.length-1,Math.floor(t*CFG.fps))]||0;
    svg.querySelector('.mouthSmile').setAttribute('transform',`translate(130 137) scale(1 ${.3+amp*.8}) translate(-130 -137)`);
    const blob=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml'});
    const url=URL.createObjectURL(blob);
    try {
      actor=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('Cannot load Lumi SVG'));img.src=url;});
    } finally {URL.revokeObjectURL(url);}
  }
  if(sequence!==renderSequence) return canvas;
  drawBackground(t);
  scenery.forEach(o=>ctx.drawImage(o.image,o.x,o.y,o.width,o.height));
  if(actor) {
    const x=(170+330*smooth(p/.42))*(CFG.vw/960);
    const ground=428*(CFG.vh/540);
    const size=CFG.vh>CFG.vw?270:235;
    const bob=walking?Math.abs(Math.sin(t*10))*5:Math.sin(t*2)*1.5;
    ctx.drawImage(actor,x-size/2,ground-size*310/260-bob,size,size*310/260);
  }
  return canvas;
};
window.renderFrameBatch = async function(start,count,fps) {
  playing=false;
  const frames=[];
  for(let i=0;i<count;i++) {
    await window.renderFrameAt((start+i)/(fps||CFG.fps));
    frames.push(canvas.toDataURL('image/jpeg',.92).split(',')[1]);
  }
  return frames;
};
let playing=true, origin=null, pausedAt=0;
async function loop(ts) {
  if(origin===null) origin=ts;
  if(playing) {pausedAt=Math.min((ts-origin)/1000,CFG.duration);await window.renderFrameAt(pausedAt);}
  requestAnimationFrame(loop);
}
window.addEventListener('keydown',e=> {
  if(e.code==='Space'){e.preventDefault();playing=!playing;origin=performance.now()-pausedAt*1000;}
  if(e.code==='KeyR'){origin=performance.now();pausedAt=0;playing=true;}
});
window.renderFrameAt(0);
requestAnimationFrame(loop);
