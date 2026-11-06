/* Small deterministic benchmarks. Separate from school rewards and arcade standings. */
(() => {
  'use strict';
  const catalogue={
    number:{name:'Память на числа',unit:'цифр',limit:300,hint:'Запомни число и введи его, когда оно исчезнет.'},
    verbal:{name:'Знакомое слово',unit:'верных ответов',limit:180,hint:'Реши, было ли это слово раньше в этой попытке. Три ошибки завершают тест.'},
    sequence:{name:'Световой маршрут',unit:'шагов',limit:300,hint:'Повтори последовательность вспышек в том же порядке.'},
    spatial:{name:'Поворот в уме',unit:'верных ответов',limit:90,hint:'Найди повёрнутую фигуру. Дальше — больше вариантов и меньше времени на ответ. Три ошибки завершают тест.'}
  };
  const words='арбуз автобус адрес азбука акула ананас апельсин берег билет блокнот болото ботинок бумага вагон ведро ветер вилка вокзал воробей время гараж газета гитара глобус город грибы груша двор дерево диван дорога доска дракон енот завод замок звезда зеркало зонт игрушка индюк искра кабина камень карандаш карман картина качели книга колесо комета корабль корзина космос котёнок краска кролик крыша кувшин кухня лампа лента лестница лиса ложка луна лыжи магазин маяк медведь метро молоко молоток морковь мост мяч наука облако огород озеро океан орбита остров палатка пальма парус песок печенье пещера пианино письмо планета платок поезд подарок подушка полка посуда почта проект птица пузырь пуговица радуга ракета ракушка растение река рельсы рисунок робот ромашка рюкзак самолёт сапог сахар свеча свитер семя скала скамейка скрипка слон снег собака солнце сосна стакан станция стена стол сумка театр телефон тетрадь трава тропа труба туман тыква улица улитка утро фонарь фрукты хлеб цветок чемодан чайник черепаха шкаф школа щётка экран этаж яблоко якорь ящик'.split(' ');
  const shapes=[[[0,0],[0,1],[0,2],[1,2]],[[1,0],[1,1],[1,2],[0,2]],
    [[0,0],[1,0],[1,1],[2,1]],[[1,0],[2,0],[0,1],[1,1]],
    [[0,0],[1,0],[2,0],[1,1]],[[0,0],[0,1],[1,1],[1,2]],
    [[0,0],[0,1],[0,2],[1,2],[2,2]],[[0,0],[1,0],[0,1],[1,1],[0,2]],
    [[1,0],[0,1],[1,1],[1,2],[2,2]],[[0,0],[1,0],[2,0],[1,1],[1,2]],
    [[0,0],[0,1],[1,1],[2,1],[2,2]],[[0,0],[1,0],[1,1],[1,2],[2,2]]];
  const random=w=>{let x=w.rng;x^=x<<13;x^=x>>>17;x^=x<<5;w.rng=x>>>0;return w.rng/4294967296;};
  const pick=(w,a)=>a[Math.floor(random(w)*a.length)];
  const normalize=s=>{const mx=Math.min(...s.map(p=>p[0])),my=Math.min(...s.map(p=>p[1]));return s.map(([x,y])=>[x-mx,y-my]);};
  const rotate=(s,n)=>{let out=s.map(p=>p.slice());for(let i=0;i<n;i++)out=out.map(([x,y])=>[-y,x]);return normalize(out);};
  const key=s=>normalize(s).map(p=>p.join(',')).sort().join(';');
  const signatures=new WeakMap();
  const canonical=s=>{if(!signatures.has(s))signatures.set(s,[0,1,2,3].map(n=>key(rotate(s,n))).sort()[0]);return signatures.get(s);};
  let largerShapes=null;
  function spatialPool(size) {
    if(size<=5)return shapes.filter(s=>s.length===size);
    if(!largerShapes) {
      largerShapes={1:[[[0,0]]]};
      for(let n=2;n<=7;n++) {
        const unique=new Map();
        for(const s of largerShapes[n-1])for(const [x,y] of s)for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
          const next=[x+dx,y+dy];if(s.some(p=>p[0]===next[0]&&p[1]===next[1]))continue;
          const grown=normalize([...s,next]),k=canonical(grown);if(!unique.has(k))unique.set(k,grown);
        }
        largerShapes[n]=[...unique.values()];
      }
    }
    largerShapes['ready'+size]??=largerShapes[size].filter(s=>new Set([0,1,2,3].map(n=>key(rotate(s,n)))).size===4);
    return largerShapes['ready'+size];
  }
  function spatialDifficulty(score) {
    const level=score<5?1:score<12?2:score<20?3:4;
    return {level,cards:[4,6,8,8][level-1],seconds:[12,10,8,6][level-1],cells:level+3};
  }
  function question(w) {
    w.since=w.tick;w.phase='answer';
    if(w.test==='number') {
      w.number=String(1+Math.floor(random(w)*9));
      for(let i=1;i<=w.score;i++)w.number+=Math.floor(random(w)*10);
      w.phase='show';w.until=w.tick+Math.ceil((1+(w.score+1)*.6)*60);
    }
    if(w.test==='verbal') {
      const seen=Object.keys(w.seen),fresh=words.filter(v=>!w.seen[v]);
      w.word=seen.length&&(!fresh.length||random(w)<.42)?pick(w,seen):pick(w,fresh);
    }
    if(w.test==='sequence') {
      let next=Math.floor(random(w)*9);if(next===w.pattern.at(-1))next=(next+1)%9;
      w.pattern.push(next);w.index=0;w.phase='show';w.until=w.tick+w.pattern.length*34+24;
    }
    if(w.test==='spatial') {
      const rules=w.rules>=2?spatialDifficulty(w.score):null;
      if(rules){w.difficulty=rules;w.until=w.tick+rules.seconds*60;}
      const pool=rules?spatialPool(rules.cells):shapes.filter(s=>s.length===(w.score<6?4:5));
      w.shape=pick(w,pool);const correct=rotate(w.shape,1+Math.floor(random(w)*3)),signature=canonical(w.shape);
      const wrong=pool.filter(s=>canonical(s)!==signature),choices=[correct],used=new Set([key(correct)]);
      const candidates=wrong.flatMap(s=>[0,1,2,3].map(n=>rotate(s,n)));
      const count=rules?.cards||4;
      while(choices.length<count){const i=Math.floor(random(w)*candidates.length),s=candidates.splice(i,1)[0];if(!used.has(key(s))){choices.push(s);used.add(key(s));}}
      w.correct=Math.floor(random(w)*count);w.choices=choices;
      [w.choices[0],w.choices[w.correct]]=[w.choices[w.correct],w.choices[0]];
    }
  }
  function create(setup) {
    if(!catalogue[setup.test])throw Error('Unknown benchmark');
    const w={test:setup.test,rules:setup.rules||1,rng:setup.seed>>>0||17,tick:0,time:0,score:0,mistakes:0,
      ended:false,phase:'show',seen:{},pattern:[],index:0,rounds:0};question(w);return w;
  }
  function advance(w,ticks) {
    for(let i=0;i<ticks&&!w.ended;i++) {
      w.tick++;w.time=w.tick/60;
      if(w.phase==='show'&&w.tick>=w.until){w.phase='answer';w.since=w.tick;}
      if(w.time>=catalogue[w.test].limit)w.ended=true;
      if(!w.ended&&w.test==='spatial'&&w.rules>=2&&w.tick>=w.until) {
        w.mistakes++;w.rounds++;w.timeouts=(w.timeouts||0)+1;w.lastOutcome='timeout';
        if(w.mistakes>=3)w.ended=true;else question(w);
      }
    }
  }
  function input(w,a) {
    if(w.ended||w.phase!=='answer'||w.tick-w.since<6)return false;
    let ok=false;
    if(w.test==='number'&&a.type==='number'&&typeof a.value==='string'&&a.value.length<=32) {
      ok=a.value.trim()===w.number;
      if(!ok){w.expected=w.number;w.given=a.value.trim();w.ended=true;return true;}
      w.score++;if(w.score>=24)w.ended=true;else question(w);return true;
    }
    if(w.test==='verbal'&&a.type==='word'&&['new','seen'].includes(a.value)) {
      ok=(a.value==='seen')===!!w.seen[w.word];w.seen[w.word]=true;
    } else if(w.test==='sequence'&&a.type==='cell'&&Number.isInteger(a.i)&&a.i>=0&&a.i<9) {
      if(a.i!==w.pattern[w.index]){w.ended=true;return true;}
      w.index++;if(w.index===w.pattern.length){w.score=w.pattern.length;if(w.score>=32)w.ended=true;else question(w);}
      return true;
    } else if(w.test==='spatial'&&a.type==='choice'&&Number.isInteger(a.i)&&a.i>=0&&a.i<w.choices.length) {
      ok=a.i===w.correct;
    } else return false;
    w.lastOutcome=ok?'correct':'wrong';w.rounds++;if(ok)w.score++;else w.mistakes++;
    if(w.mistakes>=3)w.ended=true;else question(w);return true;
  }
  function report(w){return {test:w.test,score:w.score,complete:w.ended,timeMs:Math.round(w.time*1000),
    mistakes:w.mistakes,rounds:w.rounds,expected:w.expected||'',given:w.given||'',
    ...(w.test==='spatial'&&w.rules>=2?{rules:2,level:w.difficulty.level,timeouts:w.timeouts||0}:{})};}
  function verify(setup,events,ticks) {
    if(!Array.isArray(events)||events.length>5000||!Number.isInteger(ticks)||ticks<0||ticks>36000)throw Error('Invalid benchmark replay');
    const w=create(setup);let previous=0;
    for(const a of events){if(!Number.isInteger(a.t)||a.t<previous||a.t>ticks)throw Error('Invalid action time');
      advance(w,a.t-w.tick);if(w.ended)throw Error('Action after test');input(w,a);previous=a.t;}
    advance(w,ticks-w.tick);return report(w);
  }
  window.ArcadeBenchmarks={catalogue,create,advance,input,report,verify,spatialDifficulty};
})();
