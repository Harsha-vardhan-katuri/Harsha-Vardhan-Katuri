import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from collections import Counter


USERNAME = "Harsha-vardhan-katuri"
GRAPHQL_URL = "https://api.github.com/graphql"

# Visual configuration
BG = "#000000"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
PRIMARY = "#A371F7"
SECONDARY = "#58A6FF"
BORDER = "#30363D"


def github_graphql(query: str, variables: dict) -> dict:
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise RuntimeError("GITHUB_TOKEN environment variable is not available.")

    payload = json.dumps({
        "query": query,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "github-profile-stats"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {exc.code}: {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Unable to reach GitHub API: {exc}"
        ) from exc

    if "errors" in data:
        raise RuntimeError(
            "GraphQL error:\n" + json.dumps(data["errors"], indent=2)
        )

    return data["data"]


def escape_xml(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_number(value: int) -> str:
    return f"{value:,}"


def text(x, y, value, size=14, fill=TEXT, weight="normal", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}px" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">'
        f'{escape_xml(value)}</text>'
    )


def rect(x, y, width, height, fill=BG, stroke=BORDER, radius=10):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
    )


def generate_stats_svg(stats: dict, output_path: str) -> None:
    width = 900
    height = 270

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        text(35, 42, "GitHub Stats", 24, TEXT, "bold"),
        text(
            35,
            67,
            "Public GitHub activity",
            13,
            MUTED
        ),
    ]

    cards = [
        ("Repositories", format_number(stats["repositories"])),
        ("Followers", format_number(stats["followers"])),
        ("Following", format_number(stats["following"])),
        ("Contributions", format_number(stats["contributions"])),
        ("Commits", format_number(stats["commits"])),
        ("Pull Requests", format_number(stats["pull_requests"])),
        ("Issues", format_number(stats["issues"])),
        ("PR Reviews", format_number(stats["reviews"])),
    ]

    card_w = 198
    card_h = 70
    gap_x = 15
    gap_y = 15
    start_x = 35
    start_y = 88

    for i, (label, value) in enumerate(cards):
        row = i // 4
        col = i % 4

        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)

        svg.append(rect(x, y, card_w, card_h))
        svg.append(text(x + 15, y + 25, label, 12, MUTED))
        svg.append(text(x + 15, y + 51, value, 22, PRIMARY, "bold"))

    svg.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("\n".join(svg))


def generate_languages_svg(languages: dict, output_path: str) -> None:
    width = 700
    height = 300

    total = sum(languages.values())

    if total == 0:
        total = 1

    ordered = sorted(
        languages.items(),
        key=lambda item: item[1],
        reverse=True
    )[:7]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        text(30, 40, "Top Languages", 24, TEXT, "bold"),
        text(
            30,
            64,
            "Based on languages detected across repositories",
            13,
            MUTED
        ),
    ]

    bar_x = 30
    bar_y = 88
    bar_width = 640
    bar_height = 18

    # Combined bar
    current_x = bar_x

    colors = [
        "#A371F7",
        "#58A6FF",
        "#3FB950",
        "#F0883E",
        "#FF7B72",
        "#D2A8FF",
        "#79C0FF",
    ]

    for index, (_, amount) in enumerate(ordered):
        segment_width = bar_width * (amount / total)

        svg.append(
            f'<rect x="{current_x}" y="{bar_y}" '
            f'width="{segment_width:.2f}" height="{bar_height}" '
            f'fill="{colors[index % len(colors)]}"/>'
        )

        current_x += segment_width

    # Legend
    legend_y = 145

    for index, (language, amount) in enumerate(ordered):
        percentage = (amount / total) * 100

        col = index % 2
        row = index // 2

        x = 35 + col * 320
        y = legend_y + row * 38

        svg.append(
            f'<circle cx="{x}" cy="{y - 5}" r="6" '
            f'fill="{colors[index % len(colors)]}"/>'
        )

        svg.append(
            text(
                x + 15,
                y,
                f"{language}  {percentage:.1f}%",
                14,
                TEXT,
                "normal"
            )
        )

    svg.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("\n".join(svg))


def calculate_streak(calendar_days):
    if not calendar_days:
        return 0, 0

    contribution_map = {
        day["date"]: day["contributionCount"]
        for day in calendar_days
    }

    dates = sorted(contribution_map.keys(), reverse=True)

    today = datetime.utcnow().date()

    # Find latest active contribution day.
    latest_active = None

    for date_string in dates:
        date_obj = datetime.strptime(
            date_string, "%Y-%m-%d"
        ).date()

        if contribution_map[date_string] > 0:
            latest_active = date_obj
            break

    if latest_active is None:
        return 0, 0

    # Current streak
    current_streak = 0
    cursor = latest_active

    while True:
        value = contribution_map.get(cursor.isoformat(), 0)

        if value <= 0:
            break

        current_streak += 1
        cursor -= timedelta(days=1)

    # Longest streak
    longest_streak = 0
    running = 0

    for date_string in sorted(contribution_map.keys()):
        if contribution_map[date_string] > 0:
            running += 1
            longest_streak = max(longest_streak, running)
        else:
            running = 0

    return current_streak, longest_streak


def generate_streak_svg(
    current_streak: int,
    longest_streak: int,
    contributions: int,
    output_path: str
) -> None:
    width = 700
    height = 240

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        text(30, 42, "GitHub Streak", 24, TEXT, "bold"),
    ]

    cards = [
        ("Current Streak", f"{current_streak} days"),
        ("Longest Streak", f"{longest_streak} days"),
        ("Contributions", format_number(contributions)),
    ]

    card_widths = [205, 205, 205]
    gap = 18
    x = 30

    for i, (label, value) in enumerate(cards):
        width_card = card_widths[i]

        svg.append(
            rect(
                x,
                75,
                width_card,
                105
            )
        )

        svg.append(
            text(
                x + width_card / 2,
                108,
                label,
                13,
                MUTED,
                "normal",
                "middle"
            )
        )

        svg.append(
            text(
                x + width_card / 2,
                148,
                value,
                24,
                PRIMARY,
                "bold",
                "middle"
            )
        )

        x += width_card + gap

    svg.append(
        text(
            30,
            215,
            "Automatically updated by GitHub Actions",
            12,
            MUTED
        )
    )

    svg.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("\n".join(svg))


def main():
    now = datetime.utcnow()
    one_year_ago = now - timedelta(days=365)

    from_date = one_year_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(
      ownerAffiliations: OWNER,
      privacy: PUBLIC,
      first: 100
    ) {
      totalCount

      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }

    followers {
      totalCount
    }

    following {
      totalCount
    }

    contributionsCollection(
      from: $from,
      to: $to
    ) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions

      contributionCalendar {
        totalContributions

        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

    data = github_graphql(
        query,
        {
            "login": USERNAME,
            "from": from_date,
            "to": to_date,
        }
    )

    user = data["user"]
    contributions = user["contributionsCollection"]

    calendar_days = []

    for week in contributions["contributionCalendar"]["weeks"]:
        calendar_days.extend(
            week["contributionDays"]
        )

    current_streak, longest_streak = calculate_streak(
        calendar_days
    )

    language_counter = Counter()

    repositories = user["repositories"]["nodes"]

    for repository in repositories:
        languages = repository.get("languages") or {}

        for edge in languages.get("edges", []):
            language_counter[
                edge["node"]["name"]
            ] += edge["size"]

    stats = {
        "repositories": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "contributions": contributions["contributionCalendar"][
            "totalContributions"
        ],
        "commits": contributions["totalCommitContributions"],
        "pull_requests": contributions[
            "totalPullRequestContributions"
        ],
        "issues": contributions[
            "totalIssueContributions"
        ],
        "reviews": contributions[
            "totalPullRequestReviewContributions"
        ],
    }

    generate_stats_svg(
        stats,
        "github-stats.svg"
    )

    generate_languages_svg(
        dict(language_counter),
        "github-languages.svg"
    )

    generate_streak_svg(
        current_streak,
        longest_streak,
        stats["contributions"],
        "github-streak.svg"
    )

    print("GitHub statistics generated successfully.")
    print(json.dumps(stats, indent=2))
    print(
        f"Current streak: {current_streak} days"
    )
    print(
        f"Longest streak: {longest_streak} days"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)