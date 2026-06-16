/*
 * physics.js — ЧИСТАЯ игровая логика Orbit Hopper.
 *
 * Здесь нет ни Canvas, ни DOM, ни requestAnimationFrame — только математика.
 * Зачем так? Чистые функции (вход -> выход, без побочных эффектов) легко
 * тестировать в Node без браузера. Весь файл работает в двух средах:
 *   - в браузере: подключается тегом <script>, функции кладутся в window.Physics;
 *   - в Node:     подключается через require(), функции уходят в module.exports.
 *
 * Это самодельный "UMD"-паттерн (см. экспорт в самом низу файла).
 */
(function (root, factory) {
  const api = factory();
  // В браузере window.Physics, в Node — module.exports.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.Physics = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // --- Базовые помощники ---------------------------------------------------

  function dist(ax, ay, bx, by) {
    const dx = ax - bx;
    const dy = ay - by;
    return Math.hypot(dx, dy);
  }

  function clamp(value, min, max) {
    return value < min ? min : value > max ? max : value;
  }

  // Линейная интерполяция: при t=0 вернёт a, при t=1 вернёт b.
  // Используется для плавного следования камеры.
  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  // --- Орбитальная механика ------------------------------------------------

  // Позиция космонавта на орбите. Планета в (cx, cy), космонавт под углом
  // angle на расстоянии orbitRadius от центра.
  function orbitPosition(cx, cy, angle, orbitRadius) {
    return {
      x: cx + Math.cos(angle) * orbitRadius,
      y: cy + Math.sin(angle) * orbitRadius,
    };
  }

  // Меньшие планеты крутят космонавта быстрее (рискованнее по таймингу),
  // большие — медленнее. 1/sqrt(r) даёт мягкую, не слишком резкую зависимость.
  function orbitSpeedForRadius(radius, base) {
    return base / Math.sqrt(radius);
  }

  // Скорость отрыва — по касательной к орбите.
  // Касательная перпендикулярна радиус-вектору: если радиус (cos a, sin a),
  // то касательная (-sin a, cos a). direction (+1/-1) задаёт сторону вращения.
  function tangentVelocity(angle, direction, speed) {
    return {
      vx: -Math.sin(angle) * direction * speed,
      vy: Math.cos(angle) * direction * speed,
    };
  }

  // Попал ли летящий космонавт в зону гравитационного захвата планеты.
  function shouldCapture(distanceToCenter, captureRadius) {
    return distanceToCenter <= captureRadius;
  }

  // При захвате считаем, на какой угол/радиус/направление встать.
  // Направление вращения берём из знака векторного произведения
  // радиус-вектора (от планеты к космонавту) и вектора скорости:
  // положительное -> против часовой (+1), отрицательное -> по часовой (-1).
  function computeCapture(cx, cy, ax, ay, vx, vy, planetRadius, captureRadius) {
    const rx = ax - cx;
    const ry = ay - cy;
    const angle = Math.atan2(ry, rx);
    const distance = Math.hypot(rx, ry);
    // Не даём встать вплотную к поверхности и не дальше зоны захвата.
    const orbitRadius = clamp(distance, planetRadius + 14, captureRadius);
    const cross = rx * vy - ry * vx;
    const direction = cross >= 0 ? 1 : -1;
    return { angle, orbitRadius, direction };
  }

  // --- Гравитация чёрной дыры ----------------------------------------------

  // Ускорение, которое чёрная дыра придаёт летящему космонавту.
  // Падает с квадратом расстояния (закон тяготения), но ограничено сверху,
  // чтобы у самого горизонта не улетало в бесконечность.
  function blackHolePull(bhx, bhy, ax, ay, strength) {
    const dx = bhx - ax;
    const dy = bhy - ay;
    const d2 = dx * dx + dy * dy;
    const d = Math.sqrt(d2) || 1;
    const accel = Math.min(strength / d2, 4000);
    return { ax: (dx / d) * accel, ay: (dy / d) * accel };
  }

  // --- Детерминированный ГПСЧ (для тестируемой генерации) -------------------

  // Обычный Math.random() нельзя протестировать (каждый запуск разный).
  // LCG с явным seed даёт воспроизводимую последовательность -> тесты стабильны.
  function makeRng(seed) {
    let state = seed >>> 0 || 1;
    return function next() {
      // Параметры из Numerical Recipes.
      state = (1664525 * state + 1013904223) >>> 0;
      return state / 4294967296; // -> [0, 1)
    };
  }

  function randRange(rng, min, max) {
    return min + rng() * (max - min);
  }

  // Процедурная генерация следующей планеты относительно предыдущей.
  // Новая планета всегда впереди (смещение по углу около 0 рад = вправо),
  // на достижимой касательным прыжком дистанции. difficulty слегка
  // увеличивает разлёт. Всё детерминировано от rng -> поддаётся тестам.
  function generateNextPlanet(prev, rng, difficulty) {
    const d = randRange(rng, 230, 350) * (1 + difficulty * 0.12);
    const offsetAngle = randRange(rng, -0.6, 0.6); // вверх/вниз от горизонтали
    const radius = randRange(rng, 24, 70);
    return {
      baseX: prev.baseX + Math.cos(offsetAngle) * d,
      baseY: prev.baseY + Math.sin(offsetAngle) * d,
      radius,
      captureRadius: radius + randRange(rng, 55, 90),
      orbitDir: rng() < 0.5 ? 1 : -1,
      // "Покачивание" планеты по вертикали (часть планет "движется").
      bobAmp: rng() < 0.45 ? randRange(rng, 18, 55) : 0,
      bobSpeed: randRange(rng, 0.6, 1.6),
      bobPhase: randRange(rng, 0, Math.PI * 2),
    };
  }

  return {
    dist,
    clamp,
    lerp,
    orbitPosition,
    orbitSpeedForRadius,
    tangentVelocity,
    shouldCapture,
    computeCapture,
    blackHolePull,
    makeRng,
    randRange,
    generateNextPlanet,
  };
});
