/* Vehicle illustrations share paint and silhouettes; simulation stays in games-hill.js. */
(() => {
    'use strict';
    const H = ArcadeHill;
    const ink = '#26383e', steel = '#46575b', glass = '#335767', trim = '#d9dfd8';
    const models = {
        scout: {
            width: .85, wheels: [-1.29, 1.28], radius: .49,
            body: [[-1.86,.69],[1.82,.69],[1.97,1.23],[1.65,1.24],[.74,1.24],[.24,2.04],[-.91,2.04],[-1.16,1.24],[-1.86,1.24]],
            windows: [[[-1.01,1.40],[-.80,1.91],[-.20,1.91],[-.20,1.40]], [[-.08,1.40],[-.08,1.91],[.16,1.91],[.49,1.40]]],
            windshield: [[.30,1.96],[.65,1.39]],
            stripe: '#f0dfb4'
        },
        buggy: {
            width: .78, wheels: [-1.33, 1.34], radius: .53,
            body: [[-1.88,.68],[1.90,.68],[2.02,1.12],[1.39,1.18],[.67,1.08],[-.55,1.04],[-1.60,1.28],[-1.88,1.08]],
            windows: [], stripe: '#e8bc68'
        },
        truck: {
            width: .92, wheels: [-1.37, 1.30], radius: .55,
            body: [[-2.00,.72],[1.94,.72],[2.05,.98],[1.86,1.30],[-1.94,1.30]],
            windows: [[[.15,1.66],[.15,2.34],[1.08,2.34],[1.51,1.66]]],
            windshield: [[1.21,2.36],[1.69,1.66]],
            stripe: '#dfcfac'
        },
        rover: {
            width: .94, wheels: [-1.31, 1.31], radius: .50,
            body: [[-1.96,.75],[1.86,.75],[2.03,1.10],[1.53,1.62],[.85,1.96],[-.95,1.96],[-1.56,1.62],[-1.96,1.09]],
            windows: [[[-1.38,1.36],[-.88,1.81],[-.36,1.81],[-.36,1.36]], [[-.23,1.36],[-.23,1.81],[.37,1.81],[.37,1.36]], [[.50,1.36],[.50,1.81],[.79,1.81],[1.42,1.43],[1.42,1.36]]],
            windshield: [[.94,1.85],[1.56,1.51]],
            stripe: '#efb94f'
        }
    };

    function mix(hex, target, ratio) {
        const from = hex.match(/[a-f\d]{2}/gi).map(v => parseInt(v,16));
        const to = target.match(/[a-f\d]{2}/gi).map(v => parseInt(v,16));
        return '#' + from.map((v,i) => Math.round(v+(to[i]-v)*ratio).toString(16).padStart(2,'0')).join('');
    }

    const paintFor = (id, value) => /^#[a-f\d]{6}$/i.test(value || '') ? value : H.getCar(id).color;
    const point = (x,y,z) => [280+x*68-y*40, 248+x*17+y*25-z*64];
    const points = values => values.map(v => v.map(n => n.toFixed(1)).join(',')).join(' ');
    const polygon = (values, fill, stroke = ink, weight = 1.5, extra = '') =>
        `<polygon points="${points(values)}" fill="${fill}" stroke="${stroke}" stroke-width="${weight}" stroke-linejoin="round" ${extra}/>`;
    const side = (shape, y, fill, stroke = ink, weight = 1.5, extra = '') =>
        polygon(shape.map(([x,z]) => point(x,y,z)), fill, stroke, weight, extra);
    const line = (values, color = ink, width = 2, extra = '') =>
        `<polyline points="${points(values)}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linejoin="round" stroke-linecap="round" ${extra}/>`;
    const sideLine = (shape, y, color, width, extra) => line(shape.map(([x,z]) => point(x,y,z)),color,width,extra);
    const circle = (x,y,z,r,fill,stroke = 'none',width = 1) => {
        const p = point(x,y,z);
        return `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${width}"/>`;
    };

    function solid(shape, width, color) {
        let result = side(shape,-width,mix(color,ink,.28));
        for (let i=0;i<shape.length;i++) {
            const a=shape[i], b=shape[(i+1)%shape.length];
            if ((b[1]-a[1])*2560-(b[0]-a[0])*2380<=0) continue;
            const fill=b[0]<a[0] ? mix(color,'#ffffff',.28) : mix(color,ink,.20);
            result += polygon([point(a[0],-width,a[1]),point(b[0],-width,b[1]),
                point(b[0],width,b[1]),point(a[0],width,a[1])],fill);
        }
        return result+side(shape,width,color);
    }

    function ring(x,y,z,r,fill,stroke=ink,weight=1.5,from=0,to=Math.PI*2) {
        const pts=Array.from({length:49},(_,i)=> {
            const t=from+(to-from)*i/48;
            return point(x+Math.cos(t)*r,y,z+Math.sin(t)*r);
        });
        return (fill==='none' ? line(pts,stroke,weight) : polygon(pts,fill,stroke,weight));
    }

    function wheel(x,y,r,rover=false) {
        let svg=ring(x,y,.51,r,'#253137','#182329',2.5);
        svg+=ring(x,y,.51,r*.82,'#344248','#536165',1);
        for(let i=0;i<20;i++) {
            const t=i*Math.PI/10;
            svg+=line([point(x+Math.cos(t)*r*.87,y,.51+Math.sin(t)*r*.87),
                point(x+Math.cos(t+.04)*r*.98,y,.51+Math.sin(t+.04)*r*.98)],'#586469',2.8);
        }
        svg+=ring(x,y+.015,.51,r*.57,rover?'#d8dedb':'#c7cfc9',ink,1.8);
        svg+=ring(x,y+.02,.51,r*.33,'#516069',ink,1);
        for(let i=0;i<5;i++) {
            const t=i*Math.PI*2/5;
            svg+=circle(x+Math.cos(t)*r*.40,y+.025,.51+Math.sin(t)*r*.40,2.0,'#f4f0dc');
        }
        return svg+ring(x,y+.025,.51,r*.14,rover?'#e2ba5f':'#929e97',ink,1);
    }

    function front(shape, x, fill, stroke=ink, weight=1.5) {
        return polygon(shape.map(([y,z])=>point(x,y,z)),fill,stroke,weight);
    }

    function glazing(id, model) {
        let out='';
        for(const shape of model.windows) {
            out+=side(shape,model.width+.018,glass,ink,2);
            const [a,b]=shape;
            out+=sideLine([[a[0]+.06,a[1]+.06],[b[0]+.06,b[1]-.08]],model.width+.025,'#9bc6cd',2.8);
        }
        if(model.windshield) {
            const [top,bottom]=model.windshield;
            out+=polygon([point(top[0],-model.width+.10,top[1]),point(top[0],model.width-.10,top[1]),
                point(bottom[0],model.width-.10,bottom[1]),point(bottom[0],-model.width+.10,bottom[1])],glass,ink,2);
            out+=line([point(top[0]+.04,-model.width+.22,top[1]-.04),
                point(bottom[0]-.04,-model.width+.22,bottom[1]+.04)],'#a5d0d2',3);
        }
        return out;
    }

    function details(id, model, color) {
        const y=model.width+.026;
        let out='';
        if(id==='scout') {
            out+=sideLine([[-1.12,1.29],[-1.12,.93],[.49,.93],[.49,1.28]],y,mix(color,ink,.4),1.7);
            out+=sideLine([[-.95,1.30],[-.72,1.30]],y,ink,3);
            out+=sideLine([[-1.85,1.06],[1.58,1.06]],y,model.stripe,3.7);
            // Roof rack and luggage are actual volumes, not a floating roof symbol.
            out+=solid([[-.97,2.10],[.32,2.10],[.32,2.16],[-.97,2.16]],.93,steel);
            out+=solid([[-.78,2.17],[-.15,2.17],[-.15,2.48],[-.70,2.48],[-.78,2.40]],.57,'#8f9d79');
            for(const x of [-.60,-.30]) out+=line([point(x,-.59,2.48),point(x,.59,2.48),point(x,.59,2.18)],'#3e4c41',3);
            out+=front([[-.35,.91],[.35,.91],[.35,1.15],[-.35,1.15]],1.94,ink);
            for(let i=0;i<5;i++) out+=line([point(1.95,-.26+i*.13,.94),point(1.95,-.26+i*.13,1.12)],'#9eafa2',2);
        } else if(id==='buggy') {
            // Seats, exposed engine, a complete roll cage and rear wing.
            out+=solid([[-1.70,1.20],[-1.12,1.20],[-1.12,1.46],[-1.70,1.46]],.49,steel);
            for(const sy of [-.42,.42]) {
                out+=side([[-.43,1.02],[.13,1.02],[.13,1.15],[-.23,1.15],[-.36,1.65],[-.57,1.65]],sy,'#cfa35b',ink,2);
            }
            for(const sy of [-.78,.78]) {
                out+=sideLine([[-.91,1.09],[-.57,2.08],[.28,2.08],[.94,1.13]],sy,ink,8);
                out+=sideLine([[-.91,1.09],[.28,2.08]],sy,steel,3.5);
            }
            for(const x of [-.57,.28]) out+=line([point(x,-.78,2.08),point(x,.78,2.08)],steel,7);
            for(const sy of [-.55,.55]) out+=line([point(-1.62,sy,1.35),point(-1.62,sy,1.75)],steel,5);
            out+=solid([[-1.91,1.69],[-1.40,1.69],[-1.40,1.81],[-1.91,1.81]],1.04,'#374b50');
            out+=sideLine([[-1.85,.82],[1.78,.82]],y,model.stripe,5);
            for(const x of [-1.23,1.15]) {
                const pts=Array.from({length:9},(_,i)=>point(x+(i%2?.07:-.07),y+.05,.72+i*.045));
                out+=line(pts,'#e3aa57',3.5);
            }
            out+=front([[-.31,.89],[.31,.89],[.31,1.07],[-.31,1.07]],1.96,steel);
        } else if(id==='truck') {
            out+=sideLine([[-1.88,1.34],[-.27,1.34],[-.27,2.14],[-1.80,2.14]],y,'#797b64',2);
            for(const x of [-1.57,-.94,-.34]) {
                out+=line([point(x,-.93,2.23),point(x,.95,2.23),point(x,.95,1.32)],'#857d62',3.5);
            }
            out+=sideLine([[.10,1.58],[.10,1.02],[1.44,1.02],[1.44,1.58]],y,mix(color,ink,.4),1.7);
            out+=sideLine([[.26,1.51],[.50,1.51]],y,ink,3.7);
            out+=sideLine([[.06,1.24],[1.61,1.24]],y,model.stripe,4.5);
            out+=sideLine([[-.16,1.45],[-.16,2.58],[-.28,2.66]],y+.08,steel,6);
            out+=front([[-.42,1.13],[.42,1.13],[.42,1.49],[-.42,1.49]],1.98,ink);
            for(const z of [1.20,1.30,1.40]) out+=line([point(1.99,-.36,z),point(1.99,.36,z)],'#899994',2.4);
        } else {
            out+=sideLine([[-1.83,1.13],[1.63,1.13]],y,model.stripe,6);
            out+=sideLine([[-.27,1.29],[-.27,.95],[.45,.95],[.45,1.29]],y,steel,1.8);
            out+=sideLine([[-1.45,1.02],[-.89,1.02]],y,trim,2.5);
            out+=solid([[-1.42,2.02],[-.34,2.02],[-.34,2.10],[-1.42,2.10]],1.02,'#345363');
            for(let i=0;i<5;i++) out+=line([point(-1.34+i*.20,-.94,2.11),point(-1.34+i*.20,.94,2.11)],'#7dabb6',1.2);
            for(const sy of [-.53,0,.53]) out+=line([point(-1.42,sy,2.11),point(-.34,sy,2.11)],'#7dabb6',1.2);
            out+=line([point(-.92,-.18,2.12),point(-.92,-.18,2.82),point(-.67,-.18,3.0)],steel,4);
            out+=front([[-.48,2.72],[-.16,2.54],[.16,2.72],[-.16,2.87]],-.67,'#dce4dd',steel,1.7);
            out+=circle(-.61,-.18,2.91,4,'#edb949');
            out+=front([[-.40,.95],[.40,.95],[.40,1.12],[-.40,1.12]],1.98,steel);
        }
        return out;
    }

    function svg(id='scout', value) {
        if(!models[id]) id='scout';
        const model=models[id], color=paintFor(id,value);
        let body='';
        for(const x of model.wheels) {
            const contact=point(x,model.width+.10,0);
            body+=`<ellipse cx="${contact[0]}" cy="${contact[1]}" rx="29" ry="6" transform="rotate(14 ${contact[0]} ${contact[1]})" fill="#26383e" opacity=".12"/>`;
        }
        // Far wheels precede the shell; near wheels remain attached to their wheel arches.
        for(const x of model.wheels) body+=wheel(x,-model.width-.05,model.radius,id==='rover');
        body+=solid(model.body,model.width,color);
        if(id==='truck') {
            body+=solid([[-1.94,1.28],[-.21,1.28],[-.21,2.23],[-1.79,2.23],[-1.94,2.08]],.93,'#c6bd9b');
            body+=solid([[-.04,1.02],[1.94,1.02],[1.97,1.55],[1.20,2.48],[.01,2.48]],.89,color);
        }
        body+=glazing(id,model)+details(id,model,color);
        // Dark sill, raised wheel arch lips, fenders and front protection.
        body+=sideLine([[-1.85,.76],[1.76,.76]],model.width+.04,steel,7);
        for(const x of model.wheels) body+=ring(x,model.width+.05,.51,model.radius+.075,'none',steel,7,0,Math.PI);
        body+=solid([[1.79,.65],[2.13,.65],[2.13,.85],[1.79,.85]],model.width+.10,steel);
        for(const sy of [-.67,.67]) {
            const z=id==='truck'?1.32:id==='rover'?.96:1.04;
            body+=front([[sy-.13,z-.08],[sy+.13,z-.08],[sy+.13,z+.08],[sy-.13,z+.08]],id==='truck'?1.99:1.98,'#fff1b8',steel,1.3);
        }
        for(const x of model.wheels) body+=wheel(x,model.width+.10,model.radius,id==='rover');
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="80 20 430 305" fill="none" aria-hidden="true" focusable="false" data-hill-model="${id}"><ellipse cx="285" cy="266" rx="185" ry="29" transform="rotate(14 285 266)" fill="#354840" opacity=".07"/><ellipse cx="285" cy="266" rx="151" ry="17" transform="rotate(14 285 266)" fill="#354840" opacity=".07"/>${body}</svg>`;
    }

    // Side profiles use the original chassis coordinates and never alter wheel physics.
    function drawBody(ctx, h) {
        const color=paintFor(h.car,h.paint), m=models[h.car] || models.scout;
        const path=(shape,fill,stroke=ink,width=.055)=> {
            ctx.beginPath();
            shape.forEach(([x,z],i)=>i?ctx.lineTo(x,z):ctx.moveTo(x,z));
            ctx.closePath();ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();
        };
        const translate=shape=>shape.map(([x,z])=>[x*.84,(z-.98)*.83]);
        ctx.lineJoin='round';ctx.lineCap='round';
        path(translate(m.body),color);
        if(h.car==='truck') {
            path(translate([[-1.94,1.28],[-.21,1.28],[-.21,2.23],[-1.79,2.23],[-1.94,2.08]]),'#c6bd9b');
            path(translate([[-.04,1.02],[1.94,1.02],[1.97,1.55],[1.20,2.48],[.01,2.48]]),color);
        }
        for(const window of m.windows) path(translate(window),glass);
        ctx.strokeStyle=steel;ctx.lineWidth=.10;
        if(h.car==='buggy') {
            const cage=translate([[-.91,1.09],[-.57,2.08],[.28,2.08],[.94,1.13]]);
            ctx.beginPath();cage.forEach(([x,z],i)=>i?ctx.lineTo(x,z):ctx.moveTo(x,z));ctx.stroke();
            path(translate([[-1.91,1.69],[-1.40,1.69],[-1.40,1.81],[-1.91,1.81]]),steel);
        }
        if(h.car==='scout') path(translate([[-.97,2.10],[.32,2.10],[.32,2.23],[-.97,2.23]]),steel);
        if(h.car==='rover') {
            path(translate([[-1.42,2.02],[-.34,2.02],[-.34,2.14],[-1.42,2.14]]),'#345363');
            ctx.beginPath();ctx.moveTo(-.75,.95);ctx.lineTo(-.75,1.6);ctx.lineTo(-.54,1.75);ctx.stroke();
        }
        ctx.strokeStyle=m.stripe;ctx.lineWidth=.065;
        ctx.beginPath();ctx.moveTo(-1.30,.11);ctx.lineTo(1.30,.11);ctx.stroke();
        path([[1.35,-.20],[1.76,-.20],[1.76,-.06],[1.35,-.06]],steel);
        ctx.fillStyle='#fff1b8';ctx.fillRect(1.39,.015,.20,.13);
        ctx.fillStyle='#b8634e';ctx.fillRect(-1.57,-.10,.09,.13);
    }

    window.ArcadeHillArt={svg,drawBody};
})();
