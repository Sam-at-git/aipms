"""Hotel domain API routers."""


def get_hotel_routers():
    """Return list of all hotel domain FastAPI routers."""
    from app.hotel.routers import (
        rooms, guests, reservations, checkin, checkout,
        tasks, billing, employees, prices, reports,
    )
    return [
        rooms.router,
        guests.router,
        reservations.router,
        checkin.router,
        checkout.router,
        tasks.router,
        billing.router,
        employees.router,
        prices.router,
        reports.router,
    ]
