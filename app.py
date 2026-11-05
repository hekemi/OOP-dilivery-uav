from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from simulation import Point, SimulationConfig, run_simulation


st.set_page_config(page_title="UAV Delivery Lab", page_icon="🚁", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #f8fbff 0%, #eef4ff 100%); }
    [data-testid="stMetric"] { background: white; border: 1px solid #dce8f8; padding: 14px; border-radius: 14px; box-shadow: 0 4px 14px #183b5b0d; }
    .hero { padding: 22px 28px; border-radius: 20px; background: linear-gradient(120deg,#12355b,#1d6fa5); color: white; margin-bottom: 20px; }
    .hero h1 { margin: 0; font-size: 2.3rem; } .hero p { opacity: .85; margin: 6px 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>🚁 UAV Delivery Lab</h1><p>Имитационная модель доставки заказов в городской сети 10×10</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Параметры эксперимента")
    seed = st.number_input("Seed", min_value=0, value=42, step=1)
    drones = st.slider("Количество дронов K", 1, 20, 2)
    capacity = st.slider("Вместимость N, заказов", 1, 30, 5)
    speed = st.slider("Скорость, км/ч", 1, 80, 10)
    st.subheader("Ограничения батареи")
    limited_range = st.checkbox("Ограничить дальность полёта", value=False)
    max_range = st.slider("Дальность без подзарядки, км", 2, 100, 25, disabled=not limited_range)
    charge = st.slider("Зарядка на складе, часов", 0.0, 8.0, 0.0, 0.25, disabled=not limited_range)
    st.subheader("Экономика")
    revenue = st.number_input("Доход с заказа", min_value=0.0, value=100.0, step=10.0)
    cost = st.number_input("Стоимость 1 км", min_value=0.0, value=2.0, step=0.5)
    depot_x = st.number_input("Склад X", 0, 9, 5)
    depot_y = st.number_input("Склад Y", 0, 9, 5)

config = SimulationConfig(
    seed=int(seed),
    drones=drones,
    capacity=capacity,
    speed_kmh=float(speed),
    max_range_km=float(max_range) if limited_range else None,
    charge_hours=float(charge) if limited_range else 0.0,
    revenue_per_order=float(revenue),
    cost_per_km=float(cost),
    depot=Point(int(depot_x), int(depot_y)),
)
result = run_simulation(config)

metrics = st.columns(5)
metrics[0].metric("Доставлено", f"{result.delivered_count}", f"из {result.generated_count}")
metrics[1].metric("Процент доставки", f"{result.delivered_count / max(result.generated_count, 1):.1%}")
metrics[2].metric("Пробег", f"{result.total_distance_km:.1f} км")
metrics[3].metric("Прибыль", f"{result.total_profit:,.0f} ₽")
metrics[4].metric("Загрузка флота", f"{result.utilization:.1%}")

left, right = st.columns([1.2, 1])
with left:
    st.subheader("Карта сети и спроса")
    points = []
    for order in result.orders:
        points.append(
            {
                "x": order.point.x,
                "y": order.point.y,
                "Тип": "Доставлен" if order.delivered_at is not None else "Не доставлен",
                "Размер": 1,
            }
        )
    for point in result.high_demand_points:
        points.append({"x": point.x, "y": point.y, "Тип": "Точка генерации (λ=5)", "Размер": 8})
    points.append({"x": config.depot.x, "y": config.depot.y, "Тип": "Склад", "Размер": 14})
    map_df = pd.DataFrame(points)
    fig = px.scatter(
        map_df,
        x="x",
        y="y",
        color="Тип",
        size="Размер",
        hover_data={"x": True, "y": True, "Размер": False},
        color_discrete_map={"Склад": "#e63946", "Точка генерации (λ=5)": "#f4a261", "Доставлен": "#2a9d8f", "Не доставлен": "#8d99ae"},
    )
    fig.update_layout(height=480, xaxis_title="Координата X", yaxis_title="Координата Y", legend_title="")
    fig.update_yaxes(scaleanchor="x", scaleratio=1, dtick=1)
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader("Динамика выполнения")
    if result.timeline:
        timeline = pd.DataFrame(result.timeline)
        hourly = timeline.groupby("hour", as_index=False)["orders"].sum()
        chart = px.bar(hourly, x="hour", y="orders", labels={"hour": "Час суток", "orders": "Заказов"})
        chart.update_layout(height=240, showlegend=False)
        st.plotly_chart(chart, use_container_width=True)
        st.dataframe(
            timeline[["drone", "hour", "orders", "distance_km", "duration_h"]].rename(
                columns={"drone": "Дрон", "hour": "Старт, ч", "orders": "Заказы", "distance_km": "Пробег, км", "duration_h": "Полёт, ч"}
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("За текущие сутки ни один рейс не был выполнен.")

st.subheader("Параметры модели")
st.caption(
    "Заказы генерируются по распределению Пуассона: 3 точки с интенсивностью 5 заказов/ч с 08:00 до 20:00 "
    "и 10 точек с интенсивностью 0,1 заказов/ч круглосуточно. Дрон строит маршрут склад → точки → склад."
)
st.info(
    f"Среднее время доставки: {result.average_delivery_hours:.2f} ч • "
    f"Рейсов: {sum(drone.missions for drone in result.drones)} • "
    f"Осталось в очереди: {result.undelivered_count}"
)
