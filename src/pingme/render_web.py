"""One self-contained HTML report per run: tiles, charts, tables and the route map.

Built only from the saved record: nothing here measures anything. Colours and
forms follow the dataviz palette (validated for colour-blind separation).
"""

from __future__ import annotations

import copy
import html
import json
import shutil
import subprocess
from typing import Literal

import plotly.graph_objects as go
from plotly import __version__ as PLOTLY_VERSION
from plotly.offline import get_plotlyjs

from .probe import INTERVAL_S
from .render_map import TRACE_QUERIES, hop_rows, map_figure, traced_path, traces_for
from .store import burst_probes, data_dir, is_silent

TARGET_ORDER = ["router", "isp-hop", "london", "madrid", "us-east", "sao-paulo"]

# Light-mode hexes; JS swaps to the dark step of the same hue when the page is dark.
LIGHT = {"idle": "#2a78d6", "download": "#eb6834", "upload": "#1baf7a", "busy": "#eb6834",
         "bar": "#2a78d6", "range": "#86b6ef", "muted": "#898781", "lost": "#d03b3b",
         "london": "#2a78d6", "madrid": "#eb6834", "us-east": "#1baf7a", "sao-paulo": "#eda100",
         "router": "#898781", "isp-hop": "#898781"}
DARK = {"idle": "#3987e5", "download": "#d95926", "upload": "#199e70", "busy": "#d95926",
        "bar": "#3987e5", "range": "#1c5cab", "muted": "#898781", "lost": "#e05252",
        "london": "#3987e5", "madrid": "#d95926", "us-east": "#199e70", "sao-paulo": "#c98500",
        "router": "#898781", "isp-hop": "#898781"}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
CHROME = {"light": {"surface": "#fcfcfb", "page": "#f9f9f7", "ink": "#0b0b0b", "ink2": "#52514e",
                    "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
                    "border": "rgba(11,11,11,0.10)"},
          "dark": {"surface": "#1a1a19", "page": "#0d0d0d", "ink": "#ffffff", "ink2": "#c3c2b7",
                   "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
                   "border": "rgba(255,255,255,0.10)"}}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
PLOT_CONFIG = {"displaylogo": False, "responsive": True,
               "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

# pingme's own thresholds, stated in the footnote so nobody mistakes them for a standard
LOSS_WARN, LOSS_CRIT = 1.0, 5.0
PENALTY_WARN, PENALTY_CRIT = 50.0, 200.0
BURST_WARN, BURST_CRIT = 2, 5


def _fmt(v, nd: int = 1, unit: str = "") -> str:
    return "—" if v is None else f"{v:,.{nd}f}{unit}"


def _layout(title: str | None = None, height: int = 260, legend: bool = True) -> dict:
    c = CHROME["light"]
    axis = {"gridcolor": c["grid"], "linecolor": c["axis"], "zeroline": False,
            "tickfont": {"color": c["muted"], "size": 11}, "title_font": {"color": c["ink2"]}}
    return {"template": "none", "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)", "font": {"family": FONT, "color": c["ink"]},
            "margin": {"l": 48, "r": 12, "t": 36 if title else 12, "b": 40}, "height": height,
            "title": {"text": title or "", "font": {"size": 13, "color": c["ink2"]}, "x": 0},
            "xaxis": axis, "yaxis": dict(axis), "showlegend": legend,
            "legend": {"orientation": "h", "y": 1.12, "x": 0, "font": {"size": 11}},
            "hoverlabel": {"font": {"family": FONT}}}


def _div(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id,
                       config=PLOT_CONFIG, default_height=fig.layout.height or 260)


def _phase_bands(fig: go.Figure, marks: dict) -> None:
    dl, ul, back = marks.get("download"), marks.get("upload"), marks.get("idle-again")
    for start, end, role in ((dl, ul, "download"), (ul, back, "upload")):
        if start is not None and end is not None:
            fig.add_vrect(x0=start, x1=end, fillcolor=LIGHT[role], opacity=0.08, line_width=0,
                          annotation_text=role, annotation_position="top left",
                          annotation_font={"size": 10, "color": CHROME["light"]["muted"]})


def _hist(entry: dict) -> go.Figure:
    fig = go.Figure()
    idle = [s[1] for s in entry["samples"] if s[3] == "idle"]
    busy = [s[1] for s in entry["samples"] if s[3] in ("download", "upload")]
    for vals, role, name in ((idle, "idle", "idle"), (busy, "busy", "during speed test")):
        if vals:
            fig.add_trace(go.Histogram(x=vals, name=name, nbinsx=40, opacity=0.8,
                                       marker={"color": LIGHT[role]}, meta={"role": role},
                                       hovertemplate="%{x} ms: %{y} probes<extra>" + name + "</extra>"))
    a = entry["all"]
    c = CHROME["light"]
    for key, label in (("min_ms", "best"), ("median_ms", "median"), ("p95_ms", "p95")):
        if a.get(key) is not None:
            fig.add_vline(x=a[key], line={"color": c["muted"], "width": 1, "dash": "dot"},
                          annotation_text=f"{label} {a[key]:.0f}", annotation_position="top",
                          annotation_font={"size": 10, "color": c["ink2"]})
    fig.update_layout(_layout("round trip, ms (probes per bin)"), barmode="overlay", bargap=0.06)
    return fig


def _timeline(entry: dict, marks: dict) -> go.Figure:
    fig = go.Figure()
    for phase in ("idle", "download", "upload"):
        pts = [(s[2], s[1]) for s in entry["samples"] if s[3] == phase]
        if pts:
            fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="markers",
                                     name=phase, marker={"color": LIGHT[phase], "size": 5},
                                     meta={"role": phase},
                                     hovertemplate="%{x:.1f} s: %{y} ms<extra>" + phase + "</extra>"))
    _phase_bands(fig, marks)
    _lost_marks(fig, entry)
    fig.update_layout(_layout("round trip over the run, ms"))
    fig.update_xaxes(title_text="seconds")
    return fig


def _lost_marks(fig: go.Figure, entry: dict) -> None:
    """Every probe that never came back, on the floor of the timeline, plus the worst burst."""
    loss = entry.get("loss") or {}
    lost = loss.get("lost") or []
    if not lost:
        return
    fig.add_trace(go.Scatter(x=[t for _, t in lost], y=[0] * len(lost), mode="markers",
                             name="lost", meta={"role": "lost"},
                             marker={"color": LIGHT["lost"], "size": 7, "symbol": "x"},
                             hovertemplate="%{x:.1f} s: probe lost<extra></extra>"))
    if loss.get("longest_burst_probes", 0) >= BURST_WARN and loss.get("longest_burst_at_s"):
        start = loss["longest_burst_at_s"]
        fig.add_vrect(x0=start, x1=start + loss["longest_burst_s"], fillcolor=LIGHT["lost"],
                      opacity=0.15, line_width=0, annotation_text="longest burst",
                      annotation_position="top right",
                      annotation_font={"size": 10, "color": STATUS["critical"]})


def _throughput(sp: dict) -> go.Figure:
    samples = sp["samples_mbps"]
    xs = [i * 0.25 for i in range(len(samples))]
    fig = go.Figure(go.Scatter(x=xs, y=samples, mode="lines", line={"color": LIGHT["bar"], "width": 2},
                               name=sp["direction"], meta={"role": "bar"},
                               hovertemplate="%{x:.2f} s: %{y:.1f} Mbit/s<extra></extra>"))
    fig.update_layout(_layout(f"{sp['direction']} — {sp['mbps']:.1f} Mbit/s average", height=200,
                              legend=False))
    fig.update_xaxes(title_text="seconds")
    return fig


def _comparison(targets: dict, order: list[str]) -> go.Figure:
    names = [n for n in order if n in targets and targets[n]["all"]["median_ms"] is not None]
    med = [targets[n]["all"]["median_ms"] for n in names]
    p95 = [targets[n]["all"]["p95_ms"] for n in names]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=names, x=med, orientation="h", name="median",
                         marker={"color": LIGHT["bar"], "cornerradius": 4}, meta={"role": "bar"},
                         text=[f"{m:.0f}" for m in med], textposition="outside",
                         textfont={"color": CHROME["light"]["ink2"], "size": 11},
                         hovertemplate="%{y}: median %{x:.1f} ms<extra></extra>"))
    fig.add_trace(go.Scatter(y=names, x=p95, mode="markers", name="p95",
                             marker={"color": LIGHT["range"], "size": 10, "symbol": "line-ns",
                                     "line": {"width": 2, "color": LIGHT["range"]}},
                             meta={"role": "range"},
                             hovertemplate="%{y}: p95 %{x:.1f} ms<extra></extra>"))
    fig.update_layout(_layout("median round trip with p95 mark, ms", height=60 + 34 * len(names)),
                      bargap=0.35)
    fig.update_yaxes(autorange="reversed")
    return fig


def _status(value: float | None, warn: float, crit: float) -> tuple[str, str]:
    if value is None:
        return "muted", "?"
    if value >= crit:
        return "critical", "✕"
    if value >= warn:
        return "warning", "▲"
    return "good", "✓"


def _loss_status(lost: int | None, loss_pct: float | None) -> tuple[str, str]:
    """Green only when nothing at all went missing: the target is zero loss, not 1 %."""
    if loss_pct is None or lost is None:
        return "muted", "?"
    if lost == 0:
        return "good", "✓"
    if loss_pct >= LOSS_CRIT:
        return "critical", "✕"
    if loss_pct >= LOSS_WARN:
        return "serious", "▲"
    return "warning", "▲"


def _tile(label: str, value: str, sub: str = "", status: tuple[str, str] | None = None) -> str:
    badge = ""
    if status and status[0] != "muted":
        badge = (f'<span class="badge {status[0]}" title="{status[0]}">'
                 f'{status[1]} {status[0]}</span>')
    return (f'<div class="tile"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{value}</div><div class="sub">{html.escape(sub)} {badge}</div></div>')


def _stats_table(entry: dict) -> str:
    cols = [("loss_pct", "loss %"), ("min_ms", "best"), ("median_ms", "median"),
            ("mean_ms", "mean"), ("p95_ms", "p95"), ("p99_ms", "p99"), ("max_ms", "max"),
            ("stdev_ms", "st.dev"), ("jitter_ms", "jitter"), ("received", "replies"),
            ("sent", "sent")]
    head = "".join(f"<th>{h}</th>" for _, h in cols)
    rows = ""
    for phase in ("all", "idle", "busy"):
        s = entry[phase]
        cells = "".join(f"<td>{_fmt(s.get(k), 0 if k in ('received', 'sent') else 1)}</td>"
                        for k, _ in cols)
        rows += f"<tr><th>{phase}</th>{cells}</tr>"
    return (f'<details><summary>table</summary><table class="stats"><thead><tr><th></th>{head}'
            f"</tr></thead><tbody>{rows}</tbody></table></details>")


def _route_table(trace_entry: dict) -> str:
    """Every hop to this target, with the delay each one adds on top of the last."""
    rows = hop_rows(trace_entry)
    if not rows:
        return ""
    body = ""
    for r in rows:
        if r["ip"] is None:
            body += ('<tr class="quiet"><th>{n}</th><td colspan="5">no reply</td></tr>'
                     .format(n=r["n"]))
            continue
        where = "—" if not r["place"] else f'{r["place"]} <small>({r["source"]})</small>'
        note = "" if not r["no_reply"] else (
            f' <small class="quiet">{r["no_reply"]} of {TRACE_QUERIES} probes unanswered'
            "</small>")
        body += (f'<tr><th>{r["n"]}</th><td>{html.escape(r["ip"])}</td>'
                 f'<td><small>{html.escape(r["hostname"] or "")}</small></td>'
                 f"<td>{where}</td><td>{_fmt(r['ms'])}{note}</td>"
                 f"<td>{'' if r['step_ms'] is None else format(r['step_ms'], '+.1f')}</td></tr>")
    return ('<details><summary>every hop, and where the time goes</summary>'
            '<table class="stats hops"><thead><tr><th>#</th><th>address</th><th>name</th>'
            "<th>placed</th><th>reached in, ms</th><th>added, ms</th></tr></thead>"
            f"<tbody>{body}</tbody></table></details>")


def _target_section(name: str, entry: dict, marks: dict, i: int,
                    trace_entry: dict | None = None) -> str:
    a = entry["all"]
    silent = is_silent(entry)
    lost = None if a["loss_pct"] is None else a["sent"] - a["received"]
    loss_status = _loss_status(lost, a["loss_pct"])
    penalty = None
    if entry["busy"]["p95_ms"] is not None and entry["idle"]["p95_ms"] is not None:
        penalty = entry["busy"]["p95_ms"] - entry["idle"]["p95_ms"]
    pen_status = _status(penalty, PENALTY_WARN, PENALTY_CRIT)
    physics = entry.get("physics") or {}
    facts = [f"loss {_fmt(a['loss_pct'], 1, '%')}"]
    if lost is not None:
        facts[0] += f" ({lost:,} of {a['sent']:,} probes)"
    burst = burst_probes(entry) or 0
    if burst:
        loss = entry["loss"]
        badge = _status(burst, BURST_WARN, BURST_CRIT)
        facts.append(f"longest burst {burst} probes ({loss['longest_burst_s']:.1f} s) "
                     f'<span class="badge {badge[0]}">{badge[1]} burst</span>'
                     if burst >= BURST_WARN else
                     f"longest burst {burst} probe ({loss['longest_burst_s']:.1f} s)")
    facts += [f"best {_fmt(a['min_ms'])} ms",
              f"median {_fmt(a['median_ms'])} ms", f"p95 {_fmt(a['p95_ms'])} ms",
              f"jitter {_fmt(a['jitter_ms'])} ms"]
    if penalty is not None:
        facts.append(f"under-load penalty {penalty:+.0f} ms "
                     f'<span class="badge {pen_status[0]}">{pen_status[1]} {pen_status[0]}</span>')
    path = traced_path(trace_entry) if trace_entry else None
    if path:
        facts.append("traced path: <b>" + html.escape(path) + "</b>")
    if physics.get("most_consistent"):
        facts.append(f"timing estimate: {html.escape(physics['most_consistent'])} "
                     f"(~{physics['effective_ms']:.0f} ms after local overhead)")
    route = (entry.get("route") or {}).get("dev")
    if silent:
        facts = [f"{a['sent']:,} probes sent, none came back"]
        body = ('<p class="quiet">This address does not answer probes. That is a setting on '
                "the device, not a fault on the line, so no loss figure is shown for it.</p>")
    elif entry.get("error") and not entry["samples"]:
        body = f'<p class="error">{html.escape(entry["error"])}</p>'
    else:
        body = (f'<div class="pair">{_div(_hist(entry), f"h{i}")}{_div(_timeline(entry, marks), f"t{i}")}'
                f"</div>{_stats_table(entry)}"
                f"{_route_table(trace_entry) if trace_entry else ''}")
    badge = ("" if silent else
             f'<span class="badge {loss_status[0]}">{loss_status[1]} loss</span>')
    return (f'<section class="card" id="target-{name}"><h2>{name} '
            f'<span class="ip">{entry["ip"]}{" · via " + route if route else ""}</span>'
            f'{badge}</h2>'
            f'<p class="facts">{" · ".join(facts)}</p>{body}</section>')


def _css() -> str:
    lt, dk = CHROME["light"], CHROME["dark"]

    def block(c, dark=False):
        return (f"--surface:{c['surface']};--page:{c['page']};--ink:{c['ink']};--ink2:{c['ink2']};"
                f"--muted:{c['muted']};--grid:{c['grid']};--axis:{c['axis']};"
                f"--border:{c['border']};"
                f"color-scheme:{'dark' if dark else 'light'};")

    return f"""
:root{{{block(lt)}}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{{block(dk, True)}}}}}
:root[data-theme="dark"]{{{block(dk, True)}}}
body{{margin:0;background:var(--page);color:var(--ink);font-family:{FONT};font-size:14px;line-height:1.45}}
main{{max-width:1180px;margin:0 auto;padding:20px 16px 48px}}
h1{{font-size:20px;margin:0 0 2px}} h2{{font-size:15px;margin:0 0 6px}} h3{{font-size:13px;color:var(--ink2);margin:14px 0 6px;font-weight:600}}
.meta{{color:var(--ink2);margin:0 0 16px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:0 0 14px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:0 0 14px}}
.tile{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}}
.tile .label{{color:var(--ink2);font-size:12px}} .tile .value{{font-size:28px;font-weight:600;margin:2px 0}}
.tile .sub{{color:var(--muted);font-size:12px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} @media (max-width:820px){{.pair{{grid-template-columns:1fr}}}}
.ip{{color:var(--muted);font-weight:400;font-size:12px;margin-left:8px}}
.facts{{color:var(--ink2);margin:0 0 8px}}
.badge{{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;border-radius:999px;margin-left:8px;color:#fff;vertical-align:middle}}
.badge.good{{background:{STATUS['good']}}} .badge.warning{{background:{STATUS['warning']};color:#0b0b0b}}
.badge.serious{{background:{STATUS['serious']}}} .badge.critical{{background:{STATUS['critical']}}}
details{{margin:4px 0 0}} summary{{cursor:pointer;color:var(--muted);font-size:12px}}
table.stats{{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:12px;margin-top:6px;width:100%}}
table.stats th,table.stats td{{text-align:right;padding:3px 8px;border-bottom:1px solid var(--grid)}} table.stats th:first-child{{text-align:left}}
table.hops td:nth-child(2),table.hops td:nth-child(3),table.hops td:nth-child(4){{text-align:left}}
table.hops tr.quiet td{{text-align:left;color:var(--muted)}} table.hops small{{color:var(--muted)}}
.error{{color:{STATUS['critical']}}} .quiet{{color:var(--muted)}}
.foot{{color:var(--muted);font-size:12px;margin-top:20px}}
.plotly-graph-div{{width:100%}}
"""


def explorer_css() -> str:
    """The rules the explorer shell needs on top of _css(): picker, run tiles, diff table.

    Kept in its own function because the per-run report pages never use any of it, and
    the explorer is the only page that has a table you can tick and charts side by side.
    """
    return """.picker{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.picker th{font-weight:600;color:var(--ink2);text-align:left;padding:6px 8px;border-bottom:1px solid var(--axis);white-space:nowrap;cursor:pointer;user-select:none}
.picker th.num{text-align:right}
.picker td{padding:7px 8px;border-bottom:1px solid var(--grid);white-space:nowrap}
.picker td.num{text-align:right}
.picker tbody tr{cursor:pointer}
.picker tbody tr:hover td{background:rgba(137,135,129,0.08)}
.picker tbody tr.on:hover td{background:rgba(137,135,129,0.22)}
/* a neutral tint: a selected row must not wear the colour that means "first run ticked" */
.picker tr.on td{background:rgba(137,135,129,0.16)}
.tick{display:inline-block;width:16px;height:16px;border:1.5px solid var(--ink2);border-radius:4px;vertical-align:middle;background:var(--surface)}
.tick.on{border-color:var(--ink);background:var(--ink)}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:middle}
#pick{overflow-x:auto}
.hint{color:var(--muted);font-size:12px;margin:8px 0 0}
.runs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin:0 0 14px}
/* the picker's name cell is a td.run as well, so the tile look stays inside the tile grid */
.runs .run{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px;border-top:3px solid var(--axis)}
.runs .run .name{font-weight:600;font-size:14px}
.runs .run .sub{color:var(--ink2);font-size:12px;margin:2px 0 8px}
.runs .run .speed{font-size:22px;font-weight:600}
.runs .run .speed small{font-size:12px;font-weight:400;color:var(--muted)}
.seg{display:inline-flex;border:1px solid var(--axis);border-radius:8px;overflow:hidden;font-size:13px;vertical-align:middle}
.seg span{padding:6px 12px;border-right:1px solid var(--grid);color:var(--ink2);cursor:pointer}
.seg span:last-child{border-right:0}
.seg span.on{background:var(--ink);color:var(--surface);font-weight:600}
.filter{display:flex;align-items:center;gap:12px;margin:18px 0 12px;font-size:13px;color:var(--ink2);flex-wrap:wrap}
.diff{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
.diff th,.diff td{text-align:right;padding:5px 10px;border-bottom:1px solid var(--grid)}
.diff th:first-child,.diff td:first-child{text-align:left;color:var(--ink2);font-weight:400}
.diff thead th{color:var(--ink2);font-weight:600;border-bottom:1px solid var(--axis)}
.diff td.best{font-weight:600;color:var(--ink)}
.ctitle{font-size:13px;color:var(--ink2);margin:0 0 4px}
.note{color:var(--muted);font-size:12px;margin:6px 0 0}
.empty{padding:34px 16px;text-align:center;color:var(--ink2)}
.empty b{display:block;font-size:16px;color:var(--ink);margin-bottom:4px}
.frame{width:100%;border:0;display:block;min-height:600px}
.refused{color:var(--ink2);font-size:13px;margin:8px 0 0}
main.loading{opacity:0.55;transition:opacity 120ms}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
"""


def explorer_tokens() -> dict:
    """Colours, target order and thresholds for the explorer, emitted into the page as JSON.

    The comparison charts are drawn in JavaScript, so this is how they stay in step with
    the Python report pages: nothing on the site hard-codes a hex or a threshold, it all
    comes from here. The three run slots are the categorical slots the palette validator
    passes on the map in both light and dark; a fourth hue fails the colour-blindness
    check against orange, which is why at most three runs can be ticked at once.
    """
    slots = ["london", "madrid", "us-east"]
    return {
        "runSlots": {"light": [LIGHT[k] for k in slots], "dark": [DARK[k] for k in slots]},
        "chrome": copy.deepcopy(CHROME),
        "status": dict(STATUS),
        "targetOrder": list(TARGET_ORDER),
        "thresholds": {"lossWarn": LOSS_WARN, "lossCrit": LOSS_CRIT,
                       "penaltyWarn": PENALTY_WARN, "penaltyCrit": PENALTY_CRIT,
                       "burstWarn": BURST_WARN, "burstCrit": BURST_CRIT},
        "intervalS": INTERVAL_S,
        "maxRuns": len(slots),
        "font": FONT,
    }


def _theme_js() -> str:
    """Swap every trace to the dark steps of the same hues when the page is dark."""
    return f"""
(function(){{
  const LIGHT={json.dumps(LIGHT)}, DARK={json.dumps(DARK)}, C={json.dumps(CHROME)};
  function isDark(){{const t=document.documentElement.dataset.theme;
    return t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);}}
  function apply(){{
    const dark=isDark(), pal=dark?DARK:LIGHT, c=dark?C.dark:C.light;
    document.querySelectorAll('.plotly-graph-div').forEach(div=>{{
      if(!div.data) return;
      div.data.forEach((tr,i)=>{{
        const role=tr.meta&&tr.meta.role; if(!role||!pal[role]) return;
        const upd={{}};
        if(tr.marker){{upd['marker.color']=pal[role]; if(tr.marker.line) upd['marker.line.color']=pal[role];}}
        if(tr.line) upd['line.color']=pal[role];
        Plotly.restyle(div, upd, [i]);
      }});
      Plotly.relayout(div, {{'font.color':c.ink,'xaxis.gridcolor':c.grid,'yaxis.gridcolor':c.grid,
        'xaxis.linecolor':c.axis,'yaxis.linecolor':c.axis,'title.font.color':c.ink2,
        'geo.bgcolor':'rgba(0,0,0,0)','geo.landcolor':dark?'#2a2a28':'#f2efe9',
        'geo.oceancolor':dark?'#151a20':'#dbe9f6','geo.countrycolor':dark?'#444':'#bbb',
        'geo.coastlinecolor':dark?'#555':'#999'}});
    }});
  }}
  apply(); matchMedia('(prefers-color-scheme: dark)').addEventListener('change', apply);
  new MutationObserver(apply).observe(document.documentElement,{{attributes:true,attributeFilter:['data-theme']}});
}})();
"""


def redact(run: dict) -> dict:
    """A deep copy of the run with the public IP and the Wi-Fi name replaced by "redacted"."""
    out = copy.deepcopy(run)
    s = out.get("snapshot") or {}
    if s.get("public"):
        s["public"]["ip"] = "redacted"
    if s.get("wifi"):
        s["wifi"]["ssid"] = "redacted"
    return out


# cdn.plot.ly does not serve the plotly.js that ships with this plotly (checked: 7.0.0 → 403),
# so the site keeps its own copy of the exact bundled version, written once by publish().
PLOTLY_ASSET = f"assets/plotly-{PLOTLY_VERSION}.min.js"


def _plotly_script(plotly_mode: Literal["inline", "external"], src: str) -> str:
    if plotly_mode == "external":
        return f'<script src="{html.escape(src)}"></script>'
    return f"<script>{get_plotlyjs()}</script>"


def build_report(run: dict, traces: dict | None = None, *,
                 plotly: Literal["inline", "external"] = "inline",
                 plotly_src: str = "../" + PLOTLY_ASSET) -> str:
    """Return the full HTML for a run. `traces` is the optional route-trace result.

    `plotly="external"` references plotly.js at `plotly_src` instead of embedding the 4 MB
    bundle; `PLOTLY_ASSET` is the path publish() writes the bundle to inside the site.
    """
    s, a = run["snapshot"], run["analysis"]
    pub = s.get("public") or {}
    targets = a["targets"]
    order = sorted(targets, key=lambda n: TARGET_ORDER.index(n) if n in TARGET_ORDER else 99)
    speeds = {x["direction"]: x for x in run["speed"]}
    measured = [t for t in targets.values()
                if t["all"]["loss_pct"] is not None and not is_silent(t)]
    worst_loss = max((t["all"]["loss_pct"] for t in measured), default=None)
    lost_total = sum(t["all"]["sent"] - t["all"]["received"] for t in measured)
    counted = [b for b in (burst_probes(t) for t in targets.values()) if b is not None]
    worst_burst = max(counted, default=None)
    sp_phys = (targets.get("sao-paulo") or {}).get("physics") or {}

    if s.get("medium") == "wifi" and s.get("wifi"):
        w = s["wifi"]
        conn = (f"Wi-Fi {html.escape(str(w.get('ssid')))} · {w.get('generation') or ''} · "
                f"{_fmt(w.get('freq_mhz'), 0)} MHz ch{w.get('channel')} {w.get('width_mhz')} MHz · "
                f"{w.get('signal_dbm')} dBm · link ↓{_fmt(w.get('rx_bitrate_mbps'), 0)} "
                f"↑{_fmt(w.get('tx_bitrate_mbps'), 0)} Mbit/s")
    elif s.get("medium") == "ethernet" and s.get("ethernet"):
        e = s["ethernet"]
        conn = f"Ethernet {e.get('link_speed_mbps')} Mbit/s {e.get('duplex')} duplex"
    else:
        conn = "connection type unknown"
    meta = (f"{run['timestamp'][:19].replace('T', ' ')} UTC · {run['duration_s']:.0f} s run · {conn} · "
            f"public {html.escape(str(pub.get('ip')))} ({html.escape(str(pub.get('isp')))}, "
            f"{html.escape(str(pub.get('city')))}, {html.escape(str(pub.get('country')))})")

    tiles = [
        _tile("download", f"{speeds.get('download', {}).get('mbps', 0):.1f} <small>Mbit/s</small>",
              f"{speeds.get('download', {}).get('bytes_total', 0) / 1e6:.0f} MB in "
              f"{speeds.get('download', {}).get('seconds', 0):.0f} s"),
        _tile("upload", f"{speeds.get('upload', {}).get('mbps', 0):.1f} <small>Mbit/s</small>",
              f"{speeds.get('upload', {}).get('bytes_total', 0) / 1e6:.0f} MB in "
              f"{speeds.get('upload', {}).get('seconds', 0):.0f} s"),
        _tile("worst packet loss", _fmt(worst_loss, 1, "%"),
              f"{lost_total:,} probes lost across all targets",
              _loss_status(lost_total, worst_loss)),
        _tile("longest burst",
              "—" if worst_burst is None else f"{worst_burst} <small>probes</small>",
              "not counted on this run"
              if worst_burst is None else
              f"{worst_burst * INTERVAL_S:.1f} s in a row, worst target",
              _status(worst_burst, BURST_WARN, BURST_CRIT)),
        _tile("local overhead", f"{a['local_overhead_ms']:.0f} <small>ms</small>",
              a["local_overhead_how"]),
        _tile("São Paulo route", html.escape(sp_phys.get("most_consistent") or "—"),
              f"~{sp_phys.get('effective_ms', 0):.0f} ms after local overhead"
              if sp_phys else "no measurement"),
    ]
    thr = "".join(_div(_throughput(sp), f"s-{sp['direction']}") for sp in run["speed"]
                  if sp["samples_mbps"])
    sections = "".join(_target_section(n, targets[n], run.get("phase_marks_s", {}), i,
                                       (traces or {}).get(n))
                       for i, n in enumerate(order))
    comparison = _div(_comparison(targets, order), "cmp")
    map_html = ""
    if traces:
        fig = map_figure(run, traces)
        fig.update_layout(height=520, margin={"l": 0, "r": 0, "t": 30, "b": 0},
                          paper_bgcolor="rgba(0,0,0,0)", font={"family": FONT})
        map_html = f'<section class="card"><h2>route map</h2>{_div(fig, "map")}</section>'

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pingme — {html.escape(run['id'])}</title><style>{_css()}</style>
{_plotly_script(plotly, plotly_src)}</head><body><main>
<h1>pingme — {html.escape(run['id'])}</h1><p class="meta">{meta}</p>
<div class="tiles">{''.join(tiles)}</div>
<section class="card"><h2>throughput</h2><div class="pair">{thr}</div></section>
{sections}
<section class="card"><h2>targets compared</h2>{comparison}</section>
{map_html}
<p class="foot">Round trips measured with the system ping at 5 per second per target; the speed
test ran against Cloudflare while probing continued. "Under-load penalty" is the busy p95
minus the idle p95. A burst is the longest run of probes lost back to back. Badges use
pingme's own thresholds: any lost probe at all is flagged, loss ≥{LOSS_WARN:g} % serious,
≥{LOSS_CRIT:g} % critical; burst ≥{BURST_WARN:g} probes warning, ≥{BURST_CRIT:g} critical;
penalty ≥{PENALTY_WARN:g} ms warning, ≥{PENALTY_CRIT:g} ms critical. An address that never
answers is reported as silent rather than as total loss.
Route verdicts compare the best round trip, minus local overhead, with the time light needs
through fibre along each candidate cable path (×1.3 for real cable routing). Each hop in
"every hop" was measured {TRACE_QUERIES} times by traceroute, so its delay wobbles and an
"added" figure can come out negative; that is noise, not a router giving time back. Routers
often answer traceroute slowly or not at all on purpose, so an unanswered probe there says
nothing about the traffic passing through.</p>
</main><script>{_theme_js()}</script></body></html>"""


def write_report(run: dict, status=lambda msg: None, with_map: bool = True) -> str:
    traces = traces_for(run, status) if with_map else None
    reports = data_dir() / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"{run['id']}.html"
    path.write_text(build_report(run, traces), encoding="utf-8")
    opener = shutil.which("xdg-open")
    if opener:
        try:
            subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            pass
    return str(path)
