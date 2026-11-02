/* Original vector illustration system for Kopatych's garden. */
(() => {
  'use strict';
  let serial = 0;
  const p = {ink:'#775034',orange:'#cf773c',light:'#e9984d',cream:'#fae6b2',leaf:'#71864b',dark:'#4d623d',gold:'#ebbf62',wood:'#bc8d59',blue:'#a5c4c4'};
  const wrap = (body,box='0 0 80 80',cover=false) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}" preserveAspectRatio="${cover?'xMidYMid slice':'xMidYMid meet'}" fill="none" aria-hidden="true" focusable="false">${body}</svg>`;
  const leaf=(x,y,rotate=0)=>`<g transform="translate(${x} ${y}) rotate(${rotate})"><path d="M0 0Q-21-19-24-6-22 7 0 0Z" fill="#879a52"/><path d="M0 0Q17-28 24-13 25-1 0 0Z" fill="#6b8648"/><path d="M0 0q-5-35 5-33 11 2-5 33Z" fill="#a3b66c"/></g>`;
  function character(boost=false){
    const id='kopatych-coat-'+(++serial);
    return wrap(`<defs><radialGradient id="${id}" cx=".3" cy=".23" r=".84"><stop stop-color="#e89c54"/><stop offset=".65" stop-color="#d78542"/><stop offset="1" stop-color="#be6933"/></radialGradient></defs>
      <ellipse cx="150" cy="281" rx="88" ry="10" fill="#6c58391b"/>
      <g stroke="#87512e" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round">
      <path d="M222 153q31-19 35-1 6 19-25 31" fill="#cb7638"/>
      <path d="m253 130-8 129" stroke="#ba8c54" stroke-width="9"/>
      <path d="m249 255 26 3-6 22-14 9-12-11Z" fill="#c0c6bb" stroke="#7f8c7d" stroke-width="3"/>
      <path d="m248 126 11 1 3-22-15-1Z" fill="#bd8a50"/>
      <path d="M99 251q-21 12-16 23 8 15 36 2l5-17m47 0 8 18q26 11 32-3 4-11-19-23" fill="#b96d35"/>
      <path d="M78 105q-20-26-35-8-13 17 9 34m151-24q21-27 36-10 14 16-7 35" fill="#c77a3c"/>
      <path d="M69 109q-11-14-17-5t7 19m155-14q10-15 17-6t-6 20" fill="#e6a45e" stroke="none"/>
      <circle cx="143" cy="174" r="96" fill="url(#${id})"/>
      <path d="M62 189q-26-10-32 8-6 19 27 27" fill="#d98944"/>
      <path d="M62 197q-10-4-15-1m12 12-10 1" stroke="#b76b32" stroke-width="2.5"/>
      </g>
      <path d="M77 157q4-38 35-49" stroke="#f5bd7380" stroke-width="7" stroke-linecap="round"/>
      <ellipse cx="120" cy="160" rx="25" ry="33" fill="#fff6db" stroke="#a96b3c" stroke-width="2"/>
      <ellipse cx="169" cy="160" rx="25" ry="33" fill="#fff6db" stroke="#a96b3c" stroke-width="2"/>
      <ellipse cx="127" cy="166" rx="7" ry="12" fill="#4b372a"/><ellipse cx="162" cy="166" rx="7" ry="12" fill="#4b372a"/>
      <circle cx="129" cy="162" r="2.3" fill="#fff"/><circle cx="164" cy="162" r="2.3" fill="#fff"/>
      <path d="M97 127q17-13 35-3m23 0q19-10 34 4" stroke="#804824" stroke-width="8" stroke-linecap="round"/>
      <ellipse cx="145" cy="207" rx="42" ry="29" fill="#f2ca86"/>
      <path d="M130 191q16-9 30 0l-5 12q-10 7-20 0Z" fill="#914c2b"/>
      <path d="M145 202v12m-22 2q23 19 45-1" stroke="#86502d" stroke-width="3.5" stroke-linecap="round" fill="none"/>
      <path d="m136 224 18-1-2 8h-12Z" fill="#fff4d9"/>
      <ellipse cx="98" cy="200" rx="10" ry="5" fill="#df9c5e"/><ellipse cx="190" cy="200" rx="10" ry="5" fill="#df9c5e"/>
      <g transform="rotate(-7 143 82)" stroke="#aa793b" stroke-width="3" stroke-linejoin="round">
      <path d="m91 80 14-45q29-23 63-6l23 50" fill="${boost?'#f5d582':'#edc66e'}"/>
      <path d="m99 60q46-12 84 0l5 14-92 9Z" fill="#a96940" stroke="none"/>
      <path d="M58 86q70-37 166-6 16 7 5 17-74-8-155 8-22-5-16-19Z" fill="#f2d48c"/>
      <path d="m103 42 3 10m17-20 1 16m18-19v17m18-15 2 17m17-11 4 13" stroke="#e1af56" stroke-width="2"/>
      <path d="M77 93q72-18 132-5" fill="none" stroke="#ffe8ac" stroke-width="3"/>
      <g transform="translate(90 62)" stroke="none"><circle cx="-6" cy="-3" r="6" fill="#fff7d8"/><circle cx="1" cy="-8" r="6" fill="#fff7d8"/><circle cx="7" cy="0" r="6" fill="#fff7d8"/><circle cx="0" cy="6" r="6" fill="#fff7d8"/><circle r="4.5" fill="#d9a841"/></g>
      </g>
      <path d="M243 154q13-3 13 7t-13 8" fill="#d48340" stroke="#87512e" stroke-width="3"/>`, '0 0 300 300');
  }
  function scene(){
    return wrap(`<rect width="640" height="560" fill="#eaf0d8"/>
      <path d="M0 207Q141 105 308 185T640 164V560H0Z" fill="#d7e2b8"/>
      <path d="M0 276Q162 175 334 245T640 221V560H0Z" fill="#c7d59f"/>
      <path d="M0 359Q160 259 373 336T640 282V560H0Z" fill="#afc385"/>
      <g fill="#fbfbeb"><path d="M40 67q-9-25 16-28 11-26 31-10 25-9 28 20 24 1 23 17Z"/><path d="M435 91q-4-20 19-23 9-23 31-12 22-4 23 17 22 4 19 19Z" opacity=".65"/></g>
      <g transform="translate(-90 56)"><circle cx="531" cy="52" r="25" fill="#edcf87"/>
      <g stroke="#e6c87d" stroke-width="2.5" stroke-linecap="round"><path d="M531 15V7m0 90v-8m36-37h9m-90 0h9m11-26-6-6m62 62-6-6m6-56-6 6m-50 50-6 6"/></g>
      </g><g transform="translate(500 151)"><path d="M-5 46 36 8l42 38v83H-5Z" fill="#d8b786"/><path d="m-17 49 54-52 55 52-8 9L37 16-9 59Z" fill="#b77a4a"/><path d="M23 129V74h28v55" fill="#a37a50"/><path d="m28 82 19 39m0-39-19 39" stroke="#dcb98a" stroke-width="3"/><rect x="11" y="48" width="19" height="16" rx="3" fill="#f7dfac"/><path d="M20 49v13" stroke="#bd9967" stroke-width="2"/></g>
      <g stroke="#c1b180" stroke-width="4" fill="#e4d8b1"><path d="M0 298h95m-95 18h95"/><path d="m10 285 6-7 6 7v49H10Zm32-4 6-7 6 7v52H42Zm31-3 6-7 6 7v51H73Z"/></g>
      <g fill="#91a76a"><ellipse cx="43" cy="217" rx="39" ry="48"/><ellipse cx="80" cy="239" rx="31" ry="40"/><ellipse cx="614" cy="248" rx="51" ry="57"/></g>
      <g fill="#c8a772"><path d="M62 417q231-52 514 7l-19 26q-251-47-481 1Z"/><path d="M16 493q307-66 613 4l-14 30q-300-65-582 0Z"/></g>
      <g fill="none" stroke="#ac8b58" stroke-width="2" opacity=".35"><path d="M80 430q210-37 468 5M43 508q281-54 557 2"/></g>
      ${[87,151,215,405,470,533].map((x,i)=>leaf(x,429+(i%2)*4,i%2?14:-8)).join('')}
      ${[55,116,177,238,371,432,493,554,609].map((x,i)=>leaf(x,509+(i%2)*6,i%2?-12:6)).join('')}
      <g fill="#f4e8bc"><circle cx="36" cy="380" r="3"/><circle cx="590" cy="370" r="3"/><circle cx="562" cy="336" r="2"/></g>
      <g fill="#8c9f6a"><ellipse cx="113" cy="352" rx="9" ry="2" transform="rotate(-31 113 352)"/><ellipse cx="118" cy="348" rx="7" ry="2" transform="rotate(24 118 348)"/></g>`, '0 0 640 560',true);
  }
  function item(id){
    id=({battery:'energy',irrigation:'water',beehives:'bee',orchard:'tree',silo:'barn'})[id]||id;
    const stroke=`stroke="${p.ink}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"`;
    let body='';
    if(id==='shovel')body=`<g transform="rotate(25 40 40)" ${stroke}><path d="M35 43V17h10v26" fill="#cba573"/><path d="M28 9h24v13q-12 11-24 0Z" fill="#aa8758"/><path d="M34 15h12v4q-6 5-12 0Z" fill="#f4e7c7" stroke-width="2"/><path d="m26 43 27-1-1 17q-3 10-13 15-11-7-14-16Z" fill="#a7bbb3"/><path d="m40 47-1 20" stroke="#dbe4d8"/></g>`;
    if(id==='gloves')body=`<g ${stroke}><path d="M13 51 9 31q-1-7 4-7l5 11-1-19q1-7 6-3l3 20 1-22q4-6 7 0l-1 23 6-17q5-4 7 2l-5 22q15-12 15-4l-10 20-3 9-25-2Z" fill="#a8b57e"/><path d="m17 57 28 4-2 12-25-3Z" fill="#778a58"/><path d="M49 56q18-13 20-3l-2 20-16 2-7-12" fill="#bfc99c"/></g>`;
    if(id==='energy')body=`<g ${stroke}><path d="m38 9-6 23H18l13 36 10-24h15L43 9Z" fill="#e4b75e"/><path d="m38 17-4 22h12L35 61" stroke="#f8dc92" stroke-width="3"/><path d="M15 14 9 8m51 8 7-5m-2 50 8 4M8 47l-6 3" stroke="#baa675"/></g>`;
    if(id==='well')body=`<g ${stroke}><path d="M14 44q26-12 52 0v23q-26 15-52 0Z" fill="#cfb990"/><ellipse cx="40" cy="44" rx="26" ry="8" fill="#a89570"/><path d="M19 43V15m42 28V15" stroke="#b18a58" stroke-width="6"/><path d="m10 18 30-13 30 13Z" fill="#b97a4a"/><path d="M39 18v29" stroke="#8f7652" stroke-width="2"/><path d="m32 45 15-1-2 11H34Z" fill="#a7b7a7"/><path d="M15 58h50m-35-8v9m19 0v12m-23-9v9" stroke="#a99370" stroke-width="2"/><path d="M7 74h66" stroke="#c9b998"/></g>`;
    if(id==='water')body=`<g ${stroke}><path d="M18 39q-2-21 11-25 15-3 18 20" stroke="#98b4ae" stroke-width="6"/><path d="M16 32h36v35H16Z" fill="#a9c5bf"/><path d="m52 42 16-9 4 7-20 18" fill="#a9c5bf"/><path d="m65 30 11 8-4 7-12-8Z" fill="#d4dfd1"/><path d="M21 39h24m-24 8h24" stroke="#dce8d7"/><path d="M10 71h47" stroke="#d5c5a0"/></g>`;
    if(id==='beds')body=`<g ${stroke}><path d="m8 42 44-10 21 13-43 17Z" fill="#b99261"/><path d="M8 42v9l21 16 44-13v-9L29 58Z" fill="#b68e5e"/><path d="m17 42 13 11 32-9" stroke="#8e6d45"/><path d="m28 39 3 10m18-15 3 10" stroke="#ecaa63" stroke-width="7"/></g>${leaf(28,36,0)}${leaf(49,31,9)}`;
    if(id==='helper')body=`<g ${stroke}><path d="M18 69V47q2-14 22-14t22 14v22" fill="#9eaf7b"/><path d="m25 43 8 26m23-27-6 27" stroke="#d0d8b4"/><circle cx="40" cy="27" r="17" fill="#e5bb86"/><path d="M18 18q23-14 45 0l-1 7H18Z" fill="#dfc580"/><path d="m27 17 3-13h21l4 13" fill="#e5ce8b"/><path d="m34 29 1 1m12-1 1 1" stroke-width="4"/><path d="M36 37h9"/></g>`;
    if(id==='bee'||id==='beehives')body=`<g ${stroke}><path d="M23 27q-6-10 8-12 9-16 19 0 13 3 6 14" fill="#dabb77"/><path d="M16 32q0-10 25-10t25 10v7H16Zm-3 14q0-9 28-9t28 9v8H13Zm-3 17q0-10 31-10t31 10v9H10Z" fill="#e2c88e"/><path d="M34 72V59q7-9 14 0v13" fill="#8c693e"/><path d="M23 31h35M21 47h39" stroke="#f5dfab"/></g>`;
    if(id==='greenhouse')body=`<g ${stroke}><path d="M9 38q0-28 31-28t31 28v33H9Z" fill="#d9e4ce"/><path d="M9 38h62M40 10v61M22 16v55m36-55v55" stroke="#8ea27a"/><path d="m9 50 61-1" stroke="#a3b78a"/><path d="M33 71V47h14v24" fill="#adc19b"/><path d="M5 73h70" stroke="#b69d70"/></g><path d="m49 28 9-10" stroke="#f8f5de" stroke-width="4" stroke-linecap="round"/>`;
    if(id==='tree'||id==='orchard')body=`<g ${stroke}><path d="M35 68V42h10v26" fill="#b28a59"/><path d="M16 28q-6-19 15-18 13-13 26 1 21 1 13 22 9 18-12 22-15 13-30 0Q5 52 16 28Z" fill="#9aaa70"/><circle cx="27" cy="29" r="7" fill="#db9a60"/><circle cx="55" cy="24" r="7" fill="#deb56b"/><circle cx="44" cy="44" r="7" fill="#d89051"/><path d="M23 72h34" stroke="#d3c4a1"/></g>`;
    if(id==='market')body=`<g ${stroke}><path d="M14 33h52v38H14Z" fill="#dec89d"/><path d="M9 33 17 9h46l9 24Z" fill="#c27b50"/><path d="m27 10-4 23m18-23v23m15-23 5 23" stroke="#f7e4bc" stroke-width="9"/><path d="M9 33q3 9 12 0 7 9 14 0 8 9 15 0 10 9 22 0" fill="#d99668"/><path d="M23 71V46h34v25" fill="#ac9268"/><path d="M18 56h44" stroke="#ecdab6"/><path d="M6 73h69" stroke="#c2b18c"/></g>`;
    if(id==='barn'||id==='silo')body=`<g ${stroke}><path d="M12 31 40 8l28 23v42H12Z" fill="#cb9970"/><path d="m6 34 34-29 35 29" stroke="#ad784f" stroke-width="8"/><path d="M25 73V42h30v31" fill="#b47d53"/><path d="m26 44 27 27m0-27L27 71" stroke="#ead0a0"/><rect x="32" y="20" width="16" height="13" rx="2" fill="#f1dfb1"/><path d="M5 75h71" stroke="#c4b28b"/></g>`;
    if(id==='compost')body=`<g ${stroke}><path d="m12 30 29-13 28 13v40H12Z" fill="#ae8e61"/><path d="M13 40h55M13 51h55M13 62h55" stroke="#d9bd8d"/><path d="M22 30q14-27 33-5" fill="#7e985d"/><path d="M39 31V12m-1 9-10-6m11 1 12-8" stroke="#6f854c"/></g>`;
    if(id==='windmill')body=`<g ${stroke}><path d="m25 32-8 42h47l-9-42-15-17Z" fill="#dcc79e"/><path d="m18 34 22-23 22 23" fill="#b77a51"/><path d="M35 74V56h12v18" fill="#a18259"/><g transform="rotate(24 40 32)"><path d="M36 4h9v57h-9Z" fill="#e8d8b0"/><path d="M10 28h59v9H10Z" fill="#e8d8b0"/></g><circle cx="40" cy="32" r="6" fill="#a18259"/></g>`;
    if(id==='pond')body=`<g ${stroke}><ellipse cx="40" cy="52" rx="34" ry="21" fill="#b6c8ae"/><ellipse cx="40" cy="51" rx="28" ry="14" fill="#9abdb9"/><path d="M18 52h14m10 6h17" stroke="#dbe6cf"/><path d="M62 40V12m7 30V20" stroke="#7c9561"/><path d="M60 12v13m7-7v12" stroke="#b7995e" stroke-width="6"/><ellipse cx="28" cy="43" rx="9" ry="4" fill="#8fa56e"/><path d="m28 43 8-3" stroke="#6f864f"/><path d="M15 70h51" stroke="#c6b794"/></g>`;
    if(id==='tractor')body=`<g ${stroke}><path d="M15 30h33l5 13h19v18H13Z" fill="#afbd81"/><path d="M27 31V12h21l8 31H26" fill="#b4c9be"/><path d="M29 17h14v18H29Z" fill="#e4e6cf"/><path d="M61 43V25h5" fill="none"/><circle cx="24" cy="60" r="16" fill="#786c52"/><circle cx="24" cy="60" r="8" fill="#d2bc85"/><circle cx="63" cy="63" r="11" fill="#786c52"/><circle cx="63" cy="63" r="5" fill="#d2bc85"/><path d="M53 48h15" stroke="#758356"/></g>`;
    if(id==='nursery')body=`<g ${stroke}><path d="M9 48h62l-4 25H14Z" fill="#c6a675"/><path d="M20 48V27m20 20V13m19 35V27" stroke="#7c925d"/><path d="M20 34Q3 34 8 20q15-4 12 14Zm1-3q15 0 12-14-14-3-12 14ZM40 22Q23 20 27 6q16 0 13 16Zm2 6q18-3 13-17-16 0-13 17ZM59 37Q43 35 47 22q13-1 12 15Zm1-8q15 0 12-13-13-1-12 13Z" fill="#a3b77c"/><path d="M15 57h50m-50 8h49" stroke="#ead4a7"/></g>`;
    if(id==='railway')body=`<g ${stroke}><path d="M8 70h65M8 77h65m-55-10v12m16-12v12m16-12v12m16-12v12" stroke="#ab9571"/><path d="M12 34h39v27H12Zm7-22h28v23H19Z" fill="#b4bc86"/><path d="M24 18h17v13H24Z" fill="#e7e2c5"/><path d="M51 43h17v18H51Z" fill="#c28b5d"/><path d="M59 43V24h8v19" fill="#9e8662"/><circle cx="23" cy="61" r="8" fill="#a38c63"/><circle cx="43" cy="61" r="8" fill="#a38c63"/><circle cx="65" cy="61" r="7" fill="#a38c63"/><path d="M62 17q-9-7 0-12m7 8q8-6 2-10" fill="none" stroke="#c2c4a4"/></g>`;
    if(id==='cart')body=`<g ${stroke}><path d="M10 29h51v27H16Z" fill="#d2b580"/><path d="M15 39h43M19 49h36" stroke="#f1dbb1"/><path d="M60 35h10l5 19H61" fill="#b5c18c"/><circle cx="25" cy="60" r="10" fill="#8e7958"/><circle cx="61" cy="60" r="10" fill="#8e7958"/><circle cx="25" cy="60" r="4" fill="#e4cca0"/><circle cx="61" cy="60" r="4" fill="#e4cca0"/><path d="m22 27 6-13 17 4-3 12" fill="#e0a260"/><path d="m30 14-6-8m7 8 6-9" stroke="#8a9d64"/></g>`;
    if(id==='gift')body=`<g ${stroke}><rect x="13" y="29" width="54" height="43" rx="4" fill="#e2be72"/><rect x="9" y="24" width="62" height="14" rx="4" fill="#edce88"/><path d="M34 25v47h12V25" fill="#a5b17a"/><path d="M40 24Q13 27 19 10q7-12 21 14Zm0 0Q67 27 61 10q-7-12-21 14Z" fill="#bdc699"/></g>`;
    return wrap(`<ellipse cx="40" cy="74" rx="28" ry="4" fill="#bfb08e25"/>${body}`);
  }
  window.KopatychArt={character,scene,item};
})();
