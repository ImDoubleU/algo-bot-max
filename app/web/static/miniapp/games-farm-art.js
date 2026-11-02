/* Original vector illustration system for Kopatych's garden. */
(() => {
  'use strict';
  let serial = 0;
  const p = {ink:'#775034',orange:'#cf773c',light:'#e9984d',cream:'#fae6b2',leaf:'#71864b',dark:'#4d623d',gold:'#ebbf62',wood:'#bc8d59',blue:'#a5c4c4'};
  const wrap = (body,box='0 0 80 80',cover=false) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}" preserveAspectRatio="${cover?'xMidYMid slice':'xMidYMid meet'}" fill="none" aria-hidden="true" focusable="false">${body}</svg>`;
  const leaf=(x,y,rotate=0)=>`<g transform="translate(${x} ${y}) rotate(${rotate})"><path d="M0 0Q-21-19-24-6-22 7 0 0Z" fill="#879a52"/><path d="M0 0Q17-28 24-13 25-1 0 0Z" fill="#6b8648"/><path d="M0 0q-5-35 5-33 11 2-5 33Z" fill="#a3b66c"/></g>`;
  const STAGES=[
    {level:1,name:'Первый огород'}, {level:5,name:'Уютная ферма'},
    {level:10,name:'Цветущая долина'}, {level:17,name:'Большое хозяйство'},
    {level:24,name:'Легендарная усадьба'}
  ];
  function stage(level=1){
    const index=Math.max(0,STAGES.filter(s=>level>=s.level).length-1);
    return {...STAGES[index],index,next:STAGES[index+1]?.level||null};
  }
  function character(boost=false,level=1){
    const t=stage(level).index;
    const cloth=['','#8da36a','#779aa0','#557b65','#e6d6a2'][t];
    const band=['#a96940','#72824c','#86624a','#416354','#a47e3d'][t];
    const outfit=t?`<g stroke="#675c3d" stroke-width="2.5" stroke-linejoin="round">
      <path d="M76 205q11 11 21 14l-2 22q45 24 96-1l-1-21 19-14 15 37q-23 29-81 29-49 0-73-24Z" fill="${cloth}"/>
      <path d="m83 181 14 5 12 55-15 4Zm111 3 13-4-8 63-15-3Z" fill="${cloth}"/>
      <circle cx="103" cy="236" r="4" fill="#ead18a"/><circle cx="190" cy="236" r="4" fill="#ead18a"/>
      <path d="M123 241h44l-3 17q-18 8-37 0Z" fill="${t===4?'#b49c5e':t===3?'#3d6450':'#627f64'}"/>
      <path d="M127 247h35" stroke="#e4d9ad" stroke-width="1.5"/>
      ${t>=2?'<path d="M79 267q23-10 41-2v10q-26 16-40 4Zm96-3q25-7 41 5l-5 11q-19 9-34-3Z" fill="#6d7656"/>':''}
      ${t>=3?'<path d="m190 216 10 4-5 13-11-6Z" fill="#e0b75c"/><circle cx="194" cy="222" r="3" fill="#f9e3a0"/>':''}
      ${t===4?'<path d="M77 231q-10 15-4 19m143-20q9 16 0 24" stroke="#d6b15c" stroke-width="4"/>':''}
    </g>`:'';
    const id='kopatych-coat-'+(++serial);
    return wrap(`<defs><radialGradient id="${id}" cx=".3" cy=".23" r=".84"><stop stop-color="#e89c54"/><stop offset=".65" stop-color="#d78542"/><stop offset="1" stop-color="#be6933"/></radialGradient></defs>
      <ellipse cx="150" cy="281" rx="88" ry="10" fill="#6c58391b"/>
      <g stroke="#87512e" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round">
      <path d="M222 153q31-19 35-1 6 19-25 31" fill="#cb7638"/>
      <path d="m253 130-8 129" stroke="#ba8c54" stroke-width="9"/>
      <path d="m249 255 26 3-6 22-14 9-12-11Z" fill="${t>=3?'#d9be73':t>=2?'#d0ded9':'#c0c6bb'}" stroke="#7f8c7d" stroke-width="3"/>
      <path d="m248 126 11 1 3-22-15-1Z" fill="#bd8a50"/>
      <path d="M99 251q-21 12-16 23 8 15 36 2l5-17m47 0 8 18q26 11 32-3 4-11-19-23" fill="#b96d35"/>
      <path d="M78 105q-20-26-35-8-13 17 9 34m151-24q21-27 36-10 14 16-7 35" fill="#c77a3c"/>
      <path d="M69 109q-11-14-17-5t7 19m155-14q10-15 17-6t-6 20" fill="#e6a45e" stroke="none"/>
      <circle cx="143" cy="174" r="96" fill="url(#${id})"/>
      <path d="M62 189q-26-10-32 8-6 19 27 27" fill="#d98944"/>
      <path d="M62 197q-10-4-15-1m12 12-10 1" stroke="#b76b32" stroke-width="2.5"/>
      </g>
      ${outfit}
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
      <path d="m91 80 14-45q29-23 63-6l23 50" fill="${boost?'#f5d582':t===4?'#f5dda0':t>=2?'#d5be7f':'#edc66e'}"/>
      <path d="m99 60q46-12 84 0l5 14-92 9Z" fill="${band}" stroke="none"/>
      <path d="M58 86q70-37 166-6 16 7 5 17-74-8-155 8-22-5-16-19Z" fill="#f2d48c"/>
      <path d="m103 42 3 10m17-20 1 16m18-19v17m18-15 2 17m17-11 4 13" stroke="#e1af56" stroke-width="2"/>
      <path d="M77 93q72-18 132-5" fill="none" stroke="#ffe8ac" stroke-width="3"/>
      <g transform="translate(90 62)" stroke="none"><circle cx="-6" cy="-3" r="6" fill="#fff7d8"/><circle cx="1" cy="-8" r="6" fill="#fff7d8"/><circle cx="7" cy="0" r="6" fill="#fff7d8"/><circle cx="0" cy="6" r="6" fill="#fff7d8"/><circle r="4.5" fill="#d9a841"/></g>
      ${t>=2?'<path d="m195 67 9-27q13 7 4 25l-12 8" fill="#71945a" stroke="#577342" stroke-width="2"/>':''}
      ${t===4?'<g transform="translate(157 68)" stroke="#aa803c" stroke-width="2"><path d="m0-11 4 7 8 1-6 6 1 8-7-4-7 4 1-8-6-6 8-1Z" fill="#f8df8b"/></g>':''}
      </g>
      <path d="M243 154q13-3 13 7t-13 8" fill="#d48340" stroke="#87512e" stroke-width="3"/>`, '0 0 300 300');
  }
  // The same closed panels are used in scenery and in the shop illustration.
  function greenhouse(){
    return `<g stroke="#7f956e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="40" cy="71" rx="37" ry="4" fill="#697b4d22" stroke="none"/>
      <path d="M8 35Q8 10 32 10T56 35L70 28Q70 4 47 4T22 28Z" fill="#c8dcbd"/>
      <path d="m56 35 14-7v33l-14 7Z" fill="#adc4a3"/>
      <path d="M8 35Q8 10 32 10T56 35v33H8Z" fill="#e2ecd4"/>
      <path d="M20 18v50m24-50v50M8 36h48M8 50h48m7-18v33m-7-18 14-7" fill="none"/>
      <path d="M26 68V44h14v24Z" fill="#b9cda9"/>
      <path d="M36 55v4" stroke="#7d895f"/>
      <path d="m13 31 9-10m24 10 4-5" stroke="#fffbed" stroke-width="3"/>
      <path d="M5 70h53l15-8" fill="none" stroke="#a08d63" stroke-width="3"/>
    </g>`;
  }
  function sceneryItem(id,x,y,scale){
    const art=item(id).replace(/^<svg[^>]*>/,'').replace(/<\/svg>$/,'');
    return `<g data-scenery="${id}" transform="translate(${x} ${y}) scale(${scale})">${art}</g>`;
  }
  function scene(level=1,items={}){
    const t=stage(level).index;
    const sky=['#eaf0d8','#e9efcf','#dcebdc','#dfeddf','#f0e7c9'][t];
    const cottage=t>=1&&t<4?`<g transform="translate(500 151)"><path d="M-5 46 36 8l42 38v83H-5Z" fill="#d8b786"/><path d="m-17 49 54-52 55 52-8 9L37 16-9 59Z" fill="#b77a4a"/><path d="M23 129V74h28v55" fill="#a37a50"/><path d="m28 82 19 39m0-39-19 39" stroke="#dcb98a" stroke-width="3"/><rect x="11" y="48" width="19" height="16" rx="3" fill="#f7dfac"/><path d="M20 49v13" stroke="#bd9967" stroke-width="2"/></g>`:'';
    const fence=t>=1?`<g stroke="#c1b180" stroke-width="4" fill="#e4d8b1"><path d="M0 298h95m-95 18h95"/><path d="m10 285 6-7 6 7v49H10Zm32-4 6-7 6 7v52H42Zm31-3 6-7 6 7v51H73Z"/></g>`:'';
    const shrubs=t>=1?`<g fill="#91a76a"><ellipse cx="43" cy="217" rx="39" ry="48"/><ellipse cx="80" cy="239" rx="31" ry="40"/><ellipse cx="614" cy="248" rx="51" ry="57"/></g>`:'';
    const beds=t>=1||items.beds>0?`<g fill="#c8a772"><path d="M62 417q231-52 514 7l-19 26q-251-47-481 1Z"/>${t>=1?'<path d="M16 493q307-66 613 4l-14 30q-300-65-582 0Z"/>':''}</g>
      <g fill="none" stroke="#ac8b58" stroke-width="2" opacity=".35"><path d="M80 430q210-37 468 5${t>=1?'M43 508q281-54 557 2':''}"/></g>
      ${[87,151,215,405,470,533].map((x,i)=>leaf(x,429+(i%2)*4,i%2?14:-8)).join('')}
      ${(t>=1?[55,116,177,238,371,432,493,554,609]:[]).map((x,i)=>leaf(x,509+(i%2)*6,i%2?-12:6)).join('')}`:'';
    const orchard=items.orchard>0?sceneryItem('orchard',2,170,1.1):'';
    const apiary=items.beehives>0?sceneryItem('beehives',593,311,.5):'';
    const nursery=items.nursery>0?sceneryItem('nursery',6,409,.72):'';
    const train=items.railway>0?sceneryItem('railway',427,350,.7):'';
    const flourish=t>=1?`<path d="M270 560q-23-76 86-190l32 12q-95 106-67 178Z" fill="#e1cf9c"/>
      <g fill="#ecbd9a">${[30,65,112,548,586,622].map((x,n)=>`<circle cx="${x}" cy="${350+n%2*20}" r="6"/>`).join('')}</g>
      <g fill="#e5cd89">${[48,87,570,608].map(x=>`<circle cx="${x}" cy="387" r="4"/>`).join('')}</g>
      <g stroke="#d1c09a" stroke-width="3"><path d="M18 318h102m-102 20h102m-85-31v45m32-45v45m32-45v45"/></g>`:'';
    const water=t>=2||items.pond>0?`<path d="M0 300q105-31 186 14t-5 49Q70 349 0 393Z" fill="#a5c9c4"/>
      <path d="M0 337q90-21 156 12m-128 9 49-5" stroke="#deebd7" stroke-width="3" stroke-linecap="round"/>
      <path d="m106 313 65 11-8 34-66-11Z" fill="#bca273"/><path d="m110 320 52 9m-56 1 52 9m-54 0 52 9" stroke="#ead5ac" stroke-width="3"/>
`:'';
    const glasshouse=t>=2||items.greenhouse>0?`<g data-scenery="greenhouse" transform="translate(510 306) scale(1.22)">${greenhouse()}</g>`:'';
    const mill=t>=3||items.windmill>0?`<g transform="translate(40 130)"><path d="m27 41-8 116h89L88 41 57 8Z" fill="#d9c89b" stroke="#9d845a" stroke-width="3"/><path d="M12 51 57 5l45 46Z" fill="#a97548"/><path d="M48 157v-34h25v34" fill="#927c56"/><g transform="rotate(18 57 58)" stroke="#9c885c" stroke-width="3" fill="#f3e2b6"><path d="M50 0h14v116H50Z"/><path d="M0 51h115v14H0Z"/></g><circle cx="57" cy="58" r="9" fill="#aa9362"/></g>
`:'';
    const rails=t>=3||items.railway>0?`<path d="M0 400q303-46 640 4" stroke="#a39475" stroke-width="9"/><path d="M0 395q303-46 640 4" stroke="#ded0af" stroke-width="3"/>`:'';
    const festival=t>=4?`<path d="M0 95q300 70 640-10" stroke="#b29b69" stroke-width="2"/>
      ${[30,100,175,255,335,415,495,575].map((x,n)=>`<path d="m${x} ${108+Math.sin(n*.5)*25} 25 4-15 24Z" fill="${['#d6a26a','#99af76','#cdb76b'][n%3]}"/>`).join('')}
      <g transform="translate(463 130)"><path d="M0 43 65 0l65 43v113H0Z" fill="#ece0b7" stroke="#b89c68" stroke-width="3"/><path d="m-8 44 73-51 73 51" stroke="#71875b" stroke-width="12"/><path d="M48 156v-61h35v61" fill="#a9b988"/><circle cx="65" cy="57" r="14" fill="#d4b775"/><path d="M16 76h20v29H16Zm78 0h20v29H94Z" fill="#b8cfb1"/></g>
      <g fill="#fff2c4">${[37,90,187,460,578,611].map((x,n)=>`<path d="m${x} ${282+n%3*21} 3-7 3 7 7 3-7 3-3 7-3-7-7-3Z"/>`).join('')}</g>`:'';
    return wrap(`<rect width="640" height="560" fill="${sky}"/>
      <path d="M0 207Q141 105 308 185T640 164V560H0Z" fill="#d7e2b8"/>
      <path d="M0 276Q162 175 334 245T640 221V560H0Z" fill="#c7d59f"/>
      <path d="M0 359Q160 259 373 336T640 282V560H0Z" fill="#afc385"/>
      <g fill="#fbfbeb"><path d="M40 67q-9-25 16-28 11-26 31-10 25-9 28 20 24 1 23 17Z"/><path d="M435 91q-4-20 19-23 9-23 31-12 22-4 23 17 22 4 19 19Z" opacity=".65"/></g>
      <g transform="translate(-90 56)"><circle cx="531" cy="52" r="25" fill="#edcf87"/>
      <g stroke="#e6c87d" stroke-width="2.5" stroke-linecap="round"><path d="M531 15V7m0 90v-8m36-37h9m-90 0h9m11-26-6-6m62 62-6-6m6-56-6 6m-50 50-6 6"/></g>
      </g>${cottage}
      ${fence}
      ${shrubs}
      ${beds}
      ${water}${flourish}${orchard}${mill}${rails}${festival}${glasshouse}${apiary}${nursery}${train}
      <g fill="#f4e8bc"><circle cx="36" cy="380" r="3"/><circle cx="590" cy="370" r="3"/><circle cx="562" cy="336" r="2"/></g>
      <g fill="#8c9f6a"><ellipse cx="113" cy="352" rx="9" ry="2" transform="rotate(-31 113 352)"/><ellipse cx="118" cy="348" rx="7" ry="2" transform="rotate(24 118 348)"/></g>`, '0 0 640 560',true);
  }
  function neighbor(kind){
    const outline='stroke="#67503d" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"';
    const body=kind==='rabbit'?`<g ${outline}><path d="M27 30Q8-12 25 3q13 14 14 29m7-1Q42-6 57 2q12 6-1 30" fill="#a7cdcf"/><circle cx="40" cy="47" r="29" fill="#a7cdcf"/><ellipse cx="31" cy="43" rx="8" ry="11" fill="#fff9de"/><ellipse cx="49" cy="43" rx="8" ry="11" fill="#fff9de"/><path d="m29 44 1 1m18-1 1 1" stroke-width="5"/><path d="M35 53q5-5 10 0l-5 5Z" fill="#c5786d"/><path d="M28 60q12 14 25-3" fill="none"/><path d="M36 65h10l-1 7h-8Z" fill="#fff9de"/></g>`:kind==='hedgehog'?`<g ${outline}><path d="m12 35-6-15 16 2 1-16 15 10L50 4l6 17 17 1-6 17Z" fill="#92759f"/><circle cx="40" cy="48" r="29" fill="#b69bc0"/><circle cx="27" cy="45" r="12" fill="#f8ecd8"/><circle cx="53" cy="45" r="12" fill="#f8ecd8"/><path d="M38 44h4m-31-2-5-3m62 3 6-3" stroke="#745278" stroke-width="4"/><path d="m28 45 1 1m23-1 1 1" stroke-width="5"/><path d="m36 55 4 4 5-4" fill="#916383"/><path d="M32 66q8 5 16 0" fill="none"/></g>`:`<g ${outline}><path d="m15 33-6-23 23 10m23 0 19-11-8 27" fill="#b39bb9"/><circle cx="40" cy="47" r="30" fill="#b39bb9"/><ellipse cx="28" cy="43" rx="13" ry="15" fill="#f6e6c7"/><ellipse cx="53" cy="43" rx="13" ry="15" fill="#f6e6c7"/><path d="m28 43 1 1m23-1 1 1" stroke-width="6"/><path d="m34 54 13-1-7 12Z" fill="#daa66c"/><path d="M24 70q16 11 32 0" stroke="#90769b"/><path d="m18 13 13-10 19 3 12 10" fill="#dfcc98"/></g>`;
    return wrap(body);
  }
  function crop(id){
    const moon=id==='moon',amber=id==='amber';
    const soil=moon?'#c7c9b3':amber?'#dfc58b':'#c7cfaa',root=moon?'#a497bc':amber?'#e3aa51':'#d08368';
    return wrap(`<ellipse cx="80" cy="112" rx="51" ry="7" fill="#c6bda33b"/><path d="M24 78q57-17 112 0l-9 29q-45 15-93 0Z" fill="${soil}"/>
      <g stroke="#806342" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M65 52q-12 8-9 25l18 30q6 5 10-2l20-34q1-18-14-21Z" fill="${root}"/>
      <path d="m60 67 14 5m-5 15 13 4m13-27-13 5" fill="none" stroke="#ac7d50" opacity=".6"/>
      <path d="M79 54Q45 37 51 21q24-4 28 33Zm0 0Q75 16 91 12q16 17-12 42Zm0 0q30-30 42-15-9 20-42 15Z" fill="#91a56b" stroke="#73834f"/>
      <path d="m39 87 12 3m55-3 14-3" stroke="#a99b74"/></g>
      ${moon?'<g fill="#e5d795"><path d="m30 26 3-7 3 7 7 3-7 3-3 7-3-7-7-3Z"/><circle cx="122" cy="19" r="2"/><path d="M122 49q-12-5-5-17-1 11 10 10Z"/></g>':amber?'<g fill="#efce76"><path d="m29 40 5-13 5 13 13 5-13 5-5 13-5-13-13-5Z"/><circle cx="122" cy="65" r="3"/></g>':'<path d="M25 45q-11-3-10-11 11-3 16 7" fill="#bdcb9b"/>'}`, '0 0 160 130');
  }
  function route(id){
    const sky=id==='sky',coast=id==='coast';
    return wrap(`<rect x="1" y="1" width="248" height="128" rx="5" fill="${sky?'#e7e5d7':coast?'#dfeae1':'#e8ecd6'}"/>
      <circle cx="204" cy="28" r="14" fill="#ead198"/><path d="M0 78q62-50 139-4t111-20v76H0Z" fill="#c3d1ae"/><path d="M0 108q82-47 164-7t86-3v32H0Z" fill="#a9bd8d"/>
      ${coast?'<path d="M0 87q97-18 146 11t104-3v35H0Z" fill="#abc9c4"/><path d="m23 106 32-3m62 15 41-1m40-6 30-3" stroke="#e3ede1" stroke-width="2"/><path d="M64 96 86 63l34 37Z" fill="#9dad91"/><path d="m77 79 9-16 9 18" fill="#e6e6cd"/>':sky?sceneryItem('balloon',71,12,1.05)+'<path d="m157 79 39-9 32 11-12 13-46 3Z" fill="#8ca07a"/><path d="m170 96 18 20 9-22" fill="#b7bd9b"/>':'<path d="M105 130q-17-31 28-65" stroke="#dfc99a" stroke-width="15" fill="none"/><g fill="#819d72">'+[25,59,190,218].map((x,i)=>`<path d="m${x} ${42+i%2*11}-19 39h38Z"/><path d="M${x-2} ${77+i%2*11}v21" stroke="#9b895f" stroke-width="4"/>`).join('')+'</g>'}
      <path d="M15 15h27m-27 5h16" stroke="#a8b79c" stroke-width="2" stroke-linecap="round"/>`, '0 0 250 130');
  }
  function note(id){
    let body='';const st='stroke="#7a6a4a" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"';
    if(id==='garden_notes')body=`<g ${st}><path d="M37 15h80v99H37Z" fill="#a5b58a"/><path d="M45 15v99m-7-88h9m-9 15h9m-9 15h9m-9 15h9m-9 15h9" stroke="#e6dbbc"/><path d="M60 37h39v48H60Z" fill="#f1e8ca"/><path d="M78 75V50m0 14q-21-5-9-18 15 6 9 18Zm1-9q20 0 15-17-16 0-15 17Z" fill="#91a46e"/></g>`;
    if(id==='seed_sorting')body=`<g ${st}><path d="m24 48 73-22 35 26-72 30Z" fill="#d9c39a"/><path d="M24 48v28l35 28 73-30V52L60 82Z" fill="#bda06c"/><path d="m49 40 33 31m-6-40 31 30M24 62l35 28 73-30" fill="none"/><g fill="#e7d79c">${[0,1,2,3].map((n)=>`<ellipse cx="${46+n*17}" cy="${49+n%2*7}" rx="7" ry="4" transform="rotate(-25 ${46+n*17} ${49+n%2*7})"/>`).join('')}</g></g>`;
    if(id==='trail_maps')body=`<g ${st}><path d="m24 27 35-11 39 12 38-13-9 89-36 11-38-14-37 12Z" fill="#eee1bb"/><path d="m59 16-6 85m45-73-7 87" stroke="#c4b18a"/><path d="M37 83q6-37 43-18t33-31" fill="none" stroke="#a18e59" stroke-dasharray="4 5"/><circle cx="37" cy="83" r="5" fill="#a3b77d"/><path d="m106 32 15 9m-1-11-14 14" stroke="#ad8756"/></g>`;
    if(id==='soil_calendar')body=`<g ${st}><rect x="31" y="24" width="96" height="86" rx="4" fill="#f0e5c6"/><path d="M31 24h96v22H31Z" fill="#a2b487"/><path d="M48 16v19m60-19v19" stroke-width="5"/><path d="M47 61h64M47 79h64m-48-23v42m19-42v42m19-42v42" stroke="#cbbd96"/><path d="m86 85 8 7 16-18" fill="none" stroke="#7f965d" stroke-width="4"/></g>`;
    if(id==='challenge_training')body=`<g ${st}><path d="M69 15h25v10H69Zm12 10v8m31 6 8-7" fill="#ccb577"/><circle cx="81" cy="73" r="40" fill="#ded2a8"/><circle cx="81" cy="73" r="31" fill="#f8efd2"/><path d="M81 50v24l17 8" fill="none" stroke="#89995e" stroke-width="4"/><path d="M53 73h5m47 0h5m-29 23v5"/></g>`;
    return wrap(`<ellipse cx="80" cy="117" rx="51" ry="5" fill="#c6bda330"/>${body}`, '0 0 160 130');
  }
  function medal(kind,tier,claimed=false){
    const colors=[['#b9c79c','#e5ebd6'],['#bc926b','#ead4b4'],['#a6b5b1','#e0e6df'],['#c6a15a','#f1dfaa'],['#aa91ae','#e6dbea']][tier];
    const glyph={harvest:'M32 31q-4-8 4-10 9 1 4 10L29 46Zm3-10-6-5m7 5 7-7',manual:'m27 44 18-20m-2-7 5-5 9 8-5 5Zm-20 17-8 2 1 9 9-1 4-8',building:'m19 31 21-16 21 16v22H19Zm15 22V36h13v17',neighbors:'M20 47q0-13 11-13t11 13m1-3q0-11 10-11t10 11M24 23a7 7 0 1 0 14 0 7 7 0 0 0-14 0m22-1a6 6 0 1 0 12 0 6 6 0 0 0-12 0',care:'M40 49V32m-1 4Q18 33 24 21q16 0 15 15Zm1-9q16 0 13-13-13-2-13 13Z',rare:'M24 44h32l-3 13H27ZM40 44V24m0 12Q18 32 25 20q14 0 15 16Zm0-8q17 0 14-14-14-2-14 14Z',expeditions:'m40 15 8 18 16 7-18 7-6 17-7-18-18-6 18-7Z',research:'M22 18h34v38H22Zm8 0v38m6-28h12m-12 9h12m-12 9h8',trials:'m40 14 8 16 18 2-13 13 3 18-16-9-16 9 3-18-13-13 18-2Z'}[kind];
    return wrap(`<path d="m20 48-5 29 17-7 8 8 3-25m-3 0 10 24 8-9 15 3-12-29" fill="${colors[0]}" opacity=".72"/><circle cx="40" cy="35" r="31" fill="${colors[0]}"/><circle cx="40" cy="35" r="26" fill="${colors[1]}" stroke="#fff8dd" stroke-width="1.5"/><path d="${glyph}" transform="translate(6 4) scale(.85)" fill="none" stroke="#7c694b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>${claimed?'<circle cx="64" cy="58" r="10" fill="#819a61"/><path d="m59 58 4 4 7-8" fill="none" stroke="#fff9e5" stroke-width="2.4"/>':''}`, '0 0 80 84');
  }
  function item(id){
    id=({battery:'energy',irrigation:'water',beehives:'bee',orchard:'tree',silo:'barn',vineyard:'tree',autoshovel:'shovel',orangery:'greenhouse',foundry:'workshop'})[id]||id;
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
    if(id==='greenhouse')body=greenhouse();
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
    if(id==='workshop')body=`<g ${stroke}><path d="M10 46h60v12H10Zm6 12v17m47-17v17" fill="#b99867"/><path d="M16 46V15h48v31" fill="#ded1a9"/><path d="m21 21 22 21m-3-30 15 15-6 6-15-15Z" stroke="#8a7753" stroke-width="5"/><path d="m30 12-5 10 7 7 10-5-5 13-12-1-7-12Z" fill="#adc2b0"/><path d="M19 62h41v9H19Z" fill="#c7ad7c"/><circle cx="39" cy="66" r="2" fill="#806b4a"/></g>`;
    if(id==='logistics')body=`<g ${stroke}><path d="M15 25h33v32H15Z" fill="#dec28c"/><path d="M48 35h16l9 13v11H48Z" fill="#a3b887"/><path d="M53 38h9l6 9H53Z" fill="#e1ead4"/><circle cx="26" cy="61" r="9" fill="#9e8860"/><circle cx="61" cy="61" r="9" fill="#9e8860"/><path d="M2 32h7m-8 8h8m-5 8h5" stroke="#a5b17d" stroke-width="3"/><path d="m24 35 9 5-9 5" fill="none" stroke="#a78550"/></g>`;
    if(id==='seedlab')body=`<g ${stroke}><path d="M22 8h28v8H22Zm6 8v17L12 59q-5 13 9 13h37q13-1 6-14L44 33V16" fill="#d9e5d0"/><path d="M22 49h32l10 15q1 7-8 7H22q-11 0-7-10Z" fill="#b4c68c"/><path d="M37 59V38m0 9q-19-2-12-14 13 0 12 14Zm1-4q18-2 13-14-13-1-13 14Z" fill="#8fa66b"/><path d="m19 60 4-7" stroke="#f7f3d9" stroke-width="3"/><circle cx="54" cy="57" r="3" fill="#e4d49a"/></g>`;
    if(id==='backpack')body=`<g ${stroke}><path d="M18 27q0-12 22-12t22 12v43H18Z" fill="#a4b682"/><path d="M31 17V8h18v9" fill="none"/><path d="M13 33h54v12H13Z" fill="#c0cba0"/><path d="M25 48h30v18H25Z" fill="#829a67"/><path d="M30 35v16m20-16v16" stroke="#d6c18a" stroke-width="4"/></g>`;
    if(id==='balloon')body=`<g ${stroke}><path d="M13 28q0-25 27-25t27 25q0 20-27 38-27-18-27-38Z" fill="#e0b379"/><path d="M31 5q-15 27 9 61Q64 32 49 5" fill="#c9d2a0"/><path d="m30 58 4 11m16-11-4 11"/><path d="M30 67h20v10H30Z" fill="#bc9864"/></g>`;
    if(id==='highland')body=`<g ${stroke}><path d="m4 65 25-49 14 23 13-32 21 58Z" fill="#b0c1a3"/><path d="m20 34 9-18 11 19-10-5Z" fill="#f1edd8"/><path d="m47 29 9-22 10 27-11-6Z" fill="#f1edd8"/><path d="M5 64h72v10H5Z" fill="#91a573"/><path d="M30 64V48h22v16" fill="#c5a97c"/><path d="m25 49 16-14 17 14" fill="#a98057"/></g>`;
    if(id==='exosuit')body=`<g ${stroke}><path d="M22 16h36v36H22Z" fill="#a5bdb0"/><path d="m22 25-10 9v25m46-34 10 9v25M29 52l-7 23m29-23 7 23" stroke-width="8"/><circle cx="40" cy="33" r="11" fill="#d8c58b"/><path d="m40 24-5 10h7l-3 9" fill="none"/></g>`;
    if(id==='lighthouse')body=`<g ${stroke}><path d="m25 24-8 49h47l-9-49Z" fill="#e2d4ab"/><path d="M21 48h39l-3-13H23Z" fill="#c99c74"/><path d="M24 23V11h32v12" fill="#d9deb5"/><path d="m18 12 22-10 23 10Z" fill="#a47c54"/><path d="M37 73V58h10v15" fill="#a18e64"/><path d="M9 17H2m77 0h-7" stroke="#dbc476" stroke-width="4"/></g>`;
    if(id==='seedbag')body=`<g ${stroke}><path d="M29 17h23l-4 16q16 8 19 29 1 13-27 13T13 62q3-22 20-29Z" fill="#d2bd8b"/><path d="M27 32h27" stroke="#8b9861" stroke-width="5"/><path d="M40 62V44m0 11q-18-3-11-14 13 1 11 14Zm1-8q15-1 10-11-11 0-10 11Z" fill="#9cad76"/></g>`;
    if(id==='materials')body=`<g ${stroke}><path d="m8 31 52-14 12 12-53 15Z" fill="#d9b580"/><path d="m19 44 53-15v13L19 57 8 44V31" fill="#bf9c68"/><path d="m9 56 51-13 12 12-52 15Z" fill="#e0c494"/><path d="M20 70v8l52-15v-8" fill="#bca171"/><path d="m25 31 21-5m-18 37 24-7" stroke="#f0d6a7"/></g>`;
    if(id==='gift')body=`<g ${stroke}><rect x="13" y="29" width="54" height="43" rx="4" fill="#e2be72"/><rect x="9" y="24" width="62" height="14" rx="4" fill="#edce88"/><path d="M34 25v47h12V25" fill="#a5b17a"/><path d="M40 24Q13 27 19 10q7-12 21 14Zm0 0Q67 27 61 10q-7-12-21 14Z" fill="#bdc699"/></g>`;
    return wrap(`<ellipse cx="40" cy="74" rx="28" ry="4" fill="#bfb08e25"/>${body}`);
  }
  window.KopatychArt={character,scene,item,stage,neighbor,crop,route,note,medal};
})();
