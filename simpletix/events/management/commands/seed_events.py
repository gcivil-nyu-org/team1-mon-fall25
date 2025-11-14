import random
import os
from datetime import datetime, timedelta, time
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import transaction
from django.contrib.auth import get_user_model
from django.conf import settings

# ---- Optional Algolia guard (no-op if package/feature is missing) ----
try:
    from algoliasearch_django.decorators import disable_auto_indexing  # type: ignore
except Exception:  # pragma: no cover
    @contextmanager
    def disable_auto_indexing():
        yield

# ---- Models ----
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
    "TechFest NYC", "Indie Music Night", "Rooftop Cinema", "City Marathon 10K",
    "Stand-Up Fridays", "Broadway Highlights", "AR/VR Demo Day", "Startups & Pizza",
    "Jazz in the Park", "Night Market", "Street Food Carnival", "Comedy Open Mic",
    "Film Society Showcase", "Brooklyn Makers Expo", "Esports Showdown",
    "Data & Donuts", "Salsa Social", "NYC Photo Walk", "AI Dev Meetup",
    "Poetry & Coffee", "Wine & Jazz", "K-Pop Dance Night", "Book Club Live",
    "Theater Lab", "Late Night Laughs", "Central Park Picnic Sessions",
    "Synthwave Night", "Live Coding Music Jam", "Design Talks", "Urban Art Tour",
]
NEIGHBORHOODS = ["Manhattan", "Midtown", "Brooklyn", "Queens", "Harlem", "SoHo", "DUMBO", "UWS", "UES"]
DESCRIPTIONS = [
    "Join us for a night of incredible performances and local talent.",
    "A community gathering with music, workshops, and great food.",
    "Hands-on demos, lightning talks, and networking with builders.",
    "An open-air showcase celebrating NYC’s creative energy.",
]

# ---- Deterministic title->banner mapping ----
SEED_BANNERS_DIR = (getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[3])
                    / "static" / "img" / "seed_banners")

TITLE_BANNER_MAP = {
    "TechFest NYC":       "techfest.png",
    "Indie Music Night":  "Indiemusic.png",   # (note the capital I)
    "Rooftop Cinema":     "rooftopcinema.png",
    "City Marathon 10K":  "marathon.png",
    "Stand-Up Fridays":   "standup.png",
    "Startups & Pizza":   "startups.png",
    "Comedy Open Mic":    "openmic.png",
    "Jazz in the Park":   "jazz.png",
    "Night Market":      "nightmarket.png",
    "Street Food Carnival": "foodcarnival.png",
    "Film Society Showcase": "filmsociety.png",
    # Others intentionally unmapped → will have no banner
}

def banner_file_for_title(title: str) -> Path | None:
    fname = TITLE_BANNER_MAP.get(title)
    if not fname:
        return None
    p = SEED_BANNERS_DIR / fname
    return p if p.exists() else None


# ---------------- Helpers ----------------
def has_field(model, field_name: str) -> bool:
    return any(getattr(f, "name", None) == field_name for f in model._meta.get_fields())


def pick_category_value():
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
    Always use a deterministic organizer so seeded events behave the same
    across machines/environments. Defaults to seed_org/Seed@12345; override
    with SEED_ORG_USER / SEED_ORG_PASS env vars if needed.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    username = os.getenv("SEED_ORG_USER", "seed_org")
    password = os.getenv("SEED_ORG_PASS", "Seed@12345")

    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"email": f"{username}@example.com", "is_staff": True}
    )
    if not user.check_password(password):
        user.set_password(password)
        user.is_staff = True
        user.save(update_fields=["password", "is_staff"])

    # Ensure OrganizerProfile exists for this user
    if OrganizerProfile is None or not has_field(Event, "organizer"):
        return None

    org, _ = OrganizerProfile.objects.get_or_create(user=user, defaults={"full_name": "Seed Organizer"})
    return org



def ensure_test_accounts():
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
            User.objects.create_user(username=username, password=pwd, email=f"{username}@example.com")
            created.append(username)
    return created


# ---------------- Management command ----------------
class Command(BaseCommand):
    help = "Seed demo events + 7 test accounts. Deterministic banners by title. Algolia-safe."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=30, help="Number of events to create (default 30)")
        parser.add_argument("--no-tickets", action="store_true", help="Create events without TicketInfo")
        parser.add_argument("--start-days", type=int, default=2, help="Start generating events N days from today")
        parser.add_argument("--span-days", type=int, default=60, help="Distribute events across this many days")

    @transaction.atomic
    def handle(self, *args, **opts):
        count = opts["count"]
        no_tickets = opts["no_tickets"]
        start_days = opts["start_days"]
        span_days = max(1, opts["span_days"])

        created_users = ensure_test_accounts()
        if created_users:
            self.stdout.write(self.style.SUCCESS(f"Created test users: {', '.join(created_users)}"))
        else:
            self.stdout.write("Test users already exist. ✅")

        organizer = get_or_create_default_organizer()
        if organizer:
            self.stdout.write(
                f"Using organizer: {getattr(organizer, 'full_name', getattr(organizer, 'id', 'organizer'))}"
            )

        created_events = []
        total_tix = 0

        with disable_auto_indexing():
            for i in range(count):
                title = TITLES[i % len(TITLES)]
                date = (datetime.today() + timedelta(days=start_days + random.randint(0, span_days))).date()
                t = time(hour=random.choice([18, 19, 20, 21]), minute=random.choice([0, 15, 30, 45]))
                location = f"{random.choice(NEIGHBORHOODS)}, NYC"
                description = random.choice(DESCRIPTIONS)

                ev_kwargs = dict(title=title, description=description, date=date, time=t, location=location)
                if organizer and has_field(Event, "organizer"):
                    ev_kwargs["organizer"] = organizer

                ev = Event(**ev_kwargs)

                # Deterministic banner (only if mapped and file exists)
                if has_field(Event, "banner"):
                    bn_path = banner_file_for_title(title)
                    if bn_path is not None:
                        try:
                            with open(bn_path, "rb") as fh:
                                ev.banner.save(f"seed_{i}_{bn_path.name}", File(fh), save=False)
                        except Exception:
                            pass

                ev.save()
                created_events.append(ev)

                # Tickets
                if not no_tickets and TicketInfo is not None:
                    used_categories = set()
                    num_ticket_types = random.choice([1, 2, 3])
                    attempts = 0
                    max_attempts = num_ticket_types * 4

                    tix_batch = []
                    while len(used_categories) < num_ticket_types and attempts < max_attempts:
                        attempts += 1
                        category_value = pick_category_value()
                        if category_value in used_categories:
                            continue
                        used_categories.add(category_value)

                        price = random.choice([15, 20, 25, 30, 35, 49, 59, 79, 99])
                        availability = random.choice([25, 50, 75, 100, 150, 200])

                        kwargs = dict(event=ev, price=price, availability=availability)
                        if has_field(TicketInfo, "category"):
                            kwargs["category"] = category_value
                        elif has_field(TicketInfo, "ticket_type"):
                            kwargs["ticket_type"] = category_value

                        tix_batch.append(TicketInfo(**kwargs))

                    if tix_batch:
                        TicketInfo.objects.bulk_create(tix_batch, ignore_conflicts=True)
                        total_tix += len(tix_batch)

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(created_events)} events with "
            f"{0 if no_tickets or TicketInfo is None else total_tix} tickets "
            f"({'with' if has_field(Event, 'banner') else 'without'} banners support). 🎉"
        ))
