/* Presentation only: each game has its own touch, rhythm and celebration. */
(() => {
    'use strict';
    const M = () => window.AlgoGameMotion;
    const profiles = {
        orbit: {color:'#bfe691',shape:'star'},
        evolve: {color:'#a7ca76',shape:'leaf'},
        bugs: {color:'#a7e6bf',shape:'pixel'},
        tower: {color:'#e7bd69',shape:'chip'},
        typing: {color:'#bd8d4e',shape:'letter'},
        debug: {color:'#7eb6d1',shape:'pixel'},
        '2048': {color:'#dc9f50',shape:'tile'},
        drop: {color:'#c5a4ee',shape:'bubble'},
        memory: {color:'#94b395',shape:'star'},
        react: {color:'#a5c86e',shape:'ring'},
        blocks: {color:'#8ab1d6',shape:'tile'},
        bubbles: {color:'#88cedc',shape:'bubble'},
        sort: {color:'#9ab994',shape:'bubble'},
        words: {color:'#c4a06c',shape:'letter'}
    };

    function wrap(id, view, stage, options) {
        const style = profiles[id];
        if (!style) return view;
        let sequence = 0, previous = null, stopped = false, trailAt = 0, budget = 24;
        const timers = new Set(), animations = new Set();
        const root = document.createElement('div');
        root.className = 'arcade-feedback';
        root.setAttribute('aria-hidden','true');
        root.style.setProperty('--feedback-color',style.color);
        root.dataset.shape = style.shape;
        const limited = () => M().reduced() || options.quality?.() === 'low';
        const later = (fn, ms) => {
            const timer=setTimeout(()=>{timers.delete(timer);if(!stopped)fn();},ms);
            timers.add(timer);
        };
        const animate = (node, frames, duration=280, delay=0) => {
            if (!node || limited() || stopped) return;
            if (animations.size>=32) animations.values().next().value.cancel();
            const a=node.animate(frames,{duration,delay,easing:'cubic-bezier(.18,.8,.27,1)'});
            animations.add(a);
            a.finished.then(()=>animations.delete(a),()=>animations.delete(a));
        };
        const rect = node => {
            if(!node)return null;
            const a=node.getBoundingClientRect(), b=stage.getBoundingClientRect();
            return {x:a.left-b.left+stage.scrollLeft,y:a.top-b.top+stage.scrollTop,
                width:a.width,height:a.height};
        };
        const centre = node => {
            const r=rect(node);
            return r?{x:r.x+r.width/2,y:r.y+r.height/2}:fallback();
        };
        const fallback = () => ({x:stage.clientWidth/2,y:Math.min(100,stage.clientHeight*.3)});
        const point = (x,y) => {
            const canvas=view.canvas || stage.querySelector('canvas');
            if(!canvas)return fallback();
            const r=rect(canvas);
            return {x:r.x+x*r.width/360,y:r.y+y*r.height/430};
        };
        const attach = () => {
            if(root.parentElement!==stage) stage.append(root);
            root.dataset.reduced=String(M().reduced());
        };
        const add = (className,p,life=650) => {
            attach();
            while(root.childElementCount>=42)root.firstElementChild.remove();
            const n=document.createElement('i');n.className=className;
            n.style.left=p.x+'px';n.style.top=p.y+'px';root.append(n);
            later(()=>n.remove(),life);return n;
        };
        const burst = (p,count=10) => {
            if(limited())return;
            count=Math.min(count,budget);budget-=count;
            if(!count)return;
            add('arcade-impact-ring',p);
            for(let i=0;i<count;i++) {
                const a=i*Math.PI*2/count+.25, distance=18+(i%3)*11;
                const n=add('arcade-impact-piece',p,680);
                n.style.setProperty('--dx',Math.cos(a)*distance+'px');
                n.style.setProperty('--dy',Math.sin(a)*distance-10+'px');
                n.style.setProperty('--turn',(i%2?160:-120)+'deg');
                n.style.setProperty('--delay',(i%3)*14+'ms');
            }
        };
        const label = (value,p=fallback(),kind='good') => {
            root.querySelector('.arcade-impact-label')?.remove();
            const n=add('arcade-impact-label is-'+kind,{
                x:Math.max(64,Math.min(stage.clientWidth-64,p.x)),
                y:Math.max(28,Math.min(stage.clientHeight-30,p.y-20))
            },1000);
            n.textContent=value;
            const half=n.offsetWidth/2+6;
            n.style.left=Math.max(half,Math.min(stage.clientWidth-half,p.x))+'px';
        };
        const pop = node => animate(node,[{scale:'.88'},{scale:'1.08',offset:.55},{scale:'1'}]);
        const flash = (node,bad=false) => animate(node,[
            {boxShadow:`0 0 0 3px ${bad?'#c78875':style.color}`},
            {boxShadow:'0 0 0 0 transparent'}
        ],450);
        const ghost = (item,target) => {
            if(!item || !target || limited())return;
            const original=item.node.querySelector('canvas');
            if(!original)return;
            const to=rect(target.querySelector('canvas')||target),from=item.art||item.r,
                node=document.createElement('canvas');
            node.width=original.width;node.height=original.height;
            node.getContext('2d').drawImage(original,0,0);
            node.setAttribute('aria-hidden','true');node.className='arcade-transfer-ghost';
            Object.assign(node.style,{left:from.x+'px',top:from.y+'px',
                width:from.width+'px',height:from.height+'px'});
            attach();root.append(node);
            animate(node,[{translate:'0 0',opacity:1,scale:'1'},
                {translate:`${to.x-from.x}px ${to.y-from.y}px`,opacity:0,scale:'.45'}],260);
            later(()=>node.remove(),280);
        };
        const capture = w => {
            if(id==='evolve'&&w.cues.some(c=>c.n>sequence&&c.type==='evolve')) return [...stage.querySelectorAll('.evolve-grid>button')]
                .map(node=>({node,r:rect(node),art:rect(node.querySelector('canvas'))}));
            if(id==='blocks'&&previous&&w.blockBoard.some((v,i)=>v!==previous.board[i])) return [...stage.querySelectorAll('.block-cell')]
                .map(node=>({r:rect(node),filled:node.classList.contains('is-filled'),
                    color:node.style.getPropertyValue('--cell')}));
            return null;
        };
        const event = (cue,w,old,delta) => {
            let p=Number.isFinite(cue.x)&&Number.isFinite(cue.y)?point(cue.x,cue.y):fallback();
            if(cue.type==='miss'||cue.type==='wrong'||cue.type==='wordMiss') {
                flash(stage.querySelector(id==='words'?'.words-form':id==='debug'?'.debug-code':'.reaction-pad'),true);
                if(id==='bugs')label('Робота не трогаем',p,'careful');
                return;
            }
            if(id==='orbit'&&cue.type==='land') {
                p=point(180,281);burst(p,14);label('Есть посадка!',p);
            }
            if(id==='bugs'&&cue.type==='hit') {burst(p,9);label('+1',p);}
            if(id==='tower'&&['stack','perfect'].includes(cue.type)) {
                burst(p,cue.type==='perfect'?16:6);
                if(cue.type==='perfect')label(cue.combo>1?'Идеально ×'+cue.combo:'Идеально!',p);
                animate(view.canvas,[{translate:'0 1px'},{translate:'0 0'}],130);
            }
            if(id==='drop'&&cue.type==='merge') {
                burst(p,10);if(delta>0)label('+'+delta,p);
            }
            if(id==='evolve'&&cue.type==='evolve') {
                const node=stage.querySelectorAll('.evolve-grid>button')[cue.to];
                ghost(old?.[cue.from],node);p=centre(node);burst(p,10);pop(node);
                if(delta>0)label('+'+delta,p);
            }
            if(id==='evolve'&&cue.type==='rescue') {
                const node=stage.querySelectorAll('.evolve-grid>button')[cue.to];
                burst(centre(node),14);label('Спасён!',centre(node));
            }
            if(id==='2048'&&cue.type==='slide') {
                const cells=stage.querySelectorAll('.number-cell');
                const targets=[...new Set(cue.moves.filter(m=>m.merged).map(m=>m.to))];
                for(const to of targets)burst(centre(cells[to]),6);
                if(targets.length>=2)label(targets.length+' слияния',centre(cells[targets.at(-1)]));
            }
            if(id==='memory'&&cue.type==='pair') {
                for(const i of cue.cells) {
                    const node=stage.querySelector(`[data-card="${i}"]`);pop(node);burst(centre(node),6);
                }
                label('Пара!',centre(stage.querySelector(`[data-card="${cue.cells.at(-1)}"]`)));
            }
            if(id==='react'&&cue.type==='reaction') {
                const node=stage.querySelector('.reaction-pad');flash(node);pop(node);
                burst(centre(node),10);
            }
            if(id==='debug'&&cue.type==='correct') {
                const node=stage.querySelector('.debug-feedback');flash(node);burst(centre(node),10);
                pop(stage.querySelector('.debug-feedback b'));
            }
            if(id==='blocks'&&cue.type==='clearLines') {
                const cells=stage.querySelectorAll('.block-cell');
                for(let i=0;i<64;i++) if(cue.rows.includes(Math.floor(i/8))||cue.cols.includes(i%8)) {
                    if(!limited()&&old?.[i]?.filled) {
                        const r=old[i].r,n=add('arcade-cleared-tile',{x:r.x+r.width/2,y:r.y+r.height/2});
                        n.style.width=r.width+'px';n.style.height=r.height+'px';
                        n.style.background=old[i].color; n.style.setProperty('--turn',(i%2?35:-35)+'deg');
                    }
                    flash(cells[i]);
                }
                const lines=cue.rows.length+cue.cols.length;
                label(cue.combo>1?'Комбо ×'+cue.combo:lines===1?'Линия!':lines+' линии',centre(stage.querySelector('.blocks-board')));
            }
            if(id==='bubbles'&&cue.type==='bubblePop') {
                const positions=cue.cells.map(i=>ArcadeExtras.bubblePoint(i));
                for(const pos of positions.slice(0,6))burst(point(pos.x,pos.y),4);
                p=positions.length?point(positions[0].x,positions[0].y):p;
                label(cue.fallen?'Цепочка! +'+delta:'+'+delta,p);
            }
            if(id==='sort'&&cue.type==='pour') {
                const target=stage.querySelector(`[data-tube="${cue.to}"]`);
                if(target?.classList.contains('is-complete')){burst(centre(target),10);flash(target);}
            }
            if(id==='sort'&&cue.type==='sortWin') {
                burst(centre(stage.querySelector('.sort-tubes')),18);label('Всё по цветам!');
            }
            if(id==='words'&&cue.type==='wordFound') {
                const node=stage.querySelector('.words-found>span:last-child');
                animate(node,[{translate:'0 -12px',rotate:'-6deg',opacity:0},{translate:'0 0',rotate:'0deg',opacity:1}],320);
                burst(centre(node),7);
            }
            if(cue.type==='level'&&w.level>1)label('Новый этап');
        };
        const update=view.update;
        view.update=(w,dt)=>{
            if(stopped)return;
            const old=capture(w);update(w,dt);attach();budget=24;
            const reset=!previous||w.tick<previous.tick||w.seed!==previous.seed;
            if(reset) {
                sequence=w.cueSeq||0;root.replaceChildren();trailAt=w.time;
            } else {
                const cues=w.cues.filter(c=>c.n>sequence&&c.t>=w.tick-60).slice(-8);
                const delta=Math.max(0,w.score-previous.score);
                for(const cue of cues)event(cue,w,old,delta);
                sequence=w.cueSeq||sequence;
                if(id==='memory')for(const i of w.opened.filter(i=>!previous.opened.includes(i))) {
                    animate(stage.querySelector(`[data-card="${i}"]`),[
                        {transform:'perspective(500px) rotateY(85deg)',opacity:.4},
                        {transform:'perspective(500px) rotateY(0)',opacity:1}],220);
                }
                if(id==='blocks'&&old) [...stage.querySelectorAll('.block-cell')].forEach((n,i)=>{
                    if(n.classList.contains('is-filled')&&!old[i]?.filled)pop(n);
                });
                if(id==='typing'&&w.typed.length>previous.typed) {
                    const correct=w.typed.at(-1)===w.text[w.typed.length-1];
                    if(correct) {
                        const keys=stage.querySelectorAll('.typewriter-body>span');
                        animate(keys[w.typed.length%Math.max(1,keys.length)],[{translate:'0 3px'},{translate:'0 0'}],110);
                        if(w.score>0&&Math.floor(w.score/25)>Math.floor(previous.score/25)) {
                            flash(stage.querySelector('.typing-passage'));label(w.score+' знаков');
                        }
                    } else flash(stage.querySelector('.typing-passage'),true);
                }
                if(!limited()&&!options.paused()&&w.time-trailAt>.06) {
                    let p=null;
                    if(id==='bubbles'&&w.projectile)p=point(w.projectile.x,w.projectile.y);
                    if(id==='orbit'&&w.flight) {
                        const t=Math.min(1,w.flight),e=t*t*(3-2*t);
                        p=point(w.from.x+(180+Math.cos(w.flightTarget)*105-w.from.x)*e+(180-(180+Math.cos(w.flightTarget)*105))*e,
                            w.from.y+(281+Math.sin(w.flightTarget)*160+69-w.from.y)*e-Math.sin(t*Math.PI)*65+(281-(281+Math.sin(w.flightTarget)*160))*e);
                    }
                    if(p)add('arcade-flight-trail',p,340);
                    trailAt=w.time;
                }
            }
            previous={tick:w.tick,seed:w.seed,score:w.score,opened:w.opened?.slice()||[],
                typed:w.typed?.length||0,board:w.blockBoard?.slice()||[]};
        };
        options.signal?.addEventListener('abort',()=>{
            stopped=true;for(const t of timers)clearTimeout(t);timers.clear();
            for(const a of animations)a.cancel();animations.clear();root.remove();previous=null;
        },{once:true});
        return view;
    }

    async function card(game, report, mode) {
        const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=1080;
        const c=canvas.getContext('2d'),color=profiles[game.id]?.color||'#8aaa7b';
        c.fillStyle='#f7f4eb';c.fillRect(0,0,1080,1080);
        c.fillStyle=color;c.fillRect(0,0,1080,22);
        c.fillStyle='#263d36';c.textAlign='left';c.font='700 32px Segoe UI';c.fillText('ALGO ARCADE',74,105);
        c.font='700 56px Segoe UI';
        let title=game.name;
        while(c.measureText(title).width>920&&title.length>5)title=title.slice(0,-2);
        c.fillText(title+(title===game.name?'':'…'),74,200);
        c.fillStyle=color;c.beginPath();c.roundRect(74,260,932,540,40);c.fill();
        c.fillStyle='#243a32';c.textAlign='center';c.font='700 34px Segoe UI';
        c.fillText(report.journey?'УРОВЕНЬ '+report.journey.stage:mode==='practice'?'ТРЕНИРОВКА':'СОРЕВНОВАНИЕ',540,340);
        const art=document.createElement('div');art.innerHTML=ArcadePersonality.score(game.id,0,'');
        const svg=art.querySelector('svg');
        if(svg) {
            const markup=svg.outerHTML.replace('<svg ','<svg xmlns="http://www.w3.org/2000/svg" ')
                .replaceAll('var(--play-wash)','#fff8e4').replaceAll('currentColor','#486252');
            const url=URL.createObjectURL(new Blob([markup],{type:'image/svg+xml'}));
            try {
                const image=new Image();image.src=url;await image.decode();
                c.drawImage(image,115,390,350,320);
            } finally {URL.revokeObjectURL(url);}
        }
        const reaction=game.id==='react'&&report.details?.reactionMs>0;
        const value=reaction?report.details.reactionMs:report.score;
        const score=Number(value).toLocaleString('ru-RU');
        let size=168;c.font='800 '+size+'px Segoe UI';
        while(c.measureText(score).width>440){size-=4;c.font='800 '+size+'px Segoe UI';}
        c.fillText(score,735,555);
        const unit=reaction?'мс · средняя реакция':game.unit;
        size=38;c.font='600 '+size+'px Segoe UI';
        while(c.measureText(unit).width>440){size-=2;c.font='600 '+size+'px Segoe UI';}
        c.fillText(unit,735,630);
        if(report.journey){c.font='700 42px Segoe UI';c.fillText('★'.repeat(report.journey.stars)+'☆'.repeat(3-report.journey.stars),540,725);}
        c.fillStyle='#263d36';c.font='700 52px Segoe UI';c.fillText('Сможешь лучше?',540,915);
        c.font='400 28px Segoe UI';c.fillText('Игры в Algo MAX',540,975);
        return new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('Не удалось создать карточку')),'image/png'));
    }

    function result(run, cover, report) {
        if(!profiles[run.g.id])return;
        cover.dataset.feedbackGame=run.g.id;
        const actions=cover.querySelector('.arcade-result-actions');
        if(!actions)return;
        if(!M().reduced()&&(report.journey?.success||run.finishResult?.run.accepted&&report.score>run.oldBest)) {
            cover.classList.add('has-celebration');
        }
        const button=document.createElement('button');button.className='arcade-share-result';
        button.textContent='Поделиться результатом';actions.append(button);
        const note=document.createElement('p');note.className='arcade-share-note';note.setAttribute('role','status');note.hidden=true;
        actions.append(note);
        let blobPromise=null;
        const download = file => {
            const url=URL.createObjectURL(file),a=document.createElement('a');
            a.href=url;a.download=file.name;document.body.append(a);a.click();a.remove();
            setTimeout(()=>URL.revokeObjectURL(url),10000);
            note.textContent='Карточка сохранена';note.hidden=false;
        };
        // Generate on demand; no request, pupil details or uploads are involved.
        button.onclick=async()=>{
            if(button.disabled)return;button.disabled=true;note.hidden=true;
            try {
                blobPromise ||= card(run.g,report,run.mode);
                const blob=await blobPromise,file=new File([blob],'algo-'+run.g.id+'.png',{type:'image/png'});
                if(navigator.canShare?.({files:[file]})&&navigator.share) {
                    try {await navigator.share({files:[file],title:run.g.name});}
                    catch(error){if(error.name!=='AbortError')download(file);}
                } else download(file);
            } catch(error) {
                if(error.name!=='AbortError'){note.textContent='Не удалось сохранить. Попробуй ещё раз.';note.hidden=false;blobPromise=null;}
            } finally {button.disabled=false;}
        };
    }
    window.ArcadeFeedback={wrap,result,card};
})();
