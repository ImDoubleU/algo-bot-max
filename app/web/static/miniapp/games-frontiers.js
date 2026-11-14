/* Original active games. Fixed-step rules are replayed on the server. No idle income. */
(() => {
  'use strict';
  const games = [
    {id:'ocean',name:'Острова сокровищ',tag:'Довези находки домой',goal:120,unit:'очков',color:'blue',kind:'fun',
      hint:'Веди лодку за зверями. Редкие живут дальше от причала. Верни груз на базу, избегай акул и следи за запасом воздуха.'},
    {id:'slap',name:'Шлёп-арена',tag:'Последний на острове',goal:150,unit:'очков',color:'peach',kind:'fun',
      hint:'Подойди к сопернику и ударь в его сторону. Сбрасывай противников с острова, уходи от замаха и береги равновесие.'},
    {id:'plane',name:'Крылья на сборку',tag:'Собери. Испытай. Переделай.',goal:600,unit:'метров',color:'yellow',kind:'fun',
      hint:'Распредели 12 деталей между крыльями, мотором и баком. Запусти самолёт, проходи кольца, управляй наклоном и тягой.'},
    {id:'menagerie',name:'Чудо-эволюция',tag:'Из малыша в великана',goal:1200,unit:'очков',color:'mint',kind:'fun',
      hint:'Собирай плоды и ешь существ меньше себя. Уходи от крупных. При эволюции выбирай способность: панцирь, скорость или притяжение.'}
  ].map(g=>({...g,icon:g.id,fresh:true,tutorial:g.hint}));
  const ids=new Set(games.map(g=>g.id)), clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  const species=['Пыжик','Грибопёс','Лимоногусь','Мохолап','Котокрыл','Пузырёк','Дракоша','Облакозуб','Солнцехвост','Звездоглот','Туманорог','Лунный кит'];
  const chapters=['Первый выход','За знакомый берег','Необычные находки','Опасный маршрут','Сила команды','Большая экспедиция'];
  function create(w,setup,H) {
    const chapter=w.journey?.chapter||0;
    const f=w.frontier={kind:w.id,phase:'play',x:180,y:355,vx:0,vy:0,ax:0,ay:0,aimX:180,aimY:100,
      invincible:0,cool:0,actionUntil:0,delivered:0,combo:0,chapter,damages:0,toast:'',toastUntil:0,facingX:0,facingY:-1,aimMode:'move'};
    if(w.id==='ocean')Object.assign(f,{air:100,cargo:[],capacity:3,bank:0,boat:1,items:[],sharks:[],islands:[{x:75,y:205,r:28},{x:288,y:160,r:25}]});
    if(w.id==='ocean'){
      for(let i=0;i<22;i++)f.items.push(seaItem(w,H,i));
      for(let i=0;i<3+Math.floor(chapter/2);i++)f.sharks.push({x:45+i*100,y:85+i*55,vx:0,vy:0,phase:H.random(w)*6,alert:0});
    }
    if(w.id==='slap'){
      Object.assign(f,{x:180,y:250,enemies:[],wave:1,glove:0,hits:0,kills:0,particles:[]});
      spawnWave(w,H);
    }
    if(w.id==='plane')Object.assign(f,{phase:'build',wing:4,engine:4,tank:4,x:0,y:220,angle:0,vx:58,vy:0,fuel:100,
      boost:false,tilt:0,gates:[],rings:0,launched:false,landed:0});
    if(w.id==='plane'&&setup.planeBuild){const b=setup.planeBuild;
      if(['wing','engine','tank'].every(k=>Number.isInteger(b[k])&&b[k]>=1&&b[k]<=8)&&b.wing+b.engine+b.tank<=12)for(const k of ['wing','engine','tank'])f[k]=b[k];
    }
    if(w.id==='menagerie'){
      Object.assign(f,{x:180,y:220,xp:0,level:1,fruit:[],creatures:[],speed:0,magnet:0,armor:0,dash:0,health:3,mutations:0,rebirths:0});
      for(let i=0;i<40;i++)f.fruit.push({x:20+H.random(w)*320,y:70+H.random(w)*335,type:i%4});
      for(let i=0;i<5;i++)f.creatures.push(wild(w,H,i));
    }
    if(w.id==='evolve'){
      Object.assign(f,{phase:'play',tile:30,oxygen:36,maxOxygen:36,cargo:[],team:[],capacity:4,map:[],selected:-1,
        explored:[],sector:0,moves:0,scan:0,saved:0,merges:0,shield:0});
      rescueMap(w,H);
    }
    w.details.frontierRules=1;
  }
  function note(w,H,text){const f=w.frontier;f.toast=text;f.toastUntil=w.time+2;H.emit(w,'frontier',{text});}
  function seaItem(w,H,i){const level=i%7===0?4:i%3===0?2:1;return {x:22+H.random(w)*316,y:(level===4?50:level===2?130:220)+H.random(w)*85,level,taken:false};}
  function wild(w,H,i){const f=w.frontier,e={x:20+H.random(w)*320,y:65+H.random(w)*330,level:Math.min(12,Math.max(1,f.level-1+(i%3))),phase:H.random(w)*6,stun:0};
    if(e.level>f.level&&distance(e,f)<100)e.x=e.x<180?20:340;return e;
  }
  function spawnWave(w,H){const f=w.frontier;for(let i=0;i<Math.min(7,2+f.wave);i++){
    const a=(i/(2+f.wave))*Math.PI*2,r=70+H.random(w)*35;
    f.enemies.push({x:180+Math.cos(a)*r,y:225+Math.sin(a)*r,vx:0,vy:0,stun:0,windup:0,cool:1+i*.3,health:1+Math.floor((f.wave-1)/3),id:i});
  }}
  function rescueMap(w,H){
    const f=w.frontier;f.tile=30;f.explored=[30,24,31];f.oxygen=f.maxOxygen;
    // A connected grid; obstacles cost oxygen but never make a target unreachable.
    f.map=Array.from({length:36},(_,i)=>({kind:i===30?'base':i%6===0||i>=30?'path':H.random(w)<.22?'hazard':'path',level:0}));
    const slots=H.shuffled(w,Array.from({length:29},(_,i)=>i+1).filter(i=>i!==24));
    for(let n=0;n<9;n++)f.map[slots[n]]={kind:'beast',level:1+Math.floor(H.random(w)*Math.min(9,2+f.sector+f.chapter))};
    for(let n=9;n<12;n++)f.map[slots[n]]={kind:'air',level:0};
    f.map[30]={kind:'base',level:0};
  }
  function has(id){return ids.has(id);}
  function active(w){return !!w.frontier;}
  function frozen(w){return !!w.frontier&&w.frontier.phase!=='play';}
  function motion(f,dt,speed,drag=7){
    const len=Math.max(1,Math.hypot(f.ax,f.ay));f.vx+=(f.ax/len*speed-f.vx)*Math.min(1,dt*drag);f.vy+=(f.ay/len*speed-f.vy)*Math.min(1,dt*drag);
    f.x+=f.vx*dt;f.y+=f.vy*dt;
  }
  function step(w,H){
    const f=w.frontier;if(!f||f.phase!=='play')return;
    const dt=H.DT;f.cool=Math.max(0,f.cool-dt);f.invincible=Math.max(0,f.invincible-dt);
    if(w.id==='ocean')seaStep(w,H);
    if(w.id==='slap')slapStep(w,H);
    if(w.id==='plane')flightStep(w,H);
    if(w.id==='menagerie')wildStep(w,H);
    if(w.id==='evolve'&&ArcadeClock.time(w)>=(w.journey?.seconds||240))H.end(w,'Экспедиция завершена');
    if(has(w.id)&&w.id!=='plane'&&ArcadeClock.time(w)>=(w.journey?.seconds||180))H.end(w,'Экспедиция завершена');
    w.details.delivered=f.delivered;w.details.damages=f.damages;
    if(w.id==='plane'&&f.launched)w.details.blueprint={wing:f.wing,engine:f.engine,tank:f.tank};
    if(w.id==='evolve'){w.details.rescued=f.saved;w.details.species=[...new Set(f.team)];}
  }
  function seaStep(w,H){
    const f=w.frontier,dt=H.DT,boost=f.actionUntil>w.time;
    motion(f,dt,(65+f.boat*8)*(boost?1.8:1),3);
    f.x=clamp(f.x,17,343);f.y=clamp(f.y,55,390);
    const safe=f.y>345||f.islands.some(i=>distance(f,i)<i.r+12);
    f.air=clamp(f.air+(safe?22:-1.2-f.cargo.length*.22)*dt,0,100);
    if(f.y>345&&f.cargo.length){
      const n=f.cargo.reduce((a,v)=>a+v*10,0);w.score+=n;f.bank+=n;f.delivered+=f.cargo.length;f.cargo=[];
      const boat=1+Math.floor(w.score/120);if(boat>f.boat){f.boat=boat;f.capacity=Math.min(7,3+Math.floor(boat/2));note(w,H,'Лодка улучшена!');}else note(w,H,'Груз спасён · +'+n);
    }
    for(const it of f.items){
      if(!it.taken&&f.cargo.length<f.capacity&&distance(f,it)<20){it.taken=true;it.respawn=w.time+12;f.cargo.push(it.level);H.emit(w,'collect',{x:it.x,y:it.y});}
      if(it.taken&&w.time>=it.respawn)Object.assign(it,seaItem(w,H,Math.floor(H.random(w)*21)));
    }
    for(const s of f.sharks){
      s.phase+=dt;const hunt=!safe&&distance(f,s)<100,angle=hunt?Math.atan2(f.y-s.y,f.x-s.x):s.phase*.6;
      s.x=clamp(s.x+Math.cos(angle)*dt*(hunt?55+f.chapter*4:22),18,342);s.y=clamp(s.y+Math.sin(angle)*dt*(hunt?55+f.chapter*4:22),55,330);s.alert=hunt;s.heading=angle;
      if(!safe&&distance(s,f)<23&&!f.invincible){f.damages++;f.invincible=2;f.air=Math.max(0,f.air-18);f.cargo.pop();f.vx*= -1;f.vy*= -1;note(w,H,'Акула! К острову!');}
    }
    if(f.air<=0){f.cargo=[];H.end(w,'Воздух закончился. Спасённый груз остался на базе.');}
  }
  function slapStep(w,H){
    const f=w.frontier,dt=H.DT,radius=Math.max(98,154-f.wave*3);
    motion(f,dt,100,3.5);
    if(f.aimMode==='move'){f.aimX=f.x+f.facingX*80;f.aimY=f.y+f.facingY*80;}
    for(const e of f.enemies){
      e.cool-=dt;e.stun=Math.max(0,e.stun-dt);
      if(e.stun<=0){const a=Math.atan2(f.y-e.y,f.x-e.x),d=distance(e,f);
        if(d>34){e.vx+=(Math.cos(a)*(35+f.wave*4)-e.vx)*dt*3;e.vy+=(Math.sin(a)*(35+f.wave*4)-e.vy)*dt*3;}
        else {e.vx*=.94;e.vy*=.94;if(e.cool<=0&&!e.windup)e.windup=.6;}
        if(e.windup){e.windup-=dt;if(e.windup<=0){e.windup=0;e.cool=1.7;if(d<58&&!f.invincible){f.vx+=Math.cos(a)*260;f.vy+=Math.sin(a)*260;f.invincible=.45;f.damages++;H.emit(w,'hit',{x:f.x,y:f.y});}}}
      }else {e.vx*=.986;e.vy*=.986;}
      e.x+=e.vx*dt;e.y+=e.vy*dt;
    }
    const fallen=f.enemies.filter(e=>Math.hypot(e.x-180,e.y-225)>radius+12);
    if(fallen.length){f.kills+=fallen.length;w.score+=fallen.length*25;f.enemies=f.enemies.filter(e=>!fallen.includes(e));note(w,H,'За борт! +'+fallen.length*25);}
    if(!f.enemies.length){f.wave++;f.glove=Math.min(2,Math.floor(w.score/150));f.x=180;f.y=250;f.vx=f.vy=0;spawnWave(w,H);note(w,H,'Раунд '+f.wave);}
    if(Math.hypot(f.x-180,f.y-225)>radius+14)H.end(w,'Ты вылетел с арены');
    w.level=Math.min(10,f.wave);w.details.kills=f.kills;
  }
  function ground(x){return 338+Math.sin(x*.007)*27+Math.sin(x*.017)*12;}
  function flightStep(w,H){
    const f=w.frontier,dt=H.DT;
    f.angle=clamp(f.angle+(f.tilt*1.1-f.angle*.25)*dt,-.85,.85);
    const thrust=f.boost&&f.fuel>0;f.fuel=Math.max(0,f.fuel-(thrust?5.5:1.2)*dt/(.6+f.tank*.16));
    f.vx=clamp(f.vx+((thrust?30+f.engine*7:5)-f.vx*.12-Math.max(0,-Math.sin(f.angle))*25)*dt,20,190);
    const lift=(f.vx*(.35+f.wing*.08))*(1-Math.abs(f.angle)*.35);
    f.vy=clamp(f.vy+(58-lift+Math.sin(f.angle)*65-f.vy*.7)*dt,-100,120);
    f.x+=f.vx*dt;f.y=clamp(f.y+f.vy*dt,65,420);
    if(f.gates.length<5){const x=f.x+260+f.gates.length*240;f.gates.push({x,y:100+H.random(w)*150,passed:false});}
    for(const g of f.gates)if(!g.passed&&Math.abs(g.x-f.x)<22&&Math.abs(g.y-f.y)<36){g.passed=true;f.rings++;f.fuel=Math.min(100,f.fuel+12);H.emit(w,'collect',{x:120,y:f.y});}
    f.gates=f.gates.filter(g=>g.x>f.x-100);
    w.score=Math.floor(f.x+f.rings*50);w.details.rings=f.rings;
    if(f.y>=ground(f.x)-12||f.fuel<=0&&f.y>ground(f.x)-30)H.end(w,'Полёт завершён');
    if(ArcadeClock.time(w)>=180)H.end(w,'Дальний перелёт завершён');
  }
  function wildStep(w,H){
    const f=w.frontier,dt=H.DT;
    motion(f,dt,75+f.speed*18+(f.actionUntil>w.time?90:0));f.x=clamp(f.x,15,345);f.y=clamp(f.y,70,408);
    const range=15+f.magnet*12;
    for(const it of f.fruit)if((it.sleep||0)<=w.time&&distance(f,it)<range&&Math.hypot(f.vx,f.vy)>8){
      f.xp+=3;w.score+=5*(f.rebirths+1);it.x=18+H.random(w)*324;it.y=70+H.random(w)*330;it.sleep=w.time+4+f.level*.2;H.emit(w,'collect',{x:f.x,y:f.y});
    }
    for(let i=0;i<f.creatures.length;i++){
      const e=f.creatures[i];e.phase+=dt;const angle=distance(e,f)<100?Math.atan2(f.y-e.y,f.x-e.x)+(e.level>f.level?0:Math.PI):e.phase;
      e.x=clamp(e.x+Math.cos(angle)*(15+e.level*3)*dt,20,340);e.y=clamp(e.y+Math.sin(angle)*(15+e.level*3)*dt,70,400);
      if(distance(e,f)<20){
        if(e.level<f.level||f.actionUntil>w.time&&e.level===f.level){f.xp+=15;w.score+=30*e.level*(f.rebirths+1);f.creatures[i]=wild(w,H,i);H.emit(w,'evolve',{x:f.x,y:f.y});}
        else if(e.level>f.level&&!f.invincible){f.health--;f.damages++;f.invincible=2+f.armor*.5;f.vx=(f.x-e.x)*8;f.vy=(f.y-e.y)*8;if(f.health<=0)H.end(w,'Приключение завершено');}
      }
    }
    const target=25+f.level*15;
    if(f.xp>=target&&f.level<12){f.xp-=target;f.level++;f.phase='mutation';f.ax=f.ay=f.vx=f.vy=0;f.mutations++;
      while(f.creatures.length<Math.min(12,4+f.level))f.creatures.push(wild(w,H,f.creatures.length));
      note(w,H,'Новый вид: '+species[f.level-1]);}
    w.level=Math.min(10,f.level);w.details.species=f.level;w.details.mutations=f.mutations;
  }
  function rescueMove(w,i,H){
    const f=w.frontier;if(f.cool||!Number.isInteger(i)||i<0||i>=36)return false;
    const x=f.tile%6,y=Math.floor(f.tile/6);if(Math.abs(i%6-x)+Math.abs(Math.floor(i/6)-y)!==1)return false;
    const t=f.map[i],cost=t.kind==='hazard'?(f.team.some(v=>v>=4)?1:3):1;
    if(t.kind==='beast'&&f.cargo.length>=f.capacity){note(w,H,'Рюкзак полон. Вернись на базу');return false;}
    f.tile=i;f.moves++;f.cool=.14;f.oxygen-=cost;
    for(const n of [i,i-6,i+6,i%6?i-1:-1,i%6<5?i+1:-1])if(n>=0&&n<36&&!f.explored.includes(n))f.explored.push(n);
    if(t.kind==='air'){f.oxygen=Math.min(f.maxOxygen,f.oxygen+12);t.kind='path';note(w,H,'Воздух +12');}
    if(t.kind==='beast'){f.cargo.push(t.level);t.kind='path';H.emit(w,'collect',{x:i%6*52+50,y:Math.floor(i/6)*48+90});}
    if(i===30){
      f.oxygen=f.maxOxygen;
      if(f.cargo.length){const points=f.cargo.reduce((a,v)=>a+v*12,0);w.score+=points;f.saved+=f.cargo.length;f.delivered=f.saved;
        f.team.push(...f.cargo);f.cargo=[];f.team=f.team.sort((a,b)=>b-a).slice(0,12);
        // Each pair becomes a stronger companion. Its passive applies next sortie.
        for(let v=1;v<9;v++)while(f.team.filter(n=>n===v).length>=2){f.team.splice(f.team.indexOf(v),1);f.team.splice(f.team.indexOf(v),1);f.team.push(v+1);f.merges++;}
        f.maxOxygen=36+Math.min(18,f.saved*2);f.capacity=Math.min(7,4+Math.floor(f.saved/6));
        note(w,H,'Спасено '+f.saved+' · +'+points);
        if(f.map.every(n=>n.kind!=='beast')){f.sector++;rescueMap(w,H);note(w,H,'Новый сектор '+(f.sector+1));}
      }
    }
    w.merges=f.merges;w.details.rescued=f.saved;
    if(f.oxygen<=0)H.end(w,'Воздух закончился. Спасённые звери в безопасности.');return true;
  }
  function input(w,a,H){
    const f=w.frontier;if(!f)return false;
    if(a.type==='steer'&&typeof a.x==='number'&&typeof a.y==='number'&&Number.isFinite(a.x)&&Number.isFinite(a.y)){
      f.ax=clamp(a.x,-1,1);f.ay=clamp(a.y,-1,1);
      if(w.id==='slap'&&(f.ax||f.ay)){f.facingX=f.ax;f.facingY=f.ay;f.aimMode='move';}
      return true;
    }
    if(a.type==='aim'&&Number.isFinite(a.x)&&Number.isFinite(a.y)){f.aimX=clamp(a.x,0,360);f.aimY=clamp(a.y,0,430);f.aimMode='point';return true;}
    if(w.id==='evolve'){
      if(a.type==='cell')return rescueMove(w,a.i,H);
      if(a.type==='scan'&&f.scan<=w.time){f.scan=w.time+12;f.scanUntil=w.time+3;note(w,H,'Сектор просканирован');return true;}
      return false;
    }
    if(w.id==='plane'){
      if(a.type==='build'&&f.phase==='build'&&['wing','engine','tank'].includes(a.part)&&Number.isInteger(a.value)&&a.value>=1&&a.value<=8){
        const total=f.wing+f.engine+f.tank-f[a.part]+a.value;if(total>12)return false;f[a.part]=a.value;return true;
      }
      if(a.type==='launch'&&f.phase==='build'){f.phase='play';f.launched=true;return true;}
      if(a.type==='flight'&&f.phase==='play'&&[-1,0,1].includes(a.tilt)&&typeof a.boost==='boolean'){f.tilt=a.tilt;f.boost=a.boost;return true;}
    }
    if(w.id==='menagerie'){
      if(a.type==='mutate'&&f.phase==='mutation'&&['speed','magnet','armor','dash'].includes(a.trait)&&f[a.trait]<(a.trait==='dash'?4:3)){
        f[a.trait]++;f.health=Math.min(5,3+f.armor);f.phase='play';H.emit(w,'evolve',{x:f.x,y:f.y});return true;
      }
      if(a.type==='rebirth'&&f.level>=6&&f.rebirths<2){f.rebirths++;f.level=1;f.xp=0;f.health=3+f.armor;f.phase='play';f.creatures=f.creatures.map((_,i)=>wild(w,H,i));return true;}
    }
    if(a.type==='ability'&&f.phase==='play'&&f.cool<=0){
      if(w.id==='slap'){
        f.cool=.5;f.actionUntil=w.time+.2;f.hits++;const aim=Math.atan2(f.aimY-f.y,f.aimX-f.x);
        for(const e of f.enemies)if(distance(e,f)<68){
          const angle=Math.atan2(e.y-f.y,e.x-f.x),delta=Math.atan2(Math.sin(angle-aim),Math.cos(angle-aim));
          if(Math.abs(delta)>1.45)continue;const strength=(200+f.glove*35)/(1+(e.health-1)*.3);e.vx=Math.cos(angle)*strength;e.vy=Math.sin(angle)*strength;e.stun=.85;e.windup=0;H.emit(w,'hit',{x:e.x,y:e.y});
        }return true;
      }
      if(w.id==='ocean'){f.cool=7;f.actionUntil=w.time+1.3;return true;}
      if(w.id==='menagerie'){f.cool=6-f.dash*.7;f.actionUntil=w.time+1+f.dash*.2;return true;}
    }
    if(w.id==='slap'&&a.type==='glove'&&Number.isInteger(a.value)&&a.value>=0&&a.value<=2&&w.tick===0){f.glove=a.value;return true;}
    return false;
  }
  function specs(){return Object.fromEntries(games.map(g=>[g.id,{name:g.name,chapters,goals:
    g.id==='ocean'?[30,70,120,180,260,360]:g.id==='slap'?[25,75,150,225,325,450]:g.id==='plane'?[250,450,650,850,1100,1400]:[100,250,450,700,1000,1500],
    power:{plane:'Запас топлива',ocean:'Запас воздуха',slap:'Защитное поле',menagerie:'Аптечка'}[g.id],
    action:{plane:'Восстановить 35 топлива',ocean:'Восстановить 35 воздуха',slap:'Защита на 3 секунды',menagerie:'Восстановить одно здоровье'}[g.id],
    rules:['Первое испытание','Дальше от базы','Опасный маршрут','Большая цель'],reward:'Знаки экспедиции'}]));}
  function tutorial(w){const f=w.frontier;
    if(w.id==='ocean'){f.items=[{x:180,y:310,level:1,taken:false}];f.sharks=[];}
    if(w.id==='slap')f.enemies=[{x:180,y:145,vx:0,vy:0,stun:0,windup:0,cool:10,health:1,id:1}];
    if(w.id==='menagerie'){f.xp=37;f.fruit[0]={x:180,y:190,type:0};f.creatures=[];}
    if(w.id==='evolve'){f.map[24]={kind:'beast',level:1};f.explored.push(24);}
  }
  function tutorialDone(w){const f=w.frontier;return w.id==='ocean'?f.delivered>0:w.id==='slap'?f.kills>0:w.id==='plane'?f.launched&&w.score>=150:w.id==='menagerie'?f.level>=2&&f.phase==='play':f.saved>0;}
  window.ArcadeFrontiers={games,has,active,frozen,create,step,input,specs,species,ground,tutorial,tutorialDone};
})();
