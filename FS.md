сделай максимально минимальный бэк, фронт. 
прочитай guides, core md. 
у openweather api бесплатный раз в 15 мин, учитывай это, и тест делай только когда нужно.

координаты турбины 1: https://maps.app.goo.gl/iN6svMt69D5qRpFU9
координаты турбины 2: https://maps.app.goo.gl/8UQMwsYavY6nLvFY8

что видит пользователь: 

    1. Turbine:
    - Turbine 1
    - Turbine 2
    - Both / Farm total

    2. Forecast issue time:
    - например 2026-01-31 00:00

    3. Horizon:
    - 24 hours
    - 48 hours

под капотом: 

    4. Weather source:
    - Open-Meteo ECMWF
    - fallback if available

    5. проеоброзовать данные, чтобы скормить модели

    6. предикт локально моделью и вернуть бэку, а тот в свою очередь фронту


7. фронт все это время ждет просто, мини загрузка анимации


все это запускается докером.