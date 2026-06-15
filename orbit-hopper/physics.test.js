/*
 * physics.test.js — юнит-тесты чистой логики Orbit Hopper.
 *
 * Запуск (без установки зависимостей, нужен Node 18+):
 *   node --test orbit-hopper/
 * или конкретно этот файл:
 *   node --test orbit-hopper/physics.test.js
 *
 * Тестируем только physics.js: это чистые функции, их поведение детерминировано
 * и не зависит от Canvas/DOM. game.js не покрываем юнит-тестами осознанно —
 * он завязан на браузерное окружение (его проверяем вручную в браузере).
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("./physics.js");

const EPS = 1e-9;

test("dist: считает евклидово расстояние", () => {
  assert.equal(P.dist(0, 0, 3, 4), 5);
  assert.equal(P.dist(1, 1, 1, 1), 0);
});

test("clamp: зажимает значение в границах", () => {
  assert.equal(P.clamp(5, 0, 10), 5);
  assert.equal(P.clamp(-3, 0, 10), 0);
  assert.equal(P.clamp(99, 0, 10), 10);
});

test("lerp: t=0 -> a, t=1 -> b, t=0.5 -> середина", () => {
  assert.equal(P.lerp(10, 20, 0), 10);
  assert.equal(P.lerp(10, 20, 1), 20);
  assert.equal(P.lerp(10, 20, 0.5), 15);
});

test("orbitPosition: угол 0 кладёт точку справа от центра", () => {
  const pos = P.orbitPosition(100, 50, 0, 30);
  assert.ok(Math.abs(pos.x - 130) < EPS);
  assert.ok(Math.abs(pos.y - 50) < EPS);
});

test("orbitPosition: угол PI/2 кладёт точку снизу (ось Y вниз)", () => {
  const pos = P.orbitPosition(0, 0, Math.PI / 2, 10);
  assert.ok(Math.abs(pos.x - 0) < 1e-6);
  assert.ok(Math.abs(pos.y - 10) < 1e-6);
});

test("orbitSpeedForRadius: меньший радиус -> большая угловая скорость", () => {
  const small = P.orbitSpeedForRadius(25, 9.5);
  const big = P.orbitSpeedForRadius(100, 9.5);
  assert.ok(small > big);
});

test("tangentVelocity: перпендикулярна радиус-вектору", () => {
  const angle = 0.7;
  const v = P.tangentVelocity(angle, 1, 300);
  // Радиус-вектор (cos, sin); скалярное произведение с касательной = 0.
  const dot = Math.cos(angle) * v.vx + Math.sin(angle) * v.vy;
  assert.ok(Math.abs(dot) < 1e-6);
  // Модуль скорости равен заданной величине.
  assert.ok(Math.abs(Math.hypot(v.vx, v.vy) - 300) < 1e-6);
});

test("tangentVelocity: смена direction разворачивает вектор", () => {
  const a = P.tangentVelocity(0.7, 1, 300);
  const b = P.tangentVelocity(0.7, -1, 300);
  assert.ok(Math.abs(a.vx + b.vx) < 1e-6);
  assert.ok(Math.abs(a.vy + b.vy) < 1e-6);
});

test("shouldCapture: внутри радиуса захвата -> true, снаружи -> false", () => {
  assert.equal(P.shouldCapture(90, 100), true);
  assert.equal(P.shouldCapture(100, 100), true);
  assert.equal(P.shouldCapture(101, 100), false);
});

test("computeCapture: радиус орбиты зажат между поверхностью и зоной захвата", () => {
  // Космонавт слишком близко к поверхности -> орбита поднимается до min.
  const near = P.computeCapture(0, 0, 5, 0, 0, 100, 40, 120);
  assert.equal(near.orbitRadius, 40 + 14);
  // Космонавт за зоной захвата -> орбита ограничена captureRadius.
  const far = P.computeCapture(0, 0, 200, 0, 0, 100, 40, 120);
  assert.equal(far.orbitRadius, 120);
});

test("computeCapture: знак скорости задаёт направление вращения", () => {
  // Космонавт справа от планеты (r = +x). Скорость вверх (-y) -> cross<0 -> dir -1.
  const a = P.computeCapture(0, 0, 50, 0, 0, -100, 30, 120);
  assert.equal(a.direction, -1);
  // Скорость вниз (+y) -> cross>0 -> dir +1.
  const b = P.computeCapture(0, 0, 50, 0, 0, 100, 30, 120);
  assert.equal(b.direction, 1);
});

test("blackHolePull: тянет к дыре и слабеет с расстоянием", () => {
  const near = P.blackHolePull(100, 0, 50, 0, 90000); // дыра справа
  assert.ok(near.ax > 0); // тянет вправо (к дыре)
  assert.ok(Math.abs(near.ay) < 1e-9);
  const far = P.blackHolePull(1000, 0, 50, 0, 90000);
  assert.ok(near.ax > far.ax); // ближе -> сильнее
});

test("blackHolePull: ускорение ограничено сверху у горизонта", () => {
  const onTop = P.blackHolePull(0, 0, 0.001, 0, 90000);
  assert.ok(Math.hypot(onTop.ax, onTop.ay) <= 4000 + 1e-6);
});

test("makeRng: детерминирован при одном seed", () => {
  const a = P.makeRng(42);
  const b = P.makeRng(42);
  for (let i = 0; i < 5; i++) assert.equal(a(), b());
});

test("makeRng: значения в [0,1) и разные seed дают разные потоки", () => {
  const r = P.makeRng(7);
  for (let i = 0; i < 100; i++) {
    const v = r();
    assert.ok(v >= 0 && v < 1);
  }
  assert.notEqual(P.makeRng(1)(), P.makeRng(2)());
});

test("randRange: попадает в [min, max)", () => {
  const r = P.makeRng(99);
  for (let i = 0; i < 100; i++) {
    const v = P.randRange(r, 5, 9);
    assert.ok(v >= 5 && v < 9);
  }
});

test("generateNextPlanet: новая планета впереди и с валидными полями", () => {
  const prev = { baseX: 0, baseY: 0 };
  const r = P.makeRng(123);
  const p = P.generateNextPlanet(prev, r, 0);
  assert.ok(p.baseX > prev.baseX, "планета должна быть правее (впереди)");
  assert.ok(p.radius >= 24 && p.radius <= 70);
  assert.ok(p.captureRadius > p.radius, "зона захвата больше планеты");
  assert.ok(p.orbitDir === 1 || p.orbitDir === -1);
});

test("generateNextPlanet: детерминирован при одном seed", () => {
  const prev = { baseX: 0, baseY: 0 };
  const p1 = P.generateNextPlanet(prev, P.makeRng(5), 0);
  const p2 = P.generateNextPlanet(prev, P.makeRng(5), 0);
  assert.deepEqual(p1, p2);
});

test("generateNextPlanet: больше difficulty -> дальше разлёт (в среднем)", () => {
  // Сравним суммарную дистанцию на одинаковых seed при разной сложности.
  let easy = 0;
  let hard = 0;
  for (let seed = 1; seed <= 20; seed++) {
    const pe = P.generateNextPlanet({ baseX: 0, baseY: 0 }, P.makeRng(seed), 0);
    const ph = P.generateNextPlanet({ baseX: 0, baseY: 0 }, P.makeRng(seed), 1.4);
    easy += Math.hypot(pe.baseX, pe.baseY);
    hard += Math.hypot(ph.baseX, ph.baseY);
  }
  assert.ok(hard > easy);
});
