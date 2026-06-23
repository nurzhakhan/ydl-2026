"""Собирает разбор `freelancers_stats_traps.ipynb` из ячеек и выполняет его."""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

md, code = new_markdown_cell, new_code_cell
cells = []

cells.append(md(
"""# Пример расследования: «Поймай статистику, которая врёт»
### YDL 2026 · фрилансеры · разбор

Перед нами `ydl_freelancers.csv`, выдуманные данные о 221 фрилансере: специализация, город, возраст,
опыт в месяцах, часы в неделю, доход, рейтинг от клиентов, отметка об отклике на опрос и несколько
шумовых колонок.

Правило игры одно: **мы не верим ни одному числу, пока не проверили, откуда оно взялось.**
Ниже мы пройдём задание лабы по шагам и поймаем пять разных способов, которыми статистика врёт."""))

cells.append(code(
"""import pandas as pd, numpy as np
from scipy import stats
import matplotlib.pyplot as plt

df = pd.read_csv('ydl_freelancers.csv')
print('строк:', len(df), '  колонок:', df.shape[1])
df.head()"""))

cells.append(code("df['specialization'].unique()"))
cells.append(code("df['specialization'].value_counts()"))

cells.append(md(
"""## Задание 1. Допросите одну колонку: доход

Считаем сводку. Не глядим на неё как на формальность, сравниваем среднее и медиану."""))

cells.append(code("df['income'].describe().round(0)"))
cells.append(code(
"""print('среднее :', round(df.income.mean()))
print('медиана :', round(df.income.median()))
print('отношение среднее/медиана:', round(df.income.mean()/df.income.median(), 2))"""))

cells.append(md(
"""### Ловушка №1: среднее завышено перекосом

Среднее (около 769 000) заметно больше медианы (около 589 000). Когда они так расходятся, данные
перекошены, и среднее уже не «типичный фрилансер». Посмотрим на гистограмму и на тех, кто тянет хвост."""))

cells.append(code(
"""fig, ax = plt.subplots(figsize=(7,3))
ax.hist(df.income/1000, bins=40, color='#7C3AED')
ax.axvline(df.income.mean()/1000, color='#F97316', linestyle='--', label='среднее')
ax.axvline(df.income.median()/1000, color='#0D9488', linestyle='--', label='медиана')
ax.set_xlabel('доход, тыс. тг'); ax.set_ylabel('человек'); ax.legend()
plt.show()"""))

cells.append(code(
"""# проверяем руками: кто в правом хвосте?
df.nlargest(9, 'income')[['specialization','weekly_hours','income']]"""))

cells.append(md(
"""Хвост это девять человек из специализации «Своё агентство» с доходами в миллионы. Их всего 9 из 221,
но они утягивают среднее вверх. Честный ответ про «типичного фрилансера» даёт **медиана**.

То же видно через группировку: средняя по «Своё агентство» огромная, и она искажает общую среднюю."""))

cells.append(code(
"df.groupby('specialization')['income'].agg(['count','mean','median']).round(0)"))

cells.append(md(
"""## Ловушка №2: пропуски, которые молчат

Посчитаем средний рейтинг. Но сначала спросим: по скольким строкам он вообще считается?"""))

cells.append(code(
"""print('средний рейтинг:', round(df.rating.mean(), 2))
print('ответили:', df.rating.notna().sum(), '   молчат:', df.rating.isna().sum())"""))

cells.append(code(
"""# кто именно не оставил рейтинг? сравним доход ответивших и молчащих
df.groupby(df.rating.isna())['income'].median().rename({False:'ответили', True:'молчат'}).round(0)"""))

cells.append(md(
"""Рейтинг «6.5» посчитан не по всем. Молчат в основном люди с низким доходом, а это как раз те, у кого
дела идут хуже. Среднее по ответившим выглядит хорошо именно потому, что неуспешные выпали из выборки.
Число честное по арифметике, но врёт по сути.

## Задание 2. Одна корреляция: часы и доход"""))

cells.append(code(
"""r = df['weekly_hours'].corr(df['income'])
print('корреляция часов и дохода по всем данным: r =', round(r, 2))"""))

cells.append(md(
"""### Ловушка №3: парадокс Симпсона

Получилось `r = -0.33`. Буквально: чем больше человек работает, тем меньше зарабатывает. Звучит дико,
поэтому не верим и режем по специализации."""))

cells.append(code(
"""df.groupby('specialization')[['weekly_hours', 'income']].apply(
    lambda g: round(g.weekly_hours.corr(g.income), 2)
).rename('r внутри специализации')"""))

cells.append(code(
"""# покажем глазами: внутри каждой специализации связь идёт вверх, а общий тренд вниз
colors = {'Аналитика данных':'#5B21B6','Веб-разработка':'#0D9488',
          'Дизайн':'#F97316','Своё агентство':'#9CA3AF'}
fig, ax = plt.subplots(figsize=(7,4))
for sp, g in df.groupby('specialization'):
    ax.scatter(g.weekly_hours, g.income/1000, s=18, color=colors[sp], label=sp, alpha=0.8)
ax.set_xlabel('часов в неделю'); ax.set_ylabel('доход, тыс. тг'); ax.legend(fontsize=8)
plt.show()"""))

cells.append(md(
"""Внутри каждой специализации связь **положительная** (около +0.8): больше часов, выше доход. Но
специализации стоят лесенкой: аналитики работают меньше часов и получают больше, дизайнеры наоборот.
Когда мы смешали всех в одну кучу, эта лесенка перевернула общий знак. Это парадокс Симпсона. Вывод
«больше работаешь, меньше платят» был артефактом смешения групп.

## Ловушка №4: смещение выборки

Представим, что доход мы узнали из опроса, и берём только тех, кто откликнулся."""))

cells.append(code(
"""print('средний по всем          :', round(df.income.mean()))
print('средний по откликнувшимся :', round(df[df.responded==1].income.mean()))
print('завышение опроса          :', str(round(100*(df[df.responded==1].income.mean()/df.income.mean()-1)))+'%')"""))

cells.append(md(
"""Опрос показывает доход примерно на 14% выше реального. Причина: охотнее отвечают те, у кого
доход высокий. Это тот же «опрос выживших», кривая выборка дала кривой вывод.

## Бонус: z-score и выбросы

Стандартизуем доход и вытащим точки, где значение далеко от среднего."""))

cells.append(code(
"""z = (df.income - df.income.mean()) / df.income.std()
df.assign(z=z.round(2)).loc[z.abs() > 3, ['specialization','weekly_hours','income','z']]"""))

cells.append(md(
"""Все выбросы это «Своё агентство». Те самые девять человек, что портили среднюю в Задании 1. z-score
нашёл их автоматически.

## Особый вызов: охота на призрак

В данных есть восемь чисто случайных колонок `noise1` ... `noise8`. Они ни с чем не связаны по
построению. Переберём все их пары и поищем самую «значимую» корреляцию."""))

cells.append(code(
"""noise = [f'noise{i}' for i in range(1, 9)]
res = []
for i in range(len(noise)):
    for j in range(i+1, len(noise)):
        r, p = stats.pearsonr(df[noise[i]], df[noise[j]])
        res.append((noise[i], noise[j], round(r, 3), round(p, 3)))
res = pd.DataFrame(res, columns=['A','B','r','p']).sort_values('p')
res.head(5)"""))

cells.append(md(
"""Лучшая пара даёт `r ≈ 0.16` и `p ≈ 0.02`, формально «значимо» (p меньше 0.05). Но мы своими руками
сделали эти колонки случайными, связи там нет. Мы просто проверили 28 пар, и пара случайно прошла порог.

Это **p-hacking**: если перебрать достаточно гипотез, что-нибудь всегда выскочит «значимым». Именно так
рождаются ложные открытия, и ровно поэтому модель с R² = 0.99 на подогнанных признаках может оказаться
пустышкой. Самое ценное здесь не найденная корреляция, а понимание, почему ей нельзя верить.

## Что мы поймали

1. **Среднее дохода** завышено горсткой агентств. Честный ответ даёт медиана.
2. **Средний рейтинг** посчитан без неуспешных, они просто не ответили.
3. **Корреляция часов и дохода** перевернулась из-за смешения специализаций (парадокс Симпсона).
4. **Опрос** завысил доход, потому что отвечали в основном высокодоходные.
5. **«Значимая» корреляция** между случайными колонками оказалась призраком (p-hacking).

Пять чисел, и каждое звучало убедительно. Ни одному нельзя было верить без проверки. Это и есть работа
сегодняшнего дня."""))

nb = new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})

with open('freelancers_stats_traps.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
print('notebook written:', len(cells), 'cells')
