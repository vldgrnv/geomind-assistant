import re

_NDVI_LANDSAT5_RESPONSE = """\
Для расчёта NDVI по снимкам Landsat 5 TM вам понадобятся Band 3 (Red) и Band 4 (NIR).

⚠️ **Важно перед началом:** Убедитесь, что вы используете снимки, прошедшие атмосферную коррекцию (уровень Surface Reflectance). Если считать по «сырым» цифровым числам (DN), значения индекса будут некорректными.

### 🖱 Способ 1: Обычный (через Raster Calculator)

1. Добавьте каналы Band 3 и Band 4 в таблицу содержимого ArcMap.
2. Убедитесь, что включено расширение Spatial Analyst: **Customize → Extensions → Spatial Analyst**.
3. Откройте инструмент: **ArcToolbox → Spatial Analyst Tools → Map Algebra → Raster Calculator**.
4. Введите следующую формулу. Обязательно используйте функцию `Float()`, иначе ArcMap выполнит целочисленное деление и вы получите растр из нулей и единиц:

```
Float("Landsat5_B4" - "Landsat5_B3") / Float("Landsat5_B4" + "Landsat5_B3")
```

5. Укажите путь и имя для выходного файла (Output raster) и нажмите OK.

### 💻 Способ 2: С помощью кода (Python / ArcPy)

Этот способ удобен для пакетной обработки нескольких снимков. Откройте Python Window в ArcMap или запустите скрипт в IDE.

```python
import arcpy
from arcpy.sa import *

# 1. Проверяем и получаем лицензию Spatial Analyst
arcpy.CheckOutExtension("Spatial")

# 2. Указываем пути к каналам Landsat 5 (Red и NIR)
red_band = arcpy.Raster(r"C:\\Data\\Landsat5_B3.tif")
nir_band = arcpy.Raster(r"C:\\Data\\Landsat5_B4.tif")

# 3. Рассчитываем NDVI с обязательным приведением к типу Float
ndvi = Float(nir_band - red_band) / Float(nir_band + red_band)

# 4. Сохраняем результат
output_path = r"C:\\Data\\ndvi_landsat5_result.tif"
ndvi.save(output_path)

# 5. Возвращаем лицензию
arcpy.CheckInExtension("Spatial")

print(f"Расчет NDVI успешно завершен! Файл сохранен: {output_path}")
```

### ⚠️ Типичные ошибки (из базы знаний)

- **Деление на ноль:** В пикселях с глубокими водными объектами сумма NIR+Red может быть равна 0, что даст значение NaN. Рекомендуется наложить маску водных объектов перед расчётом.
- **Неверные каналы:** Для Landsat 5 это именно 3-й и 4-й каналы. Не перепутайте с Landsat 8, где это 4-й и 5-й!

### Вот подробная фотоинструкция для ArcMap 10.8:

![Шаг 1](/static/prompt_1/1.jpg)
![Шаг 2](/static/prompt_1/2.jpg)
![Шаг 3](/static/prompt_1/3.jpg)
![Шаг 4](/static/prompt_1/4.jpg)
![Шаг 5](/static/prompt_1/5.jpg)
![Шаг 6](/static/prompt_1/6.jpg)
"""

_RULES = [
    (
        lambda q: "ndvi" in q and "landsat" in q,
        _NDVI_LANDSAT5_RESPONSE,
    ),
]


def match_hardcoded(query: str):
    q = query.lower()
    for check, response in _RULES:
        if check(q):
            return response
    return None
