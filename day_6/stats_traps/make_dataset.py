"""
Генератор синтетического датасета `ydl_freelancers.csv`.

Данные выдуманы намеренно так, чтобы в них естественно жили пять способов,
которыми статистика врёт. Сид фиксирован — датасет воспроизводим.

Что заложено по построению:
  1. Перекос среднего  — горстка «Своё агентство» с доходами в миллионы.
  2. MNAR-пропуски      — рейтинг чаще пропущен у фрилансеров с низким доходом.
  3. Парадокс Симпсона  — внутри специализации часы↔доход растут, а в общей куче падают.
  4. Смещение выборки   — на опрос (responded) охотнее отвечают высокодоходные.
  5. P-hacking          — noise1..noise8 чисто случайны, связи там нет.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)

# name, n, mean_hours, hours_std, base_income, slope(+), noise_std
specs = [
    ("Аналитика данных", 70, 24, 4,  895000, 20000,  65000),
    ("Веб-разработка",   82, 40, 4,  555000, 18000,  58000),
    ("Дизайн",           60, 51, 4,  389000, 12000,  39000),
    ("Своё агентство",    9, 30, 6, 4000000, 30000, 700000),
]
cities = ["Алматы", "Астана", "Шымкент", "Караганда"]

rows = []
for name, n, mh, hs, base, slope, nstd in specs:
    hours = rng.normal(mh, hs, n).clip(10, 70)
    # внутри специализации связь положительная: больше часов -> выше доход
    income = base + slope * (hours - mh) + rng.normal(0, nstd, n)
    income = income.clip(150000, None)
    age = rng.integers(21, 45, n)
    exp = rng.integers(0, 60, n)
    for i in range(n):
        rows.append({
            "specialization": name,
            "city": str(rng.choice(cities)),
            "age": int(age[i]),
            "experience_months": int(exp[i]),
            "weekly_hours": round(float(hours[i]), 1),
            "income": int(round(income[i], -3)),
        })

df = pd.DataFrame(rows)
inc = df["income"].values
lo, hi = df.income.quantile(0.1), df.income.quantile(0.9)

# 2. рейтинг с MNAR: чем ниже доход, тем выше шанс пропуска
rating = (6.5 + rng.normal(0, 1.2, len(df))).clip(1, 10).round(1).astype(float)
p_missing = np.interp(inc, [lo, hi], [0.55, 0.10])
rating[rng.random(len(df)) < p_missing] = np.nan
df["rating"] = rating

# 4. отклик на опрос: высокодоходные отвечают охотнее
p_resp = np.interp(inc, [lo, hi], [0.35, 0.85])
df["responded"] = (rng.random(len(df)) < p_resp).astype(int)

# 5. восемь чисто случайных колонок (отдельный RNG: сид подобран так, чтобы
#    одна пара случайно прошла порог p<0.05 — это и есть наглядный p-hacking)
rng_noise = np.random.default_rng(7)
for k in range(1, 9):
    df[f"noise{k}"] = rng_noise.normal(0, 1, len(df)).round(3)

df = df.sample(frac=1, random_state=7).reset_index(drop=True)
df.to_csv("ydl_freelancers.csv", index=False)

# --- диагностика для подгонки текста разбора ---
print("shape:", df.shape)
print(df.groupby("specialization")["income"].agg(["count", "mean", "median"]).round(0))
print("mean/median:", round(df.income.mean()), round(df.income.median()),
      round(df.income.mean() / df.income.median(), 2))
print("overall r hours~income:", round(df.weekly_hours.corr(df.income), 2))
print(df.groupby("specialization").apply(
    lambda g: round(g.weekly_hours.corr(g.income), 2)))
print("rating mean:", round(df.rating.mean(), 2),
      "| ответили:", df.rating.notna().sum(), "| молчат:", df.rating.isna().sum())
print("median income ответили/молчат:",
      df.groupby(df.rating.isna())["income"].median().round(0).to_dict())
print("income all:", round(df.income.mean()),
      "| responded==1:", round(df[df.responded == 1].income.mean()),
      "| +%:", round(100 * (df[df.responded == 1].income.mean() / df.income.mean() - 1)))
