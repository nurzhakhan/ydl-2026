/*
 * game.js — оркестровка игры Orbit Hopper.
 *
 * Тут живёт всё "грязное": Canvas, цикл анимации, ввод, экраны.
 * Вся чистая математика вынесена в physics.js (window.Physics) — так её
 * можно тестировать отдельно (см. physics.test.js).
 */
(function () {
  "use strict";

  const P = window.Physics;

  // === Ассеты (CC0, см. assets/CREDITS.md) =================================
  // Картинки грузим асинхронно. Игра стартует, даже если что-то не догрузилось:
  // спрайт может быть null -> рисуем процедурный фолбэк (кружок/частицу).
  // Так одна оборванная загрузка не ломает всю игру.
  const PLANET_COUNT = 12;
  const Assets = {
    planets: [], // массив Image (или null)
    meteors: [],
    bg: null,
    ready: false,
  };

  function loadImage(src) {
    const img = new Image();
    img.src = src;
    // onerror оставляем тихим: img.complete останется false -> фолбэк.
    return img;
  }

  function loadAssets() {
    Assets.bg = loadImage("assets/img/bg.png");
    for (let i = 1; i <= PLANET_COUNT; i++) {
      Assets.planets.push(loadImage(`assets/planets/planet${i}.png`));
    }
    for (let i = 1; i <= 4; i++) {
      Assets.meteors.push(loadImage(`assets/img/meteor${i}.png`));
    }
  }
  loadAssets();

  // Помощник: картинка реально готова к отрисовке?
  function imgReady(img) {
    return img && img.complete && img.naturalWidth > 0;
  }

  // === Звук ================================================================
  // Простой пул: на каждый эффект держим несколько клонов <audio>, чтобы
  // звуки могли накладываться (например, две звезды подряд). Без WebAudio —
  // так проще и достаточно для коротких сэмплов.
  const Sound = {
    enabled: true,
    pools: {},
    load(name, src, copies, volume) {
      const pool = [];
      for (let i = 0; i < copies; i++) {
        const a = new Audio(src);
        a.volume = volume;
        a.preload = "auto";
        pool.push(a);
      }
      this.pools[name] = { list: pool, idx: 0 };
    },
    play(name) {
      if (!this.enabled) return;
      const pool = this.pools[name];
      if (!pool) return;
      const a = pool.list[pool.idx];
      pool.idx = (pool.idx + 1) % pool.list.length;
      try {
        a.currentTime = 0;
        a.play().catch(() => {}); // браузер может блокировать до первого клика
      } catch (_) {}
    },
  };
  Sound.load("launch", "assets/sound/launch.ogg", 3, 0.5);
  Sound.load("capture", "assets/sound/capture.ogg", 3, 0.45);
  Sound.load("star", "assets/sound/star.wav", 4, 0.4);
  Sound.load("gameover", "assets/sound/gameover.ogg", 1, 0.6);

  // === Фоновая музыка ======================================================
  // Один зацикленный трек (CC0 "Heavenly Loop"). Браузеры блокируют автозвук
  // до первого жеста пользователя, поэтому реально стартуем по первому
  // клику/тапу/нажатию (см. Music.unlock в инициализации).
  // Настройки храним в памяти (по условию — без localStorage; при деплое
  // можно сохранять Music.enabled/volume в localStorage).
  const Music = {
    el: new Audio("assets/sound/music.ogg"),
    enabled: true,
    volume: 0.4,
    init() {
      this.el.loop = true;
      this.el.volume = this.volume;
    },
    // Запустить, если включена и ещё не играет.
    play() {
      if (!this.enabled) return;
      this.el.play().catch(() => {}); // тихо игнорируем блокировку автозвука
    },
    setEnabled(on) {
      this.enabled = on;
      if (on) this.play();
      else this.el.pause();
    },
    setVolume(v) {
      this.volume = v;
      this.el.volume = v;
    },
  };
  Music.init();

  // === Частицы =============================================================
  // Лёгкий пул частиц для вспышек при захвате/подборе/гибели.
  let particles = [];
  function spawnBurst(x, y, color, count, speed) {
    for (let i = 0; i < count; i++) {
      const ang = (Math.PI * 2 * i) / count + Math.random() * 0.5;
      const sp = speed * (0.5 + Math.random());
      particles.push({
        x,
        y,
        vx: Math.cos(ang) * sp,
        vy: Math.sin(ang) * sp,
        life: 1, // 1 -> 0
        decay: 1.4 + Math.random() * 1.2,
        size: 2 + Math.random() * 3,
        color,
      });
    }
  }
  function updateParticles(dt) {
    for (const p of particles) {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vx *= 0.92; // трение -> разлёт затухает
      p.vy *= 0.92;
      p.life -= p.decay * dt;
    }
    particles = particles.filter((p) => p.life > 0);
  }

  // === Состояние сессии =====================================================
  // ВАЖНО про сохранение: по условию задачи рекорд и валюта живут только в
  // памяти на время сессии (без localStorage). Чтобы сохранять их между
  // запусками при реальном деплое, замени чтение/запись session.* на
  //   localStorage.getItem("orbitHopper.best") / setItem(...)
  // здесь и в endGame(). Песочница может блокировать localStorage, поэтому
  // по умолчанию держим в обычных JS-переменных.
  const session = {
    best: 0,
    currency: 0, // суммарно собранные звёзды за сессию
  };

  // === Канвас ===============================================================
  const canvas = document.getElementById("canvas");
  const ctx = canvas.getContext("2d");
  let W = 0;
  let H = 0;

  function resize() {
    // Поддержка Retina: рисуем в физических пикселях, масштабируем контекст.
    const dpr = window.devicePixelRatio || 1;
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // === Конфигурация ========================================================
  const CFG = {
    baseLaunchSpeed: 360, // px/с, скорость отрыва (растёт с difficulty)
    baseOrbitSpeed: 9.5, // множитель угловой скорости (см. orbitSpeedForRadius)
    maxFlightDistance: 720, // пролетел столько без захвата -> улетел в пустоту
    astronautRadius: 9,
    seedStart: 12345, // фиксированный seed -> воспроизводимый старт, дальше живёт
  };

  // === Игровое состояние раунда ============================================
  const STATE = {
    START: "start",
    PLAYING: "playing",
    PAUSED: "paused",
    GAMEOVER: "gameover",
  };
  let state = STATE.START;

  let planets = [];
  let stars = [];
  let asteroids = [];
  let blackHoles = [];
  let astronaut = null;
  let camera = { x: 0, y: 0 };
  let rng = null;
  let elapsed = 0; // секунд с начала раунда -> сложность/скорость
  let score = 0;
  let jumps = 0;
  let starsCollected = 0;
  let lastPlanetIndex = 0; // для возрастающего id планет
  const START_LIVES = 3;
  let lives = START_LIVES; // попытки: тратятся при гибели, 0 -> настоящий Game Over
  let invuln = 0; // секунды неуязвимости после возрождения (анти-мгновенная смерть)

  // === DOM-ссылки ==========================================================
  const el = {
    hud: document.getElementById("hud"),
    score: document.getElementById("score"),
    best: document.getElementById("best"),
    currency: document.getElementById("currency"),
    startScreen: document.getElementById("start-screen"),
    gameoverScreen: document.getElementById("gameover-screen"),
    finalScore: document.getElementById("final-score"),
    finalJumps: document.getElementById("final-jumps"),
    finalStars: document.getElementById("final-stars"),
    finalBest: document.getElementById("final-best"),
    lives: document.getElementById("lives"),
    pauseBtn: document.getElementById("pause-btn"),
    pauseScreen: document.getElementById("pause-screen"),
    scoreBig: document.getElementById("score-big"),
  };

  // === Локализация (i18n) ==================================================
  // Словарь переводов: ключ -> текст на каждом языке. Строки с разметкой
  // (тэги <br>, <kbd>) помечаются в HTML атрибутом data-i18n-html и ставятся
  // через innerHTML; обычный текст — через data-i18n и textContent (безопаснее).
  const I18N = {
    kk: {
      score: "Ұпай",
      best: "Рекорд",
      jumps: "Секірулер",
      collected: "Жиналған",
      gameOver: "Ұшу аяқталды",
      play: "► Ойнау",
      retry: "↻ Қайтадан",
      tagline:
        "Орбитадан ажырау үшін экранды басыңыз.<br />Келесі планетаның тартылысын ұстап қал.",
      controlsHint: "Басқару: шерту / тап / <kbd>Бос орын</kbd>",
      retryHint: "немесе <kbd>Бос орын</kbd> басыңыз",
      paused: "Кідіріс",
      resume: "► Жалғастыру",
      pauseHint: "немесе <kbd>P</kbd> басыңыз",
    },
    ru: {
      score: "Очки",
      best: "Рекорд",
      jumps: "Прыжков",
      collected: "Собрано",
      gameOver: "Полёт окончен",
      play: "► Играть",
      retry: "↻ Ещё раз",
      tagline:
        "Тапни, чтобы оторваться от орбиты.<br />Поймай гравитацию следующей планеты.",
      controlsHint: "Управление: клик / тап / <kbd>Пробел</kbd>",
      retryHint: "или нажми <kbd>Пробел</kbd>",
      paused: "Пауза",
      resume: "► Продолжить",
      pauseHint: "или нажми <kbd>P</kbd>",
    },
    en: {
      score: "Score",
      best: "Best",
      jumps: "Jumps",
      collected: "Collected",
      gameOver: "Flight over",
      play: "► Play",
      retry: "↻ Retry",
      tagline:
        "Tap to break away from orbit.<br />Catch the gravity of the next planet.",
      controlsHint: "Controls: click / tap / <kbd>Space</kbd>",
      retryHint: "or press <kbd>Space</kbd>",
      paused: "Paused",
      resume: "► Resume",
      pauseHint: "or press <kbd>P</kbd>",
    },
  };

  // По умолчанию казахский. Храним в переменной (по условию — без localStorage;
  // при деплое можно сохранять выбор в localStorage.getItem("orbitHopper.lang")).
  let currentLang = "kk";

  function setLang(lang) {
    if (!I18N[lang]) return;
    currentLang = lang;
    const dict = I18N[lang];

    // Простой текст.
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      const key = node.getAttribute("data-i18n");
      if (dict[key] != null) node.textContent = dict[key];
    });
    // Текст с разметкой.
    document.querySelectorAll("[data-i18n-html]").forEach((node) => {
      const key = node.getAttribute("data-i18n-html");
      if (dict[key] != null) node.innerHTML = dict[key];
    });

    // Подсветка активной кнопки + язык страницы для скринридеров.
    document.querySelectorAll("#lang-switch button").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-lang") === lang);
    });
    document.documentElement.lang = lang;
  }

  // === Сложность ===========================================================
  // Чем дольше летим, тем выше множитель -> быстрее отрыв и вращение,
  // тайминг становится жёстче. Ограничен сверху, чтобы не стало нереально.
  function difficulty() {
    return P.clamp(elapsed * 0.03, 0, 1.4);
  }
  function speedMul() {
    return 1 + difficulty() * 0.6;
  }

  // === Текущая позиция центра планеты (с учётом покачивания) ===============
  function planetCenter(planet) {
    const bob = planet.bobAmp
      ? Math.sin(elapsed * planet.bobSpeed + planet.bobPhase) * planet.bobAmp
      : 0;
    return { x: planet.baseX, y: planet.baseY + bob };
  }

  // === Процедурная генерация ===============================================
  function spawnPlanet(prev) {
    const p = P.generateNextPlanet(prev, rng, difficulty());
    p.id = ++lastPlanetIndex;
    p.spriteIndex = Math.floor(rng() * PLANET_COUNT); // какой PNG рисовать
    planets.push(p);

    // Между планетами иногда сыплем звёзды, астероиды, чёрные дыры.
    populateGap(prev, p);
    return p;
  }

  function populateGap(a, b) {
    const midX = (a.baseX + b.baseX) / 2;
    const midY = (a.baseY + b.baseY) / 2;

    // Звёзды (коллектиблы) — 0..3 шт. вдоль отрезка между планетами.
    const starCount = Math.floor(P.randRange(rng, 0, 3.99));
    for (let i = 0; i < starCount; i++) {
      const t = P.randRange(rng, 0.25, 0.75);
      stars.push({
        x: P.lerp(a.baseX, b.baseX, t) + P.randRange(rng, -40, 40),
        y: P.lerp(a.baseY, b.baseY, t) + P.randRange(rng, -60, 60),
        r: 8,
        taken: false,
      });
    }

    // Астероид — с шансом ~35%, в стороне от прямой линии центров.
    if (rng() < 0.35) {
      asteroids.push({
        x: midX + P.randRange(rng, -70, 70),
        y: midY + P.randRange(rng, -90, 90),
        r: P.randRange(rng, 10, 20),
        // Часть астероидов дрейфует по вертикали.
        driftAmp: rng() < 0.5 ? P.randRange(rng, 20, 50) : 0,
        driftSpeed: P.randRange(rng, 0.5, 1.4),
        driftPhase: P.randRange(rng, 0, Math.PI * 2),
        baseY: midY,
        spriteIndex: Math.floor(rng() * 4),
        spin: P.randRange(rng, -1.5, 1.5), // угловая скорость вращения спрайта
      });
    }

    // Чёрная дыра — реже (~15%) и дальше от центров (иначе непроходимо).
    if (rng() < 0.15) {
      blackHoles.push({
        x: midX + P.randRange(rng, -50, 50),
        y: midY + P.randRange(rng, 70, 130) * (rng() < 0.5 ? 1 : -1),
        deathR: 16,
        pullR: 150,
      });
    }
  }

  function asteroidPos(ast) {
    const dy = ast.driftAmp
      ? Math.sin(elapsed * ast.driftSpeed + ast.driftPhase) * ast.driftAmp
      : 0;
    return { x: ast.x, y: ast.baseY + dy };
  }

  // Догенерировать планеты, пока есть запас впереди по горизонтали;
  // удалить всё, что давно ушло за левый край камеры.
  function manageWorld() {
    let last = planets[planets.length - 1];
    while (last.baseX < camera.x + W + 500) {
      last = spawnPlanet(last);
    }
    const cutoff = camera.x - 400;
    planets = planets.filter((p) => p.baseX > cutoff || p === astronaut.planet);
    stars = stars.filter((s) => s.x > cutoff);
    asteroids = asteroids.filter((a) => a.x > cutoff);
    blackHoles = blackHoles.filter((b) => b.x > cutoff);
  }

  // === Инициализация раунда ================================================
  function resetRound() {
    // Каждый раунд берём свежий, но детерминированный seed от стартового +
    // прошедших раундов, чтобы старты были разнообразны, но воспроизводимы.
    rng = P.makeRng(CFG.seedStart + jumps + score + 1);
    planets = [];
    stars = [];
    asteroids = [];
    blackHoles = [];
    particles = [];
    elapsed = 0;
    score = 0;
    jumps = 0;
    starsCollected = 0;
    lastPlanetIndex = 0;
    lives = START_LIVES;
    invuln = 0;

    // Первая планета — крупная и неподвижная, чтобы было где начать.
    const first = {
      id: ++lastPlanetIndex,
      baseX: 0,
      baseY: 0,
      radius: 60,
      captureRadius: 130,
      orbitDir: 1,
      bobAmp: 0,
      bobSpeed: 0,
      bobPhase: 0,
      spriteIndex: 0,
    };
    planets.push(first);

    astronaut = {
      orbiting: true,
      planet: first,
      angle: 0,
      orbitRadius: first.radius + 28,
      direction: first.orbitDir,
      x: 0,
      y: 0,
      flightDist: 0,
      // Планета, которую только что покинули: игнорируем её для захвата,
      // пока космонавт не выйдет за её радиус захвата (иначе мгновенный реловк).
      ignorePlanet: null,
    };

    camera.x = first.baseX - W / 2;
    camera.y = first.baseY - H / 2;

    // Заполним мир вперёд.
    manageWorld();
  }

  // === Ввод (легко заменяемая абстракция) ==================================
  // Один источник правды о "действии". Чтобы позже сделать слингшот
  // (зажатие + прицел), достаточно расширить этот объект событиями
  // pointerdown/pointermove/pointerup и не трогать игровую логику.
  const Input = {
    onAction: null,
    attach() {
      const fire = (e) => {
        // Не реагируем на клики по кнопкам оверлеев — у них свои обработчики.
        if (e.target && e.target.classList.contains("btn")) return;
        if (this.onAction) this.onAction();
      };
      canvas.addEventListener("pointerdown", fire);
      window.addEventListener("keydown", (e) => {
        if (e.code === "Space") {
          e.preventDefault();
          if (this.onAction) this.onAction();
        }
      });
    },
  };

  // Единая точка действия: смысл зависит от текущего экрана.
  function handleAction() {
    if (state === STATE.START) {
      startGame();
    } else if (state === STATE.PLAYING) {
      launch();
    } else if (state === STATE.PAUSED) {
      resumeGame();
    } else if (state === STATE.GAMEOVER) {
      startGame();
    }
  }

  // Отрыв от орбиты по касательной.
  function launch() {
    if (!astronaut.orbiting) return;
    const v = P.tangentVelocity(
      astronaut.angle,
      astronaut.direction,
      CFG.baseLaunchSpeed * speedMul()
    );
    astronaut.orbiting = false;
    astronaut.vx = v.vx;
    astronaut.vy = v.vy;
    astronaut.flightDist = 0;
    astronaut.ignorePlanet = astronaut.planet; // не ловиться сразу обратно
    Sound.play("launch");
  }

  // === Обновление физики ===================================================
  function update(dt) {
    elapsed += dt;
    if (invuln > 0) invuln -= dt;

    if (astronaut.orbiting) {
      updateOrbiting(dt);
    } else {
      updateFlying(dt);
    }

    updateCamera(dt);
    manageWorld();
    checkCollectibles();
  }

  function updateOrbiting(dt) {
    const planet = astronaut.planet;
    const angSpeed =
      P.orbitSpeedForRadius(planet.radius, CFG.baseOrbitSpeed) * speedMul();
    astronaut.angle += angSpeed * astronaut.direction * dt;
    const c = planetCenter(planet);
    const pos = P.orbitPosition(c.x, c.y, astronaut.angle, astronaut.orbitRadius);
    astronaut.x = pos.x;
    astronaut.y = pos.y;

    // Даже на орбите можно влететь в астероид (риск у движущихся планет).
    if (invuln <= 0 && hitAnyAsteroid()) loseLife();
  }

  function updateFlying(dt) {
    // Гравитация чёрных дыр.
    for (const bh of blackHoles) {
      const pull = P.blackHolePull(bh.x, bh.y, astronaut.x, astronaut.y, 90000);
      astronaut.vx += pull.ax * dt;
      astronaut.vy += pull.ay * dt;
    }

    const stepX = astronaut.vx * dt;
    const stepY = astronaut.vy * dt;
    astronaut.x += stepX;
    astronaut.y += stepY;
    astronaut.flightDist += Math.hypot(stepX, stepY);

    // Снимаем игнор с покинутой планеты, как только вышли из её зоны захвата.
    if (astronaut.ignorePlanet) {
      const c = planetCenter(astronaut.ignorePlanet);
      if (
        P.dist(astronaut.x, astronaut.y, c.x, c.y) >
        astronaut.ignorePlanet.captureRadius
      ) {
        astronaut.ignorePlanet = null;
      }
    }

    // Попытка захвата орбитой ближайшей подходящей планеты.
    for (const planet of planets) {
      if (planet === astronaut.ignorePlanet) continue;
      const c = planetCenter(planet);
      const d = P.dist(astronaut.x, astronaut.y, c.x, c.y);
      // Врезались в саму планету -> смерть. Иначе попали в зону -> захват.
      if (d < planet.radius - 2) {
        return loseLife();
      }
      if (P.shouldCapture(d, planet.captureRadius)) {
        capture(planet, c);
        return;
      }
    }

    // Смерти в полёте: чёрная дыра, астероид (неуязвимость их прощает),
    // и улёт в пустоту (от него неуязвимость НЕ спасает — это не "случайность").
    if (invuln <= 0) {
      for (const bh of blackHoles) {
        if (P.dist(astronaut.x, astronaut.y, bh.x, bh.y) < bh.deathR) {
          return loseLife();
        }
      }
      if (hitAnyAsteroid()) return loseLife();
    }
    if (astronaut.flightDist > CFG.maxFlightDistance) return loseLife();
  }

  function capture(planet, center) {
    const cap = P.computeCapture(
      center.x,
      center.y,
      astronaut.x,
      astronaut.y,
      astronaut.vx,
      astronaut.vy,
      planet.radius,
      planet.captureRadius
    );
    astronaut.orbiting = true;
    astronaut.planet = planet;
    astronaut.angle = cap.angle;
    astronaut.orbitRadius = cap.orbitRadius;
    astronaut.direction = cap.direction;

    // Успешный прыжок: очки за прыжок + бонус за скорость игры.
    jumps += 1;
    score += 100;
    updateHud();

    // Вспышка частиц в точке захвата + звук силового поля.
    spawnBurst(astronaut.x, astronaut.y, "127,216,255", 22, 220);
    Sound.play("capture");
  }

  function hitAnyAsteroid() {
    for (const ast of asteroids) {
      const pos = asteroidPos(ast);
      if (
        P.dist(astronaut.x, astronaut.y, pos.x, pos.y) <
        ast.r + CFG.astronautRadius
      ) {
        return true;
      }
    }
    return false;
  }

  function checkCollectibles() {
    for (const s of stars) {
      if (s.taken) continue;
      if (P.dist(astronaut.x, astronaut.y, s.x, s.y) < s.r + CFG.astronautRadius + 4) {
        s.taken = true;
        starsCollected += 1;
        score += 25;
        updateHud();
        spawnBurst(s.x, s.y, "255,215,106", 12, 140);
        Sound.play("star");
      }
    }
  }

  function updateCamera(dt) {
    // Плавное следование: лерп к цели. factor зависит от dt, чтобы поведение
    // не плыло при разном FPS. 1 - exp(-k*dt) — кадронезависимое сглаживание.
    const k = 4;
    const factor = 1 - Math.exp(-k * dt);
    camera.x = P.lerp(camera.x, astronaut.x - W / 2, factor);
    camera.y = P.lerp(camera.y, astronaut.y - H / 2, factor);
  }

  // === Рендеринг ===========================================================
  // Параллакс-звёзды фона: фиксированы в "слоях", сдвигаются медленнее камеры.
  const bgStars = [];
  for (let i = 0; i < 140; i++) {
    bgStars.push({
      x: Math.random() * 2000,
      y: Math.random() * 2000,
      r: Math.random() * 1.6 + 0.3,
      layer: Math.random() * 0.5 + 0.1, // 0.1..0.6 — коэффициент параллакса
    });
  }

  function drawBackground() {
    // Слой 1: тайлим звёздную картинку с лёгким параллаксом.
    if (imgReady(Assets.bg)) {
      const tile = Assets.bg.naturalWidth; // 256
      const par = 0.3; // фон движется медленнее камеры
      const ox = mod(-camera.x * par, tile);
      const oy = mod(-camera.y * par, tile);
      for (let x = -tile + ox; x < W; x += tile) {
        for (let y = -tile + oy; y < H; y += tile) {
          ctx.drawImage(Assets.bg, x, y);
        }
      }
    }
    // Слой 2: процедурные звёзды (второй параллакс-слой поверх).
    ctx.save();
    for (const s of bgStars) {
      // Звёзды тайлятся по модулю, сдвиг зависит от слоя (параллакс).
      const px = mod(s.x - camera.x * s.layer, W);
      const py = mod(s.y - camera.y * s.layer, H);
      ctx.globalAlpha = s.layer + 0.3;
      ctx.fillStyle = "#cfe3ff";
      ctx.beginPath();
      ctx.arc(px, py, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function mod(n, m) {
    return ((n % m) + m) % m;
  }

  function worldToScreen(x, y) {
    return { x: x - camera.x, y: y - camera.y };
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    drawBackground();

    // Чёрные дыры (под планетами).
    for (const bh of blackHoles) {
      const s = worldToScreen(bh.x, bh.y);
      const grad = ctx.createRadialGradient(s.x, s.y, 2, s.x, s.y, bh.pullR);
      grad.addColorStop(0, "rgba(120,40,200,0.9)");
      grad.addColorStop(0.25, "rgba(40,10,80,0.5)");
      grad.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(s.x, s.y, bh.pullR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#000";
      ctx.beginPath();
      ctx.arc(s.x, s.y, bh.deathR, 0, Math.PI * 2);
      ctx.fill();
    }

    // Планеты + кольца зоны захвата.
    for (const planet of planets) {
      const c = planetCenter(planet);
      const s = worldToScreen(c.x, c.y);

      ctx.strokeStyle = "rgba(127,216,255,0.18)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.arc(s.x, s.y, planet.captureRadius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      const sprite = Assets.planets[planet.spriteIndex];
      if (imgReady(sprite)) {
        // Рисуем спрайт в квадрат 2*radius (диаметр). Лёгкое вращение планеты.
        const d = planet.radius * 2;
        ctx.save();
        ctx.translate(s.x, s.y);
        ctx.rotate(elapsed * 0.05 * planet.orbitDir);
        ctx.drawImage(sprite, -planet.radius, -planet.radius, d, d);
        ctx.restore();
      } else {
        // Фолбэк, пока картинка не загрузилась: процедурный градиентный шар.
        const grad = ctx.createRadialGradient(
          s.x - planet.radius * 0.3,
          s.y - planet.radius * 0.3,
          planet.radius * 0.2,
          s.x,
          s.y,
          planet.radius
        );
        const hue = (planet.id * 47) % 360;
        grad.addColorStop(0, `hsl(${hue},70%,70%)`);
        grad.addColorStop(1, `hsl(${hue},65%,38%)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(s.x, s.y, planet.radius, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Астероиды (спрайт метеора с вращением; фолбэк — серый круг).
    for (const ast of asteroids) {
      const pos = asteroidPos(ast);
      const s = worldToScreen(pos.x, pos.y);
      const meteor = Assets.meteors[ast.spriteIndex];
      if (imgReady(meteor)) {
        const d = ast.r * 2.4; // спрайт чуть больше радиуса коллизии
        ctx.save();
        ctx.translate(s.x, s.y);
        ctx.rotate(elapsed * ast.spin);
        ctx.drawImage(meteor, -d / 2, -d / 2, d, d);
        ctx.restore();
      } else {
        ctx.fillStyle = "#9b8b7a";
        ctx.beginPath();
        ctx.arc(s.x, s.y, ast.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Звёзды-коллектиблы.
    for (const star of stars) {
      if (star.taken) continue;
      const s = worldToScreen(star.x, star.y);
      drawStar(s.x, s.y, star.r);
    }

    // Космонавт + "поводок" к планете на орбите.
    const a = worldToScreen(astronaut.x, astronaut.y);
    if (astronaut.orbiting) {
      const c = worldToScreen(planetCenter(astronaut.planet).x, planetCenter(astronaut.planet).y);
      ctx.strokeStyle = "rgba(255,255,255,0.25)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(c.x, c.y);
      ctx.lineTo(a.x, a.y);
      ctx.stroke();
    }
    // Во время неуязвимости космонавт мигает (визуальный сигнал «бессмертен»).
    const blink = invuln > 0 && Math.floor(elapsed * 12) % 2 === 0;
    if (!blink) {
      ctx.fillStyle = "#fff";
      ctx.shadowColor = "#7fd8ff";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(a.x, a.y, CFG.astronautRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Частицы поверх всего. life управляет и прозрачностью, и размером.
    for (const p of particles) {
      const sp = worldToScreen(p.x, p.y);
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = `rgb(${p.color})`;
      ctx.beginPath();
      ctx.arc(sp.x, sp.y, p.size * p.life, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawStar(cx, cy, r) {
    ctx.save();
    ctx.fillStyle = "#ffd76a";
    ctx.shadowColor = "#ffd76a";
    ctx.shadowBlur = 12;
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const ang = (Math.PI / 5) * i - Math.PI / 2;
      const rad = i % 2 === 0 ? r : r * 0.45;
      const px = cx + Math.cos(ang) * rad;
      const py = cy + Math.sin(ang) * rad;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // === HUD / экраны ========================================================
  function updateHud() {
    el.score.textContent = score;
    el.best.textContent = session.best;
    // Живой кошелёк: накоплено за сессию + собрано в текущем раунде.
    // (В endGame() starsCollected фиксируется в session.currency, а в новом
    //  раунде обнуляется — поэтому двойного счёта нет.)
    el.currency.textContent = session.currency + starsCollected;
    // Полные сердца = оставшиеся попытки, пустые = потраченные.
    el.lives.textContent =
      "♥".repeat(Math.max(0, lives)) +
      "♡".repeat(Math.max(0, START_LIVES - lives));
  }

  function startGame() {
    resetRound();
    state = STATE.PLAYING;
    el.startScreen.classList.add("hidden");
    el.gameoverScreen.classList.add("hidden");
    el.pauseScreen.classList.add("hidden");
    el.hud.classList.remove("hidden");
    el.scoreBig.classList.remove("hidden");
    el.pauseBtn.classList.remove("hidden");
    el.pauseBtn.textContent = "❚❚";
    updateHud();
  }

  // === Пауза ===============================================================
  // Останавливаем обновление физики (см. главный цикл), показываем оверлей и
  // ставим музыку на паузу — НЕ трогая пользовательский переключатель музыки
  // (Music.enabled), чтобы при продолжении вернуть как было.
  function pauseGame() {
    if (state !== STATE.PLAYING) return;
    state = STATE.PAUSED;
    el.pauseScreen.classList.remove("hidden");
    el.pauseBtn.textContent = "►";
    Music.el.pause();
  }
  function resumeGame() {
    if (state !== STATE.PAUSED) return;
    state = STATE.PLAYING;
    el.pauseScreen.classList.add("hidden");
    el.pauseBtn.textContent = "❚❚";
    Music.play(); // вернётся только если музыка включена пользователем
  }
  function togglePause() {
    if (state === STATE.PLAYING) pauseGame();
    else if (state === STATE.PAUSED) resumeGame();
  }

  // Гибель: тратим попытку. Если попытки остались — возрождаемся и играем
  // дальше; если нет — настоящий Game Over. Все смертельные события в физике
  // зовут именно loseLife(), а не endGame() напрямую.
  function loseLife() {
    if (state !== STATE.PLAYING) return;
    spawnBurst(astronaut.x, astronaut.y, "255,141,163", 30, 300);
    Sound.play("gameover");
    lives -= 1;
    updateHud();
    if (lives <= 0) {
      endGame();
    } else {
      respawn();
    }
  }

  // Возврат на орбиту последней планеты (она не удаляется из мира, пока мы
  // её "хозяин"). Даём короткую неуязвимость, чтобы не умереть мгновенно
  // снова, если рядом астероид/чёрная дыра.
  function respawn() {
    const planet = astronaut.planet;
    astronaut.orbiting = true;
    astronaut.direction = planet.orbitDir;
    astronaut.orbitRadius = planet.radius + 28;
    astronaut.ignorePlanet = null;
    astronaut.flightDist = 0;
    invuln = 1.6;
  }

  function endGame() {
    if (state !== STATE.PLAYING) return;
    state = STATE.GAMEOVER;

    // Тут при реальном деплое стоит писать в localStorage (см. комментарий
    // к session выше).
    session.currency += starsCollected;
    if (score > session.best) session.best = score;

    el.finalScore.textContent = score;
    el.finalJumps.textContent = jumps;
    el.finalStars.textContent = starsCollected;
    el.finalBest.textContent = session.best;
    el.hud.classList.add("hidden");
    el.scoreBig.classList.add("hidden");
    el.pauseBtn.classList.add("hidden");
    el.gameoverScreen.classList.remove("hidden");
  }

  // === Главный цикл ========================================================
  let lastTime = 0;
  function loop(now) {
    const dt = lastTime ? Math.min((now - lastTime) / 1000, 0.05) : 0;
    lastTime = now;

    if (state === STATE.PLAYING) {
      update(dt);
    }
    // Частицы живут независимо от состояния (вспышка догорает на Game Over),
    // но на паузе замирают вместе со всей сценой.
    if (state !== STATE.PAUSED) updateParticles(dt);
    // Рисуем всегда (на старте/гейм-овере виден замерший мир под оверлеем).
    if (astronaut) draw();

    requestAnimationFrame(loop);
  }

  // === Старт ===============================================================
  document.getElementById("play-btn").addEventListener("click", startGame);
  document.getElementById("retry-btn").addEventListener("click", startGame);

  // --- Пауза: кнопка, кнопка "Продолжить", клик по оверлею, клавиша P ---
  el.pauseBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePause();
  });
  document.getElementById("resume-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    resumeGame();
  });
  // Тап по любому месту оверлея паузы продолжает игру.
  el.pauseScreen.addEventListener("pointerdown", resumeGame);
  window.addEventListener("keydown", (e) => {
    if (e.code === "KeyP") {
      e.preventDefault();
      togglePause();
    }
  });

  // Кнопки переключения языка. stopPropagation, чтобы клик по кнопке не
  // считался "действием" игры (отрывом/стартом) через общий обработчик ввода.
  document.querySelectorAll("#lang-switch button").forEach((b) => {
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      setLang(b.getAttribute("data-lang"));
    });
  });
  setLang(currentLang); // применяем язык по умолчанию

  // --- Управление музыкой ---
  const musicBtn = document.getElementById("music-toggle");
  const volumeSlider = document.getElementById("volume");

  musicBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    Music.setEnabled(!Music.enabled);
    musicBtn.textContent = Music.enabled ? "🔊" : "🔇";
    musicBtn.classList.toggle("off", !Music.enabled);
  });
  volumeSlider.addEventListener("input", (e) => {
    e.stopPropagation();
    Music.setVolume(Number(volumeSlider.value) / 100);
    // Двинули громкость в плюс при выключенной музыке -> считаем как «включить».
    if (Music.volume > 0 && !Music.enabled) musicBtn.click();
  });

  // Разблокировка звука: первый жест пользователя запускает музыку (политика
  // автозвука в браузерах). Слушатель одноразовый — { once: true }.
  function unlockAudio() {
    Music.play();
  }
  window.addEventListener("pointerdown", unlockAudio, { once: true });
  window.addEventListener("keydown", unlockAudio, { once: true });

  Input.onAction = handleAction;
  Input.attach();

  // Создаём начальный мир, чтобы было что показать под стартовым оверлеем.
  resetRound();
  requestAnimationFrame(loop);
})();
