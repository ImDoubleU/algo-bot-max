/* Presentation only: the same illustrated worlds continue from the library into play. */
(() => {
  'use strict';
  const themes = {
    orbit: ['#171d42', '#e1bdff', '#f2edff', 'space'],
    evolve: ['#153d32', '#c4e8a0', '#edfae3', 'garden'],
    bugs: ['#0d3632', '#9de4c4', '#e5fff3', 'circuit'],
    tower: ['#273648', '#ffcf73', '#fff4df', 'construction'],
    typing: ['#385446', '#f1d19a', '#fff8e7', 'desk'],
    debug: ['#14263d', '#68dcdf', '#e6f8ff', 'terminal'],
    '2048': ['#62462d', '#ffcf79', '#fff6e3', 'wood'],
    drop: ['#2b214e', '#c7acff', '#f6edff', 'cosmos'],
    memory: ['#293b52', '#f4cf8e', '#fff6e0', 'cards'],
    react: ['#173a3a', '#a7ecab', '#ecfff1', 'instruments'],
    kopatych: ['#2c4933', '#ffd17a', '#fff4d6', 'garden'],
    blocks: ['#274766', '#ffda73', '#eef7ff', 'toys'],
    hill: ['#253d37', '#ffce75', '#fff4df', 'rally'],
    bubbles: ['#0a3748', '#83e6df', '#e6ffff', 'aquarium'],
    sort: ['#2a5355', '#8ed4c1', '#f0fffa', 'laboratory'],
    words: ['#62452d', '#f1d18e', '#fff6e7', 'desk'],
  };

  function decorate(run) {
    const dialog = run.dialog, id = run.g.id, theme = themes[id];
    if (!theme) return;
    dialog.classList.add('has-interior');
    dialog.setAttribute('aria-label', run.g.name || dialog.querySelector('header h2')?.textContent || id);
    const scenes = { orbit: 'orbit.webp', evolve: 'expedition.webp', bugs: 'board.webp',
      tower: 'tower.webp', typing: 'playroom-v2.webp', debug: 'board.webp',
      '2048': 'playroom-v2.webp', drop: 'orbit.webp', memory: 'felt.svg',
      react: 'expedition.webp', kopatych: 'expedition.webp', blocks: 'playroom-v2.webp',
      hill: 'meadow.webp', bubbles: 'bubbles.webp', sort: 'laboratory-v2.webp', words: 'playroom-v2.webp' };
    dialog.style.setProperty('--interior-scene', `url('/miniapp/static/worlds/${scenes[id]}')`);
    dialog.dataset.interior = theme[3];
    for (const [key, value] of [['--interior-ink', theme[0]], ['--interior-accent', theme[1]],
        ['--interior-text', theme[2]], ['--interior-cover', `url('/miniapp/static/covers/${id}-960.webp')`]]) {
      dialog.style.setProperty(key, value);
    }
    const score = dialog.querySelector('#gameScore')?.parentElement;
    if (score && !score.querySelector('.interior-score-label')) {
      const label = document.createElement('span');
      label.className = 'interior-score-label';
      for (const node of [...score.childNodes]) {
        if (node.nodeType === Node.TEXT_NODE) { label.textContent += node.textContent; node.remove(); }
      }
      score.prepend(label);
    }
    if (score && !score.querySelector('.interior-score-icon')) {
      const icon = document.createElement('span'); icon.className = 'interior-score-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = '<svg viewBox="0 0 24 24"><path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/></svg>';
      score.insertBefore(icon, score.querySelector('#gameScore'));
    }
    const heading = dialog.querySelector('header h2')?.parentElement;
    if (heading) {
      let mode = heading.querySelector('.interior-mode');
      if (!mode) { mode = document.createElement('span'); mode.className = 'interior-mode'; heading.prepend(mode); }
      mode.textContent = dialog.classList.contains('is-learning') ? 'Обучение'
        : run.world?.journey ? 'Уровни' : dialog.dataset.playMode === 'ranked' ? 'Соревнование' : 'Тренировка';
    }
    const level = dialog.querySelector('#gameLevel');
    if (level) level.dataset.caption = run.world?.journey ? 'Уровень' : 'Сложность';
  }
  window.ArcadeInteriors = { decorate, themes };
})();
