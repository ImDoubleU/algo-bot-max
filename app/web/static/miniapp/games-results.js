/* Shared presentation for results and the server-confirmed reward receipt. */
(() => {
    'use strict';
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    } [c]));
    const trophy = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 4h8v6a4 4 0 0 1-8 0Z"/><path d="M8 6H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 2v5m-4 1h8"/></svg>';

    function reward(receipt) {
        if (!receipt?.awards?.length) return '';
        const total = receipt.credited + receipt.pending;
        const note = receipt.pending ? `${receipt.credited ? receipt.credited + ' AC начислено. ' : ''}${receipt.pending} AC начислим после обновления недельного лимита.` : 'Астрокоины уже на игровом балансе';
        return `<section class="arcade-reward-receipt" role="status" aria-live="polite"><span aria-hidden="true">✦</span><div><b>Поздравляем!</b><strong>Ваша награда — ${total} AC</strong><p>${esc(note)}</p></div></section>`;
    }

    function breakdown(receipt) {
        if (!receipt?.awards?.length) return '';
        return `<ul class="arcade-result-awards">${receipt.awards.map(a=>`<li><span>${esc(a.label.split('·').at(-1).trim())}</span><b>+${a.amount} AC</b></li>`).join('')}</ul>`;
    }

    function normal(run, result, rank) {
        const report = result.run.report,
            record = result.run.accepted && report.score > run.oldBest;
        const reaction = run.g.id === 'react' && report.score > 0 && report.details.reactionMs > 0;
        const value = reaction ? report.details.reactionMs : report.score,
            unit = reaction ? 'мс · средняя реакция' : run.g.unit;
        const hill = run.g.id === 'hill',
            caption = record ? 'Новый рекорд!' : hill ? 'Заезд завершён' : run.mode === 'practice' ? 'Тренировка завершена' : 'Игра завершена';
        const note = run.mode === 'practice' ? (hill ? 'Свободный заезд не участвует в рейтинге.' : 'Тренировка не участвует в рейтинге.') : result.run.accepted ? 'Результат сохранён в таблице лидеров.' : 'Эта игра завершена без участия в рейтинге.';
        return `${reward(result.rewards)}<div class="arcade-score-result"><p>${caption}</p>${ArcadePersonality.score(run.g.id, value, unit)}${reaction?`<p class="game-reaction-result">Точных реакций: ${report.score}</p>`:''}${result.run.accepted&&rank?`<div class="arcade-result-place">Твоё место — <b>#${rank}</b></div>`:''}</div><div class="arcade-result-actions"><button class="games-main" data-again>Ещё раз</button><button class="game-back" data-back>К играм</button></div><details class="arcade-result-details"><summary>Подробнее</summary>${breakdown(result.rewards)}<p>${note}</p><button data-analysis>Разбор игры</button></details>`;
    }

    function journey(run, report, receipt) {
        const j = report.journey;
        const hill = run.g.id === 'hill',
            back = hill ? 'К экспедиции' : 'К уровням';
        return `${reward(receipt)}<div class="arcade-level-result"><p>${hill?'Заезд':'Уровень'} ${j.stage}</p><div class="journey-result-stars" aria-label="${j.stars} из 3 звёзд">${'★'.repeat(j.stars)}${'☆'.repeat(3-j.stars)}</div><h3>${j.success?(hill?'Заезд пройден!':'Уровень пройден!'):'Попробуем ещё?'}</h3><p>${report.score} / ${j.goal}${hill?' м':''}</p></div><div class="arcade-result-actions"><button class="games-main" data-journey-next>${!j.success?'Ещё раз':j.stage<24?(hill?'Следующий заезд':'Следующий уровень'):back}</button>${j.stage<24||!j.success?`<button class="game-back" data-journey-map>${back}</button>`:''}</div><details class="arcade-result-details"><summary>Звёзды и награды</summary>${breakdown(receipt)}<ul class="journey-result-goals">${ArcadeJourneyView.starGoals(ArcadeJourney.mission(run.g.id,j.stage)).map((goal,i)=>`<li class="${j.stars>i?'is-done':''}"><span>${j.stars>i?'✓':'○'}</span>${esc(goal)}</li>`).join('')}</ul></details>`;
    }
    window.ArcadeResults = {
        trophy,
        reward,
        normal,
        journey
    };
})();
