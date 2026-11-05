"""Discrete-event simulation for a UAV delivery network."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Optional


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass
class Order:
    order_id: int
    created_at: float
    point: Point
    delivered_at: Optional[float] = None


@dataclass
class Drone:
    drone_id: int
    available_at: float = 0.0
    missions: int = 0
    distance_km: float = 0.0
    charging_hours: float = 0.0


@dataclass
class SimulationConfig:
    seed: int = 42
    grid_size: int = 10
    drones: int = 2
    capacity: int = 5
    speed_kmh: float = 10.0
    max_range_km: Optional[float] = None
    charge_hours: float = 0.0
    revenue_per_order: float = 100.0
    cost_per_km: float = 2.0
    high_intensity: float = 5.0
    low_intensity: float = 0.1
    high_points: int = 3
    low_points: int = 10
    depot: Point = field(default_factory=lambda: Point(5, 5))


@dataclass
class SimulationResult:
    orders: list[Order]
    delivered_orders: list[Order]
    drones: list[Drone]
    high_demand_points: list[Point]
    low_demand_points: list[Point]
    timeline: list[dict]
    total_distance_km: float
    total_profit: float
    average_delivery_hours: float
    utilization: float

    @property
    def generated_count(self) -> int:
        return len(self.orders)

    @property
    def delivered_count(self) -> int:
        return len(self.delivered_orders)

    @property
    def undelivered_count(self) -> int:
        return self.generated_count - self.delivered_count


def optimize_deliveries(
    base_config: SimulationConfig,
    max_drones: int = 20,
    max_speed_kmh: int = 80,
    max_capacity: int = 30,
) -> tuple[SimulationConfig, SimulationResult]:
    """Find the configuration delivering the most orders within supplied limits."""
    if min(max_drones, max_speed_kmh, max_capacity) < 1:
        raise ValueError("Ограничения оптимизации должны быть положительными.")

    best_config = SimulationConfig(
        **{
            **base_config.__dict__,
            "drones": 1,
            "speed_kmh": 1.0,
            "capacity": 1,
        }
    )
    best_result = run_simulation(best_config)
    # При максимизации числа доставок большая скорость не ухудшает расписание,
    # поэтому достаточно проверить заданную максимальную скорость.
    for drone_count in range(1, max_drones + 1):
        for capacity in range(1, max_capacity + 1):
            candidate_config = SimulationConfig(
                **{
                    **base_config.__dict__,
                    "drones": drone_count,
                    "speed_kmh": float(max_speed_kmh),
                    "capacity": capacity,
                }
            )
            candidate_result = run_simulation(candidate_config)
            score = (
                candidate_result.delivered_count,
                -candidate_result.total_distance_km,
                -drone_count,
                -max_speed_kmh,
                -capacity,
            )
            best_score = (
                best_result.delivered_count,
                -best_result.total_distance_km,
                -best_config.drones,
                -best_config.speed_kmh,
                -best_config.capacity,
            )
            if score > best_score:
                best_config, best_result = candidate_config, candidate_result
    return best_config, best_result


def manhattan_distance(a: Point, b: Point) -> float:
    return float(abs(a.x - b.x) + abs(a.y - b.y))


def _poisson(rng: random.Random, lam: float) -> int:
    """Generate a Poisson variate without third-party dependencies."""
    limit = math.exp(-lam)
    product = 1.0
    count = 0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def _unique_points(rng: random.Random, count: int, grid_size: int, depot: Point) -> list[Point]:
    candidates = [Point(x, y) for x in range(grid_size) for y in range(grid_size) if Point(x, y) != depot]
    return rng.sample(candidates, min(count, len(candidates)))


def generate_orders(config: SimulationConfig) -> tuple[list[Order], list[Point], list[Point]]:
    rng = random.Random(config.seed)
    high_points = _unique_points(rng, config.high_points, config.grid_size, config.depot)
    remaining = [
        Point(x, y)
        for x in range(config.grid_size)
        for y in range(config.grid_size)
        if Point(x, y) != config.depot and Point(x, y) not in high_points
    ]
    low_points = rng.sample(remaining, min(config.low_points, len(remaining)))
    orders: list[Order] = []
    next_id = 1
    for hour in range(24):
        intensity_points = high_points if 8 <= hour < 20 else []
        for point in intensity_points:
            for _ in range(_poisson(rng, config.high_intensity)):
                orders.append(Order(next_id, hour + rng.random(), point))
                next_id += 1
        for point in low_points:
            for _ in range(_poisson(rng, config.low_intensity)):
                orders.append(Order(next_id, hour + rng.random(), point))
                next_id += 1
    return sorted(orders, key=lambda order: order.created_at), high_points, low_points


def _mission_distance(depot: Point, orders: list[Order]) -> float:
    """Return a short route depot -> stops -> depot using nearest-neighbor ordering."""
    remaining = orders[:]
    current = depot
    distance = 0.0
    while remaining:
        next_order = min(remaining, key=lambda order: manhattan_distance(current, order.point))
        distance += manhattan_distance(current, next_order.point)
        current = next_order.point
        remaining.remove(next_order)
    return distance + manhattan_distance(current, depot)


def _mission_route(depot: Point, orders: list[Order]) -> list[Point]:
    remaining = orders[:]
    current = depot
    route = [depot]
    while remaining:
        next_order = min(remaining, key=lambda order: manhattan_distance(current, order.point))
        route.append(next_order.point)
        current = next_order.point
        remaining.remove(next_order)
    route.append(depot)
    return route


def run_simulation(config: SimulationConfig) -> SimulationResult:
    if config.drones < 1 or config.capacity < 1 or config.speed_kmh <= 0:
        raise ValueError("Количество дронов и вместимость должны быть положительными, скорость — больше нуля.")
    if config.max_range_km is not None and config.max_range_km <= 0:
        raise ValueError("Максимальная дальность должна быть больше нуля.")

    orders, high_points, low_points = generate_orders(config)
    drones = [Drone(index + 1) for index in range(config.drones)]
    pending: list[Order] = []
    timeline: list[dict] = []
    delivered: list[Order] = []

    for hour in range(24):
        pending.extend(order for order in orders if hour <= order.created_at < hour + 1)
        for drone in sorted(drones, key=lambda item: item.available_at):
            if drone.available_at > hour or not pending:
                continue
            # Prefer the oldest request, then fill the batch from nearby points.
            oldest = min(pending, key=lambda order: order.created_at)
            batch = [oldest]
            remaining = [order for order in pending if order is not oldest]
            remaining.sort(key=lambda order: manhattan_distance(oldest.point, order.point))
            for order in remaining:
                candidate = batch + [order]
                if len(candidate) <= config.capacity:
                    batch.append(order)
            distance = _mission_distance(config.depot, batch)
            if config.max_range_km is not None and distance > config.max_range_km:
                # Try a smaller batch; this preserves deliveries possible within the battery limit.
                feasible = []
                for size in range(len(batch), 0, -1):
                    candidate = batch[:size]
                    if _mission_distance(config.depot, candidate) <= config.max_range_km:
                        feasible = candidate
                        break
                if not feasible:
                    continue
                batch = feasible
                distance = _mission_distance(config.depot, batch)
            start = max(hour, drone.available_at)
            flight_hours = distance / config.speed_kmh
            finish = start + flight_hours + config.charge_hours
            route = _mission_route(config.depot, batch)
            for order in batch:
                order.delivered_at = finish
                delivered.append(order)
                pending.remove(order)
            drone.available_at = finish
            drone.missions += 1
            drone.distance_km += distance
            drone.charging_hours += config.charge_hours
            timeline.append(
                {
                    "hour": start,
                    "drone": f"Дрон {drone.drone_id}",
                    "orders": len(batch),
                    "distance_km": distance,
                    "duration_h": flight_hours,
                    "finish": finish,
                    "route": [(point.x, point.y) for point in route],
                }
            )

    total_distance = sum(drone.distance_km for drone in drones)
    total_profit = len(delivered) * config.revenue_per_order - total_distance * config.cost_per_km
    average_delivery = (
        sum(order.delivered_at - order.created_at for order in delivered) / len(delivered)
        if delivered
        else 0.0
    )
    utilization = (
        sum(min(drone.available_at, 24.0) for drone in drones) / (24 * config.drones)
        if drones
        else 0.0
    )
    return SimulationResult(
        orders=orders,
        delivered_orders=delivered,
        drones=drones,
        high_demand_points=high_points,
        low_demand_points=low_points,
        timeline=timeline,
        total_distance_km=total_distance,
        total_profit=total_profit,
        average_delivery_hours=average_delivery,
        utilization=utilization,
    )
