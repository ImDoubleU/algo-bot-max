/* Test pilot: only legal inputs, never direct score/state changes. */
function playAdventure(setup, attempt = 0) {
  const W = ArcadeWorld,
    E = AlgoGameEngine,
    w = W.create(setup),
    events = [];
  let iterations = 0,
    sortIndex = 0,
    lastSort = 0;
  const send = a => {
    if (w.ended) return;
    const e = {
      ...a,
      t: w.tick,
      source: w.device
    };
    events.push(e);
    W.input(w, e);
  };
  const wait = n => W.advance(w, n);
  const clone = () => JSON.parse(JSON.stringify(w));

  function boardValue(b) {
    const logs = b.map(v => v ? Math.log2(v) : 0),
      empty = b.filter(v => !v).length;
    let smooth = 0;
    const totals = [0, 0, 0, 0];
    for (let y = 0; y < 4; y++)
      for (let x = 0; x < 4; x++) {
        const i = y * 4 + x;
        if (x < 3) {
          const diff = logs[i] - logs[i + 1];
          totals[0] -= Math.max(0, diff);
          totals[1] -= Math.max(0, -diff);
          if (logs[i] && logs[i + 1]) smooth += Math.abs(diff);
        }
        if (y < 3) {
          const diff = logs[i] - logs[i + 4];
          totals[2] -= Math.max(0, diff);
          totals[3] -= Math.max(0, -diff);
          if (logs[i] && logs[i + 4]) smooth += Math.abs(diff);
        }
      }
    const monotone = Math.max(totals[0], totals[1]) + Math.max(totals[2], totals[3]);
    const weights = [16, 15, 14, 13, 9, 10, 11, 12, 8, 7, 6, 5, 1, 2, 3, 4];
    const snake = b.reduce((n, v, i) => n + v * weights[i], 0);
    return empty * 270 - smooth * 10 + monotone * 100 + Math.max(...logs) * 90 + snake * .03;
  }

  function choose2048() {
    const dirs = ['left', 'up', 'down', 'right'];
    let best = -Infinity,
      chosen = null;

    function search(state, depth) {
      if (state.journey.complete) return 1e8;
      if (state.ended) return -1e6;
      if (!depth) return boardValue(state.board);
      let value = -Infinity;
      for (const dir of dirs) {
        const next = JSON.parse(JSON.stringify(state));
        if (!W.input(next, {
            type: 'move',
            dir
          })) continue;
        value = Math.max(value, search(next, depth - 1));
      }
      return value === -Infinity ? -1e6 : value;
    }
    const depth = w.board.filter(v => !v).length < 4 ? 4 : 3;
    for (const dir of dirs) {
      const next = clone();
      if (!W.input(next, {
          type: 'move',
          dir
        })) continue;
      const value = search(next, depth - 1);
      if (value > best) {
        best = value;
        chosen = dir;
      }
    }
    return chosen;
  }
  while (!w.ended && iterations++ < 12000 && events.length < 19000) {
    const id = w.id,
      j = w.journey;
    if (id === 'orbit') {
      if (!w.flight) {
        const c = Jconfig(),
          aim = w.target + Math.sin(w.time * .8) * c.orbitDrift,
          delta = Math.abs(Math.atan2(Math.sin(w.angle - aim), Math.cos(w.angle - aim)));
        if (delta < c.orbitWindow * .25) send({
          type: 'tap'
        });
      }
      wait(1);
    } else if (id === 'tower') {
      const c = Jconfig();
      if (Math.abs(w.left - w.blocks.at(-1).left) < Math.min(2, c.perfectWindow * .4)) {
        send({
          type: 'tap'
        });
        wait(6);
      } else wait(1);
    } else if (id === 'evolve') {
      if(w.expedition) {
        const slot=w.expedition.orders.findIndex(v=>w.cells.includes(v));
        if(slot>=0){send({type:'cell',i:w.cells.indexOf(w.expedition.orders[slot])});wait(12);send({type:'rescue',slot});wait(12);continue;}
      }

      let pair = null;
      for (let i = 0; i < 16; i++)
        for (let k = i + 1; k < 16; k++)
          if (w.cells[i] === w.cells[k] && (!pair || w.cells[i] > w.cells[pair[0]])) {
            pair = [i, k];
          }
      if (!pair) break;
      wait(12);
      send({
        type: 'cell',
        i: pair[0]
      });
      wait(12);
      send({
        type: 'cell',
        i: pair[1]
      });
    } else if (id === 'bugs') {
      const target = w.targets.find(t => !t.good);
      if (target) {
        send({
          type: 'tap',
          x: target.x,
          y: target.y
        });
        wait(12);
      } else wait(6);
    } else if (id === 'typing') {
      wait(6);
      send({
        type: 'text',
        value: w.text[w.typed.length]
      });
    } else if (id === 'debug') {
      const t = w.tasks[w.index];
      wait(12);
      send({
        type: 'line',
        i: t.line
      });
      wait(12);
      send({
        type: t.freeAnswer ? 'fix' : 'answer',
        ...(t.freeAnswer?{value:t.options[t.answer]}:{i:t.answer})
      });
      if (!w.ended) {
        wait(12);
        send({
          type: 'next'
        });
      }
    } else if (id === 'memory') {
      if (w.between) {
        send({
          type: 'next'
        });
        continue;
      }
      const i = w.cards.findIndex((_, i) => !w.matched.includes(i)),
        k = w.cards.findIndex((v, k) => k !== i && v === w.cards[i] && !w.matched.includes(k));
      wait(12);
      send({
        type: 'cell',
        i
      });
      wait(12);
      send({
        type: 'cell',
        i: k
      });
    } else if (id === 'react') {
      if (w.signal === 'go') {
        wait(12);
        send({
          type: 'tap'
        });
      } else wait(3);
    } else if (id === '2048') {
      if (w.board.filter(v => !v).length < 2 && j.used < j.charges) {
        const largest = w.board.indexOf(Math.max(...w.board));
        if (largest !== 0 && w.board[0] < w.board[largest]) {
          send({
            type: 'power'
          });
          send({
            type: 'swap_cell',
            i: 0
          });
          send({
            type: 'swap_cell',
            i: largest
          });
          wait(1);
        }
      }
      const dir = choose2048();
      if (!dir) break;
      wait(18);
      send({
        type: 'move',
        dir
      });
    } else if (id === 'drop') {
      if (w.cool > 0) {
        wait(12);
        continue;
      }
      const level = w.queue[0],
        r = W.rad[level];
      let best = -Infinity,
        x = 180;
      for (let pos = r + 14; pos < 346 - r; pos += 14) {
        let y = 416 - r,
          match = 0;
        for (const b of w.balls) {
          const dx = b.x - pos,
            sum = r + b.r;
          if (Math.abs(dx) < sum) {
            const top = b.y - Math.sqrt(sum * sum - dx * dx);
            if (top < y) {
              y = top;
              match = b.level === level ? 1 : 0;
            }
          }
        }
        const value = y + match * 200 - Math.abs(pos - (attempt % 2 ? 250 : 110)) * .015;
        if (value > best) {
          best = value;
          x = pos;
        }
      }
      send({
        type: 'tap',
        x
      });
      wait(45);
    } else if (id === 'hill') {
      const h = w.hill,
        angle = Math.atan2(Math.sin(h.angle), Math.cos(h.angle)),
        lookahead = [0, .2, .4, .6, .8][attempt % 5],
        landing = lookahead ? Math.atan(ArcadeHill.slope(w, h.x + h.vx * lookahead)) : 0,
        error = landing - angle - h.omega * (.25 + (attempt % 3) * .1);
      const pedals = {
        gas: h.contact ? Number(angle < .75 + (attempt % 5) * .15) : Number(error > .04),
        brake: h.contact ? Number(angle > 1 + (attempt % 5) * .15) : Number(error < -.08)
      };
      for (const [pedal, value] of Object.entries(pedals)) {
        if (h[pedal] !== value) send({type: 'pedal', pedal, value});
      }
      wait(6);
    } else if (id === 'runner') {
      const speed = 155 + Math.min(160, w.score * 4.5),
        o = w.obstacles.find(o => !o.passed && o.x + o.width > 65);
      if (o && w.runnerGround && o.x < 91 + speed * (.31 + attempt * .015)) send({
        type: 'tap'
      });
      if (o && !w.runnerGround && o.x < 97 && o.x + o.width > 68 && w.runnerY + 22 > 380 - o.height + 6 && j.used < j.charges) send({
        type: 'power'
      });
      wait(1);
    } else if (id === 'blocks') {
      let chosen = null,
        best = -Infinity;
      for (let p = 0; p < 3; p++) {
        const piece = w.pieces[p];
        if (!piece) continue;
        for (let y = 0; y < 8; y++)
          for (let x = 0; x < 8; x++) {
            if (!piece.every(([dx, dy]) => x + dx < 8 && y + dy < 8 && !w.blockBoard[(y + dy) * 8 + x + dx])) continue;
            const b = w.blockBoard.slice();
            for (const [dx, dy] of piece) b[(y + dy) * 8 + x + dx] = 1;
            const rows = [],
              cols = [];
            for (let i = 0; i < 8; i++) {
              if (b.slice(i * 8, i * 8 + 8).every(Boolean)) rows.push(i);
              if (Array.from({
                  length: 8
                }, (_, y) => b[y * 8 + i]).every(Boolean)) cols.push(i);
            }
            const next = b.map((v, i) => rows.includes(Math.floor(i / 8)) || cols.includes(i % 8) ? 0 : v);
            let adjacent = 0,
              holes = 0,
              squares = 0;
            for (let size = 2; size <= 4; size++)
              for (let sy = 0; sy <= 8 - size; sy++)
                for (let sx = 0; sx <= 8 - size; sx++) {
                  let free = true;
                  for (let dy = 0; dy < size; dy++)
                    for (let dx = 0; dx < size; dx++)
                      if (next[(sy + dy) * 8 + sx + dx]) free = false;
                  if (free) squares += size * (attempt % 2 ? 3 : 2);
                }
            for (let i = 0; i < 64; i++)
              if (!next[i]) {
                const n = [i - 1, i + 1, i - 8, i + 8].filter(k => k >= 0 && k < 64 && Math.abs(k % 8 - i % 8) + Math.abs(Math.floor(k / 8) - Math.floor(i / 8)) === 1);
                const filled = n.filter(k => next[k]).length;
                adjacent += filled;
                holes += filled === n.length ? 1 : 0;
              }
            let options = 0,
              blocked = 0;
            for (let k = 0; k < 3; k++)
              if (k !== p && w.pieces[k]) {
                const piece = w.pieces[k],
                  count = Array.from({
                    length: 64
                  }, (_, i) => piece.every(([dx, dy]) => i % 8 + dx < 8 && Math.floor(i / 8) + dy < 8 && !next[(Math.floor(i / 8) + dy) * 8 + i % 8 + dx])).filter(Boolean).length;
                options += Math.log1p(count) * 15;
                if (!count) blocked++;
              }
            const value = options - blocked * 2000 + (rows.length + cols.length) * 160 + next.filter(v => !v).length * 3 - holes * 30 - adjacent * .3 + squares + piece.length * 12 + (attempt % 3 ? x - y : x + y) * .02;
            if (value > best) {
              best = value;
              chosen = {
                type: 'place',
                piece: p,
                x,
                y
              };
            }
          }
      }
      if (!chosen) {
        let rescue = null;
        for (let k = 0; k < 3 && !rescue; k++) {
          let p = w.pieces[k];
          if (!p) continue;
          for (let turn = 1; turn <= j.charges - j.used && !rescue; turn++) {
            const rotated = p.map(([x, y]) => [-y, x]),
              minX = Math.min(...rotated.map(v => v[0])),
              minY = Math.min(...rotated.map(v => v[1]));
            p = rotated.map(([x, y]) => [x - minX, y - minY]);
            if (Array.from({
                length: 64
              }, (_, i) => p.every(([dx, dy]) => i % 8 + dx < 8 && Math.floor(i / 8) + dy < 8 && !w.blockBoard[(Math.floor(i / 8) + dy) * 8 + i % 8 + dx])).some(Boolean)) rescue = {
              k,
              turn
            };
          }
        }
        if (rescue) {
          send({
            type: 'piece',
            i: rescue.k
          });
          for (let i = 0; i < rescue.turn; i++) send({
            type: 'power'
          });
          wait(1);
          continue;
        }
        break;
      }
      wait(18);
      send(chosen);
    } else if (id === 'bubbles') {
      if (w.projectile) {
        wait(10);
        continue;
      }
      let best = -Infinity,
        shot = null;
      for (let x = -80; x <= 440; x += 20) {
        const test = clone();
        W.input(test, {
          type: 'shoot',
          x,
          y: 0
        });
        let steps = 0;
        while (test.projectile && !test.ended && steps++ < 250) W.advance(test, 1);
        const count = test.bubbleBoard.filter(v => v >= 0).length,
          low = test.bubbleBoard.reduce((n, v, i) => v >= 0 ? Math.max(n, Math.floor(i / 8)) : n, 0);
        const value = (test.score - w.score) * 15 - low * 25 - count * .2 - (test.ended && !test.journey.complete ? 10000 : 0);
        if (value > best) {
          best = value;
          shot = {
            type: 'shoot',
            x,
            y: 0
          };
        }
      }
      if (best < 0 && j.used < j.charges) {
        send({
          type: 'power'
        });
        wait(1);
        continue;
      }
      wait(12);
      send(shot);
    } else if (id === 'sort') {
      if (w.sortWon) {
        send({
          type: 'next'
        });
        sortIndex = 0;
        continue;
      }
      if (w.score !== lastSort) {
        lastSort = w.score;
        sortIndex = 0;
      }
      const move = w.sortSolution[sortIndex++];
      if (!move) break;
      wait(12);
      send(move);
    } else if (id === 'words') {
      const word = w.wordPack.answers.find(a => !w.roundWords.includes(a) && a.length >= j.minimumWord);
      if (!word) break;
      wait(60);
      send({
        type: 'word',
        value: word
      });
    } else break;
  }

  function Jconfig() {
    const progress = w.id === 'evolve' ? w.merges : w.id === 'memory' ? w.cleared : w.score;
    return ArcadeJourney.difficulty(w, E.difficulty(w.id, progress));
  }
  return {
    events,
    ticks: w.tick,
    report: W.report(w),
    iterations,
    stuck: !w.ended
  };
}
