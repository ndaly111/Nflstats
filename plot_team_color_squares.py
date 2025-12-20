import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

NFL_TEAM_COLORS = {
    "ARI": {"primary": "#97233F", "secondary": "#000000"},
    "ATL": {"primary": "#A71930", "secondary": "#000000"},
    "BAL": {"primary": "#241773", "secondary": "#9E7C0C"},
    "BUF": {"primary": "#00338D", "secondary": "#C60C30"},
    "CAR": {"primary": "#0085CA", "secondary": "#101820"},
    "CHI": {"primary": "#0B162A", "secondary": "#C83803"},
    "CIN": {"primary": "#FB4F14", "secondary": "#000000"},
    "CLE": {"primary": "#311D00", "secondary": "#FF3C00"},
    "DAL": {"primary": "#041E42", "secondary": "#869397"},
    "DEN": {"primary": "#002244", "secondary": "#FB4F14"},
    "DET": {"primary": "#0076B6", "secondary": "#B0B7BC"},
    "GB":  {"primary": "#203731", "secondary": "#FFB612"},
    "HOU": {"primary": "#03202F", "secondary": "#A71930"},
    "IND": {"primary": "#002C5F", "secondary": "#A2AAAD"},
    "JAX": {"primary": "#006778", "secondary": "#D7A22A"},
    "KC":  {"primary": "#E31837", "secondary": "#FFB81C"},
    "LAC": {"primary": "#0080C6", "secondary": "#FFC20E"},
    "LAR": {"primary": "#003594", "secondary": "#FFA300"},
    "LV":  {"primary": "#000000", "secondary": "#A5ACAF"},
    "MIA": {"primary": "#008E97", "secondary": "#FC4C02"},
    "MIN": {"primary": "#4F2683", "secondary": "#FFC62F"},
    "NE":  {"primary": "#002244", "secondary": "#C60C30"},
    "NO":  {"primary": "#101820", "secondary": "#D3BC8D"},
    "NYG": {"primary": "#0B2265", "secondary": "#A71930"},
    "NYJ": {"primary": "#125740", "secondary": "#000000"},
    "PHI": {"primary": "#004C54", "secondary": "#A5ACAF"},
    "PIT": {"primary": "#101820", "secondary": "#FFB612"},
    "SEA": {"primary": "#002244", "secondary": "#69BE28"},
    "SF":  {"primary": "#AA0000", "secondary": "#B3995D"},
    "TB":  {"primary": "#D50A0A", "secondary": "#34302B"},
    "TEN": {"primary": "#0C2340", "secondary": "#4B92DB"},
    "WAS": {"primary": "#5A1414", "secondary": "#FFB612"},
}


def _hex_to_rgb01(hex_color: str):
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return r, g, b


def _relative_luminance(rgb):
    # WCAG relative luminance for sRGB
    def f(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = _relative_luminance(_hex_to_rgb01(hex1))
    l2 = _relative_luminance(_hex_to_rgb01(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def pick_text_color(fill_hex: str, desired_text_hex: str) -> str:
    """Return a readable text color atop the given fill color.

    The desired secondary color is used when the contrast ratio exceeds 3:1.
    Otherwise, the function falls back to either black or white based on which
    offers better contrast against the fill color.
    """

    if _contrast_ratio(fill_hex, desired_text_hex) >= 3.0:
        return desired_text_hex

    black = "#000000"
    white = "#FFFFFF"
    return white if _contrast_ratio(fill_hex, white) >= _contrast_ratio(fill_hex, black) else black


def plot_team_squares(output_path="nfl_team_color_squares.png"):
    teams = sorted(NFL_TEAM_COLORS.keys())

    cols = 8
    rows = (len(teams) + cols - 1) // cols

    fig_w = cols * 1.6
    fig_h = rows * 1.6
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.set_aspect("equal")
    ax.axis("off")

    square_size = 0.92  # leave a little padding
    pad = (1.0 - square_size) / 2.0

    for i, team in enumerate(teams):
        c = i % cols
        r = rows - 1 - (i // cols)  # top-to-bottom

        primary = NFL_TEAM_COLORS[team]["primary"]
        secondary = NFL_TEAM_COLORS[team]["secondary"]
        text_color = pick_text_color(primary, secondary)

        rect = Rectangle((c + pad, r + pad), square_size, square_size,
                         facecolor=primary, edgecolor="black", linewidth=1.0)
        ax.add_patch(rect)

        ax.text(c + 0.5, r + 0.5, team,
                ha="center", va="center",
                fontsize=18, fontweight="bold",
                color=text_color)

    ax.set_title("NFL Team Color Squares (Primary Fill + Secondary Text)", pad=18)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    plot_team_squares()
