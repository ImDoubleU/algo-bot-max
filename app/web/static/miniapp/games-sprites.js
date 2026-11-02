/* Game actors are drawn as vectors, with no platform-dependent emoji glyphs. */
(() => {
    const ink = "#4a3b64",
        palettes = {
            base: ["#b6a0ec", "#c5e998", "#efb38e"],
            mint: ["#78c9bb", "#ddf5ae", "#9fbcf1"],
            sun: ["#efbd68", "#f9dfa3", "#e99591"],
            nebula: ["#bc91e5", "#86c9e4", "#ef9bc0"]
        };

    function ellipse(c, x, y, rx, ry, color) {
        c.fillStyle = color;
        c.beginPath();
        c.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
        c.fill();
    }

    function path(c, points, fill, stroke = ink, width = 1.5) {
        c.beginPath();
        c.moveTo(...points[0]);
        for (const p of points.slice(1)) c.lineTo(...p);
        c.closePath();
        if (fill) {
            c.fillStyle = fill;
            c.fill();
        }
        if (stroke) {
            c.strokeStyle = stroke;
            c.lineWidth = width;
            c.lineJoin = "round";
            c.stroke();
        }
    }

    function eyes(c, x = 0, y = 0) {
        ellipse(c, x - 6, y, 1.8, 2.4, ink);
        ellipse(c, x + 6, y, 1.8, 2.4, ink);
        c.strokeStyle = ink;
        c.lineWidth = 1.4;
        c.beginPath();
        c.arc(x, y + 4, 3, 0, Math.PI);
        c.stroke();
    }

    function round(c, x, y, w, h, r, color, stroke = ink) {
        c.beginPath();
        c.roundRect(x, y, w, h, r);
        c.fillStyle = color;
        c.fill();
        if (stroke) {
            c.strokeStyle = stroke;
            c.lineWidth = 1.5;
            c.stroke();
        }
    }

    function draw(c, type, x, y, size = 40, options = {}) {
        const palette = palettes[options.skin] || palettes.base,
            phase = options.phase || 0;
        c.save();
        c.translate(x, y);
        c.rotate(options.angle || 0);
        c.scale(size / 40, size / 40);
        if ((typeof options.quality === "function" ? options.quality() : options.quality) !== "low") {
            c.shadowColor = "#00000022";
            c.shadowBlur = 3;
            c.shadowOffsetY = 2;
        }
        if (typeof type === "number") type = ["stone", "seed", "mushroom", "chick", "cat", "fox", "dragon", "planet", "sun", "galaxy"][Math.min(9, type)];
        switch (type) {
            case "cat":
                ellipse(c, 0, 2, 18, 18, "#e8f3fa");
                ellipse(c, 0, 2, 15, 15, "#bdcee7");
                path(c, [
                    [-12, 1],
                    [-12, -14],
                    [-3, -8],
                    [4, -8],
                    [13, -14],
                    [13, 2],
                    [9, 12],
                    [-8, 12]
                ], "#fff0ce");
                path(c, [
                    [-10, -10],
                    [-9, -4],
                    [-4, -6]
                ], "#e8b0ae", null);
                path(c, [
                    [11, -10],
                    [10, -4],
                    [5, -6]
                ], "#e8b0ae", null);
                eyes(c, 0, 1);
                round(c, -21, -1, 5, 9, 2, palette[0]);
                round(c, 16, -1, 5, 9, 2, palette[0]);
                break;
            case "bug":
            case "robot":
                c.strokeStyle = palette[0];
                c.lineWidth = 2.3;
                c.lineCap = "round";
                for (const side of [-1, 1])
                    for (let i = 0; i < 3; i++) {
                        c.beginPath();
                        c.moveTo(side * 12, -6 + i * 8);
                        c.lineTo(side * (20 + Math.sin(phase * 8 + i) * 2), -9 + i * 9);
                        c.stroke();
                    }
                round(c, -14, -17, 28, 34, type === "bug" ? 12 : 5, type === "bug" ? palette[0] : "#8ac9c4");
                round(c, -10, -8, 20, 12, 5, "#443651");
                ellipse(c, -4, -2, 2.2, 3, palette[1]);
                ellipse(c, 4, -2, 2.2, 3, palette[1]);
                c.strokeStyle = ink;
                c.lineWidth = 1.5;
                c.beginPath();
                c.moveTo(-7, 11);
                c.lineTo(7, 11);
                c.stroke();
                for (const side of [-1, 1]) {
                    c.beginPath();
                    c.moveTo(side * 7, -15);
                    c.lineTo(side * 10, -23);
                    c.stroke();
                    ellipse(c, side * 10, -23, 2.5, 2.5, palette[1]);
                }
                break;
            case "stone":
                path(c, [
                    [-16, -7],
                    [-5, -17],
                    [12, -12],
                    [18, 3],
                    [7, 16],
                    [-12, 13]
                ], "#bfbcdd");
                eyes(c, 0, 0);
                break;
            case "seed":
                ellipse(c, 0, 4, 14, 15, palette[1]);
                path(c, [
                    [0, -10],
                    [4, -20],
                    [13, -19],
                    [8, -12]
                ], "#76af86");
                eyes(c, 0, 3);
                break;
            case "mushroom":
                round(c, -6, -1, 12, 18, 4, "#f7e9bd");
                ellipse(c, 0, -5, 19, 13, palette[2]);
                ellipse(c, -7, -9, 3, 3, "#fff1d8");
                ellipse(c, 7, -6, 3, 3, "#fff1d8");
                eyes(c, 0, 6);
                break;
            case "chick":
                ellipse(c, 0, 0, 17, 18, "#f2d779");
                eyes(c, 0, -3);
                path(c, [
                    [-3, 4],
                    [0, 8],
                    [4, 4]
                ], "#dd9b61");
                break;
            case "fox":
                path(c, [
                    [-17, -17],
                    [-5, -9],
                    [6, -9],
                    [17, -17],
                    [16, 8],
                    [0, 18],
                    [-16, 8]
                ], palette[2]);
                path(c, [
                    [-15, 0],
                    [0, 8],
                    [15, 0],
                    [12, 12],
                    [0, 18],
                    [-12, 12]
                ], "#fff2d3", null);
                eyes(c, 0, -2);
                break;
            case "dragon":
                path(c, [
                    [-16, -8],
                    [-16, -20],
                    [-6, -13],
                    [7, -13],
                    [16, -21],
                    [17, 0],
                    [11, 16],
                    [-11, 16]
                ], palette[1]);
                eyes(c, 0, -1);
                path(c, [
                    [-3, 11],
                    [0, 16],
                    [4, 11]
                ], "#a1c37e", null);
                break;
            case "planet":
                ellipse(c, 0, 0, 15, 15, palette[0]);
                c.strokeStyle = palette[1];
                c.lineWidth = 4;
                c.beginPath();
                c.ellipse(0, 1, 23, 6, -.4, 0, Math.PI * 2);
                c.stroke();
                ellipse(c, -5, -5, 4, 4, "#decfff");
                break;
            case "sun":
                for (let i = 0; i < 10; i++) {
                    c.rotate(Math.PI / 5);
                    path(c, [
                        [-2, -20],
                        [0, -26],
                        [2, -20]
                    ], "#e8c66f", null);
                }
                ellipse(c, 0, 0, 16, 16, "#f5d986");
                eyes(c);
                break;
            case "galaxy":
                for (let i = 0; i < 3; i++) {
                    c.rotate(Math.PI / 3);
                    c.strokeStyle = palette[i];
                    c.lineWidth = 5;
                    c.beginPath();
                    c.ellipse(0, 0, 21, 7, 0, 0, Math.PI * 2);
                    c.stroke();
                }
                ellipse(c, 0, 0, 5, 5, "#fff1c3");
                break;
            case "pizza":
                path(c, [
                    [0, -21],
                    [-19, 15],
                    [20, 15]
                ], "#f5d886");
                c.strokeStyle = "#c4946f";
                c.lineWidth = 5;
                c.beginPath();
                c.moveTo(-18, 15);
                c.quadraticCurveTo(0, 22, 18, 15);
                c.stroke();
                ellipse(c, -4, 4, 3.5, 3.5, "#db8e88");
                ellipse(c, 6, 9, 3.5, 3.5, "#db8e88");
                break;
            case "rocket":
                path(c, [
                    [0, -23],
                    [12, -6],
                    [11, 13],
                    [-11, 13],
                    [-12, -6]
                ], "#f4eddf");
                path(c, [
                    [-11, 2],
                    [-21, 15],
                    [-10, 13]
                ], palette[0]);
                path(c, [
                    [11, 2],
                    [21, 15],
                    [10, 13]
                ], palette[0]);
                ellipse(c, 0, -5, 5, 5, "#97bbda");
                path(c, [
                    [-5, 14],
                    [0, 26],
                    [5, 14]
                ], "#f2c77f", null);
                break;
            case "bolt":
                path(c, [
                    [5, -23],
                    [-13, 3],
                    [-1, 3],
                    [-5, 23],
                    [15, -6],
                    [2, -6]
                ], "#e8ce77");
                break;
            case "gem":
                path(c, [
                    [-18, -8],
                    [-9, -18],
                    [10, -18],
                    [19, -8],
                    [0, 20]
                ], "#91c8dc");
                path(c, [
                    [-18, -8],
                    [19, -8],
                    [0, 20],
                    [-6, -8],
                    [0, -18],
                    [7, -8],
                    [0, 20]
                ], null, "#e2f4ff", 1.5);
                break;
            case "cactus":
                round(c, -6, -21, 12, 41, 6, "#9ac895");
                round(c, -17, -7, 11, 10, 5, "#9ac895");
                round(c, -18, -16, 6, 16, 3, "#9ac895");
                round(c, 6, 2, 12, 7, 3, "#9ac895");
                round(c, 13, -8, 6, 16, 3, "#9ac895");
                eyes(c, 0, 1);
                break;
            case "melon":
                path(c, [
                    [-22, -7],
                    [22, -7],
                    [15, 12],
                    [0, 23],
                    [-16, 12]
                ], "#9ac59a");
                path(c, [
                    [-18, -7],
                    [18, -7],
                    [12, 9],
                    [0, 17],
                    [-12, 9]
                ], "#eaa09f", null);
                for (const p of [
                        [-8, 0],
                        [7, 0],
                        [0, 9]
                    ]) ellipse(c, p[0], p[1], 1, 2, ink);
                break;
            case "octopus":
                ellipse(c, 0, -3, 17, 17, palette[0]);
                for (let i = -2; i <= 2; i++) {
                    c.strokeStyle = palette[0];
                    c.lineWidth = 5;
                    c.beginPath();
                    c.moveTo(i * 6, 9);
                    c.quadraticCurveTo(i * 10, 24, i * 9 + 3, 18);
                    c.stroke();
                }
                eyes(c, 0, -4);
                break;
            default:
                draw(c, "planet", 0, 0, 40, options);
        }
        c.restore();
    }
    const memory = ["cat", "planet", "pizza", "dragon", "rocket", "mushroom", "bolt", "gem", "fox", "cactus", "melon", "octopus"];

    function buttonCanvas(button, type, options = {}) {
        const c = button.querySelector("canvas") || document.createElement("canvas");
        c.width = 100;
        c.height = 100;
        c.className = "sprite-canvas";
        c.setAttribute("aria-hidden", "true");
        if (!c.parentNode) button.prepend(c);
        draw(c.getContext("2d"), type, 50, 50, 70, options);
    }
    window.ArcadeSprites = {
        draw,
        buttonCanvas,
        memory,
        palettes
    };
})();
