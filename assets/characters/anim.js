/* =====================================================================
   TRIAD STUDIO — Motor de animación de personajes (rig tipo Live2D)
   Respiración · balanceo de cabeza · parpadeo · mirada viva · habla
   pelo ondeante (capa opcional) · aura pulsante · inclinación al hablar
   ===================================================================== */
(function () {
    'use strict';

    const KEYS = ['sylphiette', 'roxy', 'eris'];
    const DEFAULTS = {
        headPivot: { x: 50, y: 58 },
        eyes: [{ x: 39, y: 50, rx: 8, ry: 9 }, { x: 61, y: 50, rx: 8, ry: 9 }],
        mouth: { x: 50, y: 63, rx: 8, ry: 7 },
        skin: '#ffd9c4',
        amplitude: { head: 1, breath: 1, float: 1, blink: 1, talk: 1, gaze: 1, hair: 1 },
        speed: 1
    };

    let rig = {};
    const actors = [];

    /* ---------- utilidades: muelle suave (movimiento natural) ---------- */
    function spring(current, target, velocity, stiffness, damping, dt) {
        const f = (target - current) * stiffness - velocity * damping;
        const v = velocity + f * dt;
        return [current + v * dt, v];
    }

    function buildActor(card) {
        const key = card.dataset.name.toLowerCase();
        const cfg = Object.assign({}, DEFAULTS, rig[key] || {});
        cfg.amplitude = Object.assign({}, DEFAULTS.amplitude,
            (rig[key] || {}).amplitude || {});

        const portrait = card.querySelector('.portrait');
        if (!portrait) return null;

        const art = portrait.querySelector('img, svg');
        if (!art) return null;

        /* --- capa de aura --- */
        const aura = document.createElement('div');
        aura.className = 'rig-aura';
        aura.style.cssText =
            'position:absolute;inset:-14%;border-radius:26px;pointer-events:none;' +
            'background:radial-gradient(circle at 50% 42%, var(--c), transparent 68%);' +
            'opacity:.16;transition:opacity .5s ease;filter:blur(6px);';
        portrait.insertBefore(aura, portrait.firstChild);

        /* --- párpados (dos elipses del color de la piel) --- */
        const lids = cfg.eyes.map(e => {
            const lid = document.createElement('div');
            lid.style.cssText =
                `position:absolute;left:${e.x - e.rx}%;top:${e.y - e.ry}%;` +
                `width:${e.rx * 2}%;height:${e.ry * 2}%;border-radius:50%;` +
                `background:${cfg.skin};opacity:0;pointer-events:none;` +
                'transform:scaleY(0);transform-origin:center;';
            portrait.appendChild(lid);
            return lid;
        });

        /* --- boca articulada --- */
        const m = cfg.mouth;
        const mouth = document.createElement('div');
        mouth.style.cssText =
            `position:absolute;left:${m.x - m.rx}%;top:${m.y - m.ry}%;` +
            `width:${m.rx * 2}%;height:${m.ry * 2}%;border-radius:50%;` +
            `background:#b8444c;opacity:0;pointer-events:none;` +
            'transform:scaleY(0);transform-origin:center;mix-blend-mode:hard-light;';
        portrait.appendChild(mouth);

        /* --- capa de pelo opcional (sylphiette_hair.png, roxy_hair.png...) --- */
        let hair = null;
        const hairImg = new Image();
        hairImg.src = '/assets/characters/' + key + '_hair.png';
        hairImg.onload = () => {
            hair = document.createElement('img');
            hair.src = hairImg.src;
            hair.style.cssText =
                'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;' +
                'pointer-events:none;transform-origin:50% 20%;';
            portrait.appendChild(hair);
        };

        return {
            key, card, portrait, art, aura, lids, mouth, hair: () => hair,
            cfg,
            /* estado de la física */
            t: Math.random() * 100,
            headV: 0, headA: 0,
            floatV: 0,
            gaze: 0, gazeTarget: 0, gazeTimer: 2 + Math.random() * 4,
            blinkTimer: 2 + Math.random() * 5, blinkPhase: 0,
            talking: false, talkAmp: 0,
            lean: 0
        };
    }

    /* ---------- observador: detecta quién está hablando ---------- */
    function watchSpeaking(a) {
        const obs = new MutationObserver(() => {
            const speaking = a.card.classList.contains('speaking');
            a.talking = speaking;
        });
        obs.observe(a.card, { attributes: true, attributeFilter: ['class'] });
    }

    /* ---------- bucle maestro de animación ---------- */
    let last = performance.now();
    function loop(now) {
        const dt = Math.min((now - last) / 1000, 0.05);
        last = now;

        for (const a of actors) {
            const amp = a.cfg.amplitude;
            const sp = a.cfg.speed;
            a.t += dt * sp;

            /* objetivo de balanceo de cabeza: onda compuesta = movimiento orgánico */
            const headTarget =
                Math.sin(a.t * 1.1) * 2.6 * amp.head +
                Math.sin(a.t * 0.47 + 1.3) * 1.6 * amp.head +
                Math.sin(a.t * 2.3 + 0.7) * 0.5 * amp.head;

            [a.headA, a.headV] = spring(a.headA, headTarget, a.headV, 40, 9, dt);

            /* flotación vertical */
            const floatTarget = Math.sin(a.t * 0.9 + 2) * 3.2 * amp.float;
            [a.floatY, a.floatV] = spring(a.floatY || 0, floatTarget, a.floatV || 0, 30, 8, dt);

            /* respiración (escala) */
            const breath = 1 + Math.sin(a.t * 1.55) * 0.013 * amp.breath;

            /* inclinación hacia el usuario cuando habla */
            const leanTarget = a.talking ? 1 : 0;
            a.lean += (leanTarget - a.lean) * Math.min(dt * 4, 1);

            /* mirada viva */
            a.gazeTimer -= dt * sp;
            if (a.gazeTimer <= 0) {
                a.gazeTarget = (Math.random() - 0.5) * 2.4 * amp.gaze;
                a.gazeTimer = 2.2 + Math.random() * 4.5;
            }
            a.gaze += (a.gazeTarget - a.gaze) * Math.min(dt * 3, 1);

            /* parpadeo */
            a.blinkTimer -= dt * sp;
            if (a.blinkTimer <= 0 && a.blinkPhase === 0) {
                a.blinkPhase = 0.001;
                a.blinkTimer = 3.2 + Math.random() * 4.2;
            }
            if (a.blinkPhase > 0) {
                a.blinkPhase += dt * 7.5;
                const p = a.blinkPhase;
                const close = p < 0.5 ? p * 2 : Math.max(0, 1 - (p - 0.5) * 2);
                for (const lid of a.lids) {
                    lid.style.opacity = '1';
                    lid.style.transform = `scaleY(${close})`;
                }
                if (p >= 1) {
                    a.blinkPhase = 0;
                    for (const lid of a.lids) {
                        lid.style.opacity = '0';
                        lid.style.transform = 'scaleY(0)';
                    }
                }
            }

            /* boca: habla ondulante mientras suena la voz */
            const talkTarget = a.talking ? 1 : 0;
            a.talkAmp += (talkTarget - a.talkAmp) * Math.min(dt * 9, 1);
            if (a.talkAmp > 0.02) {
                const osc = 0.5 + 0.5 * Math.sin(a.t * 22 * sp);
                const open = a.talkAmp * (0.35 + osc * 1.15) * amp.talk;
                a.mouth.style.opacity = String(Math.min(0.92, a.talkAmp * 0.92));
                a.mouth.style.transform = `scaleY(${open.toFixed(3)})`;
            } else {
                a.mouth.style.opacity = '0';
            }

            /* aura: pulsa con la respiración y crece al hablar */
            a.aura.style.opacity =
                String(0.13 + 0.05 * Math.sin(a.t * 1.55) + (a.talking ? 0.12 : 0));

            /* trasformación final del retrato (todo junto, suave y visible) */
            const tx = a.gaze * 1.4;
            const ty = (a.floatY || 0) * 0.6;
            const rot = a.headA + a.lean * 1.8;
            const scale = breath * (1 + a.lean * 0.045);
            a.art.style.transform =
                `translate(${tx.toFixed(2)}px, ${ty.toFixed(2)}px) ` +
                `rotate(${rot.toFixed(2)}deg) scale(${scale.toFixed(4)})`;

            /* pelo ondeante con péndulo independiente */
            const hair = a.hair();
            if (hair) {
                const sway = Math.sin(a.t * 1.35 + 0.6) * 2.2 * amp.hair +
                    Math.sin(a.t * 0.62) * 1.1 * amp.hair;
                hair.style.transform =
                    `translate(${(tx * 1.6).toFixed(2)}px, ${(ty * 1.3).toFixed(2)}px) ` +
                    `rotate(${(rot * 1.25 + sway * 0.35).toFixed(2)}deg) ` +
                    `skewX(${(sway * 0.5).toFixed(2)}deg) ` +
                    `scale(${(scale * 1.012).toFixed(4)})`;
            }
        }

        requestAnimationFrame(loop);
    }

    /* ---------- arranque ---------- */
    function init() {
        document.querySelectorAll('.agent-card').forEach(card => {
            const a = buildActor(card);
            if (a) {
                watchSpeaking(a);
                actors.push(a);
            }
        });
        if (actors.length) {
            requestAnimationFrame(loop);
            console.log(`[TRIAD] Motor de animación activo: ${actors.length} personajes riggeados.`);
        }
    }

    fetch('/assets/characters/rig.json')
        .then(r => (r.ok ? r.json() : {}))
        .then(j => {
            rig = j || {};
            init();
        })
        .catch(() => init());
})();