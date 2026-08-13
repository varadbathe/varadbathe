import urllib.request
import re
import xml.etree.ElementTree as ET
import os

def fetch_contributions(username="varadbathe"):
    url = f"https://github.com/users/{username}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response:
        return response.read().decode("utf-8")

def parse_contributions(html):
    # Extract tooltips mapping for exact contribution counts
    tooltips = {}
    tooltip_matches = re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]+)</tool-tip>', html)
    for tid, text in tooltip_matches:
        text_clean = text.strip()
        count_match = re.search(r'^(\d+|No)\s+contribution', text_clean, re.IGNORECASE)
        count = 0 if not count_match or count_match.group(1).lower() == 'no' else int(count_match.group(1))
        tooltips[tid] = (count, text_clean)

    # Parse rows
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    
    # Extract month labels and colspans from header row (row 0 or thead)
    month_labels = []
    thead = re.findall(r'<thead[^>]*>(.*?)</thead>', html, re.DOTALL)
    if thead:
        months_raw = re.findall(r'<td[^>]*colspan="(\d+)"[^>]*class="ContributionCalendar-label"[^>]*>(.*?)</td>', thead[0], re.DOTALL)
        if not months_raw:
            months_raw = re.findall(r'<td[^>]*class="ContributionCalendar-label"[^>]*colspan="(\d+)"[^>]*>(.*?)</td>', thead[0], re.DOTALL)
        
        col_acc = 0
        for colspan_str, content in months_raw:
            colspan = int(colspan_str)
            m_match = re.search(r'>(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)<', content)
            if m_match:
                m_name = m_match.group(1)
                month_labels.append({"name": m_name, "col": col_acc})
            col_acc += colspan

    # Parse day grid (7 rows: Sun=0 to Sat=6)
    grid = [[None for _ in range(53)] for _ in range(7)]
    total_contributions = 0

    for day_idx in range(7):
        if day_idx + 1 < len(rows):
            row_content = rows[day_idx + 1]
            td_matches = re.findall(r'<td[^>]*class="[^"]*ContributionCalendar-day[^"]*"[^>]*>', row_content)
            
            for week_idx, td_str in enumerate(td_matches):
                if week_idx < 53:
                    date_m = re.search(r'data-date="([^"]+)"', td_str)
                    level_m = re.search(r'data-level="([^"]+)"', td_str)
                    id_m = re.search(r'id="([^"]+)"', td_str)
                    
                    if date_m and level_m:
                        date_str = date_m.group(1)
                        level = int(level_m.group(1))
                        tid = id_m.group(1) if id_m else ""
                        
                        count, tip_text = tooltips.get(tid, (0, f"{level} contributions on {date_str}"))
                        if count == 0 and level > 0:
                            # Fallback if tooltip count extraction missed
                            count = level
                            tip_text = f"{count} contribution{'s' if count > 1 else ''} on {date_str}"
                        
                        total_contributions += count
                        grid[day_idx][week_idx] = {
                            "date": date_str,
                            "level": level,
                            "count": count,
                            "text": tip_text,
                            "week": week_idx,
                            "day": day_idx
                        }

    return grid, month_labels, total_contributions

def build_svg(grid, month_labels, total_contributions):
    cell_size = 11
    cell_gap = 3
    left_padding = 35
    top_padding = 42
    rect_rx = 2.5
    
    calendar_width = 53 * (cell_size + cell_gap)
    calendar_height = 7 * (cell_size + cell_gap)
    
    svg_width = left_padding + calendar_width + 25
    svg_height = top_padding + calendar_height + 35

    css = """
      .bg { fill: #0d1117; }
      .title { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #e6edf3; }
      .subtitle { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; fill: #8b949e; }
      .lbl { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 10px; fill: #8b949e; }
      
      .c {
        transform-box: fill-box;
        transform-origin: center;
        opacity: 0;
        animation: pop 0.55s ease-out both;
      }

      .g {
        transform-box: fill-box;
        transform-origin: center;
        opacity: 0;
        animation:
          pop 0.55s ease-out both,
          flash 0.7s ease-out both;
      }

      @keyframes pop {
        0% {
          opacity: 0;
          transform: scale(.2);
        }

        60% {
          opacity: 1;
          transform: scale(1.1);
        }

        100% {
          opacity: 1;
          transform: scale(1);
        }
      }

      @keyframes flash {
        0% {
          filter: brightness(2.4);
        }

        45% {
          filter: brightness(2.4);
        }

        100% {
          filter: brightness(1);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .c, .g {
          opacity: 1 !important;
          transform: none !important;
          filter: none !important;
          animation: none !important;
        }
      }
    """

    svg_parts = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="100%" height="100%">')
    svg_parts.append('<style>')
    svg_parts.append(css)
    svg_parts.append('</style>')
    
    # Outer card background
    svg_parts.append(f'<rect class="bg" width="{svg_width}" height="{svg_height}" rx="10" stroke="#30363d" stroke-width="1"/>')
    
    # Header Title & Subtitle
    svg_parts.append(f'<text x="{left_padding}" y="24" class="title">Contribution Journey</text>')
    svg_parts.append(f'<text x="{svg_width - 25}" y="24" class="subtitle" text-anchor="end">{total_contributions} contributions in the last year</text>')

    # Month Labels
    for m in month_labels:
        col = m["col"]
        m_name = m["name"]
        x = left_padding + col * (cell_size + cell_gap)
        svg_parts.append(f'<text x="{x}" y="{top_padding - 8}" class="lbl">{m_name}</text>')

    # Weekday Labels (Mon, Wed, Fri)
    weekdays = [("Mon", 1), ("Wed", 3), ("Fri", 5)]
    for w_name, w_day in weekdays:
        y = top_padding + w_day * (cell_size + cell_gap) + cell_size - 2
        svg_parts.append(f'<text x="{left_padding - 8}" y="{y}" class="lbl" text-anchor="end">{w_name}</text>')

    # GitHub Dark Theme Contribution Colors
    colors = {
        0: "#161b22",
        1: "#0e4429",
        2: "#006d32",
        3: "#26a641",
        4: "#39d353"
    }

    # Render Grid Cells
    for week in range(53):
        for day in range(7):
            cell = grid[day][week]
            if cell is not None:
                x = left_padding + week * (cell_size + cell_gap)
                y = top_padding + day * (cell_size + cell_gap)
                level = cell["level"]
                color = colors.get(level, colors[0])
                
                css_class = "g" if level > 0 else "c"
                delay = round(0.05 + (week * 0.022) + (day * 0.004), 3)
                
                # Escape XML special characters in tooltip text
                tooltip_text = (cell['text']
                                .replace('&', '&amp;')
                                .replace('<', '&lt;')
                                .replace('>', '&gt;')
                                .replace('"', '&quot;'))
                
                svg_parts.append(
                    f'<rect class="{css_class}" x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" '
                    f'rx="{rect_rx}" ry="{rect_rx}" fill="{color}" style="animation-delay: {delay}s;">'
                    f'<title>{tooltip_text}</title></rect>'
                )

    # Legend at bottom right
    legend_y = top_padding + calendar_height + 18
    legend_x = svg_width - 155
    svg_parts.append(f'<text x="{legend_x - 8}" y="{legend_y + cell_size - 2}" class="lbl" text-anchor="end">Less</text>')
    for l_level in range(5):
        lx = legend_x + l_level * (cell_size + 3)
        l_color = colors[l_level]
        svg_parts.append(f'<rect class="c" x="{lx}" y="{legend_y}" width="{cell_size}" height="{cell_size}" rx="{rect_rx}" ry="{rect_rx}" fill="{l_color}" style="animation-delay: 1.2s;"/>')
    svg_parts.append(f'<text x="{legend_x + 5 * (cell_size + 3) + 4}" y="{legend_y + cell_size - 2}" class="lbl">More</text>')

    svg_parts.append('</svg>')

    return "\n".join(svg_parts)

def main():
    print("Fetching contribution data for varadbathe...")
    html = fetch_contributions("varadbathe")
    grid, month_labels, total_contributions = parse_contributions(html)
    print(f"Parsed grid with {total_contributions} total contributions across 53 weeks.")
    print(f"Found {len(month_labels)} month headers.")
    
    svg_content = build_svg(grid, month_labels, total_contributions)
    
    output_path = os.path.join(os.path.dirname(__file__), "contribution-heatmap.svg")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    main()
