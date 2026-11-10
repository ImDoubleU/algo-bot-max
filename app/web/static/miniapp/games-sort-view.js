/* Ball-sort controls and flights. The verified puzzle lives in games-extra.js. */
(() => {
    'use strict';
    const colors=['#a878ed','#99d15c','#f0a16c','#ed91ae','#70b9e0','#f0ca54','#315cc4','#92542c'];
    const names=['фиолетовый','зелёный','оранжевый','розовый','голубой','жёлтый','синий','коричневый'];
    function mount(stage,send,options) {
        stage.dataset.game='sort';
        stage.innerHTML='<div class="sort-game"><div class="sort-meta"><b></b><span data-sort-progress></span><span data-sort-moves></span></div><div class="sort-tubes" role="group" aria-label="Колбы с шариками"></div><p class="sort-message" role="status"></p><div class="sort-tools"><button data-sort-restart>Заново</button>'+(options.mode==='practice'?'<button data-sort-undo>Отменить ход</button>':'')+'</div><div class="sort-complete"></div><div class="sort-effects" aria-hidden="true"></div></div>';
        const $=s=>stage.querySelector(s), grid=$('.sort-tubes'),effects=$('.sort-effects');
        let world=null,signatures=[],sequence=0,won=false,busy=false,drag=null,ignoreClickUntil=0;
        let flight=0,lastTick=0,lastSeed=null,settling=Promise.resolve();
        const animations=new Set(),hidden=new Set();
        const on=(node,event,fn)=>node.addEventListener(event,fn,{signal:options.signal});
        const cooling=()=>world?.sortCompetition&&world.tick<(world.sortReadyAt||0);
        const available=()=>!options.readOnly&&!options.paused()&&!world?.ended&&!busy&&!cooling();
        const active=()=>available()&&!world?.sortWon;
        const source=e=>e?.pointerType==='touch'?'touch':options.device;
        const input=(action,e)=>{
            if(action.type==='next'?available()&&world?.sortWon:active())send({...action,source:source(e)});
        };
        const valid=(from,to)=>from!==to&&world?.tubes[from]?.length&&world.tubes[to]?.length<4
            &&(!world.tubes[to].length||world.tubes[to].at(-1)===world.tubes[from].at(-1));
        const cancel=()=>{
            flight++;
            for(const a of animations)a.cancel();animations.clear();
            for(const n of hidden)n.style.opacity='';hidden.clear();
            effects.replaceChildren();busy=false;grid.removeAttribute('aria-busy');
        };
        const motion=(node,frames,settings)=>{
            const a=node.animate(frames,settings);animations.add(a);
            return a.finished.catch(()=>{}).finally(()=>animations.delete(a));
        };
        const bounds=()=>[...grid.querySelectorAll('[data-tube]')].map(t=>
            [...t.querySelectorAll('[data-slot]')].reduce((out,n)=>{
                out[+n.dataset.slot]=n.getBoundingClientRect();return out;
            },[]));
        const fly=(cue,old)=>{
            if(window.AlgoGameMotion.reduced()||!old?.[cue.from])return;
            const area=effects.getBoundingClientRect(),jobs=[],count=cue.count||1,
                fromSize=cue.fromSize??(world.tubes[cue.from].length+count),
                toSize=cue.toSize??(world.tubes[cue.to].length-count),
                color=cue.color??world.tubes[cue.to].at(-1),
                economical=options.quality?.()==='low';
            const token=++flight;
            busy=true;grid.setAttribute('aria-busy','true');
            for(let i=0;i<count;i++) {
                const from=old[cue.from][fromSize-1-i],
                    target=$(`[data-tube="${cue.to}"] [data-slot="${toSize+i}"]`);
                if(!from||!target)continue;
                const to=target.getBoundingClientRect(),ghost=document.createElement('i');
                ghost.className='sort-ball sort-flight';
                ghost.style.setProperty('--marble',`url('/miniapp/static/worlds/marble-${color}.svg?v=2')`);
                ghost.style.setProperty('--ball',colors[color]);
                Object.assign(ghost.style,{left:(from.left-area.left)+'px',top:(from.top-area.top)+'px',
                    width:from.width+'px',height:from.height+'px'});
                effects.append(ghost);target.style.opacity='0';hidden.add(target);
                const dx=to.left-from.left,dy=to.top-from.top,
                    lift=Math.min(0,dy)-Math.min(92,48+Math.abs(dx)*.16),
                    duration=economical?300:460,delay=i*(economical?45:75);
                jobs.push(motion(ghost,[
                    {transform:'translate(0,0) scale(1)'},
                    {transform:`translate(${dx*.2}px,${lift}px) scale(.95,1.06)`,offset:.30},
                    {transform:`translate(${dx*.78}px,${lift-8}px) scale(1.04,.97)`,offset:.64},
                    {transform:`translate(${dx}px,${dy}px) scale(1.12,.85)`,offset:.9},
                    {transform:`translate(${dx}px,${dy}px) scale(1)`}
                ],{duration,delay,easing:'cubic-bezier(.3,.05,.45,1)',fill:'both'}).then(()=>{
                    ghost.remove();if(token!==flight)return;
                    target.style.opacity='';hidden.delete(target);
                    if(!options.signal?.aborted&&target.isConnected&&!window.AlgoGameMotion.reduced()) {
                        return motion(target,[{scale:'1.14 .85'},{scale:'.95 1.06',offset:.5},{scale:'1'}],
                            {duration:180,easing:'ease-out'});
                    }
                }));
            }
            const glass=$(`[data-tube="${cue.from}"] .sort-glass`);
            if(glass)jobs.push(motion(glass,[{rotate:'0deg'},
                {rotate:(cue.to>cue.from?'8deg':'-8deg'),offset:.3},{rotate:'0deg'}],
                {duration:430,easing:'ease-in-out'}));
            settling=Promise.all(jobs).finally(()=>{
                if(token===flight){
                    busy=false;grid.removeAttribute('aria-busy');
                    if(!options.signal?.aborted&&stage.isConnected&&world)update(world);
                }
            });
        };
        const tubeInput=(from,to,e)=>{
            if(!active())return;
            if(valid(from,to))input({type:'pour',from,to},e);
            else input({type:'tube',i:to},e);
        };
        on(stage,'click',e=>{
            const b=e.target.closest('button');if(!b)return;
            if(b.dataset.tube!==undefined&&performance.now()>=ignoreClickUntil) {
                input({type:'tube',i:+b.dataset.tube},e);
            }
            if(b.hasAttribute('data-sort-restart'))input({type:'restart'},e);
            if(b.hasAttribute('data-sort-undo'))input({type:'undo'},e);
            if(b.hasAttribute('data-sort-next'))input({type:'next'},e);
        });
        on(grid,'pointerdown',e=>{
            const b=e.target.closest('[data-tube]');
            if(!b||!active()||!world?.tubes[+b.dataset.tube].length)return;
            drag={from:+b.dataset.tube,x:e.clientX,y:e.clientY,pointer:e.pointerId,moved:false};
            b.setPointerCapture(e.pointerId);
        });
        on(grid,'pointermove',e=>{
            if(!drag||e.pointerId!==drag.pointer)return;
            drag.moved ||= Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>9;
            const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-tube]');
            for(const n of grid.children)n.classList.toggle('is-drag-target',
                drag.moved&&n===target&&valid(drag.from,+n.dataset.tube));
        });
        const endDrag=e=>{
            if(!drag||e.pointerId!==drag.pointer)return;
            const d=drag;drag=null;for(const n of grid.children)n.classList.remove('is-drag-target');
            if(!d.moved||e.type!=='pointerup')return;
            ignoreClickUntil=performance.now()+400;
            const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-tube]');
            if(target&&valid(d.from,+target.dataset.tube))tubeInput(d.from,+target.dataset.tube,e);
        };
        on(grid,'pointerup',endDrag);on(grid,'pointercancel',endDrag);
        on(document,'keydown',e=>{
            if(!active()||e.repeat||e.target.matches('input,textarea'))return;
            const match=/^(?:Digit|Numpad)([1-9])$/.exec(e.code);
            if(match&&world&&+match[1]<=world.tubes.length) {
                e.preventDefault();input({type:'tube',i:+match[1]-1},e);
            }
        });
        on(document,'visibilitychange',()=>{if(document.hidden){drag=null;cancel();}});
        options.signal?.addEventListener('abort',cancel,{once:true});

        function update(w) {
            const reset=!world||w.tick<lastTick||w.seed!==lastSeed||w.tubes.length!==signatures.length;
            const old=bounds(),oldSequence=sequence;
            if(reset)cancel();
            world=w;
            if(grid.children.length!==w.tubes.length) {
                cancel();signatures=[];
                grid.style.setProperty('--tube-columns',w.tubes.length<=5?w.tubes.length:Math.ceil(w.tubes.length/2));
                grid.style.setProperty('--tube-rows',w.tubes.length<=5?1:2);
                grid.innerHTML=w.tubes.map((_,i)=>`<button data-tube="${i}" class="sort-tube"><span class="sort-glass"></span><small>${i+1}</small></button>`).join('');
            }
            w.tubes.forEach((t,i)=>{
                const button=grid.children[i],key=t.join(),selected=w.selectedTube===i,
                    complete=t.length===4&&t.every(v=>v===t[0]);
                button.classList.toggle('is-selected',selected);
                button.classList.toggle('is-complete',complete);
                button.classList.toggle('can-receive',w.selectedTube>=0&&!!valid(w.selectedTube,i));
                button.classList.toggle('is-muted',w.selectedTube>=0&&!selected&&!valid(w.selectedTube,i));
                button.setAttribute('aria-pressed',String(selected));
                button.setAttribute('aria-label',`Колба ${i+1}: ${t.length?t.slice().reverse().map(v=>names[v]).join(', '):'пусто'}`);
                if(signatures[i]!==key) {
                    $('.sort-tubes').children[i].querySelector('.sort-glass').innerHTML=[3,2,1,0].map(j=>
                        `<i data-slot="${j}" class="${t[j]===undefined?'':'sort-ball'}"${t[j]===undefined?'':` style="--ball:${colors[t[j]]};--marble:url('/miniapp/static/worlds/marble-${t[j]}.svg?v=2')"`}></i>`).join('');
                    signatures[i]=key;
                }
            });
            const cue=w.cues.filter(c=>c.n>oldSequence&&c.type==='pour'&&c.t>=w.tick-60).at(-1);
            sequence=w.cueSeq;
            lastTick=w.tick;lastSeed=w.seed;
            if(!reset&&cue){cancel();fly(cue,old);}
            const rounds=w.sortCompetition?5:w.journey?.goal;
            $('.sort-meta b').textContent=rounds?`Задача ${Math.min(rounds,w.sortWon?w.score:w.score+1)} из ${rounds}`:`Уровень ${w.sortWon?w.score:w.score+1}`;
            $('[data-sort-progress]').textContent='Собрано '+w.tubes.filter(t=>t.length===4&&t.every(v=>v===t[0])).length+' / '+(w.tubes.flat().length/4);
            $('[data-sort-moves]').textContent=`Ходов: ${w.roundMoves}`;
            $('.sort-message').textContent=w.sortMessage;
            const locked=!!(w.sortWon||w.ended||options.readOnly||busy||cooling());
            for(const button of grid.children)button.disabled=locked;
            grid.toggleAttribute('inert',locked);
            const showWin=w.sortWon&&!w.ended&&!busy&&!cooling();
            if(won!==showWin) {
                won=showWin;
                $('.sort-complete').innerHTML=won?`<div><span aria-hidden="true">✓</span><h3>${rounds?`Задача ${w.score} из ${rounds} решена`:'Всё по цветам'}</h3><button class="games-main" data-sort-next${options.readOnly?' disabled':''}>${rounds?'Следующая задача':'Следующий уровень'} →</button></div>`:'';
                if(!options.readOnly){
                    drag=null;
                    (won?$('[data-sort-next]'):grid.querySelector('button:not(:disabled)'))?.focus({preventScroll:true});
                }
            }
            $('[data-sort-undo]')?.toggleAttribute('disabled',!w.sortUndo.length||locked);
            $('[data-sort-restart]').disabled=locked;
        }
        return {update,settled:()=>settling};
    }
    window.ArcadeSortView={mount};
})();
