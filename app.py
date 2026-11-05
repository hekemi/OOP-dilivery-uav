from __future__ import annotations

import random

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from simulation import Point, SimulationConfig, optimize_deliveries, run_simulation


st.set_page_config(page_title="UAV Delivery Lab", page_icon="assets/shahed.png", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at top right, #172554 0%, #0b1120 45%, #070b14 100%); color: #e5eefb; }
    [data-testid="stHeader"] { background: rgba(7, 11, 20, .8); }
    [data-testid="stSidebar"] { background: #0d1627; border-right: 1px solid #263957; }
    [data-testid="stMetric"] { background: #111d32; border: 1px solid #2b4163; padding: 14px; border-radius: 14px; box-shadow: 0 4px 14px #00000035; }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"] { color: #f1f5ff !important; }
    [data-testid="stMetricLabel"] p { color: #a9bdd9 !important; }
    .stMarkdown, .stCaption, label, .stText, p { color: #d7e3f5; }
    h1, h2, h3 { color: #f8fbff !important; }
    .stInfo, .stAlert { background: #12233b; color: #e5eefb; border-color: #315581; }
    .hero { padding: 22px 28px; border-radius: 20px; background: linear-gradient(120deg,#172554,#075985); color: white; margin-bottom: 20px; border: 1px solid #2e6a9c; }
    .hero h1 { margin: 0; font-size: 2.3rem; } .hero p { opacity: .85; margin: 6px 0 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero"><h1>UAV Delivery Lab</h1><p>Имитационная модель доставки заказов в городской сети 10×10</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Параметры эксперимента")
    if "simulation_seed" not in st.session_state:
        st.session_state.simulation_seed = random.SystemRandom().randint(0, 2**32 - 1)
    seed_col, seed_button_col = st.columns([1.35, 1])
    with seed_col:
        st.markdown(f"**Фиксированный seed**  \n`{st.session_state.simulation_seed}`")
    with seed_button_col:
        change_seed = st.button("Сменить seed", use_container_width=True, type="primary")
    if change_seed:
        st.session_state.simulation_seed = random.SystemRandom().randint(0, 2**32 - 1)
        st.session_state.pop("optimized_result", None)
        st.session_state.pop("optimized_config", None)
        st.rerun()
    st.caption("Один seed используется для всех проверяемых конфигураций.")
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

st.subheader("Оптимизация доставленных заказов")
st.caption("Программа сама подбирает K, V и N для фиксированного seed. Ограничения дальности, зарядки и экономика берутся из боковой панели.")
run_optimization = st.button("🚀 Найти максимум", type="primary", use_container_width=False)

config = SimulationConfig(
    seed=st.session_state.simulation_seed,
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

if run_optimization:
    with st.spinner("Перебираю конфигурации дронов..."):
        optimized_config, optimized_result = optimize_deliveries(
            config,
        )
    st.session_state.optimized_config = optimized_config
    st.session_state.optimized_result = optimized_result

display_config = st.session_state.get("optimized_config", config)
display_result = st.session_state.get("optimized_result", result)
if "optimized_result" in st.session_state:
    st.success(
        f"Лучший результат для seed `{display_config.seed}`: "
        f"**{display_result.delivered_count} из {display_result.generated_count} заказов**. "
        f"Подобраны: **{display_config.drones} дрон(а)**, "
        f"**{display_config.speed_kmh:.0f} км/ч**, вместимость **{display_config.capacity}**."
    )

metrics = st.columns(5)
metrics[0].metric("Доставлено", f"{display_result.delivered_count}")
metrics[0].caption(f"из {display_result.generated_count} сгенерированных заказов")
metrics[1].metric("Процент доставки", f"{display_result.delivered_count / max(display_result.generated_count, 1):.1%}")
metrics[2].metric("Пробег", f"{display_result.total_distance_km:.1f} км")
metrics[3].metric("Прибыль", f"{display_result.total_profit:,.0f} ₽")
metrics[4].metric("Загрузка флота", f"{display_result.utilization:.1%}")

left, right = st.columns([1.2, 1])
with left:
    st.subheader(f"Сетка сети 10×10 и маршруты дронов · seed {display_config.seed}")
    demand = {(x, y): 0 for x in range(10) for y in range(10)}
    for order in display_result.orders:
        demand[(order.point.x, order.point.y)] += 1
    fig = go.Figure()
    for x in range(10):
        for y in range(10):
            fig.add_shape(
                type="rect", x0=x - 0.48, y0=y - 0.48, x1=x + 0.48, y1=y + 0.48,
                layer="below",
                line=dict(color="#29415f", width=1), fillcolor="#0e1a2c",
            )
            if demand[(x, y)]:
                fig.add_annotation(
                    x=x, y=y, text=str(demand[(x, y)]), showarrow=False,
                    font=dict(size=11, color="#e8f1ff"),
                )
    route_colors = ["#38bdf8", "#a78bfa", "#f472b6", "#facc15", "#34d399"]
    shown_drones = set()
    for index, mission in enumerate(display_result.timeline):
        route = mission["route"]
        fig.add_trace(
            go.Scatter(
                x=[point[0] for point in route], y=[point[1] for point in route],
                mode="lines+markers",
                name=mission["drone"],
                legendgroup=mission["drone"],
                showlegend=mission["drone"] not in shown_drones,
                line=dict(color=route_colors[int(mission["drone"].split()[-1]) % len(route_colors)], width=4),
                marker=dict(size=9, line=dict(color="#f8fbff", width=1)),
                hovertemplate=f"{mission['drone']}<extra></extra>",
            )
        )
        shown_drones.add(mission["drone"])
    fig.add_trace(go.Scatter(
        x=[display_config.depot.x], y=[display_config.depot.y], mode="markers+text",
        text=["СКЛАД"], textposition="top center", name="Склад",
        marker=dict(size=18, color="#ef4444", symbol="diamond"),
        textfont=dict(color="#fecaca", size=11),
    ))
    high_x = [point.x for point in display_result.high_demand_points]
    high_y = [point.y for point in display_result.high_demand_points]
    fig.add_trace(go.Scatter(
        x=high_x, y=high_y, mode="markers", name="Точки λ=5",
        marker=dict(size=14, color="#fb923c", symbol="star"),
    ))
    # Координаты вынесены за пределы клеток, чтобы не пересекаться с маршрутами.
    for coordinate in range(10):
        fig.add_annotation(
            x=coordinate, y=-0.72, text=str(coordinate), showarrow=False,
            font=dict(size=11, color="#d7e3f5"), xanchor="center", yanchor="top",
        )
        fig.add_annotation(
            x=-0.72, y=coordinate, text=str(coordinate), showarrow=False,
            font=dict(size=11, color="#d7e3f5"), xanchor="right", yanchor="middle",
        )
    fig.update_layout(
        height=560, template="plotly_dark", paper_bgcolor="#0b1322", plot_bgcolor="#0b1322",
        title=f"Фиксированный seed: {display_config.seed}",
        xaxis=dict(range=[-1, 9.6], showticklabels=False, title=None, gridcolor="#1f3552", zeroline=False),
        yaxis=dict(range=[-1, 9.6], showticklabels=False, title=None, gridcolor="#1f3552", zeroline=False, scaleanchor="x", scaleratio=1),
        legend_title="", margin=dict(l=45, r=20, t=20, b=38),
    )
    st.plotly_chart(fig, use_container_width=True)
with right:
    st.subheader(f"Динамика выполнения · seed {display_config.seed}")
    if display_result.timeline:
        timeline = pd.DataFrame(display_result.timeline)
        hourly = timeline.groupby("hour", as_index=False)["orders"].sum()
        chart = px.bar(hourly, x="hour", y="orders", labels={"hour": "Час суток", "orders": "Заказов"}, template="plotly_dark")
        chart.update_layout(
            height=240, showlegend=False, paper_bgcolor="#0b1322", plot_bgcolor="#0b1322",
            title=f"Фиксированный seed: {display_config.seed}",
        )
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
    f"Seed: {display_config.seed} • "
    f"Среднее время доставки: {display_result.average_delivery_hours:.2f} ч • "
    f"Рейсов: {sum(drone.missions for drone in display_result.drones)} • "
    f"Осталось в очереди: {display_result.undelivered_count}"
)
