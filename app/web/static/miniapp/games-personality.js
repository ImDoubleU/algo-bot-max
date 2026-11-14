/* Game-specific instruments and physical play surfaces. Never mutates game rules. */
(() => {
    'use strict';
    const labels = {
        orbit: 'Посадки',
        evolve: 'Очки',
        bugs: 'Баги',
        tower: 'Этажи',
        typing: 'Знаки',
        debug: 'Исправлено',
        '2048': 'Плитка',
        drop: 'Очки',
        memory: 'Пары',
        react: 'Попадания',
        kopatych: 'Урожай',
        blocks: 'Очки',
        runner: 'Преграды',
        hill: 'Дистанция, м',
        bubbles: 'Очки',
        sort: 'Решено',
        words: 'Слова', ocean:'Спасено',slap:'Очки',plane:'Дистанция, м',menagerie:'Очки'
    };
    const stamps = {
        orbit: '<circle cx="120" cy="110" r="94" fill="var(--play-wash)"/><circle cx="120" cy="110" r="83" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="4 5"/><ellipse cx="120" cy="110" rx="111" ry="27" fill="none" stroke="currentColor" opacity=".25" transform="rotate(-20 120 110)"/>',
        evolve: '<path d="M120 207C33 206 28 151 47 90 62 40 88 22 120 15c32 7 58 25 73 75 19 61 14 116-73 117Z" fill="var(--play-wash)" stroke="currentColor" stroke-width="2"/><path d="M120 24q-14-36-52-17 10 31 52 17 26-31 55-13-20 32-55 13Z" fill="currentColor" opacity=".65"/>',
        bugs: '<path d="M8 65h25m-25 30h25m-25 30h25m-25 30h25m174-90h25m-25 30h25m-25 30h25m-25 30h25M65 8v25m35-25v25m40-25v25m35-25v25m-110 154v25m35-25v25m40-25v25m35-25v25" stroke="currentColor" stroke-width="8"/><rect x="29" y="29" width="182" height="162" rx="16" fill="#203d35" stroke="currentColor" stroke-width="3"/><path d="m45 47 9 9m132 115 9 9" stroke="#b7d8a9" stroke-width="2"/>',
        tower: '<path d="M20 205V42h60v163M30 42V17h40v25" fill="var(--play-wash)" stroke="currentColor" stroke-width="3"/><path d="M30 60h12v14H30m25-14h12v14H55M30 91h12v14H30m25-14h12v14H55M30 122h12v14H30m25-14h12v14H55M30 153h12v14H30m25-14h12v14H55M10 206h220" fill="currentColor" opacity=".55"/><path d="M91 201V52h137v149" fill="var(--play-wash)" opacity=".55"/>',
        typing: '<path d="M35 8h143l30 30v174H35Z" fill="#fffdf4" stroke="#d7c29b" stroke-width="2"/><path d="M178 8v30h30M53 175h138m-138 12h100" fill="none" stroke="#d7c29b" stroke-width="2"/><path d="M50 32h94m-94 9h64" stroke="#e9ddc6" stroke-width="4"/>',
        debug: '<rect x="9" y="25" width="222" height="167" rx="13" fill="#203146" stroke="#526d8b" stroke-width="3"/><path d="M10 54h220" stroke="#526d8b"/><circle cx="28" cy="40" r="4" fill="#d3948f"/><circle cx="42" cy="40" r="4" fill="#e0c67e"/><circle cx="56" cy="40" r="4" fill="#9bbd87"/><path d="m28 155 9 7-9 7m18 0h18" fill="none" stroke="#8ab4cf" stroke-width="3"/>',
        '2048': '<rect x="34" y="22" width="172" height="176" rx="23" fill="#d6ac7f"/><rect x="34" y="14" width="172" height="176" rx="23" fill="var(--play-wash)" stroke="#c99d72" stroke-width="3"/><path d="M52 31h123M50 174h140" stroke="#fff8e9" opacity=".8" stroke-width="4"/>',
        drop: '<ellipse cx="120" cy="190" rx="76" ry="15" fill="#d8c8e9"/><path d="M96 20h48v20a79 79 0 1 1-48 0Z" fill="#ede3f7" fill-opacity=".75" stroke="#b7a0cf" stroke-width="3"/><path d="M62 143q25-22 58 0t58 0" fill="none" stroke="#b7a0cf" stroke-width="2"/><circle cx="172" cy="72" r="13" fill="#d8b5df"/><circle cx="74" cy="166" r="10" fill="#b5cde3"/>',
        memory: '<g transform="rotate(-12 78 117)"><rect x="19" y="40" width="114" height="156" rx="13" fill="#c5dacd" stroke="#8bab97" stroke-width="2"/><path d="m75 75 16 29-16 29-16-29Z" fill="#91b09e"/></g><g transform="rotate(7 152 105)"><rect x="91" y="19" width="124" height="165" rx="13" fill="#fffdf7" stroke="#a5c1ad" stroke-width="2"/></g>',
        react: '<path d="M104 4h32v16h-32Zm-20 20L72 10m84 14 12-14" fill="var(--play-wash)" stroke="currentColor" stroke-width="4"/><circle cx="120" cy="117" r="87" fill="#fffdf5" stroke="currentColor" stroke-width="6"/><path d="M120 38v12m67 67h-12M53 117h12m55 67v12" stroke="currentColor" stroke-width="3"/>',
        kopatych: '<path d="M49 108q0-92 71-92t71 92" fill="none" stroke="#bda078" stroke-width="10"/><path d="m22 91 19 112h158l19-112Z" fill="#e4caa0" stroke="#b69567" stroke-width="3"/><path d="M32 119h175M36 145h166M39 172h159M64 94l10 109m25-109 3 109m34-109-3 109m33-109-10 109" stroke="#b69567" stroke-width="2" opacity=".65"/><path d="m63 83 18-38 18 42m38-3 21-47 17 52" fill="#e7a975" stroke="#af8e5a" stroke-width="2"/><path d="m75 43-6-15m12 15 9-16m65 11-4-16m8 16 11-12" stroke="#8fa36c" stroke-width="6"/><rect x="67" y="98" width="108" height="77" rx="12" fill="#fff6e4"/>',
        blocks: '<path d="M13 18h58v58H13Zm62 0h58v58H75Zm62 0h58v58h-58ZM13 80h58v58H13Zm0 62h58v58H13Zm62 0h58v58H75Zm62 0h58v58h-58Zm62 0h29v58h-29Z" fill="#bfd2eb" stroke="#8fa9cd" stroke-width="2"/><rect x="69" y="69" width="160" height="114" rx="13" fill="#fff" stroke="#9cb6d4" stroke-width="3"/>',
        runner: '<path d="m9 50 202-31 20 153-201 31Z" fill="#e5d4ed" stroke="#b292c2" stroke-width="2"/><path d="m15 61 200-31M29 190l200-31" stroke="#c8b1d6" stroke-width="3"/><g fill="#a486b4">' + Array.from({
            length: 14
        }, (_, i) => `<rect x="${24+i*14}" y="${i%2?172:184}" width="14" height="12" transform="rotate(-9 120 180)"/>`).join('') + '</g>',
        bubbles: '<g stroke="#8dbdc8" stroke-width="2"><circle cx="72" cy="59" r="30" fill="#c2e1ea"/><circle cx="178" cy="74" r="38" fill="#e0cee9"/><circle cx="171" cy="166" r="33" fill="#c8e2b7"/><circle cx="63" cy="163" r="37" fill="#f0d6b1"/><circle cx="120" cy="111" r="72" fill="#f5fdff"/></g><path d="M73 78q18-24 37-18" fill="none" stroke="#c3e4ec" stroke-width="7" stroke-linecap="round"/>',
        sort: '<path d="M96 8h48v18h-5v51l61 103q9 22-15 22H55q-24 0-15-22l61-103V26h-5Z" fill="#f2f8f0" stroke="#9eb994" stroke-width="3"/><path d="M68 144q50-18 104 0l23 41q4 12-13 12H58q-17 0-13-12Z" fill="#c8dfbb"/><path d="M57 169h17m-10-17h17m-10-17h17" stroke="#8ea87d" stroke-width="2"/>',
        words: '<path d="M32 12h178v185l-16 10-15-10-15 10-15-10-15 10-15-10-15 10-15-10-15 10-15-10-15 10Z" fill="#fffdf5" stroke="#d9c39b" stroke-width="2"/><path d="M47 47h147M47 70h147M47 93h147M47 116h147M47 139h147M47 162h147" stroke="#e9dcc4"/><path d="M57 12v185" stroke="#e3bfb4" stroke-width="2"/><g fill="#bca07a">' + Array.from({
            length: 6
        }, (_, i) => `<circle cx="34" cy="${29+i*28}" r="4"/>`).join('') + '</g>'
    };

    function score(game, value, unit) {
        if(game==='hill') return `<div class="hill-distance-result"><span>Пройдено</span><h3>${Number(value).toLocaleString('ru-RU')} <small>м</small></h3></div>`;
        const size = String(value).length > 5 ? 34 : String(value).length > 3 ? 44 : 56;
        const safeUnit = String(unit).replace(/[&<>"']/g, c => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        } [c]));
        return `<div class="game-score-prop prop-${game}" style="--score-size:${size}px"><svg viewBox="0 0 240 220" aria-hidden="true">${stamps[game]||'<path d="m120 22 27 55 61 9-44 43 10 61-54-29-54 29 10-61-44-43 61-9Z" fill="#e7c67d"/>'}</svg><h3>${Number(value)}<span>${safeUnit}</span></h3></div>`;
    }

    function backdrop(c, id, w, options={}) {
        if (id === 'bugs') {
            c.save();
            c.strokeStyle = '#9fc5ad12';
            c.lineWidth = 1;
            for (let x = 20; x < 360; x += 32) {
                c.beginPath();
                c.moveTo(x, 55);
                c.lineTo(x, 430);
                c.stroke();
            }
            for (let y = 55; y < 430; y += 32) {
                c.beginPath();
                c.moveTo(0, y);
                c.lineTo(360, y);
                c.stroke();
            }
            c.restore();
        }
        if (id === 'tower') {
            c.save();
            const sky=c.createLinearGradient(0,0,0,430);
            sky.addColorStop(0,'#b9d4df');sky.addColorStop(1,'#f4e4bc');
            c.fillStyle=sky;c.fillRect(0,0,360,430);
            for(let i=0;i<8;i++) {
                const x=i*53-18,h=48+(i*31)%86;
                c.fillStyle=i%2?'#8faeab':'#a9bfaf';c.fillRect(x,410-h,41,h);
                c.fillStyle='#e6e8bd';
                for(let y=420-h;y<400;y+=15)for(let n=0;n<3;n++)c.fillRect(x+7+n*10,y,4,6);
            }
            window.ArcadeWorldArt?.backdrop(c,id,w,360,430,options.theme);
            const stroke=(points,color,width=2)=>{
                c.strokeStyle=color;c.lineWidth=width;c.lineJoin='round';c.lineCap='round';
                c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.stroke();
            };
            // Twin-rail lattice mast and cross-braced jib, with a real counterweight.
            c.fillStyle='#cfaa58';c.fillRect(18,59,18,353);
            stroke([[18,412],[18,59],[36,59],[36,412]],'#7f754e',3);
            for(let y=67;y<402;y+=24) {
                stroke([[19,y],[35,y+23],[19,y+23],[35,y]],'#f4d180',1.5);
            }
            c.fillStyle='#526d6a';c.fillRect(8,409,40,10);
            c.fillStyle='#dfa94b';c.fillRect(6,43,342,20);
            stroke([[6,43],[348,43],[348,63],[6,63],[6,43]],'#90763e',2);
            for(let x=8;x<332;x+=27)stroke([[x,62],[x+13,44],[x+27,62]],'#fff0b4',1.6);
            stroke([[6,43],[27,18],[348,43]],'#6d7770',1.4);
            stroke([[27,18],[27,43]],'#8e793e',4);
            c.fillStyle='#52686b';c.fillRect(5,65,35,15);
            for(let i=0;i<3;i++){c.fillStyle='#a5b0a0';c.fillRect(6+i*11,66,9,12);}
            c.fillStyle='#dfb15b';c.fillRect(37,65,27,23);
            c.fillStyle='#466c7b';c.fillRect(42,69,17,12);
            stroke([[42,82],[59,82]],'#fff0b7',1);
            const bx=w.left+w.width/2,tx=Math.max(48,Math.min(339,bx)),
                by=390-Math.min(11,w.blocks.length)*25,hook=Math.max(91,by-13);
            c.fillStyle='#3c5959';c.fillRect(tx-9,58,18,11);
            c.fillStyle='#e5c56e';c.fillRect(tx-6,60,12,4);
            stroke([[tx-3,69],[bx-2,hook],[bx+2,hook],[tx+3,69]],'#46575a',1.3);
            c.fillStyle='#e2b04f';c.fillRect(bx-5,hook-2,10,8);
            stroke([[bx-3,hook+6],[bx,hook+10],[bx+3,hook+6]],'#485a56',2);
            stroke([[bx,hook+8],[w.left+w.width*.22,by],[w.left+w.width*.78,by],[bx,hook+8]],'#63776b',1.2);
            c.restore();
        }
        if(id==='orbit'||id==='bugs')window.ArcadeWorldArt?.backdrop(c,id,w,360,430,options.theme);
    }

    function decorate(run) {
        const stage = run.dialog.querySelector('.game-stage'),
            id = run.g.id;
        const score = run.dialog.querySelector('#gameScore');
        if (score?.parentElement) score.parentElement.firstChild.textContent = labels[id] + ' ';
        const canvas = run.view.canvas || stage.querySelector(':scope > canvas');
        if (canvas && id !== 'hill') {
            const frame = document.createElement('div');
            frame.className = 'arcade-canvas-frame frame-' + id;
            canvas.replaceWith(frame);
            frame.append(canvas);
        }
        const editorTab = () => {
            if (!stage.querySelector('.editor-tab')) stage.querySelector('.debug-code')?.insertAdjacentHTML('beforebegin', '<div class="editor-tab" aria-hidden="true"><i></i><i></i><i></i><span>main.py</span></div>');
        };
        if (id === 'debug') editorTab();
        if (id === 'typing'&&!stage.querySelector('.typing-surface')) {
            stage.querySelector('.typing-input').insertAdjacentHTML('afterend', '<div class="typewriter-body" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><i></i></div>');
        }
        if (id === 'react') {
            stage.querySelector('.reaction-pad').insertAdjacentHTML('afterbegin', '<div class="reaction-lights" aria-hidden="true"><i></i><i></i><i></i></div>');
        }
        const update = run.view.update;
        run.view.update = (w, dt) => {
            update(w, dt);
            if (id === 'debug') editorTab();
            if (id === 'evolve') stage.dataset.growth = Math.min(3, Math.floor(w.merges / 4));
        };
    }
    const baseDecorate = decorate;
    window.ArcadePersonality = {
        decorate: (run) => { baseDecorate(run); window.ArcadeInteriors?.decorate(run); },
        score,
        backdrop
    };
})();
