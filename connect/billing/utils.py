from connect.common.models import Project
from pendulum.datetime import DateTime
from typing import Tuple
from connect.billing.models import Contact
import pendulum
from itertools import groupby


def day_period(day: DateTime) -> Tuple[DateTime, ...]:
    start = day.start_of("day")
    end = day.end_of("day")
    return start, end


def daily_attendances(project: Project, start: DateTime, end: DateTime) -> int:
    day_attendances = (
        Contact.objects.filter(project=project)
        .filter(last_seen_on__range=(start, end))
        .distinct("contact_flow_uuid")
        .count()
    )
    return day_attendances


def get_attendances(project: Project, start: str, end: str) -> int:
    start = pendulum.parse(start)
    end = pendulum.parse(end)
    period = pendulum.period(start, end)

    total_per_project = 0

    for day in period.range("days"):
        start_of_the_day, end_of_the_day = day_period(day)
        day_attendances = daily_attendances(project, start_of_the_day, end_of_the_day)
        total_per_project += day_attendances

    return total_per_project


def count_attendances(contact_group: list):
    attendances = 1
    base_contact = contact_group[0]

    for contact in contact_group:
        date_period = pendulum.instance(base_contact.last_seen_on) - pendulum.instance(
            contact.last_seen_on
        )
        if abs(date_period.days) >= 1:
            attendances += 1
            base_contact = contact

    return attendances


def custom_get_attendances(project: Project, start: str, end: str):
    start = pendulum.parse(start)
    end = pendulum.parse(end)
    total_attendances = 0

    contacts = Contact.objects.filter(
        last_seen_on__range=(start, end), project=project
    ).order_by("contact_flow_uuid", "-last_seen_on")
    grouped_contacts = groupby(contacts, lambda contact: contact.contact_flow_uuid)

    for _, group in grouped_contacts:
        contact_group = list(group)
        total_attendances += count_attendances(contact_group)

    return total_attendances
