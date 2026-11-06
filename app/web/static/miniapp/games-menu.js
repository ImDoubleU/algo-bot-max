/* Large, shared entry screens. Gameplay and saved progress live in their own modules. */
(() => {
    'use strict';
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    } [c]));
    const paths = {
        ranked: '<path d="M8 4h8v6a4 4 0 0 1-8 0Z"/><path d="M8 6H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 2v5m-4 1h8"/>',
        practice: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
        learning: '<path d="M3 5q5-2 9 1 4-3 9-1v14q-5-2-9 1-4-3-9-1Zm9 1v14"/>',
        garden: '<path d="M12 22V11m0 6C4 17 2 12 3 7c6-1 10 2 9 10Zm0-5c-1-7 3-11 10-10 1 6-3 11-10 10Z"/>',
        levels: '<path d="M4 20v-5h5v-5h5V5h6M4 20h16V5"/>'
    };
    const icon = id => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[id]}</svg>`;

    function home(game) {
        return `<section class="arcade-game-menu" aria-label="Режим игры"><div class="arcade-menu-art" aria-hidden="true">${AlgoGameArt.render(game.id)}</div><div class="arcade-menu-actions">${[
            ['ranked', 'Соревнование', 'data-mode="ranked"'],
            ['practice', 'Тренировка', 'data-mode="practice"'],
            ['learning', 'Обучение', 'data-menu-learning'],
            ['levels', game.id === 'kopatych' ? 'Мой огород' : game.id === 'hill' ? 'Мой гараж' : 'Уровни', 'data-menu-levels']
        ].map(([id, title, attr]) => `<button class="arcade-menu-action ${id}" ${attr}><span class="arcade-mode-icon">${icon(id==='levels'&&game.id==='kopatych'?'garden':id)}</span><span>${title}</span><span class="arcade-menu-arrow" aria-hidden="true">›</span></button>`).join('')}</div></section>`;
    }

    function levels(game, saved, selected) {
        const stage = selected || saved.unlocked,
            mission = ArcadeJourney.mission(game, stage), total=ArcadeJourney.stageCount(game);
        const record = saved.records.find(r => r.stage === stage);
        return `<section class="arcade-game-levels journey-hub" data-journey-game="${game}" aria-label="Уровни"><div class="arcade-levels-heading"><h3>Уровни</h3><span>${saved.cleared} / ${total}</span></div><div class="arcade-current-level"><div><h4>Уровень ${stage}</h4>${record?`<span class="arcade-level-stars" aria-label="${record.stars} из 3 звёзд">${'★'.repeat(record.stars)}${'☆'.repeat(3-record.stars)}</span>`:''}</div><p>${esc(ArcadeJourneyView.labels(mission))}</p><button class="arcade-menu-start" data-journey-play="${stage}">Играть</button></div><div class="arcade-level-grid" role="group" aria-label="Выбор уровня">${Array.from({length:total}, (_, i) => {
            const n = i + 1, r = saved.records.find(r => r.stage === n), locked = n > saved.unlocked;
            return `${i%ArcadeJourney.chapterSize(game)===0?`<h4 class="arcade-level-topic">${esc(ArcadeJourney.mission(game,n).title)}</h4>`:''}<button data-journey-stage="${n}" class="journey-stop ${n===stage?'is-selected':''} ${r?'is-complete':''}" aria-label="Уровень ${n}${locked?', закрыт':r?', звёзд: '+r.stars:''}" aria-pressed="${n===stage}" ${locked?'disabled':''}><b>${n}</b><span aria-hidden="true">${locked?'<svg viewBox="0 0 24 24"><path d="M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5Z"/></svg>':r?'★'.repeat(r.stars)+'☆'.repeat(3-r.stars):'•'}</span></button>`;
        }).join('')}</div></section>`;
    }

    function arenas(selected) {
        return `<section class="arcade-arena-screen"><h3>Тренировка</h3><div class="arcade-arena-grid" role="group" aria-label="Выбор арены">${ArcadeDrop.arenas.map(a => `<button data-arena="${a.id}" aria-pressed="${a.id===selected}"><svg viewBox="0 0 100 76" aria-hidden="true"><path d="M5 5V71H95V5"/>${a.lines.map(([ax,ay,bx,by])=>`<path d="M${(ax-12)/336*90+5} ${(ay-79)/337*66+5}L${(bx-12)/336*90+5} ${(by-79)/337*66+5}"/>`).join('')}${a.pins.map(([x,y,r])=>`<circle cx="${(x-12)/336*90+5}" cy="${(y-79)/337*66+5}" r="${r/336*90}"/>`).join('')}</svg><b>${esc(a.name)}</b></button>`).join('')}</div><button class="arcade-menu-start" data-practice-start>Играть</button></section>`;
    }

    window.ArcadeMenu = {
        home,
        levels,
        arenas
    };
})();
