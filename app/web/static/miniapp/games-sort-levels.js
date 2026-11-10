/* Versioned Ball Sort adventures. The browser and server execute these same rules. */
(() => {
    'use strict';
    const chapters=['Цвет к цвету','Маленькие колбы','Под замком','Секретные слои','Точные ходы','Большая лаборатория'];
    const icons={classic:'●',small:'◒',sealed:'⌑',hidden:'?',precision:'↔',final:'★'};
    function mission(stage) {
        if(!Number.isInteger(stage)||stage<1||stage>48)throw Error('Unknown sort level');
        const chapter=Math.floor((stage-1)/8),variant=(stage-1)%8,boss=variant===7,
            colors=Math.min(7,[3,3,4,4,5,6][chapter]+Math.floor(variant/(chapter===1?2:3))),
            small=chapter===1||(chapter>=2&&variant>=4),
            sealed=chapter===2||(chapter>=4&&variant%2===1),
            hidden=chapter===3||chapter===5,
            precise=chapter>=4,
            capacity=small?(variant%3===0?3:2):4,
            kind=['classic','small','sealed','hidden','precision','final'][chapter],
            rule=chapter===0?'Собери каждый цвет отдельно':chapter===1?`В запасной колбе ${capacity} места`:
                chapter===2?'Собери цвет и открой замок':chapter===3?'Открой скрытые шарики':
                chapter===4?'Уложись в число ходов':'Соедини все правила',
            next=chapter<5?{stage:(chapter+1)*8+1,name:chapters[chapter+1],kind:Object.keys(icons)[chapter+1]}:null;
        return {game:'sort',stage,chapter,variant,title:chapters[chapter],routeVersion:2,
            goal:chapter===5?(boss?3:2):boss?2:1,seconds:900,colors,small,sealed,hidden,precise,
            capacity,sealGoal:sealed&&variant>=5?2:1,
            hiddenDepth:hidden?(variant<2?'bottom':'all'):null,
            moves:0,rule,kind,icon:icons[kind],boss,next,
            power:'Запасная колба',action:'Добавить колбу на текущую задачу'};
    }
    const capacity=(w,i)=>w.sortCaps?.[i]??4;
    const done=t=>t.length===4&&t.every(c=>c===t[0]);
    const sealed=(w,i)=>!!w.sortSeals?.[i]&&!w.sortSealUnlocked;
    const canPour=(w,from,to)=>from!==to&&!!w.tubes[from]?.length&&!!w.tubes[to]&&
        !sealed(w,from)&&!sealed(w,to)&&w.tubes[to].length<capacity(w,to)&&
        (!w.tubes[to].length||w.tubes[to].at(-1)===w.tubes[from].at(-1));
    function grouped(tubes,caps,a) {
        const from=tubes[a.from],to=tubes[a.to];
        if(!from.length||to.length>=caps[a.to]||(to.length&&to.at(-1)!==from.at(-1)))return false;
        const color=from.at(-1);
        do{to.push(from.pop());}while(from.length&&from.at(-1)===color&&to.length<caps[a.to]);
        return true;
    }
    function puzzle(w,H,m,round) {
        const count=Math.min(7,m.colors+(m.boss&&round>0?1:0)),
            order=H.shuffled(w,Array.from({length:count},(_,i)=>i)),
            tubes=order.map(c=>[c,c,c,c]).concat([[],[]]),
            caps=Array(count).fill(4).concat([m.capacity,4]);
        let solution=[],previous='',turns=2+Math.floor(m.variant/2)+m.chapter;
        for(let turn=0;turn<turns;turn++){
            let chosen=null;
            if(turn===0){
                const k=Math.min(m.capacity,1+Math.min(2,m.chapter+Math.floor(m.variant/3)));
                chosen={cycle:H.shuffled(w,Array.from({length:count},(_,i)=>i)),k,key:'first'};
            }
            for(let attempt=0;attempt<50&&!chosen;attempt++){
                const ids=H.shuffled(w,Array.from({length:count},(_,i)=>i)),
                    size=2+Math.floor(H.random(w)*Math.min(3,count-1)),cycle=ids.slice(0,size),
                    k=1+Math.floor(H.random(w)*Math.min(3,m.capacity)),
                    top=cycle.map(i=>tubes[i].at(-1));
                if(new Set(top).size!==cycle.length)continue;
                if(cycle.some((i,n)=>{
                    const t=tubes[i],incoming=top[(n+1)%cycle.length];
                    return t.length<=k||t.slice(-k-1).some(c=>c!==top[n])||t.at(-k-1)===incoming;
                }))continue;
                const key=cycle.join(':')+':'+k;
                if(key===previous)continue;
                chosen={cycle,k,key};
            }
            if(!chosen)break;
            const {cycle,k,key}=chosen;
            const moves=[[cycle[0],count],...cycle.slice(1).map((i,n)=>[i,cycle[n]]),[count,cycle.at(-1)]];
            for(const [from,to] of moves){
                tubes[to].push(...tubes[from].splice(-k));
                solution.unshift({type:'pour',from:to,to:from});
            }
            previous=key;
        }
        // A deterministic fallback always makes a real puzzle, including unlucky seeds.
        if(tubes.every(t=>!t.length||done(t))){
            for(const [from,to] of [[0,count],[1,0],[count,1]]){
                tubes[to].push(tubes[from].pop());solution.unshift({type:'pour',from:to,to:from});
            }
        }
        // Remove closed loops in the reference path; stars should not reward a generator detour.
        const copy=tubes.map(t=>t.slice()),path=[],seen=new Map([[JSON.stringify(copy),0]]);
        for(const a of solution){
            if(!grouped(copy,caps,a))throw Error('Invalid sort construction');
            const key=JSON.stringify(copy);
            if(seen.has(key)){
                path.splice(seen.get(key));
                for(const [state,index] of seen)if(index>path.length)seen.delete(state);
            }else{path.push(a);seen.set(key,path.length);}
            if(copy.every(t=>!t.length||done(t)))break;
        }
        if(!copy.every(t=>!t.length||done(t)))throw Error('Unsolvable sort construction');
        const permutation=H.shuffled(w,Array.from({length:count+2},(_,i)=>i)),
            index=new Map(permutation.map((original,i)=>[original,i]));
        return {tubes:permutation.map(i=>tubes[i]),caps:permutation.map(i=>caps[i]),
            seals:permutation.map(i=>m.sealed&&i===count+1),
            solution:path.map(a=>({...a,from:index.get(a.from),to:index.get(a.to)}))};
    }
    function round(w,H) {
        const j=w.journey;
        if(!w.sortPlan){
            w.sortPlan=Array.from({length:j.goal},(_,i)=>puzzle(w,H,j,i));
            const par=w.sortPlan.reduce((n,p)=>n+p.solution.length,0);
            j.sortGold=Math.ceil(par*1.15)+1;
            j.sortSilver=Math.ceil(par*1.6)+2;
            j.moves=Math.ceil(par*(j.precise?Math.max(1.35,1.8-j.variant*.05):3))+4;
            // A hard limit must never be below a medal target shown to the player.
            j.sortSilver=Math.min(j.sortSilver,j.moves);
            j.sortGold=Math.min(j.sortGold,j.sortSilver);
        }
        const p=w.sortPlan[w.score];
        w.tubes=p.tubes.map(t=>t.slice());w.sortCaps=p.caps.slice();w.sortSeals=p.seals.slice();
        w.sortSolution=p.solution.map(a=>({...a}));w.sortStart=w.tubes.map(t=>t.slice());
        w.sortUndo=[];w.selectedTube=-1;w.roundMoves=0;w.sortWon=false;w.sortMessage='';
        w.sortPowerUsed=false;
        resetSeen(w);
    }
    function resetSeen(w) {
        if(!w.journey)return;
        const complete=w.tubes.filter(done).length;
        w.sortSealTarget=Math.min(w.tubes.flat().length/4,complete+(w.journey.sealGoal||1));
        w.sortSealUnlocked=!w.sortSeals.some(Boolean);
        w.sortSeen=w.tubes.map(t=>t.map((_,i)=>!w.journey.hidden||
            (w.journey.hiddenDepth==='bottom'?i>0:i===t.length-1)));
    }
    function afterPour(w,from,to,count) {
        if(!w.sortSeen)return;
        w.sortSeen[from].splice(-count);
        w.sortSeen[to].push(...Array(count).fill(true));
        if(w.sortSeen[from].length)w.sortSeen[from][w.sortSeen[from].length-1]=true;
        if(w.tubes.filter(done).length>=w.sortSealTarget)w.sortSealUnlocked=true;
    }
    window.ArcadeSortLevels={chapters,icons,mission,capacity,sealed,canPour,round,resetSeen,afterPour};
})();
