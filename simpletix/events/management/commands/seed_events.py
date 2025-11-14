import os
import random
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

# ---- Optional Algolia guard (no-op if package/feature is missing) ----
try:
    from algoliasearch_django.decorators import (
        disable_auto_indexing,
    )  # type: ignore
except Exception:  # pragma: no cover

    @contextmanager
    def disable_auto_indexing():
        yield


# ---- Import your models ----
from events.models import Event

try:
    from events.models import OrganizerProfile
except Exception:
    OrganizerProfile = None

try:
    from tickets.models import TicketInfo
except Exception:
    TicketInfo = None


# ---------------- Seed data pools ----------------
TITLES = [
    "TechFest NYC",
    "Indie Music Night",
    "Rooftop Cinema",
    "City Marathon 10K",
    "Stand-Up Fridays",
    "Broadway Highlights",
    "AR/VR Demo Day",
    "Startups & Pizza",
    "Jazz in the Park",
    "Night Market",
    "Street Food Carnival",
    "Comedy Open Mic",
    "Film Society Showcase",
    "Brooklyn Makers Expo",
    "Esports Showdown",
    "Data & Donuts",
    "Salsa Social",
    "NYC Photo Walk",
    "AI Dev Meetup",
    "Poetry & Coffee",
    "Wine & Jazz",
    "K-Pop Dance Night",
    "Book Club Live",
    "Theater Lab",
    "Late Night Laughs",
    "Central Park Picnic Sessions",
    "Synthwave Night",
    "Live Coding Music Jam",
    "Design Talks",
    "Urban Art Tour",
]

NEIGHBORHOODS = [
    "Manhattan",
    "Midtown",
    "Brooklyn",
    "Queens",
    "Harlem",
    "SoHo",
    "DUMBO",
    "UWS",
    "UES",
]

DESCRIPTIONS = [
    "Join us for a night of incredible performances and local talent.",
    "A community gathering with music, workshops, and great food.",
    "Hands-on demos, lightning talks, and networking with builders.",
    "An open-air showcase celebrating NYC’s creative energy.",
]

# Title → banner filename mapping in static/img/seed_banners/
TITLE_BANNER_MAP = {
    "TechFest NYC": "techfest.png",
    "Indie Music Night": "Indiemusic.png",
    "Rooftop Cinema": "rooftopcinema.png",
    "City Marathon 10K": "marathon.png",
    "Stand-Up Fridays": "standup.png",
    "Startups & Pizza": "startups.png",
    "Comedy Open Mic": "openmic.png",
    "Jazz in the Park": "jazz.png",
}


def has_field(model, field_name: str) -> bool:
    return any(getattr(f, "name", None) == field_name for f in model._meta.get_fields())


def pick_category_value():
    """
    Returns a valid TicketInfo.category value (respects choices if present).

    Falls back to simple strings if no choices are defined.
    """
    if TicketInfo is None:
        return None
    try:
        field = TicketInfo._meta.get_field("category")
        if getattr(field, "choices", None):
            return random.choice([c[0] for c in field.choices])
    except Exception:
        pass
    return random.choice(["GA", "VIP", "STUDENT"])


def get_or_create_default_organizer():
    """
    Return a deterministic organizer for seeded events.

    Uses seed_org/Seed@12345 by default, overridable via SEED_ORG_USER
    and SEED_ORG_PASS environment variables.
    """
    User = get_user_model()
    username = os.getenv("SEED_ORG_USER", "seed_org")
    password = os.getenv("SEED_ORG_PASS", "Seed@12345")

    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"email": f"{username}@example.com", "is_staff": True},
    )
    if not user.check_password(password):
        user.set_password(password)
        user.is_staff = True
        user.save(update_fields=["password", "is_staff"])

    if OrganizerProfile is None or not has_field(Event, "organizer"):
        return None

    org, _ = OrganizerProfile.objects.get_or_create(
        user=user,
        defaults={"full_name": "Seed Organizer"},
    )
    return org


def ensure_test_accounts():
    """
    Create the 7 required test users; skip if they already exist.
    """
    User = get_user_model()
    creds = [
        ("prof_test", "Prof@12345"),
        ("ta_test", "Ta@12345"),
        ("test1", "Test@12345"),
        ("test2", "Test@12345"),
        ("test3", "Test@12345"),
        ("test4", "Test@12345"),
        ("test5", "Test@12345"),
    ]
    created = []
    for username, pwd in creds:
        if not User.objects.filter(username=username).exists():
            User.objects.create_user(
                username=username,
                password=pwd,
                email=f"{username}@example.com",
            )
            created.append(username)
    return created


def seed_banners_dir() -> Path:
    """
    Return the static folder that contains seed banners.
    """
    base_dir = getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[3])
    return Path(base_dir) / "static" / "img" / "seed_banners"


def get_banner_path_for_title(title: str) -> Path | None:
    """
    Map an event title to a banner file path, if it exists.
    """
    fname = TITLE_BANNER_MAP.get(title)
    if not fname:
        return None

    folder = seed_banners_dir()
    path = folder / fname
    if not path.exists():
        return None
    return path


def event_has_banner_field() -> bool:
    return has_field(Event, "banner")


class Command(BaseCommand):
    help = (
        "Seed the database with demo events and test accounts "
        "(Algolia-safe, no auto indexing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="Number of events to create (default 30).",
        )
        parser.add_argument(
            "--no-tickets",
            action="store_true",
            help="Create events without TicketInfo.",
        )
        parser.add_argument(
            "--start-days",
            type=int,
            default=2,
            help="Start generating events N days from today.",
        )
        parser.add_argument(
            "--span-days",
            type=int,
            default=60,
            help="Distribute events across this many days.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        count = opts["count"]
        no_tickets = opts["no_tickets"]
        start_days = opts["start_days"]
        span_days = max(1, opts["span_days"])

        created_users = ensure_test_accounts()
        if created_users:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created test users: {', '.join(created_users)}",
                )
            )
        else:
            self.stdout.write("Test users already exist. ✅")

        organizer = get_or_create_default_organizer()
        if organizer:
            name = getattr(organizer, "full_name", None) or getattr(
                organizer,
                "id",
                "organizer",
            )
            self.stdout.write(f"Using organizer: {name}")

        created_events = []
        total_tix = 0

        with disable_auto_indexing():
            for i in range(count):
                title = TITLES[i % len(TITLES)]
                date = (
                    datetime.today()
                    + timedelta(
                        days=start_days + random.randint(0, span_days),
                    )
                ).date()
                t = time(
                    hour=random.choice([18, 19, 20, 21]),
                    minute=random.choice([0, 15, 30, 45]),
                )
                location = f"{random.choice(NEIGHBORHOODS)}, NYC"
                description = random.choice(DESCRIPTIONS)

                ev_kwargs = {
                    "title": title,
                    "description": description,
                    "date": date,
                    "time": t,
                    "location": location,
                }
                if organizer and has_field(Event, "organizer"):
                    ev_kwargs["organizer"] = organizer

                ev = Event(**ev_kwargs)

                if event_has_banner_field():
                    banner_path = get_banner_path_for_title(title)
                    if banner_path is not None:
                        try:
                            with open(banner_path, "rb") as fh:
                                ev.banner.save(
                                    f"seed_{i}_{banner_path.name}",
                                    File(fh),
                                    save=False,
                                )
                            self.stdout.write(
                                f"[BANNER] {title}  ←  {banner_path.name}",
                            )
                        except Exception:
                            # If an image fails to load, proceed without a banner.
                            pass

                ev.save()
                created_events.append(ev)

                if not no_tickets and TicketInfo is not None:
                    used_categories = set()
                    num_ticket_types = random.choice([1, 2, 3])
                    attempts = 0
                    max_attempts = num_ticket_types * 4

                    tix_batch = []
                    while (
                        len(used_categories) < num_ticket_types
                        and attempts < max_attempts
                    ):
                        attempts += 1
                        category_value = pick_category_value()
                        if category_value in used_categories:
                            continue
                        used_categories.add(category_value)

                        price = random.choice(
                            [15, 20, 25, 30, 35, 49, 59, 79, 99],
                        )
                        availability = random.choice(
                            [25, 50, 75, 100, 150, 200],
                        )

                        kwargs = {
                            "event": ev,
                            "price": price,
                            "availability": availability,
                        }
                        if has_field(TicketInfo, "category"):
                            kwargs["category"] = category_value
                        elif has_field(TicketInfo, "ticket_type"):
                            kwargs["ticket_type"] = category_value

                        tix_batch.append(TicketInfo(**kwargs))

                    if tix_batch:
                        TicketInfo.objects.bulk_create(
                            tix_batch,
                            ignore_conflicts=True,
                        )
                        total_tix += len(tix_batch)

        banner_status = "with" if event_has_banner_field() else "without"
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(created_events)} events with "
                f"{0 if no_tickets or TicketInfo is None else total_tix} "
                f"tickets ({banner_status} banners support). 🎉",
            )
        )
