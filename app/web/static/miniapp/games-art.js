/* Original, self-contained SVG marks for the local Algo Arcade prototype. */
(() => {
  "use strict";
  let serial = 0;
  const faces = (x, y) =>
    `<g fill="#302a4e"><ellipse cx="${x-10}" cy="${y}" rx="3.3" ry="4.3"/><ellipse cx="${x+10}" cy="${y}" rx="3.3" ry="4.3"/></g><path d="M${x-5} ${y+12}q5 5 10 0" fill="none" stroke="#302a4e" stroke-width="2.8" stroke-linecap="round"/>`;

  function render(id) {
    if (window.ArcadeExtraArt?.has(id)) return window.ArcadeExtraArt.render(id);
    const u = "arcade-art-" + (++serial),
      g = n => `url(#${u}-${n})`;
    const star = (x, y, s = 6, c = "#f3c764") =>
      `<path d="m${x} ${y-s} ${s*.3} ${s*.7} ${s*.7} ${s*.3}-${s*.7} ${s*.3}-${s*.3} ${s*.7}-${s*.3}-${s*.7}-${s*.7}-${s*.3} ${s*.7}-${s*.3}Z" fill="${c}"/>`;
    const frame = (body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 176" fill="none" aria-hidden="true" focusable="false" data-arcade-mark="${id}"><defs>
      <linearGradient id="${u}-violet" x1="50" y1="25" x2="190" y2="160" gradientUnits="userSpaceOnUse"><stop stop-color="#d7c5ff"/><stop offset="1" stop-color="#8e6dd5"/></linearGradient>
      <linearGradient id="${u}-mint" x1="90" y1="30" x2="180" y2="165" gradientUnits="userSpaceOnUse"><stop stop-color="#e5f8b8"/><stop offset="1" stop-color="#87c8a7"/></linearGradient>
      <linearGradient id="${u}-peach" x1="80" y1="30" x2="180" y2="155" gradientUnits="userSpaceOnUse"><stop stop-color="#ffe0a2"/><stop offset="1" stop-color="#ed9a84"/></linearGradient>
      <linearGradient id="${u}-blue" x1="80" y1="30" x2="190" y2="150" gradientUnits="userSpaceOnUse"><stop stop-color="#dcf5ff"/><stop offset="1" stop-color="#8db1e6"/></linearGradient>
      <filter id="${u}-shadow" x="-40%" y="-40%" width="180%" height="200%"><feDropShadow dx="0" dy="6" stdDeviation="4" flood-color="#4a365f" flood-opacity=".16"/></filter>
    </defs>${body}</svg>`;
    const bodies = {
      orbit: () => `
        <ellipse cx="127" cy="103" rx="98" ry="36" transform="rotate(-19 127 103)" stroke="#9983c2" stroke-width="2" stroke-dasharray="4 8"/>
        ${star(36,54,8)}${star(218,47,6,"#ab92d6")}<circle cx="201" cy="139" r="3" fill="#b39bde"/>
        <g filter="${g("shadow")}"><circle cx="99" cy="117" r="33" fill="${g("violet")}" stroke="#79639f" stroke-width="2.5"/>
        <ellipse cx="99" cy="117" rx="48" ry="12" transform="rotate(-20 99 117)" stroke="#d5f19b" stroke-width="8"/>
        <circle cx="87" cy="104" r="7" fill="#e3d4ff"/><circle cx="107" cy="125" r="4" fill="#9575c3"/>
        <g transform="rotate(13 164 72)"><path d="M139 102v15h51v-15" fill="#f5f1fb" stroke="#7d6a9c" stroke-width="2.5"/>
        <circle cx="164" cy="69" r="43" fill="#fffaf0" stroke="#7d6a9c" stroke-width="2.5"/>
        <circle cx="164" cy="69" r="34" fill="${g("blue")}" stroke="#8aa6bd" stroke-width="2"/>
        <path d="m141 66 1-24 16 12h14l15-12v25q4 26-23 26t-23-27Z" fill="#fff3d5" stroke="#9a7d83" stroke-width="2" stroke-linejoin="round"/>
        <path d="m146 54 1-5 7 6m22 0 6-6v7" stroke="#e6b0a9" stroke-width="3" stroke-linecap="round"/>
        ${faces(164,70)}<path d="M140 47q7-9 17-10" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
        <rect x="121" y="64" width="9" height="17" rx="4" fill="#c1a9e8"/><rect x="198" y="64" width="9" height="17" rx="4" fill="#c1a9e8"/>
        <circle cx="181" cy="111" r="3" fill="#9acb9c"/></g></g>`,
      evolve: () => `
        ${star(37,52,7,"#a5ceb1")}${star(213,35,6)}<path d="M56 133q66 29 140-4" stroke="#9bc4aa" stroke-width="2" stroke-dasharray="4 6"/>
        <g filter="${g("shadow")}"><g transform="rotate(-12 69 96)"><rect x="42" y="71" width="54" height="57" rx="21" fill="${g("blue")}" stroke="#7b9ba5" stroke-width="2.5"/>
        <path d="m55 71-5-11m32 10 5-11" stroke="#7b9ba5" stroke-width="4" stroke-linecap="round"/>${faces(69,92)}</g>
        <g transform="rotate(7 123 92)"><rect x="98" y="67" width="51" height="55" rx="19" fill="${g("peach")}" stroke="#b48774" stroke-width="2.5"/>${faces(123,89)}</g>
        <path d="M154 72q-5-15 6-23l13 9q9-6 18-1l13-12q13 11 8 27l3 31q0 32-34 32t-33-31Z" fill="${g("mint")}" stroke="#6e9f82" stroke-width="2.8" stroke-linejoin="round"/>
        ${faces(182,85)}<ellipse cx="164" cy="101" rx="6" ry="3" fill="#f4bead"/><ellipse cx="200" cy="101" rx="6" ry="3" fill="#f4bead"/>
        <path d="m173 126-6 15m27-15 6 15" stroke="#6e9f82" stroke-width="5" stroke-linecap="round"/>
        <path d="m161 51 1-9m40 5 5-8" stroke="#eff8c6" stroke-width="3" stroke-linecap="round"/></g>`,
      bugs: () =>
        `
        <g stroke="#c39370" stroke-width="2.5" stroke-linecap="round"><path d="M48 62V45h17m126 0h17v17M48 121v17h17m126 0h17v-17"/>
        <path d="m78 72-16-8m17 30H59m21 20-15 12m112-54 16-8m-17 30h20m-22 20 16 12" stroke-width="5"/></g>
        <g filter="${g("shadow")}" transform="rotate(-9 128 88)"><path d="m107 53-5-20m47 20 7-20" stroke="#795b9a" stroke-width="4" stroke-linecap="round"/>
        <circle cx="102" cy="32" r="5" fill="#d8ef9b"/><circle cx="157" cy="32" r="5" fill="#d8ef9b"/>
        <rect x="86" y="48" width="84" height="91" rx="34" fill="${g("violet")}" stroke="#795b9a" stroke-width="2.8"/>
        <path d="M128 108v27" stroke="#9a7bc2" stroke-width="2"/><path d="M100 60q10-8 22-8" stroke="#eee0ff" stroke-width="4" stroke-linecap="round"/>
        <rect x="98" y="69" width="60" height="30" rx="13" fill="#443852"/><ellipse cx="114" cy="83" rx="4" ry="5" fill="#def2a4"/><ellipse cx="142" cy="83" rx="4" ry="5" fill="#def2a4"/>
        <path d="M118 111q10 7 20 0" stroke="#4e3a66" stroke-width="3" stroke-linecap="round"/></g>${star(196,103,7,"#d5b676")}`,
      tower: () =>
        `
        ${star(44,75,7,"#99b5db")}${star(206,47,6)}<path d="M47 149h160" stroke="#a3b5d1" stroke-width="2.5" stroke-linecap="round"/>
        <g filter="${g("shadow")}"><path d="m59 113 25-14h116l-25 14Z" fill="#b3caf1" stroke="#7c92b4" stroke-width="2.5" stroke-linejoin="round"/>
        <path d="M59 113h116v31H59Z" fill="${g("blue")}" stroke="#7c92b4" stroke-width="2.5"/><path d="m175 113 25-14v31l-25 14Z" fill="#8ba7d2" stroke="#7c92b4" stroke-width="2.5"/>
        <path d="m76 75 21-13h92l-21 13Z" fill="#e0d0fa" stroke="#9172b3" stroke-width="2.5" stroke-linejoin="round"/>
        <rect x="76" y="75" width="92" height="30" rx="3" fill="${g("violet")}" stroke="#9172b3" stroke-width="2.5"/>
        <path d="m168 75 21-13v30l-21 13Z" fill="#a68bc9" stroke="#9172b3" stroke-width="2.5"/>
        <g transform="rotate(-7 130 41)"><path d="m96 39 17-11h64l-17 11Z" fill="#fff1c0" stroke="#bd9760" stroke-width="2.5" stroke-linejoin="round"/>
        <rect x="96" y="39" width="64" height="25" rx="3" fill="${g("peach")}" stroke="#bd9760" stroke-width="2.5"/>
        <path d="m160 39 17-11v25l-17 11Z" fill="#e7af78" stroke="#bd9760" stroke-width="2.5"/>
        <path d="M111 50h8m12 0h14" stroke="#c69567" stroke-width="3" stroke-linecap="round"/></g>
        <rect x="95" y="82" width="31" height="15" rx="3" fill="#f1e7ff"/><path d="m103 87-3 3 3 3m15-6 3 3-3 3" stroke="#9675bf" stroke-width="2"/>
        <path d="M73 123h9m8 0h9m8 0h9m8 0h9m-60 10h60" stroke="#8eadd2" stroke-width="3" stroke-linecap="round"/></g>`,
      typing: () => `
        ${star(45,44,6)}${star(216,118,6,"#d6b96a")}<g filter="${g("shadow")}" transform="rotate(-7 128 103)">
        <rect x="40" y="66" width="177" height="76" rx="15" fill="#d9b36b" stroke="#ad8c53" stroke-width="2.5"/>
        <rect x="40" y="60" width="177" height="76" rx="15" fill="#fff2ca" stroke="#ad8c53" stroke-width="2.5"/>
        <g fill="#fffaf0" stroke="#d7bc85" stroke-width="1.8"><rect x="53" y="74" width="20" height="18" rx="4"/><rect x="79" y="74" width="20" height="18" rx="4"/><rect x="105" y="74" width="20" height="18" rx="4"/><rect x="131" y="74" width="20" height="18" rx="4"/><rect x="157" y="74" width="20" height="18" rx="4"/><rect x="183" y="74" width="20" height="18" rx="4"/>
        <rect x="59" y="99" width="23" height="20" rx="5"/><rect x="89" y="99" width="84" height="20" rx="5"/><rect x="180" y="99" width="23" height="20" rx="5"/></g>
        <rect x="50" y="67" width="25" height="23" rx="5" fill="${g("violet")}" stroke="#9877bc" stroke-width="2"/>
        <text x="62" y="83" text-anchor="middle" fill="#fffaf3" font-family="system-ui,sans-serif" font-weight="800" font-size="13">A</text>
        <rect x="79" y="64" width="25" height="23" rx="5" fill="${g("mint")}" stroke="#8eaf83" stroke-width="2"/>
        <text x="91" y="80" text-anchor="middle" fill="#426949" font-family="system-ui,sans-serif" font-weight="800" font-size="13">Я</text></g>
        <path d="m176 22-19 29h18l-9 26 32-37h-21l10-18Z" fill="#e4b84e" stroke="#b88b39" stroke-width="2" stroke-linejoin="round"/>
        <path d="m135 29 6 7m70 1 8-4" stroke="#d5b56f" stroke-width="3" stroke-linecap="round"/>`,
      debug: () => `
        ${star(37,113,6,"#a2b9d6")}${star(215,39,7)}<g filter="${g("shadow")}">
        <rect x="47" y="33" width="151" height="110" rx="14" fill="#f3effb" stroke="#7e8fab" stroke-width="2.5"/>
        <path d="M47 56h151" stroke="#b6c3d6" stroke-width="2"/><g fill="#a0b5d4"><circle cx="60" cy="45" r="3"/><circle cx="71" cy="45" r="3"/><circle cx="82" cy="45" r="3"/></g>
        <rect x="56" y="65" width="133" height="68" rx="6" fill="#34354e"/>
        <path d="m85 79-12 11 12 11m28-22 12 11-12 11m-18 7 8-33" stroke="#c1e49c" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M72 119h34m12 0h16" stroke="#8e89b7" stroke-width="3" stroke-linecap="round"/>
        <g transform="rotate(-14 174 109)"><path d="m185 127 20 27" stroke="#776291" stroke-width="13" stroke-linecap="round"/>
        <circle cx="170" cy="105" r="29" fill="${g("blue")}" stroke="#7c699b" stroke-width="5"/>
        <path d="m158 106 8 8 16-19" stroke="#607d76" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M151 98q4-9 12-12" stroke="#fff" stroke-width="3" stroke-linecap="round"/></g></g>`,
      "2048": () =>
        `
        ${star(38,113,6,"#dab475")}${star(218,50,6)}<g filter="${g("shadow")}" stroke-linejoin="round">
        <g transform="rotate(-9 100 74)"><rect x="61" y="29" width="65" height="61" rx="12" fill="#fff5dd" stroke="#c9af83" stroke-width="2.5"/>
        <text x="94" y="70" text-anchor="middle" fill="#ae8c59" stroke="none" font-family="system-ui,sans-serif" font-size="31" font-weight="850">2</text></g>
        <g transform="rotate(10 170 70)"><rect x="139" y="40" width="60" height="57" rx="12" fill="${g("peach")}" stroke="#c09170" stroke-width="2.5"/>
        <text x="169" y="78" text-anchor="middle" fill="#a86b4c" stroke="none" font-family="system-ui,sans-serif" font-size="28" font-weight="850">4</text></g>
        <rect x="48" y="92" width="62" height="57" rx="12" fill="${g("violet")}" stroke="#9b7db5" stroke-width="2.5"/>
        <text x="79" y="130" text-anchor="middle" fill="#fff7ee" stroke="none" font-family="system-ui,sans-serif" font-size="28" font-weight="850">8</text>
        <g transform="rotate(-5 156 119)"><rect x="111" y="85" width="91" height="71" rx="14" fill="#e6bb60" stroke="#bc904a" stroke-width="2.5"/>
        <path d="M125 94h49" stroke="#ffe8b1" stroke-width="3" stroke-linecap="round"/>
        <text x="156" y="130" text-anchor="middle" fill="#fffaf0" stroke="none" font-family="system-ui,sans-serif" font-size="27" font-weight="850">2048</text></g></g>`,
      drop: () => `
        ${star(43,56,7,"#ae96d0")}${star(218,109,6)}<g filter="${g("shadow")}">
        <path d="M66 65v73q0 14 14 14h96q14 0 14-14V65" fill="#ece8fa" fill-opacity=".65" stroke="#8d79b2" stroke-width="3" stroke-linecap="round"/>
        <path d="M74 75v57" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
        <circle cx="97" cy="123" r="23" fill="${g("mint")}" stroke="#8ead94" stroke-width="2"/>
        <circle cx="151" cy="117" r="30" fill="${g("violet")}" stroke="#9274b3" stroke-width="2.5"/>
        ${faces(151,114)}<path d="m139 94 3-8 6 7m9-1 6-7 3 11" fill="#c3a9eb" stroke="#9274b3" stroke-width="2"/>
        <path d="M83 115q3-5 9-7" stroke="#f5ffdb" stroke-width="3" stroke-linecap="round"/>
        <circle cx="151" cy="34" r="16" fill="${g("peach")}" stroke="#c79d86" stroke-width="2"/>
        <path d="M151 57v17m-5-5 5 6 5-6" stroke="#ad97c4" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="103" cy="88" r="9" fill="${g("blue")}" stroke="#9eb2ca" stroke-width="1.5"/></g>`,
      memory: () => `
        ${star(40,113,7,"#8eb798")}${star(213,47,6)}<g filter="${g("shadow")}">
        <g transform="rotate(-16 95 91)"><rect x="53" y="37" width="78" height="112" rx="13" fill="${g("violet")}" stroke="#9173b0" stroke-width="2.5"/>
        <rect x="61" y="45" width="62" height="96" rx="8" stroke="#dfcbfc" stroke-width="2"/>
        <path d="m91 70 6 14 15 6-15 6-6 15-6-15-15-6 15-6Z" fill="#f3e9ff"/>
        <circle cx="72" cy="58" r="3" fill="#dfcbfc"/><circle cx="112" cy="128" r="3" fill="#dfcbfc"/></g>
        <g transform="rotate(12 163 95)"><rect x="123" y="39" width="79" height="112" rx="13" fill="#fff9e9" stroke="#99b49b" stroke-width="2.5"/>
        <path d="m137 87 2-20 13 10h14l13-10 2 20q3 26-22 26t-22-26Z" fill="${g("mint")}" stroke="#8bac8b" stroke-width="2.3"/>
        ${faces(159,91)}<path d="m137 132 4-7 4 7-4 7Z" fill="#b5d69d"/>
        <path d="m184 52 3 5-3 5-3-5Z" fill="#b5d69d"/></g></g>`,
      react: () =>
        `
        <circle cx="121" cy="83" r="62" stroke="#d6bd7f" stroke-width="2" stroke-dasharray="3 8"/>
        <path d="m49 52-8-7m159 18 12-2m-32 72 9 9" stroke="#d4ae66" stroke-width="3" stroke-linecap="round"/>
        <g filter="${g("shadow")}"><circle cx="121" cy="88" r="48" fill="#e6c276" stroke="#b59659" stroke-width="2.5"/>
        <circle cx="121" cy="79" r="48" fill="#f9e9b8" stroke="#b59659" stroke-width="2.5"/>
        <circle cx="121" cy="79" r="37" fill="${g("mint")}" stroke="#a8bf7f" stroke-width="2"/>
        <path d="m128 49-24 34h17l-7 27 26-38h-17l5-23Z" fill="#fffaf0" stroke="#98ab69" stroke-width="2" stroke-linejoin="round"/>
        <path d="m166 111-1 30-9-6-6 14-11-5 6-14-10-2Z" fill="#fffaf1" stroke="#9d8177" stroke-width="2.5" stroke-linejoin="round"/>
        <path d="M88 58q8-10 22-13" stroke="#fffcef" stroke-width="4" stroke-linecap="round"/></g>${star(196,36,7)}`,
      arcade: () =>
        `
        <g filter="${g("shadow")}"><rect x="51" y="35" width="156" height="110" rx="31" fill="${g("violet")}" stroke="#81659f" stroke-width="3"/>
        <rect x="62" y="45" width="134" height="87" rx="22" fill="#342e4c"/>
        <path d="m129 57-27 52h16l4-9h20l4 9h16l-27-52Zm1 20 7 14h-14Z" fill="${g("mint")}"/>
        <path d="M74 84h18m-9-9v18" stroke="#f4db9d" stroke-width="4" stroke-linecap="round"/>
        <circle cx="176" cy="79" r="5" fill="#ecc1ad"/><circle cx="169" cy="95" r="5" fill="#c2ade8"/>
        <path d="M96 145h65" stroke="#b19ad4" stroke-width="5" stroke-linecap="round"/></g>${star(219,52,7)}${star(35,118,6,"#c4dda0")}`,
    };
    return frame((bodies[id] || bodies.arcade)());
  }
  window.AlgoGameArt = {
    render
  };
})();
