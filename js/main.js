/* CARS Auto Center · interface, animações e diagnóstico.
   GSAP + ScrollTrigger + SplitText: entrada do hero, títulos, réguas de desgaste, linha do tempo, contador.
   Motion: molas dos botões, botão magnético, troca de cartões do painel e do diagnóstico.
   O carro 3D (js/car3d.js) conversa com esta interface pelos eventos cars:select e cars:picked. */
(function () {
  'use strict';
  var D = window.CARS_DATA;
  var doc = document.documentElement;
  var reduce = doc.classList.contains('reduce');
  var M = window.Motion || null;
  var hasGsap = !!window.gsap;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var WA = 'https://wa.me/' + D.whatsapp + '?text=';

  if (hasGsap) {
    if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);
    if (window.SplitText) gsap.registerPlugin(window.SplitText);
  }

  /* ---------------------------------------------------------------- nav */
  var nav = $('[data-nav]');
  var onScroll = function () { nav.classList.toggle('is-scrolled', window.scrollY > 24); };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  var toggle = $('[data-menu-toggle]');
  var menu = $('[data-menu]');
  function setMenu(open) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.querySelector('.sr').textContent = open ? 'Fechar menu' : 'Abrir menu';
    doc.classList.toggle('menu-open', open);
    if (open) {
      menu.hidden = false;
      if (M && !reduce) M.animate(menu, { opacity: [0, 1] }, { duration: 0.25 });
    } else {
      menu.hidden = true;
    }
  }
  toggle.addEventListener('click', function () { setMenu(toggle.getAttribute('aria-expanded') !== 'true'); });
  $$('a', menu).forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { setMenu(false); toggle.focus(); } });
  window.addEventListener('resize', function () { if (window.innerWidth > 1080 && !menu.hidden) setMenu(false); });

  /* ---------------------------------------------------------------- Motion: molas e ímã */
  if (M && !reduce) {
    $$('.btn, .tool, .zone, .light, .channels a').forEach(function (el) {
      el.addEventListener('pointerdown', function () { M.animate(el, { scale: 0.95 }, { type: 'spring', stiffness: 600, damping: 30 }); });
      var up = function () { M.animate(el, { scale: 1 }, { type: 'spring', stiffness: 420, damping: 18 }); };
      el.addEventListener('pointerup', up);
      el.addEventListener('pointerleave', up);
    });
    if (window.matchMedia('(hover: hover)').matches) {
      $$('[data-magnetic]').forEach(function (el) {
        el.addEventListener('pointermove', function (e) {
          var r = el.getBoundingClientRect();
          var x = (e.clientX - r.left - r.width / 2) * 0.22;
          var y = (e.clientY - r.top - r.height / 2) * 0.3;
          M.animate(el, { x: x, y: y }, { type: 'spring', stiffness: 260, damping: 18 });
        });
        el.addEventListener('pointerleave', function () { M.animate(el, { x: 0, y: 0 }, { type: 'spring', stiffness: 260, damping: 14 }); });
      });
    }
  }

  /* ---------------------------------------------------------------- spotlight (21st.dev) */
  $$('[data-spot]').forEach(function (el) {
    el.addEventListener('pointermove', function (e) {
      var r = el.getBoundingClientRect();
      el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      el.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });

  /* ---------------------------------------------------------------- hero */
  function splitTitle(el, type) {
    if (!window.SplitText) return null;
    try { return window.SplitText.create(el, { type: type || 'words', mask: type || 'words', wordsClass: 'w' }); }
    catch (e) { return null; }
  }
  var readout = $('[data-readout-text]');
  var scanText = ['motor', 'freios', 'suspensão', 'elétrica', 'arrefecimento', 'sistemas verificados: 10'];
  function typeReadout() {
    var i = 0;
    var tick = function () {
      readout.textContent = i < scanText.length - 1 ? 'lendo ' + scanText[i] + '…' : scanText[i];
      i++;
      if (i < scanText.length) setTimeout(tick, 380);
    };
    tick();
  }

  if (hasGsap && !reduce) {
    var hero = $('.hero');
    var title = $('.hero__title');
    var split = splitTitle(title, 'words');
    var tl = gsap.timeline({ defaults: { ease: 'power3.out' }, onStart: function () { doc.classList.add('ready'); } });
    tl.from('[data-hero-car]', { xPercent: 28, opacity: 0, filter: 'blur(14px)', duration: 1.3, ease: 'expo.out' }, 0);
    if (split) tl.from(split.words, { yPercent: 110, duration: 0.9, stagger: 0.05 }, 0.15);
    else tl.from(title, { y: 30, opacity: 0, duration: 0.8 }, 0.15);
    tl.from('[data-hero-item]', { y: 24, opacity: 0, duration: 0.7, stagger: 0.1 }, 0.45)
      .fromTo('[data-scan]', { left: '-4%', autoAlpha: 0 }, { left: '96%', autoAlpha: 1, duration: 1.4, ease: 'power2.inOut' }, 0.9)
      .to('[data-scan]', { autoAlpha: 0, duration: 0.3 }, 2.2)
      .from('[data-pin]', { scale: 0, opacity: 0, duration: 0.5, stagger: 0.12, ease: 'back.out(2.4)' }, 1.3)
      .from('[data-readout]', { y: 14, opacity: 0, duration: 0.5, onStart: typeReadout }, 1.1);
    hero.classList.add('is-entering');
  } else {
    doc.classList.add('ready');
    if (readout) readout.textContent = scanText[scanText.length - 1];
  }

  /* títulos das seções: palavras sobem uma vez */
  if (hasGsap && window.ScrollTrigger && !reduce) {
    $$('[data-reveal]').forEach(function (el) {
      var s = splitTitle(el, 'words');
      if (!s) return;
      gsap.from(s.words, { yPercent: 105, duration: 0.8, ease: 'power3.out', stagger: 0.035, scrollTrigger: { trigger: el, start: 'top 88%', once: true } });
    });
  }

  /* ---------------------------------------------------------------- diagnóstico */
  var zonesEl = $('[data-zones]');
  var state = { zone: null, checked: {} };
  D.zones.forEach(function (z, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'zone';
    b.dataset.id = z.id;
    b.setAttribute('aria-pressed', 'false');
    b.innerHTML = '<span class="zone__n">' + String(i + 1).padStart(2, '0') + '</span>' + z.name;
    b.addEventListener('click', function () { selectZone(z.id, 'ui'); });
    zonesEl.appendChild(b);
  });

  var zoneBox = $('[data-zone]');
  var emptyBox = $('[data-empty]');
  var symBox = $('[data-symptoms]');
  var result = $('[data-result]');
  var causes = $('[data-causes]');
  var urg = $('[data-urgency]');
  var send = $('[data-send]');
  var carInput = $('[data-car]');
  var URG = [null,
    { t: 'Pode agendar', c: 'is-low' },
    { t: 'Traga nesta semana', c: 'is-mid' },
    { t: 'Pare e chame a oficina', c: 'is-high' }];

  function setStep(n) {
    $$('[data-step]').forEach(function (li) {
      var s = +li.dataset.step;
      li.classList.toggle('is-on', s <= n);
      if (s === n) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
  }

  function selectZone(id, from) {
    var z = D.zones.find(function (x) { return x.id === id; });
    if (!z) return;
    state.zone = z;
    state.checked = {};
    $$('.zone', zonesEl).forEach(function (b) {
      var on = b.dataset.id === id;
      b.setAttribute('aria-pressed', String(on));
      b.classList.toggle('is-on', on);
    });
    emptyBox.hidden = true;
    zoneBox.hidden = false;
    $('[data-zone-title]').textContent = z.name;
    $('[data-zone-what]').textContent = z.what;
    symBox.innerHTML = '';
    z.symptoms.forEach(function (s, i) {
      var id2 = 'sym-' + z.id + '-' + i;
      var lab = document.createElement('label');
      lab.className = 'sym';
      lab.setAttribute('for', id2);
      lab.innerHTML = '<input type="checkbox" id="' + id2 + '" value="' + i + '"><span class="sym__box"><svg aria-hidden="true"><use href="#i-check"/></svg></span><span>' + s.t + '</span>';
      lab.querySelector('input').addEventListener('change', function (e) {
        state.checked[i] = e.target.checked;
        updateResult();
      });
      symBox.appendChild(lab);
    });
    result.hidden = true;
    setStep(2);
    if (M && !reduce) {
      M.animate(zoneBox, { opacity: [0, 1], y: [12, 0] }, { duration: 0.35, ease: [0.2, 0.7, 0.2, 1] });
      M.animate($$('.sym', symBox), { opacity: [0, 1], x: [-8, 0] }, { delay: M.stagger ? M.stagger(0.04) : 0, duration: 0.3 });
    }
    if (from !== '3d') window.dispatchEvent(new CustomEvent('cars:select', { detail: { id: id } }));
    if (from === '3d' && window.innerWidth < 900) {
      // no celular o painel fica abaixo do carro: leva até ele
      zoneBox.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    }
  }
  window.addEventListener('cars:picked', function (e) { selectZone(e.detail.id, '3d'); });

  function updateResult() {
    var z = state.zone;
    var list = z.symptoms.filter(function (s, i) { return state.checked[i]; });
    if (!list.length) { result.hidden = true; setStep(2); return; }
    var lvl = Math.max.apply(null, list.map(function (s) { return s.n; }));
    causes.innerHTML = list.map(function (s) { return '<li class="lvl-' + s.n + '">' + s.c + '</li>'; }).join('');
    urg.textContent = URG[lvl].t;
    urg.className = 'badge ' + URG[lvl].c;
    var wasHidden = result.hidden;
    result.hidden = false;
    setStep(3);
    buildLink();
    if (wasHidden && M && !reduce) M.animate(result, { opacity: [0, 1], scale: [0.97, 1] }, { type: 'spring', stiffness: 380, damping: 26 });
  }

  function buildLink() {
    var z = state.zone;
    if (!z) return;
    var list = z.symptoms.filter(function (s, i) { return state.checked[i]; });
    var car = (carInput.value || '').trim();
    var msg = 'Olá, CARS! Fiz o pré-diagnóstico no site.\n' +
      '• Área: ' + z.name + '\n' +
      '• O que sinto: ' + list.map(function (s) { return s.t.toLowerCase(); }).join('; ') + '\n' +
      (car ? '• Carro: ' + car + '\n' : '') +
      'Podem me ajudar com um orçamento?';
    send.href = WA + encodeURIComponent(msg);
  }
  carInput.addEventListener('input', buildLink);

  /* ---------------------------------------------------------------- luzes do painel */
  var cluster = $('[data-cluster]');
  var card = $('[data-light-card]');
  D.lights.forEach(function (l) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'light lvl-' + l.level;
    b.dataset.id = l.id;
    b.setAttribute('aria-pressed', 'false');
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + l.svg + '</svg><span class="sr">' + l.name + '</span>';
    b.title = l.name;
    b.addEventListener('click', function () { showLight(l, b); });
    cluster.appendChild(b);
  });
  function showLight(l, btn) {
    $$('.light', cluster).forEach(function (x) { x.setAttribute('aria-pressed', String(x === btn)); x.classList.toggle('is-on', x === btn); });
    card.className = 'dash__card is-set lvl-' + l.level;
    $('[data-light-icon]').innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + l.svg + '</svg>';
    $('[data-light-level]').textContent = l.level === 3 ? 'VERMELHA · PARE COM SEGURANÇA' : 'AMARELA · AGENDE A VERIFICAÇÃO';
    $('[data-light-name]').textContent = l.name;
    $('[data-light-text]').innerHTML = l.text + ' <b>' + l.todo + '</b>';
    var a = $('[data-light-send]');
    a.hidden = false;
    a.href = WA + encodeURIComponent('Olá, CARS! A luz de "' + l.name.toLowerCase() + '" acendeu no painel do meu carro. O que devo fazer?');
    if (M && !reduce) {
      M.animate(card, { opacity: [0.4, 1], y: [10, 0] }, { duration: 0.3 });
      M.animate($('[data-light-icon]'), { scale: [0.6, 1], rotate: [-12, 0] }, { type: 'spring', stiffness: 420, damping: 16 });
    }
  }

  /* ---------------------------------------------------------------- réguas de desgaste */
  if (hasGsap && window.ScrollTrigger && !reduce) {
    $$('.gauge').forEach(function (g, i) {
      var fill = $('.gauge__fill', g);
      var min = parseFloat(getComputedStyle(g).getPropertyValue('--min')) || 0;
      var stop = Math.max(min - 2, 6);
      var tl2 = gsap.timeline({ scrollTrigger: { trigger: g, start: 'top 85%', once: true } });
      tl2.fromTo(fill, { width: '100%' }, { width: stop + '%', duration: 1.8, ease: 'power2.inOut', delay: i * 0.12 })
         .to(g, { '--heat': 1, duration: 0.5 }, '-=0.6');
      var num = $('[data-count]', g);
      if (num) {
        var to = +num.dataset.count, o = { v: 0 };
        tl2.to(o, { v: to, duration: 1.2, ease: 'power1.out', onUpdate: function () { num.textContent = Math.round(o.v); } }, 0);
      }
    });
  } else {
    $$('.gauge').forEach(function (g) { g.style.setProperty('--heat', 1); $('.gauge__fill', g).style.width = Math.max((parseFloat(getComputedStyle(g).getPropertyValue('--min')) || 0) - 2, 6) + '%'; });
  }

  /* ---------------------------------------------------------------- linha do tempo + selo */
  if (hasGsap && window.ScrollTrigger && !reduce) {
    var tlEl = $('[data-timeline]');
    gsap.fromTo(tlEl, { '--line': 0 }, { '--line': 1, ease: 'none', scrollTrigger: { trigger: tlEl, start: 'top 80%', end: 'bottom 55%', scrub: 0.6 } });
    gsap.from($$('li', tlEl), { x: -16, opacity: 0, stagger: 0.15, duration: 0.6, scrollTrigger: { trigger: tlEl, start: 'top 82%', once: true } });
  }

  /* ---------------------------------------------------------------- nota (number ticker) */
  var tick = $('[data-ticker]');
  if (tick && hasGsap && window.ScrollTrigger && !reduce) {
    var o2 = { v: 0 };
    gsap.to(o2, { v: 4.9, duration: 1.6, ease: 'power2.out', scrollTrigger: { trigger: tick, start: 'top 85%', once: true },
      onUpdate: function () { tick.textContent = o2.v.toFixed(1).replace('.', ','); } });
    gsap.from('.bars i', { scaleX: 0, transformOrigin: 'left', duration: 1.1, ease: 'power3.out', stagger: 0.08, scrollTrigger: { trigger: '.bars', start: 'top 88%', once: true } });
  }

  /* ---------------------------------------------------------------- aberto agora (horário real do Google) */
  var HOURS = { 1: [[420, 720], [780, 1050]], 2: [[420, 720], [780, 1050]], 3: [[420, 720], [780, 1050]], 4: [[420, 720], [780, 1050]], 5: [[420, 720], [780, 1020]], 6: [], 0: [] };
  function spNow() {
    try {
      var parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Sao_Paulo', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
      var get = function (t) { return (parts.find(function (p) { return p.type === t; }) || {}).value; };
      var wd = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(get('weekday'));
      return { d: wd, m: (+get('hour') % 24) * 60 + (+get('minute')) };
    } catch (e) { var n = new Date(); return { d: n.getDay(), m: n.getHours() * 60 + n.getMinutes() }; }
  }
  function fmt(m) { var h = Math.floor(m / 60), mi = m % 60; return h + 'h' + (mi ? String(mi).padStart(2, '0') : ''); }
  function nextOpen(now) {
    for (var k = 0; k < 8; k++) {
      var d = (now.d + k) % 7;
      var spans = HOURS[d];
      for (var j = 0; j < spans.length; j++) {
        if (k > 0 || spans[j][0] > now.m) {
          var names = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
          return (k === 0 ? 'hoje' : k === 1 ? 'amanhã' : names[d]) + ' às ' + fmt(spans[j][0]);
        }
      }
    }
    return '';
  }
  function status() {
    var now = spNow();
    var el = $('[data-status]');
    var txt = $('[data-status-text]');
    var spans = HOURS[now.d] || [];
    var open = spans.find(function (s) { return now.m >= s[0] && now.m < s[1]; });
    el.classList.toggle('is-open', !!open);
    txt.textContent = open ? 'Aberto agora · até ' + fmt(open[1]) : 'Fechado agora · abre ' + nextOpen(now);
    $$('.hours tr').forEach(function (tr) { tr.classList.toggle('is-today', +tr.dataset.day === now.d); });
  }
  status();
  setInterval(status, 60000);
})();
